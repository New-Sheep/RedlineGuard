from __future__ import annotations

from django import forms

from apps.decisions.models import Decision


class DecisionForm(forms.Form):
    action = forms.ChoiceField(
        choices=Decision.Action.choices,
        label="Decision",
        widget=forms.RadioSelect(attrs={"class": "decision-native"}),
        help_text=(
            "Accept or Edit: we remember this for the next similar clause. "
            "Override & accept as-is: mute this playbook rule for now "
            "(does not change the official company playbook). "
            "Report false positive: mark a bad flag without teaching Memory."
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
