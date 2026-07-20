"""Draft engines: FakeDraftEngine today; LlmDraftEngine later (same interface)."""

from __future__ import annotations

from typing import Any, Protocol

from scratch.poc06_memory.models import PrecedentHit
from scratch.poc07_draft.models import DraftResult


class DraftEngine(Protocol):
    def draft(
        self,
        finding: dict[str, Any],
        precedents: list[PrecedentHit] | list[dict[str, Any]],
    ) -> DraftResult: ...


def _as_hit_dicts(
    precedents: list[PrecedentHit] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in precedents:
        if isinstance(p, PrecedentHit):
            out.append(
                {
                    "id": p.record.id,
                    "decision": p.record.decision,
                    "final_text": p.record.final_text,
                    "distance": p.distance,
                    "filename": p.record.filename,
                    "created_at": p.record.created_at,
                    "clause_text": p.record.clause_text,
                }
            )
        else:
            out.append(p)
    return out


class FakeDraftEngine:
    """Deterministic draft: memory accept/edit first, else playbook fallback.

    No LLM call. A future LlmDraftEngine can implement DraftEngine the same way.
    Caller is expected to pre-filter by distance / reject-avoid.
    """

    def draft(
        self,
        finding: dict[str, Any],
        precedents: list[PrecedentHit] | list[dict[str, Any]],
    ) -> DraftResult:
        rule_id = str(finding.get("playbook_rule_id") or "unknown")
        status = str(finding.get("status") or finding.get("finding_status") or "")
        hits = _as_hit_dicts(precedents)

        usable = [
            h
            for h in hits
            if h.get("decision") in ("accept", "edit") and (h.get("final_text") or "").strip()
        ]
        # Nearest first: lower distance is better; missing distance sorts last
        usable.sort(
            key=lambda h: (
                h.get("distance") is None,
                float(h["distance"]) if h.get("distance") is not None else 1e9,
            )
        )

        if usable:
            best = usable[0]
            dist = best.get("distance")
            sim = None if dist is None else round(max(0.0, 1.0 - float(dist)), 3)
            return DraftResult(
                playbook_rule_id=rule_id,
                finding_status=status,
                draft_text=best["final_text"],
                draft_source="memory_precedent",
                precedent_ids=[str(h.get("id") or "") for h in usable if h.get("id")],
                rationale=(
                    f"Reused nearest {best.get('decision')} precedent "
                    f"(dist={best.get('distance')})"
                ),
                provenance={
                    "precedent_id": best.get("id") or "",
                    "filename": best.get("filename") or "",
                    "decision": best.get("decision") or "",
                    "date": str(best.get("created_at") or "")[:10],
                    "distance": dist,
                    "similarity": sim,
                    "clause_quote": (best.get("clause_text") or "")[:280],
                },
            )

        fallback = finding.get("suggested_counter_proposal")
        if fallback and str(fallback).strip():
            return DraftResult(
                playbook_rule_id=rule_id,
                finding_status=status,
                draft_text=str(fallback).strip(),
                draft_source="playbook_fallback",
                precedent_ids=[],
                rationale="No usable Accept/Edit memory; using playbook fallback text",
                provenance={},
            )

        return DraftResult(
            playbook_rule_id=rule_id,
            finding_status=status,
            draft_text=None,
            draft_source="none",
            precedent_ids=[],
            rationale="No precedent Accept/Edit and no playbook fallback",
            provenance={},
        )
