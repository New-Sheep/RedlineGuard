from __future__ import annotations

import sys
import threading

from django.conf import settings
from django.contrib import messages
from django.db import close_old_connections
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.contracts.models import Contract
from apps.core.labels import humanize_label
from apps.review.services.pipeline import run_pipeline
from apps.security.models import SecurityEvent


def _trigger_labels(matches) -> list[str]:
    """Dedupe and space out technical cue strings for lawyers."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in matches or []:
        text = str(raw or "").strip()
        if not text or "[compact]" in text.lower():
            continue
        if "_" in text and " " not in text:
            label = humanize_label(text, empty=text)
        else:
            label = text
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


class SecurityAlertView(View):
    template_name = "security/alert.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        event = (
            SecurityEvent.objects.filter(contract=contract)
            .order_by("-created_at")
            .first()
        )
        adj = dict(event.adjudication or {}) if event else {}
        matches = list(event.matches or []) if event else []
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "event": event,
                "adjudication": adj,
                "trigger_labels": _trigger_labels(matches),
                "can_override": bool(
                    contract.status == Contract.Status.HALTED
                    and event
                    and event.halt
                ),
            },
        )


class SecurityOverrideView(View):
    """Lawyer explicitly continues after a hard security halt."""

    def post(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        event = (
            SecurityEvent.objects.filter(contract=contract, halt=True)
            .order_by("-created_at")
            .first()
        )
        if event:
            adj = dict(event.adjudication or {})
            adj["overridden"] = True
            adj["verdict"] = "proceed"
            event.adjudication = adj
            event.halt = False
            event.summary = (
                "Human override - continuing review despite security cue. "
                + (adj.get("plain_english") or "")
            )[:500]
            event.save(update_fields=["adjudication", "halt", "summary"])

        contract.status = Contract.Status.PROCESSING
        contract.error_message = ""
        contract.save(update_fields=["status", "error_message"])

        try:
            from apps.decisions.models import AuditEvent
            from apps.decisions.services.lifecycle import log_audit

            log_audit(
                kind=AuditEvent.Kind.SECURITY_OVERRIDE,
                summary=f"Security override · {contract.filename}",
                payload={"contract_id": str(contract.pk)},
                contract=contract,
            )
        except Exception:
            pass

        sync = getattr(settings, "ANALYZE_SYNC", False) or ("test" in sys.argv)

        if sync:
            run_pipeline(contract, skip_security=True)
            contract.refresh_from_db()
            if contract.status == Contract.Status.READY:
                messages.success(request, "Override recorded - review ready.")
            else:
                messages.warning(
                    request, contract.error_message or "Override finished."
                )
            return redirect("contracts:review", pk=contract.pk)

        def _job() -> None:
            close_old_connections()
            try:
                c = Contract.objects.get(pk=pk)
                run_pipeline(c, skip_security=True)
            finally:
                close_old_connections()

        threading.Thread(
            target=_job, daemon=True, name=f"override-{pk}"
        ).start()
        messages.info(request, "Override recorded - continuing review…")
        return redirect("contracts:processing", pk=pk)
