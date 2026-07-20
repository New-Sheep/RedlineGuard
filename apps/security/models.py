from __future__ import annotations

import uuid

from django.db import models


class SecurityEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="security_events",
    )
    halt = models.BooleanField(default=False)
    matches = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True, default="")
    adjudication = models.JSONField(
        default=dict,
        blank=True,
        help_text="LLM/heuristic second opinion after cue halt",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        state = "HALT" if self.halt else "ok"
        return f"SecurityEvent {state} for {self.contract_id}"
