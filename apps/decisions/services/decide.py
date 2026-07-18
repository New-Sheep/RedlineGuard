"""Persist Accept / Edit / Reject / Override and optionally write Chroma memory."""

from __future__ import annotations

from apps.contracts.models import Contract
from apps.decisions.models import Decision
from apps.learning.services.memory import add_decision_record
from apps.review.models import Finding
from apps.review.services.overrides import append_override
from scratch.poc06_memory.models import DecisionRecord


def _clause_text_for_memory(finding: Finding) -> str:
    excerpt = (finding.clause_excerpt or "").strip()
    if excerpt:
        return excerpt[:4000]
    # Legacy fallback for findings created before Sprint 5
    return (finding.deviation_reason or finding.clause_name or finding.playbook_rule_id or "")[
        :4000
    ]


def record_decision(
    *,
    finding: Finding,
    contract: Contract,
    action: str,
    final_text: str = "",
    reasoning: str = "",
    write_memory: bool = True,
) -> Decision:
    action = action.lower().strip()
    if action not in {
        Decision.Action.ACCEPT,
        Decision.Action.EDIT,
        Decision.Action.REJECT,
        Decision.Action.OVERRIDE,
    }:
        raise ValueError(f"Unknown action: {action}")

    text = (final_text or "").strip()
    if action == Decision.Action.OVERRIDE:
        # Keep original clause language as "as-is"
        text = text or finding.suggested_counter or finding.deviation_reason or ""
        append_override(
            playbook_rule_id=finding.playbook_rule_id,
            contract_id=str(contract.id),
            reason=reasoning or "Override & accept as-is",
            clause_excerpt=finding.clause_excerpt or finding.deviation_reason or "",
        )
        write_memory = False
    elif action in (Decision.Action.ACCEPT, Decision.Action.EDIT) and not text:
        draft = getattr(finding, "draft", None)
        text = (draft.draft_text if draft else "") or finding.suggested_counter or ""

    chroma_id = ""
    # Accept/Edit with text → positive precedent; Reject → avoid signal (P1)
    memory_actions = {
        Decision.Action.ACCEPT,
        Decision.Action.EDIT,
        Decision.Action.REJECT,
    }
    if write_memory and action in memory_actions:
        clause = _clause_text_for_memory(finding)
        if clause and (action == Decision.Action.REJECT or text):
            record = DecisionRecord(
                clause_text=clause,
                decision=action,  # type: ignore[arg-type]
                final_text=text if action != Decision.Action.REJECT else "",
                playbook_rule_id=finding.playbook_rule_id,
                contract_id=str(contract.id),
                reasoning=reasoning or None,
                filename=contract.filename or None,
                doc_kind=contract.triage_kind or finding.review_run.triage_kind or None,
            )
            add_decision_record(record)
            chroma_id = record.id

    return Decision.objects.create(
        finding=finding,
        contract=contract,
        action=action,
        final_text=text,
        reasoning=reasoning,
        chroma_id=chroma_id,
        memory_active=bool(chroma_id),
    )
