"""Tests for L2 LLM judge second pass (offline Fake / mocks)."""

from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from apps.review.services.compare.layer_llm import (
    FakeJudge,
    JudgeVerdict,
    apply_llm_judgments,
)
from apps.review.services.compare.models import LayeredFinding
from apps.review.services.compare.orchestrate import compare_layered
from apps.review.services.compare.score import score_findings


def _finding(
    *,
    rule_id: str = "r1",
    sources: list | None = None,
    severity: str = "medium",
    confidence: float = 1.0,
) -> LayeredFinding:
    return LayeredFinding(
        clause_name="clause",
        status="FLAGGED",
        playbook_rule_id=rule_id,
        deviation_reason="Triggered.",
        suggested_counter_proposal="Fallback.",
        severity=severity,
        clause_excerpt="Some contract language about ownership.",
        sources=sources or ["rule"],
        confidence=confidence,
    )


_PLAYBOOK = {
    "name": "T",
    "rules": [
        {
            "id": "r1",
            "clause_type": "ip",
            "preferred": "Retain IP",
            "hard_ceiling": "No assignment",
            "fallback_text": "Retain IP.",
            "severity": "high",
            "match_any": ["assign all"],
        },
        {
            "id": "governing_law_preferred",
            "clause_type": "governing_law",
            "preferred": "England and Wales",
            "hard_ceiling": "Flag non-UK",
            "fallback_text": "England and Wales.",
            "severity": "medium",
            "match_any": ["laws of the State of California"],
        },
    ],
}


class DropJudge:
    def judge(self, **kwargs):
        return JudgeVerdict(
            violates=False, severity="low", rationale="not a violation", quote=""
        )


class ConfirmJudge:
    def judge(self, **kwargs):
        return JudgeVerdict(
            violates=True, severity="high", rationale="clear violation", quote="x"
        )


class ApplyJudgmentsTests(SimpleTestCase):
    def test_semantic_only_dropped(self):
        f = _finding(sources=["semantic"], rule_id="r1")
        kept, stats = apply_llm_judgments([f], _PLAYBOOK, judge=DropJudge())
        self.assertEqual(kept, [])
        self.assertEqual(stats["llm_dropped"], 1)

    def test_semantic_only_confirmed_adds_llm(self):
        f = _finding(sources=["semantic"], rule_id="r1", severity="medium")
        kept, stats = apply_llm_judgments([f], _PLAYBOOK, judge=ConfirmJudge())
        self.assertEqual(len(kept), 1)
        self.assertIn("llm", kept[0].sources)
        self.assertIn("semantic", kept[0].sources)
        self.assertEqual(kept[0].severity, "high")
        self.assertEqual(stats["llm_confirmed"], 1)

    def test_rule_sticky_on_disagree(self):
        f = _finding(sources=["rule"], rule_id="r1")
        kept, stats = apply_llm_judgments([f], _PLAYBOOK, judge=DropJudge())
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0].llm_disagrees)
        self.assertNotIn("llm", kept[0].sources)
        self.assertIn("LLM disagrees", kept[0].deviation_reason)
        self.assertEqual(stats["llm_disagreed"], 1)

    def test_score_llm_points_and_disagree_demotion(self):
        confirmed = _finding(sources=["semantic", "llm"], severity="high", confidence=0.9)
        disagreed = _finding(sources=["rule"], severity="medium")
        disagreed = disagreed.model_copy(update={"llm_disagrees": True})
        score, br = score_findings(
            [confirmed, disagreed],
            judge_stats={"llm_confirmed": 1, "llm_dropped": 0, "llm_disagreed": 1},
        )
        self.assertIn("llm_points", br)
        self.assertGreater(br["llm_points"], 0)
        self.assertEqual(br["llm_disagreed"], 1)
        self.assertGreater(score, 0)


class OrchestrateJudgeFlagTests(SimpleTestCase):
    @override_settings(FAKE_LLM="1", LLM_JUDGE=False, SEMANTIC_COMPARE=False)
    def test_judge_off_l0_california(self):
        text = (
            "This Agreement shall be governed by the laws of the State of California."
        )
        report = compare_layered(
            text, _PLAYBOOK, semantic=False, judge=False
        )
        self.assertEqual(len(report.reviews), 1)
        self.assertEqual(
            report.reviews[0].playbook_rule_id, "governing_law_preferred"
        )
        self.assertNotIn("llm", report.reviews[0].sources)

    @override_settings(FAKE_LLM="1", LLM_JUDGE=True, SEMANTIC_COMPARE=False)
    def test_fake_judge_confirms_l0(self):
        text = (
            "This Agreement shall be governed by the laws of the State of California."
        )
        report = compare_layered(text, _PLAYBOOK, semantic=False, judge=True)
        self.assertEqual(len(report.reviews), 1)
        self.assertIn("llm", report.reviews[0].sources)
        self.assertEqual(report.score_breakdown.get("llm_confirmed"), 1)
