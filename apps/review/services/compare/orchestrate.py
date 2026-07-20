"""Orchestrate L0 + L1 (+ optional L2 judge) compare for the Django pipeline."""

from __future__ import annotations

import os
from typing import Any

from apps.review.services.compare.layer_llm import apply_llm_judgments
from apps.review.services.compare.layer_rule import layer_rule
from apps.review.services.compare.layer_semantic import layer_semantic
from apps.review.services.compare.merge import merge_candidates
from apps.review.services.compare.models import LayeredReport
from apps.review.services.compare.score import score_findings


def _truthy(val: str | bool | None, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip() not in ("0", "false", "False", "")


def _distances() -> tuple[float, float]:
    fake = os.environ.get("FAKE_EMBED", "0").strip() not in ("0", "false", "False")
    default_max = "0.85" if fake else "0.45"
    default_strict = "0.55" if fake else "0.35"
    try:
        from django.conf import settings

        max_d = float(
            getattr(
                settings,
                "SEMANTIC_MAX_DISTANCE",
                os.environ.get("SEMANTIC_MAX_DISTANCE", default_max),
            )
        )
        strict = float(
            getattr(
                settings,
                "SEMANTIC_STRICT_DISTANCE",
                os.environ.get("SEMANTIC_STRICT_DISTANCE", default_strict),
            )
        )
        return max_d, strict
    except Exception:
        return (
            float(os.environ.get("SEMANTIC_MAX_DISTANCE", default_max)),
            float(os.environ.get("SEMANTIC_STRICT_DISTANCE", default_strict)),
        )


def _semantic_enabled() -> bool:
    try:
        from django.conf import settings

        return _truthy(
            getattr(settings, "SEMANTIC_COMPARE", os.environ.get("SEMANTIC_COMPARE", "1"))
        )
    except Exception:
        return _truthy(os.environ.get("SEMANTIC_COMPARE", "1"))


def _judge_enabled() -> bool:
    """L2 on when LLM_JUDGE truthy; default 1 if FAKE_LLM=0 else 0."""
    try:
        from django.conf import settings

        fake = str(
            getattr(settings, "FAKE_LLM", os.environ.get("FAKE_LLM", "1"))
        ).strip() not in ("0", "false", "False")
        raw = os.environ.get("LLM_JUDGE")
        if raw is None:
            raw = getattr(settings, "LLM_JUDGE", None)
        if raw is None or raw is Ellipsis:
            return not fake
        return _truthy(raw, default=not fake)
    except Exception:
        fake = os.environ.get("FAKE_LLM", "1").strip() not in ("0", "false", "False")
        raw = os.environ.get("LLM_JUDGE")
        if raw is None:
            return not fake
        return _truthy(raw, default=not fake)


def _judge_max() -> int:
    try:
        from django.conf import settings

        return int(
            getattr(
                settings,
                "LLM_JUDGE_MAX_FINDINGS",
                os.environ.get("LLM_JUDGE_MAX_FINDINGS", "8"),
            )
        )
    except Exception:
        return int(os.environ.get("LLM_JUDGE_MAX_FINDINGS", "8"))


def compare_layered(
    text: str,
    playbook: dict[str, Any] | None = None,
    *,
    semantic: bool | None = None,
    judge: bool | None = None,
) -> LayeredReport:
    playbook = playbook or {"rules": []}
    if playbook.get("empty") or not (playbook.get("rules") or []):
        score, breakdown = score_findings([])
        return LayeredReport(
            overall_risk_score=score, reviews=[], score_breakdown=breakdown
        )

    rule_hits = layer_rule(text, playbook)
    semantic_hits = []
    use_sem = _semantic_enabled() if semantic is None else semantic
    if use_sem:
        max_d, strict = _distances()
        semantic_hits = layer_semantic(
            text,
            playbook,
            max_distance=max_d,
            strict_distance=strict,
            skip_rule_ids=set(),
        )

    already = {c.playbook_rule_id for c in rule_hits} | {
        c.playbook_rule_id for c in semantic_hits
    }
    try:
        from apps.review.services.compare.layer_discover import discover_candidates

        discovered = discover_candidates(text, playbook, already=already)
        semantic_hits = list(semantic_hits) + list(discovered)
    except Exception:
        pass

    findings = merge_candidates(rule_hits, semantic_hits)
    judge_stats: dict[str, int] = {}
    use_judge = _judge_enabled() if judge is None else judge
    if use_judge and findings:
        findings, judge_stats = apply_llm_judgments(
            findings,
            playbook,
            max_findings=_judge_max(),
        )

    score, breakdown = score_findings(findings, judge_stats=judge_stats)
    return LayeredReport(
        overall_risk_score=score,
        reviews=findings,
        score_breakdown=breakdown,
    )
