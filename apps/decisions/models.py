from __future__ import annotations

import uuid

from django.db import models


class Decision(models.Model):
    class Action(models.TextChoices):
        ACCEPT = "accept", "Accept"
        EDIT = "edit", "Edit"
        REJECT = "reject", "Reject"
        OVERRIDE = "override", "Override & accept as-is"
        FALSE_POSITIVE = "false_positive", "Report false positive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    finding = models.ForeignKey(
        "review.Finding",
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    final_text = models.TextField(blank=True, default="")
    reasoning = models.TextField(blank=True, default="")
    chroma_id = models.CharField(max_length=64, blank=True, default="")
    memory_active = models.BooleanField(
        default=True,
        help_text="False after Unlearn — precedent should not be reused",
    )
    memory_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="LLM enrich: {summary, tags[]}",
    )
    superseded = models.BooleanField(
        default=False,
        help_text="True after Undo — excluded from active history",
    )
    superseded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} on {self.finding_id}"


class AuditEvent(models.Model):
    """Append-only lawyer-facing audit log (Sprint 5 lite)."""

    class Kind(models.TextChoices):
        ACTIVATE = "activate", "Playbook activate"
        RESTORE = "restore", "Playbook restore"
        OVERRIDE = "override", "Override"
        REVOKE_OVERRIDE = "revoke_override", "Revoke override"
        DECISION = "decision", "Decision"
        UNDO = "undo", "Undo decision"
        REDO = "redo", "Redo decision"
        FALSE_POSITIVE = "false_positive", "False positive"
        SECURITY_OVERRIDE = "security_override", "Security override"
        LLM_CALL = "llm_call", "LLM call"
        MISSED_CLAUSE = "missed_clause", "Missed clause propose"
        ADMIN_RESET = "admin_reset", "Admin reset"
        REACT_DRAFT = "react_draft", "ReAct draft"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    summary = models.CharField(max_length=512, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    decision = models.ForeignKey(
        Decision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    entry_hash = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.kind}: {self.summary[:40]}"
