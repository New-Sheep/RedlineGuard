from __future__ import annotations

from pathlib import Path

from django import forms
from django.conf import settings

# Prefer these at the top of the sample dropdown (value = filename on disk).
DEMO_SAMPLE_LABELS: dict[str, str] = {
    "demo_clean_flags.txt": "Demo — clean contract (2–4+ playbook flags)",
    "demo_short_nda.txt": "Demo — short form (2 flags)",
    "injection_hostile.txt": "Demo — hostile / injection (Journey C halt)",
}


def list_sample_files() -> list[str]:
    corpus = Path(settings.SCRATCH_CORPUS_DIR)
    if not corpus.is_dir():
        return []
    return sorted(
        p.name
        for p in corpus.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".txt"}
    )


def sample_choice_label(filename: str) -> str:
    return DEMO_SAMPLE_LABELS.get(filename, filename)


def ordered_sample_choices() -> list[tuple[str, str]]:
    names = list_sample_files()
    demo_first = [n for n in DEMO_SAMPLE_LABELS if n in names]
    rest = [n for n in names if n not in DEMO_SAMPLE_LABELS]
    ordered = demo_first + rest
    return [("", "— select a sample —")] + [(n, sample_choice_label(n)) for n in ordered]


class ContractIngestForm(forms.Form):
    sample_key = forms.ChoiceField(
        choices=[],
        required=False,
        label="Sample from corpus",
    )
    upload = forms.FileField(
        required=False,
        label="Or upload a PDF / TXT",
        help_text="PDF or plain text",
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
                "Choose exactly one: a corpus sample or a file upload."
            )
        if upload:
            name = getattr(upload, "name", "") or ""
            if Path(name).suffix.lower() not in {".pdf", ".txt"}:
                raise forms.ValidationError("Only PDF or TXT uploads are supported.")
        return cleaned
