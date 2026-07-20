from __future__ import annotations

from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.uploads import validate_upload_size
from apps.review.services.playbook_bootstrap import PlaybookRule


def list_playbook_samples() -> list[str]:
    corpus = Path(settings.PLAYBOOK_CORPUS_DIR)
    if not corpus.is_dir():
        return []
    return sorted(
        p.name
        for p in corpus.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".txt"}
    )


def list_starter_contract_samples() -> list[str]:
    """Past-contract samples for E2 (scratch corpus; exclude injection fixtures)."""
    corpus = Path(settings.SCRATCH_CORPUS_DIR)
    if not corpus.is_dir():
        return []
    skip = {"injection_hostile.txt"}
    return sorted(
        p.name
        for p in corpus.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".pdf", ".txt"}
        and p.name not in skip
    )


class PlaybookIngestForm(forms.Form):
    sample_key = forms.ChoiceField(choices=[], required=False, label="Sample playbook")
    upload = forms.FileField(required=False, label="Or upload a playbook PDF / TXT")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        samples = list_playbook_samples()
        self.fields["sample_key"].choices = [("", "- select a sample -")] + [
            (n, n) for n in samples
        ]

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
            try:
                validate_upload_size(upload)
            except DjangoValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc
        return cleaned


class PlaybookStarterForm(forms.Form):
    """E2: propose a starter playbook from 3–5 past contracts."""

    sample_keys = forms.MultipleChoiceField(
        choices=[],
        required=False,
        label="Sample past contracts",
        widget=forms.CheckboxSelectMultiple,
        help_text="Pick corpus NDAs / contracts you have seen before.",
    )
    uploads = forms.FileField(
        required=False,
        label="Or upload PDF / TXT files",
        # Multiple files collected via request.FILES.getlist("uploads") in the view;
        # template renders <input type="file" multiple>.
    )
    liked = forms.BooleanField(
        required=False,
        initial=True,
        label="Treat these as liked / preferred paper (shapes preferred positions)",
    )

    def __init__(self, *args, upload_list: list | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_list = list(upload_list or [])
        samples = list_starter_contract_samples()
        self.fields["sample_keys"].choices = [(n, n) for n in samples]

    def clean(self):
        cleaned = super().clean()
        samples = list(cleaned.get("sample_keys") or [])
        upload_list = list(self.upload_list)
        if not upload_list:
            single = cleaned.get("uploads")
            if single:
                upload_list = [single]
        cleaned["_upload_list"] = upload_list

        for f in upload_list:
            name = getattr(f, "name", "") or ""
            if Path(name).suffix.lower() not in {".pdf", ".txt"}:
                raise forms.ValidationError(
                    f"Only PDF or TXT uploads are supported ({name})."
                )

        total = len(samples) + len(upload_list)
        if total < 3:
            raise forms.ValidationError(
                "Select or upload at least 3 past contracts (up to 5)."
            )
        if total > 5:
            raise forms.ValidationError("Use at most 5 past contracts for a starter.")
        return cleaned


class PlaybookActivateForm(forms.Form):
    name = forms.CharField(max_length=200, label="Playbook name")
    preferred_governing_law = forms.CharField(
        max_length=200, label="Preferred governing law"
    )
    confirm = forms.BooleanField(
        label="I have reviewed these rules and want to activate this playbook",
        required=True,
    )

    def __init__(self, *args, rule_count: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.rule_count = rule_count
        for i in range(rule_count):
            self.fields[f"rule_{i}_id"] = forms.CharField(max_length=120)
            self.fields[f"rule_{i}_clause_type"] = forms.CharField(max_length=80)
            self.fields[f"rule_{i}_preferred"] = forms.CharField(
                widget=forms.Textarea(attrs={"rows": 2})
            )
            self.fields[f"rule_{i}_hard_ceiling"] = forms.CharField(
                widget=forms.Textarea(attrs={"rows": 2})
            )
            self.fields[f"rule_{i}_fallback_text"] = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
            )
            self.fields[f"rule_{i}_severity"] = forms.ChoiceField(
                choices=[
                    ("high", "high"),
                    ("medium", "medium"),
                    ("low", "low"),
                ]
            )
            self.fields[f"rule_{i}_match_any"] = forms.CharField(
                required=False,
                help_text="Comma-separated phrases to detect in contracts",
                widget=forms.Textarea(attrs={"rows": 2}),
            )

    @classmethod
    def from_proposed(cls, proposed: dict, data=None) -> PlaybookActivateForm:
        rules = proposed.get("rules") or []
        initial = {
            "name": proposed.get("name") or "",
            "preferred_governing_law": proposed.get("preferred_governing_law") or "",
        }
        for i, rule in enumerate(rules):
            initial[f"rule_{i}_id"] = rule.get("id") or f"rule_{i}"
            initial[f"rule_{i}_clause_type"] = rule.get("clause_type") or "general"
            initial[f"rule_{i}_preferred"] = rule.get("preferred") or ""
            initial[f"rule_{i}_hard_ceiling"] = rule.get("hard_ceiling") or ""
            initial[f"rule_{i}_fallback_text"] = rule.get("fallback_text") or ""
            initial[f"rule_{i}_severity"] = rule.get("severity") or "medium"
            matches = rule.get("match_any") or []
            initial[f"rule_{i}_match_any"] = ", ".join(matches)
        return cls(data, initial=initial, rule_count=len(rules))

    def cleaned_rules(self) -> list[PlaybookRule]:
        rules: list[PlaybookRule] = []
        for i in range(self.rule_count):
            raw_matches = self.cleaned_data.get(f"rule_{i}_match_any") or ""
            matches = [m.strip() for m in raw_matches.split(",") if m.strip()]
            fallback = (self.cleaned_data.get(f"rule_{i}_fallback_text") or "").strip()
            rules.append(
                PlaybookRule(
                    id=self.cleaned_data[f"rule_{i}_id"],
                    clause_type=self.cleaned_data[f"rule_{i}_clause_type"],
                    preferred=self.cleaned_data[f"rule_{i}_preferred"],
                    hard_ceiling=self.cleaned_data[f"rule_{i}_hard_ceiling"],
                    fallback_text=fallback or None,
                    severity=self.cleaned_data[f"rule_{i}_severity"],
                    match_any=matches,
                )
            )
        return rules
