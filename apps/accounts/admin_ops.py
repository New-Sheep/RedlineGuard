"""Admin lab resets + contract delete APIs."""

from __future__ import annotations

import json
import logging

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
from apps.review.services.overrides import load_overrides, save_overrides


CONFIRM = "RESET"
logger = logging.getLogger(__name__)


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


def _is_missing_collection_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg or "not found" in msg


def _chroma_count() -> int:
    try:
        return int(get_decision_store().count())
    except Exception as exc:
        if _is_missing_collection_error(exc):
            reset_decision_store()
            try:
                return int(get_decision_store().count())
            except Exception:
                return 0
        return 0


def _wipe_chroma() -> tuple[int, str | None]:
    """
    Drop the decision-memory collection.
    Returns (count_before, error_message_or_None).
    Missing/already-deleted collections count as success (already clear).
    """
    before = 0
    try:
        store = get_decision_store()
        try:
            before = int(store.count())
        except Exception as exc:
            if _is_missing_collection_error(exc):
                reset_decision_store()
                return 0, None
            raise

        store.reset()
        reset_decision_store()
        try:
            after = int(get_decision_store().count())
        except Exception as exc:
            if _is_missing_collection_error(exc):
                reset_decision_store()
                return before, None
            raise
        if after > 0:
            return before, "Could not clear all saved examples. Try again."
        return before, None
    except Exception as exc:  # noqa: BLE001
        if _is_missing_collection_error(exc):
            reset_decision_store()
            return before, None
        logger.exception("Memory reset failed")
        reset_decision_store()
        return before, "Could not clear saved examples. Try again."


class LabResetView(LoginRequiredMixin, RoleRequiredMixin, View):
    """HTML admin lab, wipe decisions / contracts / overrides / onboarding."""

    required_roles = ("admin",)
    template_name = "accounts/lab_reset.html"

    def get(self, request):
        overrides = load_overrides().get("overrides") or []
        decision_count = Decision.objects.count()
        contract_count = Contract.objects.count()
        memory_count = max(_chroma_count(), 0)
        override_count = len(overrides)
        onboarding_done = UserProfile.objects.filter(onboarding_complete=True).count()
        return render(
            request,
            self.template_name,
            {
                "decision_count": decision_count,
                "contract_count": contract_count,
                "memory_count": memory_count,
                "override_count": override_count,
                "onboarding_done_count": onboarding_done,
                "can_reset_decisions": decision_count > 0 or memory_count > 0,
                "can_reset_contracts": contract_count > 0 or memory_count > 0,
                "can_reset_overrides": override_count > 0,
                "can_reset_onboarding": onboarding_done > 0,
                "role": user_role(request.user),
                "confirm_word": CONFIRM,
            },
        )

    def post(self, request):
        if not _confirm_ok(request):
            messages.error(
                request,
                f'Type {CONFIRM} in the confirm box (the grey hint text is not filled in for you).',
            )
            return redirect("accounts:lab_reset")
        target = (request.POST.get("target") or "").strip()
        if target == "decisions":
            n, chroma_n, err = _wipe_decisions(request.user)
            if err:
                messages.error(
                    request,
                    f"Cleared {n} decision(s), but could not clear Memory: {err}",
                )
            elif n == 0 and chroma_n == 0:
                messages.success(
                    request,
                    "Already clear. No decisions or saved examples.",
                )
            else:
                messages.success(
                    request,
                    f"Cleared {n} decision(s) and {chroma_n} saved example(s).",
                )
        elif target == "contracts":
            n, chroma_n, err = _wipe_contracts(request.user)
            if err:
                messages.error(
                    request,
                    f"Deleted {n} contract(s), but could not clear Memory: {err}",
                )
            elif n == 0 and chroma_n == 0:
                messages.success(
                    request,
                    "Already clear. No contracts or saved examples.",
                )
            else:
                messages.success(
                    request,
                    f"Deleted {n} contract(s) and cleared {chroma_n} saved example(s).",
                )
        elif target == "overrides":
            before = len(load_overrides().get("overrides") or [])
            save_overrides({"version": 1, "overrides": []})
            log_audit(
                kind=AuditEvent.Kind.ADMIN_RESET,
                summary="Reset playbook overrides",
                payload={
                    "target": "overrides",
                    "count": before,
                    "actor": getattr(request.user, "username", "") or "admin",
                },
            )
            if before == 0:
                messages.success(request, "Already clear. No muted rules.")
            else:
                messages.success(request, f"Cleared {before} muted rule(s).")
        elif target == "onboarding":
            n = UserProfile.objects.update(
                onboarding_complete=False, onboarding_step=0
            )
            log_audit(
                kind=AuditEvent.Kind.ADMIN_RESET,
                summary="Reset onboarding flags",
                payload={
                    "target": "onboarding",
                    "count": n,
                    "actor": getattr(request.user, "username", "") or "admin",
                },
            )
            messages.success(
                request,
                f"Setup will show again for {n} person(s) on next sign-in.",
            )
        else:
            messages.error(request, "Unknown reset action.")
        return redirect("accounts:lab_reset")


