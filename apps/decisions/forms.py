from __future__ import annotations

from django import forms

from apps.decisions.models import Decision


class DecisionForm(forms.Form):
    action = forms.ChoiceField(
        choices=Decision.Action.choices,
        label="Decision",
        widget=forms.RadioSelect(attrs={"class": "decision-native"}),
        help_text=(
            "Accept/Edit learn for next similar drafts. "
            "Override & accept as-is suppresses this playbook rule going forward "
            "(writes playbook_overrides.json — not the golden playbook)."
        ),
    )
    final_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        label="Final / edited text",
        help_text="Used for Accept/Edit. Optional for Override (as-is) and Reject.",
    )
    reasoning = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Notes (optional)",
    )
