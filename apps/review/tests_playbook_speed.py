"""Faster playbook propose: timeout retry, truncate, Fake→LLM upgrade."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from apps.core.llm import HttpLlmClient, _should_retry_without_json_format
from apps.review.models import PlaybookImport
from apps.review.services.playbook_bootstrap import PlaybookDocument, PlaybookRule
from apps.review.services.playbook_bootstrap_llm import (
    PROPOSE_INPUT_MAX_CHARS,
    LlmPlaybookBootstrap,
)
from apps.review.services.playbook_import import mark_user_touched, run_import_and_propose
from apps.review.services.playbook_upgrade import apply_llm_upgrade, run_llm_upgrade_job


class JsonFormatRetryTests(SimpleTestCase):
    def test_timeout_should_not_retry(self):
        self.assertFalse(_should_retry_without_json_format(TimeoutError("timed out")))
        self.assertFalse(
            _should_retry_without_json_format(RuntimeError("The read timed out"))
        )

    def test_http_4xx_should_retry(self):
        self.assertTrue(
            _should_retry_without_json_format(RuntimeError("nvidia HTTP 400: bad format"))
        )
        self.assertTrue(
            _should_retry_without_json_format(ValueError("LLM JSON was not an object"))
        )

    @patch("apps.core.llm.urllib.request.urlopen")
    def test_complete_json_timeout_does_not_double_retry(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("read timed out")
        client = HttpLlmClient(
            api_key="k",
            base_url="https://example.com/v1",
            model="m",
            prefer_json_object=True,
            timeout_s=1,
            provider_name="nvidia",
        )
        with self.assertRaises(TimeoutError):
            client.complete_json(system="s", user="u")
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("apps.core.llm.urllib.request.urlopen")
    def test_complete_json_retries_on_json_parse(self, mock_urlopen):
        bad = MagicMock()
        bad.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "not-json"}}]}
        ).encode("utf-8")
        bad.__enter__.return_value = bad
        bad.__exit__.return_value = False
        good = MagicMock()
        good.read.return_value = json.dumps(
            {"choices": [{"message": {"content": '{"ok": true}'}}]}
        ).encode("utf-8")
        good.__enter__.return_value = good
        good.__exit__.return_value = False
        mock_urlopen.side_effect = [bad, good]

        client = HttpLlmClient(
            api_key="k",
            base_url="https://example.com/v1",
            model="m",
            prefer_json_object=True,
            provider_name="nvidia",
        )
        data = client.complete_json(system="s", user="u")
        self.assertEqual(data, {"ok": True})
        self.assertEqual(mock_urlopen.call_count, 2)


class PlaybookProposeTruncateTests(SimpleTestCase):
    @override_settings(PLAYBOOK_LLM_TIMEOUT=45)
    @patch("apps.review.services.playbook_bootstrap_llm.complete_json")
    def test_propose_truncates_input(self, mock_complete):
        mock_complete.return_value = {
            "name": "T",
            "preferred_governing_law": "England and Wales",
            "rules": [
                {
                    "id": "governing_law",
                    "clause_type": "governing_law",
                    "preferred": "England and Wales",
                    "hard_ceiling": "No California",
                    "fallback_text": None,
                    "severity": "high",
                    "match_any": ["California"],
                }
            ],
        }
        huge = "x" * 20000
        LlmPlaybookBootstrap().propose(huge, source_name="big.pdf", fallback_to_fake=False)
        self.assertTrue(mock_complete.called)
        user_payload = mock_complete.call_args.kwargs["user"]
        parsed = json.loads(user_payload)
        # Sanitized head is ≤ 6000; fence tags add a little overhead.
        self.assertLessEqual(len(parsed["document"]), PROPOSE_INPUT_MAX_CHARS + 120)
        self.assertEqual(mock_complete.call_args.kwargs.get("timeout_s"), 45.0)


@override_settings(FAKE_LLM="1")
class PlaybookInstantUpgradeTests(TestCase):
    """FAKE_LLM=1 for extract path; patch wants_llm_upgrade to exercise pending meta."""

    def _sample_imp(self):
        corpus = Path(settings.PLAYBOOK_CORPUS_DIR)
        sample = "Sample Playbook1.pdf"
        if not (corpus / sample).is_file():
            return None
        return PlaybookImport.objects.create(
            filename=sample,
            source=PlaybookImport.Source.SAMPLE,
            sample_key=sample,
        )

    @patch("apps.review.services.playbook_upgrade.start_llm_upgrade_async")
    @patch(
        "apps.review.services.playbook_bootstrap_llm.wants_llm_upgrade",
        return_value=True,
    )
    def test_fake_propose_reaches_proposed_quickly(self, _wants, mock_start):
        imp = self._sample_imp()
        if imp is None:
            self.skipTest("Sample Playbook1.pdf missing")
        run_import_and_propose(imp)
        imp.refresh_from_db()
        self.assertEqual(imp.status, PlaybookImport.Status.PROPOSED)
        self.assertEqual(imp.proposal_source, "fake")
        meta = (imp.proposed_json or {}).get("_meta") or {}
        self.assertEqual(meta.get("llm_upgrade"), "pending")
        self.assertFalse(meta.get("user_touched"))
        mock_start.assert_called_once()

    @patch("apps.review.services.playbook_upgrade.start_llm_upgrade_async")
    @patch(
        "apps.review.services.playbook_bootstrap_llm.wants_llm_upgrade",
        return_value=True,
    )
    def test_upgrade_replaces_rules_when_not_touched(self, _wants, _start):
        imp = self._sample_imp()
        if imp is None:
            self.skipTest("Sample Playbook1.pdf missing")
        run_import_and_propose(imp)
        imp.refresh_from_db()
        self.assertTrue((imp.proposed_json or {}).get("rules"))

        llm_doc = PlaybookDocument(
            version=1,
            name="NVIDIA playbook",
            preferred_governing_law="England and Wales",
            rules=[
                PlaybookRule(
                    id="liability_cap",
                    clause_type="liability_cap",
                    preferred="Cap at 12 months fees",
                    hard_ceiling="No uncapped liability",
                    fallback_text=None,
                    severity="high",
                    match_any=["unlimited liability"],
                )
            ],
        )
        with patch(
            "apps.review.services.playbook_bootstrap_llm.LlmPlaybookBootstrap.propose",
            return_value=llm_doc,
        ), patch(
            "apps.review.services.playbook_bootstrap_llm.bootstrap_meta",
            return_value={
                "proposal_source": "nvidia",
                "proposal_model": "test-model",
            },
        ), patch(
            "apps.review.services.playbook_bootstrap_llm.wants_llm_upgrade",
            return_value=True,
        ):
            run_llm_upgrade_job(imp.pk)

        imp.refresh_from_db()
        meta = (imp.proposed_json or {}).get("_meta") or {}
        self.assertEqual(meta.get("llm_upgrade"), "done")
        self.assertEqual(imp.proposal_source, "nvidia")
        rules = (imp.proposed_json or {}).get("rules") or []
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "liability_cap")

    @patch("apps.review.services.playbook_upgrade.start_llm_upgrade_async")
    @patch(
        "apps.review.services.playbook_bootstrap_llm.wants_llm_upgrade",
        return_value=True,
    )
    def test_upgrade_skips_when_user_touched(self, _wants, _start):
        imp = self._sample_imp()
        if imp is None:
            self.skipTest("Sample Playbook1.pdf missing")
        run_import_and_propose(imp)
        imp.refresh_from_db()
        mark_user_touched(imp)
        imp.save(update_fields=["proposed_json"])
        before = list((imp.proposed_json or {}).get("rules") or [])

        llm_doc = PlaybookDocument(
            version=1,
            name="Should not apply",
            preferred_governing_law="England and Wales",
            rules=[
                PlaybookRule(
                    id="other",
                    clause_type="other",
                    preferred="x",
                    hard_ceiling="y",
                    fallback_text=None,
                    severity="low",
                    match_any=["z"],
                )
            ],
        )
        applied = apply_llm_upgrade(
            imp,
            llm_doc,
            meta={"proposal_source": "nvidia", "proposal_model": "m"},
        )
        self.assertFalse(applied)
        imp.refresh_from_db()
        meta = (imp.proposed_json or {}).get("_meta") or {}
        self.assertEqual(meta.get("llm_upgrade"), "skipped")
        self.assertEqual((imp.proposed_json or {}).get("rules"), before)
        self.assertEqual(imp.proposal_source, "fake")
