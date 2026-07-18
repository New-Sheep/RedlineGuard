from __future__ import annotations

import uuid

from django.db import models


class Decision(models.Model):
    class Action(models.TextChoices):
        ACCEPT = "accept", "Accept"
        EDIT = "edit", "Edit"
        REJECT = "reject", "Reject"
        OVERRIDE = "override", "Override & accept as-is"

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} on {self.finding_id}"
