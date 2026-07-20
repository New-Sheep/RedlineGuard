"""First-time lawyer onboarding wizard."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.accounts.authz import LoginRequiredMixin, auth_required
from apps.accounts.models import ensure_profile
from apps.review.services.playbook_import import load_active_playbook


STEPS = [
    {
        "id": 1,
        "title": "Welcome to RedlineGuard",
        "blurb": (
            "AI proposes risks against your playbook. You confirm every Accept, Reject, "
            "and Override. This is a first-pass tool - not legal advice."
        ),
    },
    {
        "id": 2,
        "title": "Playbook · Memory · Override",
        "blurb": (
            "Playbook = firm rules (activate/import). Memory = your Accept precedents for "
            "retrieval. Override = temporary mute of a rule. Accept never mutates the golden playbook."
        ),
    },
    {
        "id": 3,
        "title": "Activate a playbook",
        "blurb": (
            "Import Sample Playbook4 (or your YAML) and Activate. Without an active playbook, "
            "review runs in no-playbook scout mode."
        ),
    },
    {
        "id": 4,
        "title": "Upload a demo contract",
        "blurb": (
            "Upload Demo clean NDA or a risky sample from the Contracts queue. Open Review - "
            "flags appear with rule ids, evidence, and plain-English why."
        ),
    },
    {
        "id": 5,
        "title": "Optional: seed Memory",
        "blurb": (
            "Accept a few flags on a known-good contract so Decision Memory has precedents. "
            "Or skip - you can Unlearn later."
        ),
    },
]


class OnboardingView(LoginRequiredMixin, View):
    template_name = "accounts/onboarding.html"

    def get(self, request):
        if not auth_required() and not request.user.is_authenticated:
            return redirect("accounts:login")
        profile = ensure_profile(request.user) if request.user.is_authenticated else None
        if profile and profile.onboarding_complete and request.GET.get("force") != "1":
            return redirect("contracts:list")
        step = int(request.GET.get("step") or (profile.onboarding_step if profile else 1) or 1)
        step = max(1, min(step, len(STEPS)))
        active = load_active_playbook()
        return render(
            request,
            self.template_name,
            {
                "steps": STEPS,
                "step": STEPS[step - 1],
                "step_num": step,
                "total": len(STEPS),
                "has_playbook": bool(active and active.get("rules")),
                "profile": profile,
            },
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        profile = ensure_profile(request.user)
        action = (request.POST.get("action") or "next").strip()
        step = int(request.POST.get("step") or 1)
        if action == "skip" or action == "finish":
            profile.onboarding_complete = True
            profile.onboarding_step = len(STEPS)
            profile.save(update_fields=["onboarding_complete", "onboarding_step"])
            messages.success(request, "Onboarding complete - open the Contracts queue.")
            return redirect("contracts:list")
        if action == "next":
            nxt = min(step + 1, len(STEPS))
            profile.onboarding_step = nxt
            if nxt >= len(STEPS):
                profile.onboarding_complete = True
            profile.save(update_fields=["onboarding_complete", "onboarding_step"])
            if profile.onboarding_complete:
                messages.success(request, "You're ready. Upload a contract to begin.")
                return redirect("contracts:list")
            return redirect(f"{request.path}?step={nxt}")
        if action == "back":
            prev = max(step - 1, 1)
            profile.onboarding_step = prev
            profile.save(update_fields=["onboarding_step"])
            return redirect(f"{request.path}?step={prev}")
        return redirect(f"{request.path}?step={step}")
