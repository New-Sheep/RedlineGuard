from __future__ import annotations

import uuid

from django.db import models


class PlaybookImport(models.Model):
    class Source(models.TextChoices):
        UPLOAD = "upload", "Upload"
        SAMPLE = "sample", "Sample"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        PROPOSED = "proposed", "Proposed"
        ACTIVATED = "activated", "Activated"
        HALTED = "halted", "Security halt"
        FAILED = "failed", "Failed"

    class ProgressStep(models.TextChoices):
        QUEUED = "queued", "Queued"
        READING = "reading", "Reading playbook PDF"
        SECURITY = "security", "Security check"
        PROPOSING = "proposing", "Proposing rules"
        DONE = "done", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=512)
    source = models.CharField(max_length=16, choices=Source.choices)
    file = models.FileField(upload_to="playbooks/%Y/%m/", blank=True, null=True)
    sample_key = models.CharField(max_length=512, blank=True, default="")
    extracted_text = models.TextField(blank=True, default="")
    proposed_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    progress_step = models.CharField(
        max_length=16,
        choices=ProgressStep.choices,
        default=ProgressStep.QUEUED,
        blank=True,
    )
    progress_label = models.CharField(max_length=128, blank=True, default="Queued")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def set_progress(self, step: str, label: str | None = None) -> None:
        self.progress_step = step
        if label is None:
            label = dict(self.ProgressStep.choices).get(step, step)
        self.progress_label = label
        self.save(update_fields=["progress_step", "progress_label"])

    def __str__(self) -> str:
        return f"{self.filename} ({self.status})"


class ReviewRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="review_runs",
    )
    risk_score = models.PositiveIntegerField(default=0)
    playbook_name = models.CharField(max_length=256, blank=True, default="")
    playbook_empty = models.BooleanField(default=False)
    triage_kind = models.CharField(max_length=64, blank=True, default="")
    triage_stakes = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ReviewRun {self.id} ({self.risk_score})"


class Finding(models.Model):
    class Status(models.TextChoices):
        FLAGGED = "FLAGGED", "Flagged"
        REQUIRES_HUMAN = "REQUIRES_HUMAN", "Needs human"
        APPROVED = "APPROVED", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review_run = models.ForeignKey(
        ReviewRun,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    playbook_rule_id = models.CharField(max_length=128)
    clause_name = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(max_length=32, choices=Status.choices)
    severity = models.CharField(max_length=32, default="medium")
    deviation_reason = models.TextField(blank=True, default="")
    suggested_counter = models.TextField(blank=True, default="")
    clause_excerpt = models.TextField(blank=True, default="")
    start_offset = models.PositiveIntegerField(default=0)
    end_offset = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["severity", "playbook_rule_id"]

    def __str__(self) -> str:
        return f"{self.playbook_rule_id} ({self.status})"


class Draft(models.Model):
    class Source(models.TextChoices):
        MEMORY = "memory_precedent", "Memory precedent"
        PLAYBOOK = "playbook_fallback", "Playbook fallback"
        LLM = "llm_suggested", "LLM suggested"
        NONE = "none", "None"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    finding = models.OneToOneField(
        Finding,
        on_delete=models.CASCADE,
        related_name="draft",
    )
    draft_text = models.TextField(blank=True, default="")
    draft_source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.NONE,
    )
    precedent_ids = models.JSONField(default=list, blank=True)
    rationale = models.TextField(blank=True, default="")
    provenance = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Draft {self.draft_source} for {self.finding_id}"
