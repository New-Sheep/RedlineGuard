from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import Client, TestCase, override_settings

from apps.contracts.models import Contract
from apps.core.llm import FakeLlmClient
from apps.learning.services import memory as memory_mod
from apps.review.models import Draft, Finding
from apps.review.services.drafting import draft_for_finding
from apps.review.services.pipeline import run_pipeline


class ProgressAndAsyncTests(TestCase):
    def test_upload_hostile_still_halts(self):
        r = Client().post("/", {"sample_key": "injection_hostile.txt"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/security/", r["Location"])

    def test_upload_demo_ready_redirect(self):
        tmp = tempfile.mkdtemp()
        try:
            chroma = Path(tmp) / "chroma"
            memory_mod.reset_decision_store()
            with override_settings(
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_async_demo",
                FAKE_LLM="1",
            ):
                memory_mod.reset_decision_store()
                r = Client().post("/", {"sample_key": "demo_short_nda.txt"})
                self.assertEqual(r.status_code, 302)
                self.assertIn("/review/", r["Location"])
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()

    def test_status_json(self):
        c = Contract.objects.create(
            filename="x.txt",
            source=Contract.Source.UPLOAD,
            status=Contract.Status.PROCESSING,
            progress_step=Contract.ProgressStep.SECURITY,
            progress_label="Security check",
        )
        r = Client().get(f"/contracts/{c.pk}/status.json")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["progress_step"], "security")
        self.assertEqual(data["status"], "processing")

    def test_pipeline_sets_done_progress(self):
        tmp = tempfile.mkdtemp()
        try:
            chroma = Path(tmp) / "chroma"
            memory_mod.reset_decision_store()
            with override_settings(
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_progress_pipe",
                FAKE_LLM="1",
            ):
                memory_mod.reset_decision_store()
                c = Contract.objects.create(
                    filename="t.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text="laws of California. shall indemnify.",
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c)
                c.refresh_from_db()
                self.assertEqual(c.status, Contract.Status.READY)
                self.assertEqual(c.progress_step, Contract.ProgressStep.DONE)
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()


class LlmDraftPortTests(TestCase):
    def test_fake_llm_fills_needs_human(self):
        result = draft_for_finding(
            finding_payload={
                "playbook_rule_id": "equity_control_cap",
                "status": "REQUIRES_HUMAN",
                "suggested_counter_proposal": None,
                "deviation_reason": "equity control flagged",
                "clause_name": "equity_control",
            },
            playbook_rule={
                "id": "equity_control_cap",
                "preferred": "No majority control by counterparty",
                "hard_ceiling": "Never >=50%",
                "fallback_text": None,
            },
            contract_text="Licensor shall maintain control of systems.",
            playbook_empty=False,
        )
        self.assertEqual(result.draft_source, "llm_suggested")
        self.assertTrue((result.draft_text or "").strip())
        self.assertIn("ownership", result.draft_text.lower())

    def test_fake_client_direct(self):
        s = FakeLlmClient().suggest_draft(
            playbook_rule={"id": "change_of_control_fee", "preferred": "No fee"},
            finding={
                "playbook_rule_id": "change_of_control_fee",
                "status": "REQUIRES_HUMAN",
            },
            fenced_contract_excerpt="<untrusted_document>x</untrusted_document>",
        )
        self.assertIn("change-of-control", s.draft_text.lower())

    def test_pipeline_llm_draft_on_requires_human(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "pb.json"
            chroma = Path(tmp) / "chroma"
            ov = Path(tmp) / "ov.json"
            pb.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "t",
                        "preferred_governing_law": "England and Wales",
                        "rules": [
                            {
                                "id": "equity_control_cap",
                                "clause_type": "equity_control",
                                "preferred": "No majority control",
                                "hard_ceiling": "Never >=50%",
                                "fallback_text": None,
                                "severity": "high",
                                "match_any": [
                                    "majority ownership",
                                    "maintain.*control",
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ov.write_text('{"version":1,"overrides":[]}\n', encoding="utf-8")
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_llm_draft",
                FAKE_LLM="1",
                PLAYBOOK_OVERRIDES_PATH=ov,
            ):
                memory_mod.reset_decision_store()
                c = Contract.objects.create(
                    filename="eq.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=(
                        "Counterparty retains majority ownership and shall maintain control."
                    ),
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c)
                f = Finding.objects.get(review_run__contract=c)
                self.assertEqual(f.status, "REQUIRES_HUMAN")
                d = Draft.objects.get(finding=f)
                self.assertEqual(d.draft_source, Draft.Source.LLM)
                self.assertTrue(d.draft_text.strip())
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()
