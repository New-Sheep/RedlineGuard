from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Case, IntegerField, Value, When


def _default_finding_sources() -> list:
    return ["rule"]


def _severity_rank_annotation():
    """High → Medium → Low (alphabetical Meta.ordering was wrong: high < low < medium)."""
    return Case(
        When(severity__iexact="high", then=Value(0)),
        When(severity__iexact="medium", then=Value(1)),
        When(severity__iexact="low", then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


class FindingQuerySet(models.QuerySet):
    def by_severity(self):
        return self.annotate(_sev_rank=_severity_rank_annotation()).order_by(
            "_sev_rank", "playbook_rule_id"
        )


class FindingManager(models.Manager):
    def get_queryset(self):
        return FindingQuerySet(self.model, using=self._db).by_severity()


class PlaybookImport(models.Model):
    class Source(models.TextChoices):
        UPLOAD = "upload", "Upload"
        SAMPLE = "sample", "Sample"
        STARTER = "starter", "Starter from past contracts"
        MANUAL = "manual", "Written from scratch"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        PROPOSED = "proposed", "Proposed"
        ACTIVATED = "activated", "Activated"
        HALTED = "halted", "Security halt"
        FAILED = "failed", "Failed"

    class ProgressStep(models.TextChoices):
        QUEUED = "queued", "Queued"
        READING = "reading", "Reading source"
        SECURITY = "security", "Security check"
        PROPOSING = "proposing", "Proposing rules"
        DONE = "done", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=512)
    source = models.CharField(max_length=16, choices=Source.choices)
    file = models.FileField(upload_to="playbooks/%Y/%m/", blank=True, null=True)
    sample_key = models.CharField(max_length=512, blank=True, default="")
    # E2: [{kind: sample|upload, key|rel, name, liked}]
    starter_manifest = models.JSONField(default=list, blank=True)
    extracted_text = models.TextField(blank=True, default="")
    proposed_json = models.JSONField(default=dict, blank=True)
    proposal_source = models.CharField(
        max_length=32,
        blank=True,
        default="fake",
        help_text="fake | nvidia | ollama | deepseek | moonshot | http",
    )
    proposal_model = models.CharField(max_length=128, blank=True, default="")
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


class CompanyPlaybook(models.Model):
    """Named company playbook in the library (reviews use the single active golden file)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    preferred_governing_law = models.CharField(max_length=200, blank=True, default="")
    document = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)
    source_import = models.ForeignKey(
        PlaybookImport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_playbooks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-updated_at"]

    def __str__(self) -> str:
        flag = "active" if self.is_active else "saved"
        return f"{self.name} ({flag})"

    @property
    def rule_count(self) -> int:
        return len((self.document or {}).get("rules") or [])


class ReviewRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="review_runs",
    )
    risk_score = models.PositiveIntegerField(default=0)
    score_breakdown = models.JSONField(default=dict, blank=True)
    playbook_name = models.CharField(max_length=256, blank=True, default="")
    playbook_empty = models.BooleanField(default=False)
    coverage_gaps = models.JSONField(
        default=list,
        blank=True,
        help_text="Playbook rules with no match in this contract",
    )
    agent_assist = models.JSONField(
        default=dict,
        blank=True,
        help_text="No-playbook scout or clean-pass brief from context agent",
    )
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
    sources = models.JSONField(default=_default_finding_sources, blank=True)
    confidence = models.FloatField(default=1.0)
    match_distance = models.FloatField(null=True, blank=True)
    plain_english = models.TextField(
        blank=True,
        default="",
        help_text="One-line plain-English gloss of the risk",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = FindingManager()

    class Meta:
        # Ordering applied via FindingManager (severity rank, not alphabetical).
        ordering = []

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
    provider_label = models.CharField(max_length=32, blank=True, default="")
    copilot_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="RewriteCopilot: {why, options[{tone,text}]}",
    )
    memory_explain = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Draft {self.draft_source} for {self.finding_id}"


class MissedClause(models.Model):
    """Lawyer-flagged gap (F22) — propose rule → Activate."""

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        ACTIVATED = "activated", "Activated"
        DISMISSED = "dismissed", "Dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="missed_clauses",
    )
    excerpt = models.TextField()
    note = models.TextField(blank=True, default="")
    proposed_rule = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PROPOSED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"MissedClause {self.status} ({self.pk})"
