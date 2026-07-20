"""Draft assembly: memory → (real LLM if FAKE_LLM=0) → playbook fallback → Fake LLM."""

from __future__ import annotations

import logging
import os
from typing import Any

from django.conf import settings

from apps.core.llm import FakeLlmClient, get_llm_client
from apps.core.llm_complete import provider_label
from apps.learning.services.memory import (
    filter_usable_accepts,
    provenance_from_hit,
    search_precedents,
)
from apps.review.services.memory_assist import explain_memory_hit
from scratch.poc02_security.security import fence, sanitize
from scratch.poc07_draft.engine import FakeDraftEngine
from scratch.poc07_draft.models import DraftResult

logger = logging.getLogger(__name__)


def _real_llm_on() -> bool:
    raw = str(getattr(settings, "FAKE_LLM", os.environ.get("FAKE_LLM", "1"))).strip()
    return raw in ("0", "false", "False")


def _llm_draft(
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
    contract_text: str,
    blocked_by_reject: bool,
) -> DraftResult:
    excerpt = (finding_payload.get("clause_excerpt") or "").strip()
    if not excerpt:
        excerpt = (contract_text or "")[:6000]
    cleaned = sanitize(excerpt)
    fenced = fence(cleaned[:6000])
    suggestion = get_llm_client().suggest_draft(
        playbook_rule=playbook_rule or {},
        finding=finding_payload,
        fenced_contract_excerpt=fenced,
    )
    preferred = (playbook_rule.get("preferred") or "").strip()
    ceiling = (playbook_rule.get("hard_ceiling") or "").strip()
    rationale = suggestion.rationale or "LLM counter aligned to playbook preferred/ceiling."
    if preferred:
        rationale = f"{rationale} Preferred: {preferred}."
    if ceiling:
        rationale = f"{rationale} Ceiling: {ceiling}."
    if blocked_by_reject:
        rationale = f"{rationale} (near Reject avoid-signal skipped memory)"
    return DraftResult(
        playbook_rule_id=str(finding_payload.get("playbook_rule_id") or "unknown"),
        finding_status=str(finding_payload.get("status") or ""),
        draft_text=suggestion.draft_text,
        draft_source="llm_suggested",
        precedent_ids=[],
        rationale=rationale.strip(),
        provenance={"provider": provider_label()},
    )


def draft_for_finding(
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
    contract_text: str,
    playbook_empty: bool,
) -> DraftResult:
    engine = FakeDraftEngine()
    filtered_hits: list = []
    near_reject = None
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

    # 1) Memory win
    if result.draft_source == "memory_precedent" and filtered_hits:
        hit = filtered_hits[0]
        explain = explain_memory_hit(
            clause_excerpt=finding_payload.get("clause_excerpt") or "",
            rule_id=str(finding_payload.get("playbook_rule_id") or ""),
            accepts=filtered_hits,
            near_reject=near_reject,
        )
        # Prefer LLM-chosen precedent if ranked
        chosen = next(
            (h for h in filtered_hits if h.record.id == explain.chosen_precedent_id),
            hit,
        )
        prov = provenance_from_hit(chosen)
        if explain.warn_reject_nearby:
            prov["warn_reject_nearby"] = True
            prov["reject_note"] = explain.reject_note
        result.draft_text = chosen.record.final_text or result.draft_text
        result.provenance = prov
        result.rationale = explain.explain or (
            f"Reused {prov.get('decision')} from {prov.get('filename') or 'prior contract'} "
            f"({prov.get('date') or 'n/a'}) · similarity {prov.get('similarity')}"
        )
        result.precedent_ids = [str(h.record.id) for h in filtered_hits if h.record.id]
        # stash explain for Draft.memory_explain via provenance
        result.provenance["memory_explain"] = explain.explain
        return result

    # 2) Real LLM when FAKE_LLM=0
    if _real_llm_on():
        try:
            return _llm_draft(
                finding_payload=finding_payload,
                playbook_rule=playbook_rule,
                contract_text=contract_text,
                blocked_by_reject=blocked_by_reject,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM draft failed, falling back to playbook/Fake: %s", exc)

    # 3) Playbook static fallback
    if result.draft_source == "playbook_fallback" and (result.draft_text or "").strip():
        result.rationale = (
            "Playbook fallback counter (no reusable Accept/Edit memory for this clause yet)."
        )
        if blocked_by_reject:
            result.rationale += " Near Reject avoid-signal skipped memory."
        result.provenance = {"provider": "Playbook"}
        return result

    # 4) Needs-human — prefer narrow ReAct agent when enabled
    if getattr(settings, "REACT_DRAFT", True):
        try:
            from apps.drafting.agent import react_draft

            react = react_draft(
                finding_payload=finding_payload,
                playbook_rule=playbook_rule or {},
                contract_text=contract_text,
            )
            if react is not None:
                try:
                    from apps.decisions.models import AuditEvent
                    from apps.decisions.services.lifecycle import log_audit

                    trace = (react.provenance or {}).get("react_trace") or []
                    log_audit(
                        kind=AuditEvent.Kind.REACT_DRAFT,
                        summary=f"ReAct draft for {react.playbook_rule_id}",
                        payload={
                            "prompt_hash": (react.provenance or {}).get("prompt_hash"),
                            "iters": len(trace),
                            "tools": [t.get("tool") for t in trace if isinstance(t, dict)],
                            "provider": (react.provenance or {}).get("provider"),
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass
                return react
        except Exception as exc:  # noqa: BLE001
            logger.warning("ReAct draft failed, falling back: %s", exc)

    try:
        return _llm_draft(
            finding_payload=finding_payload,
            playbook_rule=playbook_rule,
            contract_text=contract_text,
            blocked_by_reject=blocked_by_reject,
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
            provenance={"provider": "Fake"},
        )
