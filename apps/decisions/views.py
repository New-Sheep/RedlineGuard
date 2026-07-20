from __future__ import annotations

from django.core.paginator import Paginator
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from apps.contracts.models import Contract
from apps.decisions.models import AuditEvent, Decision
from apps.decisions.services.lifecycle import redo_decision, undo_decision
from apps.review.models import Finding
from apps.review.services.overrides import load_overrides, revoke_override
from apps.review.services.playbook_import import (
    list_playbook_versions,
    load_active_playbook,
    restore_playbook_version,
)
from apps.security.models import SecurityEvent

PAGE_SIZE = 25


class HistoryView(View):
    template_name = "decisions/history.html"

    def get(self, request):
        qs = Decision.objects.select_related("finding", "contract").order_by(
            "-created_at"
        )
        action = (request.GET.get("action") or "").strip()
        rule_id = (request.GET.get("rule_id") or "").strip()
        contract_q = (request.GET.get("contract") or "").strip()
        show_undone = request.GET.get("undone") == "1"
        if not show_undone:
            qs = qs.filter(superseded=False)
        if action:
            qs = qs.filter(action=action)
        if rule_id:
            qs = qs.filter(finding__playbook_rule_id__icontains=rule_id)
        if contract_q:
            qs = qs.filter(contract__filename__icontains=contract_q)
        page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page") or 1)
        parts = []
        for key in ("action", "rule_id", "contract", "undone"):
            val = request.GET.get(key)
            if val:
                parts.append(f"{key}={val}")
        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "decisions": page_obj.object_list,
                "action_filter": action,
                "rule_id_filter": rule_id,
                "contract_filter": contract_q,
                "show_undone": show_undone,
                "action_choices": Decision.Action.choices,
                "querystring": "&".join(parts),
            },
        )


class DecisionUndoView(View):
    def post(self, request, pk):
        decision = get_object_or_404(Decision, pk=pk)
        undo_decision(decision)
        messages.success(
            request,
            "Decision undone. If it was saved in Memory, that example was removed too.",
        )
        return redirect(request.POST.get("next") or "decisions:history")


class DecisionRedoView(View):
    def post(self, request, pk):
        decision = get_object_or_404(Decision, pk=pk)
        redo_decision(decision)
        messages.success(
            request,
            "Decision restored. Accept again if you want it back in Memory.",
        )
        return redirect(request.POST.get("next") or "decisions:history")


class AuditLogView(View):
    template_name = "decisions/audit.html"

    def get(self, request):
        qs = AuditEvent.objects.select_related("contract", "decision").order_by(
            "-created_at"
        )
        kind = (request.GET.get("kind") or "").strip()
        if kind:
            qs = qs.filter(kind=kind)
        page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page") or 1)
        q = f"kind={kind}" if kind else ""
        from apps.decisions.services.audit_chain import verify_chain

        all_events = list(AuditEvent.objects.order_by("created_at"))
        chain_ok, chain_msg = verify_chain(all_events)
        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "events": page_obj.object_list,
                "kind_filter": kind,
                "kind_choices": AuditEvent.Kind.choices,
                "querystring": q,
                "chain_ok": chain_ok,
                "chain_msg": chain_msg,
            },
        )


# --- Thin JSON CRUD APIs (Sprint 2 / 5) ---


class ApiContractsListView(View):
    def get(self, request):
        qs = Contract.objects.all().order_by("-created_at")
        status = (request.GET.get("status") or "").strip()
        if status:
            qs = qs.filter(status=status)
        page = Paginator(qs, int(request.GET.get("page_size") or PAGE_SIZE)).get_page(
            request.GET.get("page") or 1
        )
        return JsonResponse(
            {
                "count": page.paginator.count,
                "page": page.number,
                "num_pages": page.paginator.num_pages,
                "results": [
                    {
                        "id": str(c.id),
                        "filename": c.filename,
                        "status": c.status,
                        "created_at": c.created_at.isoformat(),
                        "char_count": c.char_count,
                    }
                    for c in page.object_list
                ],
            }
        )