class ContractDeleteFormView(LoginRequiredMixin, RoleRequiredMixin, View):
    """HTML POST delete for catalogue (lawyer or admin)."""

    required_roles = ("lawyer", "admin")

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
    required_roles = ("lawyer", "admin")

    def delete(self, request, pk):
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
        return JsonResponse({"ok": True, "deleted": str(pk)})


class ApiResetDecisionsView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        n, chroma_n, err = _wipe_decisions(request.user)
        if err:
            return JsonResponse(
                {
                    "ok": False,
                    "deleted_decisions": n,
                    "cleared_memory": chroma_n,
                    "error": err,
                },
                status=500,
            )
        return JsonResponse(
            {"ok": True, "deleted_decisions": n, "cleared_memory": chroma_n}
        )


class ApiResetContractsView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        n, chroma_n, err = _wipe_contracts(request.user)
        if err:
            return JsonResponse(
                {
                    "ok": False,
                    "deleted_contracts": n,
                    "cleared_memory": chroma_n,
                    "error": err,
                },
                status=500,
            )
        return JsonResponse(
            {"ok": True, "deleted_contracts": n, "cleared_memory": chroma_n}
        )


class ApiResetOverridesView(LoginRequiredMixin, RoleRequiredMixin, View):
    required_roles = ("admin",)

    def post(self, request):
        body = _json_body(request)
        if not _confirm_ok(request, body):
            return JsonResponse({"error": f"confirm must be {CONFIRM}"}, status=400)
        before = len(load_overrides().get("overrides") or [])
        save_overrides({"version": 1, "overrides": []})
        log_audit(
            kind=AuditEvent.Kind.ADMIN_RESET,
            summary="API reset overrides",
            payload={
                "target": "overrides",
                "count": before,
                "actor": getattr(request.user, "username", "") or "admin",
            },
        )
        return JsonResponse({"ok": True, "cleared_overrides": before})


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


def _wipe_decisions(user) -> tuple[int, int, str | None]:
    """Clear ORM decisions + Chroma. Returns (orm_n, chroma_before, error)."""
    n = Decision.objects.count()
    Decision.objects.all().delete()
    chroma_n, err = _wipe_chroma()
    log_audit(
        kind=AuditEvent.Kind.ADMIN_RESET,
        summary=f"Reset all decisions ({n}) + memory ({chroma_n})",
        payload={
            "target": "decisions",
            "count": n,
            "chroma_cleared": chroma_n,
            "error": err or "",
            "actor": getattr(user, "username", "") or "admin",
        },
    )
    return n, chroma_n, err


def _wipe_contracts(user) -> tuple[int, int, str | None]:
    """
    Delete all contracts (cascades review/decisions) and clear Chroma.
    Seeded Memory has no ORM rows, without this, Reset contracts leaves ghosts.
    """
    n = Contract.objects.count()
    Contract.objects.all().delete()
    Decision.objects.all().delete()  # orphans if any
    chroma_n, err = _wipe_chroma()
    log_audit(
        kind=AuditEvent.Kind.ADMIN_RESET,
        summary=f"Reset all contracts ({n}) + memory ({chroma_n})",
        payload={
            "target": "contracts",
            "count": n,
            "chroma_cleared": chroma_n,
            "error": err or "",
            "actor": getattr(user, "username", "") or "admin",
        },
    )
    return n, chroma_n, err
