"""Merge L0 + L1 candidates by playbook_rule_id."""

from __future__ import annotations

from apps.review.services.compare.models import FindingCandidate, LayeredFinding, SourceKind
from apps.review.services.severity import sort_by_severity


def merge_candidates(
    rule_hits: list[FindingCandidate],
    semantic_hits: list[FindingCandidate],
) -> list[LayeredFinding]:
    by_id: dict[str, FindingCandidate] = {}
    for c in rule_hits:
        by_id[c.playbook_rule_id] = c.model_copy(deep=True)

    for c in semantic_hits:
        rid = c.playbook_rule_id
        if rid in by_id:
            existing = by_id[rid]
            sources: list[SourceKind] = list(existing.sources)
            if "semantic" not in sources:
                sources.append("semantic")
            existing.sources = sources
            # Prefer rule span; keep semantic distance for transparency
            if existing.match_distance is None:
                existing.match_distance = c.match_distance
            # Confidence: keep rule 1.0
            by_id[rid] = existing
        else:
            by_id[rid] = c.model_copy(deep=True)

    findings: list[LayeredFinding] = []
    for c in by_id.values():
        fallback = c.fallback_text
        if fallback:
            status = "FLAGGED"
            suggestion = fallback
            if "rule" in c.sources:
                reason = (
                    f"Playbook rule `{c.playbook_rule_id}` triggered. "
                    f"Preferred: {c.preferred}. Using playbook fallback counter."
                )
            else:
                reason = (
                    f"Semantic match to playbook rule `{c.playbook_rule_id}` "
                    f"(preferred: {c.preferred}). Using playbook fallback counter."
                )
        else:
            status = "REQUIRES_HUMAN"
            suggestion = None
            reason = (
                f"Playbook rule `{c.playbook_rule_id}` triggered "
                f"({c.hard_ceiling}) but no fallback draft - needs human."
            )
            if "semantic" in c.sources and "rule" not in c.sources:
                reason = (
                    f"Semantic near-match to rule `{c.playbook_rule_id}` "
                    f"({c.hard_ceiling}); no fallback draft - needs human."
                )

        findings.append(
            LayeredFinding(
                clause_name=c.clause_name,
                status=status,  # type: ignore[arg-type]
                playbook_rule_id=c.playbook_rule_id,
                deviation_reason=reason,
                suggested_counter_proposal=suggestion,
                severity=c.severity,
                clause_excerpt=c.clause_excerpt,
                start_offset=c.start_offset,
                end_offset=c.end_offset,
                sources=list(c.sources),
                confidence=c.confidence,
                match_distance=c.match_distance,
            )
        )
    return sort_by_severity(
        findings,
        get_severity=lambda f: f.severity,
        tiebreak=lambda f: f.playbook_rule_id,
    )