class ApiDecisionDetailView(View):
    def get(self, request, pk):
        d = get_object_or_404(Decision.objects.select_related("finding", "contract"), pk=pk)
        return JsonResponse(_decision_json(d))

    def delete(self, request, pk):
        d = get_object_or_404(Decision, pk=pk)
        undo_decision(d)
        return JsonResponse({"ok": True, "id": str(pk), "superseded": True})

    def patch(self, request, pk):
        # Minimal: allow redo via {"superseded": false}
        import json

        d = get_object_or_404(Decision, pk=pk)
        try:
            body = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid json"}, status=400)
        if body.get("superseded") is False:
            redo_decision(d)
        return JsonResponse(_decision_json(d))

    def post(self, request, pk):
        # Form-friendly undo
        return self.delete(request, pk)


class ApiOverridesView(View):
    def get(self, request, rule_id=None):
        return JsonResponse(load_overrides())

    def delete(self, request, rule_id=None):
        if not rule_id:
            return JsonResponse({"error": "rule_id required"}, status=400)
        contract_id = (request.GET.get("contract_id") or "").strip()
        n = revoke_override(playbook_rule_id=rule_id, contract_id=contract_id)
        from apps.decisions.services.lifecycle import log_audit

        log_audit(
            kind=AuditEvent.Kind.REVOKE_OVERRIDE,
            summary=f"Revoked override for {rule_id}",
            payload={"rule_id": rule_id, "removed": n, "contract_id": contract_id},
        )
        return JsonResponse({"ok": True, "removed": n, "rule_id": rule_id})


class ApiPlaybookRestoreView(View):
    def post(self, request):
        import json

        try:
            body = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            body = {}
        version = (body.get("version") or request.POST.get("version") or "").strip()
        if not version:
            return JsonResponse({"error": "version required"}, status=400)
        try:
            path = restore_playbook_version(version)
        except FileNotFoundError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        return JsonResponse({"ok": True, "path": str(path), "version": version})


class ApiFindingsListView(View):
    def get(self, request):
        qs = Finding.objects.select_related("review_run", "review_run__contract").order_by(
            "-id"
        )
        contract_id = (request.GET.get("contract_id") or "").strip()
        if contract_id:
            qs = qs.filter(review_run__contract_id=contract_id)
        page = Paginator(qs, int(request.GET.get("page_size") or PAGE_SIZE)).get_page(
            request.GET.get("page") or 1
        )
        return JsonResponse(
            {
                "count": page.paginator.count,
                "page": page.number,
                "results": [
                    {
                        "id": str(f.id),
                        "contract_id": str(f.review_run.contract_id),
                        "playbook_rule_id": f.playbook_rule_id,
                        "severity": f.severity,
                        "status": f.status,
                        "sources": f.sources,
                        "plain_english": f.plain_english,
                        "match_distance": f.match_distance,
                    }
                    for f in page.object_list
                ],
            }
        )


class ApiSecurityEventsView(View):
    def get(self, request):
        qs = SecurityEvent.objects.select_related("contract").order_by("-created_at")
        page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page") or 1)
        return JsonResponse(
            {
                "count": page.paginator.count,
                "page": page.number,
                "results": [
                    {
                        "id": str(e.id),
                        "contract_id": str(e.contract_id),
                        "halt": e.halt,
                        "summary": e.summary,
                        "matches": e.matches,
                        "adjudication": e.adjudication,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in page.object_list
                ],
            }
        )


class ApiPlaybookActiveView(View):
    def get(self, request):
        pb = load_active_playbook()
        return JsonResponse(
            {
                "playbook": pb,
                "versions": list_playbook_versions(),
            }
        )


class ApiAuditListView(View):
    def get(self, request):
        qs = AuditEvent.objects.order_by("-created_at")
        page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page") or 1)
        return JsonResponse(
            {
                "count": page.paginator.count,
                "page": page.number,
                "results": [
                    {
                        "id": str(e.id),
                        "kind": e.kind,
                        "summary": e.summary,
                        "payload": e.payload,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in page.object_list
                ],
            }
        )


def _decision_json(d: Decision) -> dict:
    return {
        "id": str(d.id),
        "action": d.action,
        "superseded": d.superseded,
        "final_text": d.final_text,
        "reasoning": d.reasoning,
        "chroma_id": d.chroma_id,
        "memory_active": d.memory_active,
        "contract_id": str(d.contract_id),
        "finding_id": str(d.finding_id),
        "rule_id": d.finding.playbook_rule_id,
        "created_at": d.created_at.isoformat(),
    }
