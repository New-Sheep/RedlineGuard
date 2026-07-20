"""Transparent weighted risk score (L0/L1/L2)."""

from __future__ import annotations

from typing import Any

from apps.review.services.compare.models import LayeredFinding

_W = {"rule": 1.0, "semantic": 0.70, "llm": 0.85}
_SEV = {"high": 25, "medium": 15, "low": 5}


def score_findings(
    findings: list[LayeredFinding],
    *,
    judge_stats: dict[str, int] | None = None,
) -> tuple[int, dict[str, Any]]:
    """BASE=0; contribution = sev * max(source_weight) * confidence (+ L2 tweaks)."""
    rule_points = 0.0
    semantic_points = 0.0
    llm_points = 0.0
    rows: list[dict[str, Any]] = []
    stats = judge_stats or {}

    for f in findings:
        sev = _SEV.get((f.severity or "medium").lower(), 15)
        sources = list(f.sources or ["rule"])
        weights = [_W.get(s, 0.5) for s in sources]
        w = max(weights) if weights else 0.5
        conf = float(f.confidence or 1.0)
        if "llm" in sources and not f.llm_disagrees:
            conf = min(1.0, conf)  # already bumped in layer_llm
        contrib = sev * w * conf
        if f.llm_disagrees:
            contrib *= 0.85
        rows.append(
            {
                "rule_id": f.playbook_rule_id,
                "sources": sources,
                "severity": f.severity,
                "confidence": round(conf, 3),
                "contribution": round(contrib, 2),
                "llm_disagrees": bool(f.llm_disagrees),
            }
        )
        if "rule" in sources:
            rule_points += contrib
        elif "llm" in sources:
            llm_points += contrib
        else:
            semantic_points += contrib

    total = rule_points + semantic_points + llm_points
    score = int(min(100, round(total)))
    breakdown = {
        "base": 0,
        "rule_points": round(rule_points, 2),
        "semantic_points": round(semantic_points, 2),
        "llm_points": round(llm_points, 2),
        "finding_count": len(findings),
        "llm_confirmed": int(stats.get("llm_confirmed", 0)),
        "llm_dropped": int(stats.get("llm_dropped", 0)),
        "llm_disagreed": int(stats.get("llm_disagreed", 0)),
        "formula": (
            "sev * max(source_weight) * confidence; BASE=0; "
            "rule=1.0 semantic=0.70 llm=0.85; llm_disagrees*=0.85"
        ),
        "findings": rows,
    }
    return score, breakdown
