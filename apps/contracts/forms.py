from __future__ import annotations

from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.uploads import validate_upload_size

# Prefer these at the top of the sample dropdown (value = filename on disk).
DEMO_SAMPLE_LABELS: dict[str, str] = {
    "demo_clean_flags.txt": "Demo - clean contract (2-4+ playbook flags)",
    "demo_short_nda.txt": "Demo - short form (2 flags)",
    "injection_hostile.txt": "Demo - hostile / injection (Journey C halt)",
}


def list_sample_files() -> list[str]:
    corpus = Path(settings.SCRATCH_CORPUS_DIR)
    if not corpus.is_dir():
        return []
    return sorted(
        p.name
        for p in corpus.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".txt", ".docx"}
    )


def sample_choice_label(filename: str) -> str:
    return DEMO_SAMPLE_LABELS.get(filename, filename)


def ordered_sample_choices() -> list[tuple[str, str]]:
    names = list_sample_files()
    demo_first = [n for n in DEMO_SAMPLE_LABELS if n in names]
    rest = [n for n in names if n not in DEMO_SAMPLE_LABELS]
    ordered = demo_first + rest
    return [("", "- select a sample -")] + [(n, sample_choice_label(n)) for n in ordered]


class ContractIngestForm(forms.Form):
    sample_key = forms.ChoiceField(
        choices=[],
        required=False,
        label="Choose a sample file",
    )
    upload = forms.FileField(
        required=False,
        label="Upload PDF / Word / text",
        help_text="Text-based PDFs work best. Scanned image PDFs usually fail.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sample_key"].choices = ordered_sample_choices()

    def clean(self):
        cleaned = super().clean()
        sample = (cleaned.get("sample_key") or "").strip()
        upload = cleaned.get("upload")
        if bool(sample) == bool(upload):
            raise forms.ValidationError(
                "Choose exactly one: a sample file or an upload."
            )
        if upload:
            name = getattr(upload, "name", "") or ""
            if Path(name).suffix.lower() not in {".pdf", ".txt", ".docx"}:
                raise forms.ValidationError(
                    "Only PDF, DOCX, or TXT uploads are supported."
                )
            try:
                validate_upload_size(upload)
            except DjangoValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc
        return cleaned
