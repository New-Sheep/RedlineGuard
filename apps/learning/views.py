"""Memory UI + thin JSON APIs."""

from __future__ import annotations

from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from apps.decisions.models import AuditEvent, Decision
from apps.decisions.services.lifecycle import log_audit
from apps.learning.services.catalog import (
    active_overrides,
    precedent_rows,
    search_memory,
    unlearn_precedent,
)
from apps.review.services.overrides import revoke_override


class MemoryPageView(View):
    template_name = "learning/memory.html"

    def get(self, request):
        reject_n = Decision.objects.filter(
            action__in=[Decision.Action.REJECT, Decision.Action.EDIT],
            superseded=False,
        ).count()
        return render(
            request,
            self.template_name,
            {
                "precedents": precedent_rows(),
                "overrides": active_overrides(),
                "suggest_gaps": reject_n >= 3,
            },
        )


class MemoryRevokeOverrideView(View):
    def post(self, request):
        rule_id = (request.POST.get("rule_id") or "").strip()
        contract_id = (request.POST.get("contract_id") or "").strip()
        n = revoke_override(playbook_rule_id=rule_id, contract_id=contract_id)
        log_audit(
            kind=AuditEvent.Kind.REVOKE_OVERRIDE,
            summary=f"Revoked override for {rule_id}",
            payload={"rule_id": rule_id, "removed": n},
        )
        return redirect(request.POST.get("next") or "/memory/")


class MemoryUnlearnView(View):
    def post(self, request, precedent_id):
        unlearn_precedent(str(precedent_id))
        next_url = request.POST.get("next") or "/memory/"
        return redirect(next_url)


class MemoryListApiView(View):
    def get(self, request):
        return JsonResponse({"precedents": precedent_rows()})


class MemorySearchApiView(View):
    def get(self, request):
        q = request.GET.get("q") or ""
        rule_id = request.GET.get("rule_id") or ""
        return JsonResponse(
            {
                "q": q,
                "rule_id": rule_id,
                "hits": search_memory(q=q, rule_id=rule_id),
            }
        )


class MemoryDeleteApiView(View):
    """Mutating API — CSRF required (session cookie + X-CSRFToken or form token)."""

    def delete(self, request, precedent_id):
        ok = unlearn_precedent(str(precedent_id))
        status = 200 if ok else 404
        return JsonResponse({"ok": ok, "id": str(precedent_id)}, status=status)

    def post(self, request, precedent_id):
        # Allow form-style POST for browsers without fetch DELETE
        return self.delete(request, precedent_id)

    def get(self, request, precedent_id):
        return HttpResponseNotAllowed(["DELETE", "POST"])
