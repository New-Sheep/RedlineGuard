"""Audit helpers + decision undo/redo + hash chain."""

from __future__ import annotations

from django.utils import timezone

from apps.decisions.models import AuditEvent, Decision
from apps.decisions.services.audit_chain import GENESIS, compute_entry_hash
from apps.learning.services.catalog import unlearn_precedent
from apps.review.services.overrides import revoke_override


def log_audit(
    *,
    kind: str,
    summary: str,
    payload: dict | None = None,
    contract=None,
    decision=None,
) -> AuditEvent:
    last = AuditEvent.objects.order_by("-created_at").first()
    prev = (last.entry_hash if last and last.entry_hash else GENESIS)
    payload = payload or {}
    entry = compute_entry_hash(
        kind=kind,
        summary=(summary or "")[:512],
        payload=payload,
        prev_hash=prev,
    )
    return AuditEvent.objects.create(
        kind=kind,
        summary=(summary or "")[:512],
        payload=payload,
        contract=contract,
        decision=decision,
        prev_hash=prev,
        entry_hash=entry,
    )


def undo_decision(decision: Decision) -> Decision:
    """Supersede a decision, unlearn memory, revoke override if needed."""
    if decision.superseded:
        return decision
    if decision.chroma_id and decision.memory_active:
        unlearn_precedent(decision.chroma_id)
        decision.memory_active = False
    if decision.action == Decision.Action.OVERRIDE:
        revoke_override(
            playbook_rule_id=decision.finding.playbook_rule_id,
            contract_id=str(decision.contract_id),
        )
    decision.superseded = True
    decision.superseded_at = timezone.now()
    decision.save(
        update_fields=["superseded", "superseded_at", "memory_active"]
    )
    log_audit(
        kind=AuditEvent.Kind.UNDO,
        summary=f"Undid {decision.action} on {decision.finding.playbook_rule_id}",
        payload={"decision_id": str(decision.id), "action": decision.action},
        contract=decision.contract,
        decision=decision,
    )
    return decision


def redo_decision(decision: Decision) -> Decision:
    """Re-activate a superseded decision (simple redo)."""
    if not decision.superseded:
        return decision
    decision.superseded = False
    decision.superseded_at = None
    decision.save(update_fields=["superseded", "superseded_at"])
    log_audit(
        kind=AuditEvent.Kind.REDO,
        summary=f"Redid {decision.action} on {decision.finding.playbook_rule_id}",
        payload={"decision_id": str(decision.id)},
        contract=decision.contract,
        decision=decision,
    )
    return decision
