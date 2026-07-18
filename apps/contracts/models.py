from __future__ import annotations

import uuid

from django.db import models


class Contract(models.Model):
    class Source(models.TextChoices):
        UPLOAD = "upload", "Upload"
        SAMPLE = "sample", "Sample"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        EXTRACTED = "extracted", "Extracted"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        HALTED = "halted", "Security halt"
        FAILED = "failed", "Failed"

    class ProgressStep(models.TextChoices):
        QUEUED = "queued", "Queued"
        READING = "reading", "Reading document"
        SECURITY = "security", "Security check"
        PLAYBOOK = "playbook", "Comparing to playbook"
        MEMORY = "memory", "Looking up past decisions"
        DRAFT = "draft", "Drafting counters"
        DONE = "done", "Done"

    class Quality(models.TextChoices):
        OK = "ok", "OK"
        POOR = "poor", "Poor"
        UNKNOWN = "", "Unknown"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=512)
    source = models.CharField(max_length=16, choices=Source.choices)
    file = models.FileField(upload_to="contracts/%Y/%m/", blank=True, null=True)
    sample_key = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Filename under data/scratch_corpus/ when source=sample",
    )
    extracted_text = models.TextField(blank=True, default="")
    quality = models.CharField(max_length=16, blank=True, default="")
    page_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)
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
    triage_kind = models.CharField(max_length=64, blank=True, default="")
    triage_stakes = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

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
