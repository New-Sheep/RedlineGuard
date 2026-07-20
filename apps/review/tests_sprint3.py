from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings

from apps.contracts.forms import DEMO_SAMPLE_LABELS, ordered_sample_choices
from apps.contracts.models import Contract
from apps.contracts.services.extract import run_extract
from apps.decisions.models import Decision
from apps.decisions.services.decide import record_decision
from apps.learning.services import memory as memory_mod
from apps.review.models import Finding
from apps.review.services.overrides import append_override, load_overrides, merge_playbook_with_overrides
from apps.review.services.pipeline import run_pipeline


class DemoSampleTests(TestCase):
    def test_demo_labels_prefer_curated_files(self):
        choices = ordered_sample_choices()
        labels = [label for _, label in choices if _]
        self.assertTrue(any(label.startswith("Demo -") for label in labels))
        for filename in DEMO_SAMPLE_LABELS:
            path = Path(settings.SCRATCH_CORPUS_DIR) / filename
            self.assertTrue(path.is_file(), f"missing {filename}")

    def test_demo_clean_produces_multiple_flags(self):
        sample = "demo_clean_flags.txt"
        path = Path(settings.SCRATCH_CORPUS_DIR) / sample
        if not path.is_file():
            self.skipTest("demo_clean_flags.txt missing")

        tmp = tempfile.mkdtemp()
        try:
            chroma = Path(tmp) / "chroma"
            ov = Path(tmp) / "overrides.json"
            ov.write_text(json.dumps({"version": 1, "overrides": []}), encoding="utf-8")
            memory_mod.reset_decision_store()
            with override_settings(
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_demo_flags",
                PLAYBOOK_OVERRIDES_PATH=ov,
            ):
                memory_mod.reset_decision_store()
                contract = Contract.objects.create(
                    filename=sample,
                    source=Contract.Source.SAMPLE,
                    sample_key=sample,
                    status=Contract.Status.UPLOADED,
                )
                run_extract(contract)
                run_pipeline(contract)
                contract.refresh_from_db()
                self.assertEqual(contract.status, Contract.Status.READY)
                findings = Finding.objects.filter(review_run__contract=contract)
                self.assertGreaterEqual(findings.count(), 2)
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()


class OverrideB2Tests(TestCase):
    def test_override_suppresses_rule_on_next_run(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            ov = Path(tmp) / "overrides.json"
            pb.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "Test",
                        "preferred_governing_law": "England and Wales",
                        "rules": [
                            {
                                "id": "governing_law_preferred",
                                "clause_type": "governing_law",
                                "preferred": "England and Wales",
                                "hard_ceiling": "Flag CA",
                                "fallback_text": "England and Wales law.",
                                "severity": "medium",
                                "match_any": ["laws of California", "laws of the State of California"],
                            },
                            {
                                "id": "uncapped_or_broad_indemnity",
                                "clause_type": "indemnity",
                                "preferred": "Capped",
                                "hard_ceiling": "No broad indemnity",
                                "fallback_text": "Capped indemnity.",
                                "severity": "high",
                                "match_any": ["shall indemnify"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ov.write_text(json.dumps({"version": 1, "overrides": []}), encoding="utf-8")
            memory_mod.reset_decision_store()
            text = (
                "This Agreement shall be governed by the laws of California. "
                "Party shall indemnify the other without limit."
            )
            with override_settings(
                PLAYBOOK_PATH=pb,
                PLAYBOOK_OVERRIDES_PATH=ov,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_override_b2",
            ):
                memory_mod.reset_decision_store()
                c1 = Contract.objects.create(
                    filename="o1.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=text,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c1)
                ids = set(
                    Finding.objects.filter(review_run__contract=c1).values_list(
                        "playbook_rule_id", flat=True
                    )
                )
                self.assertIn("governing_law_preferred", ids)
                self.assertIn("uncapped_or_broad_indemnity", ids)

                f_gov = Finding.objects.get(
                    review_run__contract=c1, playbook_rule_id="governing_law_preferred"
                )
                decision = record_decision(
                    finding=f_gov,
                    contract=c1,
                    action="override",
                    reasoning="OK for this counterparty",
                )
                self.assertEqual(decision.action, Decision.Action.OVERRIDE)
                data = load_overrides()
                self.assertEqual(len(data["overrides"]), 1)
                self.assertEqual(
                    data["overrides"][0]["playbook_rule_id"], "governing_law_preferred"
                )
                # Golden playbook unchanged
                golden = json.loads(pb.read_text(encoding="utf-8"))
                self.assertEqual(len(golden["rules"]), 2)

                c2 = Contract.objects.create(
                    filename="o2.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=text,
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(c2)
                ids2 = set(
                    Finding.objects.filter(review_run__contract=c2).values_list(
                        "playbook_rule_id", flat=True
                    )
                )
                self.assertNotIn("governing_law_preferred", ids2)
                self.assertIn("uncapped_or_broad_indemnity", ids2)
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()

    def test_merge_removes_suppressed_rules(self):
        playbook = {
            "rules": [{"id": "a"}, {"id": "b"}],
            "empty": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            ov = Path(tmp) / "ov.json"
            with override_settings(PLAYBOOK_OVERRIDES_PATH=ov):
                append_override(playbook_rule_id="a", reason="test")
                merged = merge_playbook_with_overrides(playbook)
                self.assertEqual([r["id"] for r in merged["rules"]], ["b"])
                self.assertIn("a", merged["overrides_applied"])


class UploadFormPageTests(TestCase):
    def test_upload_shows_demo_hint(self):
        r = Client().get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Demo -")
