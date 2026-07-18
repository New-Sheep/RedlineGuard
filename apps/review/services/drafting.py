"""Draft assembly: memory → playbook fallback → LLM suggest."""

from __future__ import annotations

import logging
from typing import Any

from apps.core.llm import FakeLlmClient, get_llm_client
from apps.learning.services.memory import (
    filter_usable_accepts,
    provenance_from_hit,
    search_precedents,
)
from scratch.poc02_security.security import fence, sanitize
from scratch.poc07_draft.engine import FakeDraftEngine
from scratch.poc07_draft.models import DraftResult

logger = logging.getLogger(__name__)


def draft_for_finding(
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
    contract_text: str,
    playbook_empty: bool,
) -> DraftResult:
    engine = FakeDraftEngine()
    filtered_hits: list = []
    blocked_by_reject = False
    if not playbook_empty:
        rule_id = finding_payload.get("playbook_rule_id")
        query = (
            (finding_payload.get("clause_excerpt") or "").strip()
            or (finding_payload.get("deviation_reason") or "").strip()
            or f"[{rule_id}] {finding_payload.get('suggested_counter_proposal') or ''}"
        ).strip()
        raw_hits = search_precedents(query, playbook_rule_id=str(rule_id or ""), top_k=8)
        accepts, near_reject = filter_usable_accepts(raw_hits)
        if near_reject is not None:
            blocked_by_reject = True
            filtered_hits = []
        else:
            filtered_hits = accepts[:3]

    result = engine.draft(finding_payload, filtered_hits)
    if result.draft_source == "memory_precedent" and filtered_hits:
        hit = filtered_hits[0]
        prov = provenance_from_hit(hit)
        result.provenance = prov
        result.rationale = (
            f"Reused {prov.get('decision')} from {prov.get('filename') or 'prior contract'} "
            f"({prov.get('date') or 'n/a'}) · similarity {prov.get('similarity')}"
        )
        return result

    if result.draft_source != "none" and (result.draft_text or "").strip():
        if blocked_by_reject:
            result.rationale = (
                (result.rationale or "")
                + " (near Reject avoid-signal skipped memory)"
            ).strip()
        return result

    # Needs-human / empty: LLM port (Fake or HTTP)
    try:
        cleaned = sanitize(contract_text or "")
        fenced = fence(cleaned[:8000])
        suggestion = get_llm_client().suggest_draft(
            playbook_rule=playbook_rule or {},
            finding=finding_payload,
            fenced_contract_excerpt=fenced,
        )
        rationale = suggestion.rationale
        if blocked_by_reject:
            rationale = f"{rationale} (near Reject avoid-signal skipped memory)"
        return DraftResult(
            playbook_rule_id=str(finding_payload.get("playbook_rule_id") or "unknown"),
            finding_status=str(finding_payload.get("status") or ""),
            draft_text=suggestion.draft_text,
            draft_source="llm_suggested",
            precedent_ids=[],
            rationale=rationale,
            provenance={},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM draft failed, using FakeLlmClient fallback: %s", exc)
        suggestion = FakeLlmClient().suggest_draft(
            playbook_rule=playbook_rule or {},
            finding=finding_payload,
            fenced_contract_excerpt="",
        )
        return DraftResult(
            playbook_rule_id=str(finding_payload.get("playbook_rule_id") or "unknown"),
            finding_status=str(finding_payload.get("status") or ""),
            draft_text=suggestion.draft_text,
            draft_source="llm_suggested",
            precedent_ids=[],
            rationale=suggestion.rationale + f" (fallback after error: {exc})",
            provenance={},
        )
