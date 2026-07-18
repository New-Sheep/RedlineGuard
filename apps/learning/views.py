"""Memory UI + thin JSON APIs."""

from __future__ import annotations

from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from apps.learning.services.catalog import (
    active_overrides,
    precedent_rows,
    search_memory,
    unlearn_precedent,
)


class MemoryPageView(View):
    template_name = "learning/memory.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "precedents": precedent_rows(),
                "overrides": active_overrides(),
            },
        )


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


@method_decorator(csrf_exempt, name="dispatch")
class MemoryDeleteApiView(View):
    def delete(self, request, precedent_id):
        ok = unlearn_precedent(str(precedent_id))
        status = 200 if ok else 404
        return JsonResponse({"ok": ok, "id": str(precedent_id)}, status=status)

    def post(self, request, precedent_id):
        # Allow form-style POST for browsers without fetch DELETE
        return self.delete(request, precedent_id)

    def get(self, request, precedent_id):
        return HttpResponseNotAllowed(["DELETE", "POST"])
