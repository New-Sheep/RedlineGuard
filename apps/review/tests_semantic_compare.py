"""Unit + pipeline tests for L0/L1 layered compare (FAKE_EMBED=1)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.test import Client, TestCase, override_settings

from apps.contracts.models import Contract
from apps.learning.services import memory as memory_mod
from apps.review.models import Finding, ReviewRun
from apps.review.services.compare.orchestrate import compare_layered
from apps.review.services.compare.segment import segment_paragraphs
from apps.review.services.pipeline import run_pipeline


_IP_RULE = {
    "id": "ip_ownership_015ca1",
    "clause_type": "ip_ownership",
    "preferred": "Retain 100% ownership of background IP; customer gets limited license",
    "hard_ceiling": "Never assign or transfer background IP / software copyrights",
    "fallback_text": "Licensor retains all right, title and interest in background IP.",
    "severity": "high",
    "match_any": [
        "assign all intellectual property",
        "transfer ownership of",
    ],
}

_GOV_RULE = {
    "id": "governing_law_preferred",
    "clause_type": "governing_law",
    "preferred": "England and Wales",
    "hard_ceiling": "Flag non-UK governing law",
    "fallback_text": "This Agreement shall be governed by the laws of England and Wales.",
    "severity": "medium",
    "match_any": [
        "laws of the State of California",
        "laws of California",
    ],
}


def _playbook(rules: list) -> dict:
    return {
        "version": 1,
        "name": "Test playbook",
        "preferred_governing_law": "England and Wales",
        "rules": rules,
    }


class SegmentTests(TestCase):
    def test_offsets_stable(self):
        text = "Alpha paragraph one.\n\nBeta paragraph two is longer than forty characters here."
        segs = segment_paragraphs(text)
        self.assertTrue(segs)
        for s in segs:
            self.assertEqual(text[s.start : s.end].strip()[:20], s.text.strip()[:20])
            self.assertGreaterEqual(s.end, s.start)


class LayeredCompareUnitTests(TestCase):
    def test_l0_california_needle(self):
        text = (
            "This Agreement shall be governed by the laws of the State of California "
            "without regard to conflicts."
        )
        report = compare_layered(text, _playbook([_GOV_RULE]), semantic=False)
        self.assertEqual(len(report.reviews), 1)
        f = report.reviews[0]
        self.assertEqual(f.playbook_rule_id, "governing_law_preferred")
        self.assertIn("rule", f.sources)
        self.assertEqual(f.confidence, 1.0)

    def test_l1_paraphrase_ip_assign(self):
        # No exact match_any needle; synonym/overlap + hash distance should still flag.
        text = (
            "Intellectual property.\n\n"
            "Licensee irrevocably transfers all right, title and interest in the "
            "software copyrights and related intellectual property to the Customer "
            "upon payment in full under this Agreement."
        )
        report = compare_layered(
            text,
            _playbook([_IP_RULE]),
            semantic=True,
        )
        ids = {f.playbook_rule_id for f in report.reviews}
        self.assertIn("ip_ownership_015ca1", ids)
        semantic = next(f for f in report.reviews if f.playbook_rule_id == "ip_ownership_015ca1")
        self.assertIn("semantic", semantic.sources)
        self.assertTrue(semantic.playbook_rule_id)
        # Should not also be a pure regex hit on the paraphrase
        self.assertNotIn("assign all intellectual property", text.lower())

    def test_clean_doc_score_zero(self):
        text = "The parties agree to meet on Tuesdays for pizza and coffee."
        report = compare_layered(text, _playbook([_GOV_RULE, _IP_RULE]), semantic=True)
        self.assertEqual(report.reviews, [])
        self.assertEqual(report.overall_risk_score, 0)
        self.assertEqual(report.score_breakdown.get("base"), 0)
        self.assertEqual(report.score_breakdown.get("rule_points"), 0)
        self.assertEqual(report.score_breakdown.get("semantic_points"), 0)
        self.assertEqual(report.score_breakdown.get("finding_count"), 0)


class LayeredComparePipelineTests(TestCase):
    def test_score_breakdown_persisted_and_ui(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            pb.write_text(json.dumps(_playbook([_GOV_RULE])), encoding="utf-8")
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_semantic_compare",
                SEMANTIC_COMPARE=True,
                FAKE_EMBED=True,
            ):
                memory_mod.reset_decision_store()
                contract = Contract.objects.create(
                    filename="clean.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text="The parties agree to meet on Tuesdays for pizza.",
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                    char_count=50,
                )
                run_pipeline(contract)
                contract.refresh_from_db()
                self.assertEqual(contract.status, Contract.Status.READY)
                run = ReviewRun.objects.get(contract=contract)
                self.assertEqual(run.risk_score, 0)
                self.assertEqual(run.findings.count(), 0)
                self.assertIn("rule_points", run.score_breakdown)
                self.assertEqual(run.score_breakdown.get("finding_count"), 0)

                r = Client().get(f"/contracts/{contract.pk}/review/")
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "Rule hits:")
                self.assertContains(r, "Semantic:")
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()

    def test_california_still_flags_with_rule_source(self):
        tmp = tempfile.mkdtemp()
        try:
            pb = Path(tmp) / "playbook.json"
            chroma = Path(tmp) / "chroma"
            pb.write_text(json.dumps(_playbook([_GOV_RULE])), encoding="utf-8")
            memory_mod.reset_decision_store()
            with override_settings(
                PLAYBOOK_PATH=pb,
                CHROMA_PATH=chroma,
                CHROMA_COLLECTION="test_semantic_cal",
                SEMANTIC_COMPARE=True,
            ):
                memory_mod.reset_decision_store()
                contract = Contract.objects.create(
                    filename="cal.txt",
                    source=Contract.Source.UPLOAD,
                    extracted_text=(
                        "This Agreement shall be governed by the laws of the State of California."
                    ),
                    status=Contract.Status.EXTRACTED,
                    quality="ok",
                )
                run_pipeline(contract)
                f = Finding.objects.get(review_run__contract=contract)
                self.assertEqual(f.playbook_rule_id, "governing_law_preferred")
                self.assertIn("rule", f.sources)
                run = f.review_run
                self.assertGreater(run.risk_score, 0)
                self.assertIn("score_breakdown", {"score_breakdown": run.score_breakdown})
                r = Client().get(f"/contracts/{contract.pk}/review/")
                self.assertContains(r, "Rule")
                memory_mod.reset_decision_store()
        finally:
            memory_mod.reset_decision_store()
