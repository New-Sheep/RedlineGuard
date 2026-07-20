"""Admin lab resets + contract delete APIs."""

from __future__ import annotations

import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.authz import LoginRequiredMixin, RoleRequiredMixin, user_role
from apps.accounts.models import UserProfile
from apps.contracts.models import Contract
from apps.decisions.models import AuditEvent, Decision
from apps.decisions.services.lifecycle import log_audit
from apps.learning.services.catalog import unlearn_precedent
from apps.learning.services.memory import get_decision_store, reset_decision_store
from apps.review.services.overrides import save_overrides


CONFIRM = "RESET"


def _json_body(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return {}


def _confirm_ok(request, body: dict | None = None) -> bool:
    body = body or {}
    token = (
        body.get("confirm")
        or request.POST.get("confirm")
        or request.headers.get("X-Confirm-Reset")
        or ""
    )
    return str(token).strip().upper() == CONFIRM


class LabResetView(LoginRequiredMixin, RoleRequiredMixin, View):
    """HTML admin lab — wipe decisions / contracts / overrides."""

    required_roles = ("admin",)
    template_name = "accounts/lab_reset.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "decision_count": Decision.objects.count(),
                "contract_count": Contract.objects.count(),
                "role": user_role(request.user),
            },
        )

    def post(self, request):
        if not _confirm_ok(request):
            messages.error(request, f'Type {CONFIRM} in the confirm box to proceed.')
            return redirect("accounts:lab_reset")
        target = (request.POST.get("target") or "").strip()
        if target == "decisions":
            n = _wipe_decisions(request.user)
            messages.success(request, f"Reset {n} decisions + Chroma collection.")
        elif target == "contracts":
            n = _wipe_contracts(request.user)
            messages.success(request, f"Deleted {n} contracts (cascade).")
        elif target == "overrides":
            save_overrides({})
            log_audit(
                kind=AuditEvent.Kind.ADMIN_RESET,
                summary="Reset playbook overrides",
                payload={
                    "target": "overrides",
                    "actor": getattr(request.user, "username", "") or "admin",
                },
            )
            messages.success(request, "Cleared playbook overrides.")
        elif target == "onboarding":
            n = UserProfile.objects.update(onboarding_complete=False, onboarding_step=0)
            log_audit(
                kind=AuditEvent.Kind.ADMIN_RESET,
                summary="Reset onboarding flags",
                payload={
                    "target": "onboarding",
                    "count": n,
                    "actor": getattr(request.user, "username", "") or "admin",
                },
            )
            messages.success(request, f"Reset onboarding for {n} profiles.")
        else:
            messages.error(request, "Unknown reset target.")
        return redirect("accounts:lab_reset")


class ContractDeleteFormView(LoginRequiredMixin, RoleRequiredMixin, View):
    """HTML POST delete for catalogue (lawyer)."""

    required_roles = ("lawyer",)

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        for d in Decision.objects.filter(contract=contract):
            try:
                if d.chroma_id:
                    unlearn_precedent(str(d.chroma_id))
            except Exception:
                pass
        fname = contract.filename
        contract.delete()
        log_audit(
            kind=AuditEvent.Kind.ADMIN_RESET,
            summary=f"Deleted contract {fname}",
            payload={
                "target": "contract",
                "contract_id": str(pk),
                "actor": getattr(request.user, "username", "") or "lawyer",
            },
        )
        messages.success(request, f"Deleted {fname}.")
        return redirect("contracts:list")


class ApiContractDeleteView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("lawyer",)

    def delete(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        # Unlearn decisions linked to this contract before cascade
        for d in Decision.objects.filter(contract=contract):
            try:
                if d.chroma_id:
                    unlearn_precedent(str(d.chroma_id))
            except Exception:
                pass
        fname = contract.filename
        contract.delete()
        log_audit(
            kind=AuditEvent.Kind.ADMIN_RESET,
            summary=f"Deleted contract {fname}",
            payload={
                "target": "contract",
                "contract_id": str(pk),
                "actor": getattr(request.user, "username", "") or "lawyer",
            },
        )
        return JsonResponse({"ok": True, "deleted": str(pk)})


class ApiResetDecisionsView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        n = _wipe_decisions(request.user)
        return JsonResponse({"ok": True, "deleted_decisions": n})


class ApiResetContractsView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        n = _wipe_contracts(request.user)
        return JsonResponse({"ok": True, "deleted_contracts": n})


class ApiResetOverridesView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        save_overrides({})
        log_audit(
            kind=AuditEvent.Kind.ADMIN_RESET,
            summary="API reset overrides",
            payload={
                "target": "overrides",
                "actor": getattr(request.user, "username", "") or "admin",
            },
        )
        return JsonResponse({"ok": True})


class ApiResetOnboardingView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        n = UserProfile.objects.update(onboarding_complete=False, onboarding_step=0)
        log_audit(
            kind=AuditEvent.Kind.ADMIN_RESET,
            summary="API reset onboarding",
            payload={
                "target": "onboarding",
                "count": n,
                "actor": getattr(request.user, "username", "") or "admin",
            },
        )
        return JsonResponse({"ok": True, "profiles_reset": n})


def _wipe_decisions(user) -> int:
    n = Decision.objects.count()
    Decision.objects.all().delete()
    try:
        get_decision_store().reset()
        reset_decision_store()
    except Exception:
        pass
    log_audit(
        kind=AuditEvent.Kind.ADMIN_RESET,
        summary=f"Reset all decisions ({n})",
        payload={
            "target": "decisions",
            "count": n,
            "actor": getattr(user, "username", "") or "admin",
        },
    )
    return n


def _wipe_contracts(user) -> int:
    n = Contract.objects.count()
    Contract.objects.all().delete()
    log_audit(
        kind=AuditEvent.Kind.ADMIN_RESET,
        summary=f"Reset all contracts ({n})",
        payload={
            "target": "contracts",
            "count": n,
            "actor": getattr(user, "username", "") or "admin",
        },
    )
    return n
