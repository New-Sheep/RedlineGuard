"""Narrow ReAct tools for Needs-human drafting only."""

from __future__ import annotations

from typing import Any

from apps.learning.services.memory import (
    filter_usable_accepts,
    provenance_from_hit,
    search_precedents,
)
from apps.security.services.redactor import redact_pii
from scratch.poc02_security.security import fence, sanitize


def search_precedents_tool(
    *,
    query: str,
    playbook_rule_id: str = "",
) -> dict[str, Any]:
    hits = search_precedents(query, playbook_rule_id=playbook_rule_id or None, top_k=5)
    accepts, near_reject = filter_usable_accepts(hits)
    return {
        "accept_count": len(accepts),
        "blocked_by_reject": near_reject is not None,
        "top": [
            {
                "id": h.record.id,
                "decision": h.record.decision,
                "distance": h.distance,
                "snippet": (h.record.final_text or "")[:120],
            }
            for h in accepts[:3]
        ],
        "near_reject_id": near_reject.record.id if near_reject else None,
    }


def check_playbook_rule_tool(playbook_rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": playbook_rule.get("id"),
        "preferred": (playbook_rule.get("preferred") or "")[:300],
        "hard_ceiling": (playbook_rule.get("hard_ceiling") or "")[:200],
        "fallback_text": (playbook_rule.get("fallback_text") or "")[:400],
        "severity": playbook_rule.get("severity"),
    }


def redact_pii_tool(text: str) -> dict[str, Any]:
    redacted, mapping = redact_pii(text or "")
    kinds = sorted(
        {k.split("_")[1] for k in mapping if k.startswith("[REDACTED_")}
    )
    return {
        "redacted_preview": (redacted or "")[:400],
        "pii_types": kinds,
        "changed": bool(mapping),
    }


def propose_draft_tool(
    *,
    playbook_rule: dict[str, Any],
    finding: dict[str, Any],
    memory_hint: str = "",
) -> dict[str, Any]:
    preferred = (playbook_rule.get("preferred") or "").strip()
    fallback = (playbook_rule.get("fallback_text") or "").strip()
    excerpt = (finding.get("clause_excerpt") or "")[:500]
    if memory_hint:
        draft = memory_hint.strip()
        source = "memory_hint"
    elif preferred:
        draft = preferred
        source = "playbook_preferred"
    elif fallback:
        draft = fallback
        source = "playbook_fallback"
    else:
        draft = (
            f"[COUNTER] Align clause with playbook rule "
            f"{playbook_rule.get('id') or 'unknown'}."
        )
        source = "scaffold"
    return {
        "draft_text": draft,
        "source": source,
        "rationale": f"Proposed from {source}; excerpt length {len(excerpt)}.",
    }


def escalate_human_tool(*, reason: str) -> dict[str, Any]:
    return {"escalated": True, "reason": (reason or "Needs human judgment")[:300]}


def fence_excerpt(text: str) -> str:
    return fence(sanitize(text or "")[:6000])
