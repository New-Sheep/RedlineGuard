from __future__ import annotations

import uuid as uuid_lib
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.contracts.models import Contract
from apps.decisions.forms import DecisionForm
from apps.decisions.services.decide import record_decision
from apps.review.forms import PlaybookActivateForm, PlaybookIngestForm, PlaybookStarterForm
from apps.review.models import Finding, PlaybookImport
from apps.review.services.import_job import start_import_async
from apps.review.services.playbook_import import (
    activate_playbook,
    document_from_form,
    list_playbook_versions,
    load_active_playbook,
    restore_playbook_version,
)
from apps.review.services.playbook_audit import audit_playbook

PLAYBOOK_PROGRESS_STEPS = [
    ("queued", "Queued"),
    ("reading", "Reading source"),
    ("security", "Security check"),
    ("proposing", "Proposing rules"),
    ("done", "Done"),
]


def _rule_rows(form: PlaybookActivateForm) -> list[dict]:
    rows = []
    for i in range(form.rule_count):
        rows.append(
            {
                "index": i,
                "id": form[f"rule_{i}_id"],
                "clause_type": form[f"rule_{i}_clause_type"],
                "preferred": form[f"rule_{i}_preferred"],
                "hard_ceiling": form[f"rule_{i}_hard_ceiling"],
                "fallback_text": form[f"rule_{i}_fallback_text"],
                "severity": form[f"rule_{i}_severity"],
                "match_any": form[f"rule_{i}_match_any"],
            }
        )
    return rows


class ActivePlaybookView(View):
    template_name = "review/playbook_active.html"

    def get(self, request):
        playbook = load_active_playbook()
        audit = audit_playbook(playbook) if not playbook.get("empty") else None
        return render(
            request,
            self.template_name,
            {
                "playbook": playbook,
                "is_active_company_playbook": not bool(playbook.get("empty")),
                "versions": list_playbook_versions(),
                "audit": audit,
            },
        )

    def post(self, request):
        """Restore a prior playbook version (explicit)."""
        version = (request.POST.get("version") or "").strip()
        if not version:
            messages.error(request, "Pick a version to restore.")
            return redirect("review:playbook_active")
        try:
            restore_playbook_version(version)
            messages.success(request, f"Restored playbook from {version}.")
        except FileNotFoundError as exc:
            messages.error(request, str(exc))
        return redirect("review:playbook_active")


class PlaybookImportView(View):
    template_name = "review/playbook_import.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PlaybookIngestForm()})

    def post(self, request):
        form = PlaybookIngestForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)

        sample_key = (form.cleaned_data.get("sample_key") or "").strip()
        upload = form.cleaned_data.get("upload")

        if sample_key:
            imp = PlaybookImport.objects.create(
                filename=sample_key,
                source=PlaybookImport.Source.SAMPLE,
                sample_key=sample_key,
            )
        else:
            imp = PlaybookImport(
                filename=upload.name,
                source=PlaybookImport.Source.UPLOAD,
            )
            imp.file = upload
            imp.save()

        start_import_async(imp)
        return redirect("review:playbook_import_processing", pk=imp.pk)


class PlaybookStarterView(View):
    """E2 - draft a starter playbook from 3–5 past contracts."""

    template_name = "review/playbook_starter.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PlaybookStarterForm()})

    def post(self, request):
        upload_list = list(request.FILES.getlist("uploads"))
        form = PlaybookStarterForm(
            request.POST, request.FILES, upload_list=upload_list
        )
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)

        liked = bool(form.cleaned_data.get("liked"))
        samples = list(form.cleaned_data.get("sample_keys") or [])
        uploads = list(form.cleaned_data.get("_upload_list") or [])

        imp = PlaybookImport.objects.create(
            filename=f"Starter from {len(samples) + len(uploads)} past contracts",
            source=PlaybookImport.Source.STARTER,
            starter_manifest=[],
        )
        manifest: list[dict] = []
        for key in samples:
            manifest.append(
                {"kind": "sample", "key": key, "name": key, "liked": liked}
            )

        media_root = Path(settings.MEDIA_ROOT)
        dest_dir = media_root / "playbooks" / "starter" / str(imp.pk)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for uploaded in uploads:
            safe_name = Path(uploaded.name).name
            dest = dest_dir / f"{uuid_lib.uuid4().hex[:8]}_{safe_name}"
            with dest.open("wb") as out:
                for chunk in uploaded.chunks():
                    out.write(chunk)
            rel = str(dest.relative_to(media_root)).replace("\\", "/")
            manifest.append(
                {
                    "kind": "upload",
                    "rel": rel,
                    "name": safe_name,
                    "liked": liked,
                }
            )

        imp.starter_manifest = manifest
        imp.save(update_fields=["starter_manifest"])
        start_import_async(imp)
        return redirect("review:playbook_import_processing", pk=imp.pk)


class PlaybookImportProcessingView(View):
    template_name = "review/playbook_import_processing.html"

    def get(self, request, pk):
        imp = get_object_or_404(PlaybookImport, pk=pk)
        if imp.status == PlaybookImport.Status.PROPOSED:
            return redirect("review:playbook_import_detail", pk=imp.pk)
        if imp.status == PlaybookImport.Status.HALTED:
            return redirect("review:playbook_import_detail", pk=imp.pk)
        if imp.status == PlaybookImport.Status.ACTIVATED:
            return redirect("review:playbook_active")
        if imp.status == PlaybookImport.Status.FAILED:
            return render(
                request,
                self.template_name,
                {
                    "import_obj": imp,
                    "steps": PLAYBOOK_PROGRESS_STEPS,
                    "current_step": imp.progress_step or "done",
                },
            )
        return render(
            request,
            self.template_name,
            {
                "import_obj": imp,
                "steps": PLAYBOOK_PROGRESS_STEPS,
                "current_step": imp.progress_step or "queued",
            },
        )


class PlaybookImportStatusJsonView(View):
    def get(self, request, pk):
        imp = get_object_or_404(PlaybookImport, pk=pk)
        return JsonResponse(
            {
                "id": str(imp.id),
                "status": imp.status,
                "progress_step": imp.progress_step,
                "progress_label": imp.progress_label,
                "error_message": imp.error_message,
                "rule_count": len((imp.proposed_json or {}).get("rules") or []),
            }
        )


class PlaybookImportDetailView(View):
    template_name = "review/playbook_import_detail.html"

    def get(self, request, pk):
        imp = get_object_or_404(PlaybookImport, pk=pk)
        if imp.status in (
            PlaybookImport.Status.UPLOADED,
            PlaybookImport.Status.PROCESSING,
        ):
            return redirect("review:playbook_import_processing", pk=imp.pk)
        if imp.status == PlaybookImport.Status.HALTED:
            return render(
                request,
                "review/playbook_security_halt.html",
                {"import_obj": imp},
            )
        if imp.status == PlaybookImport.Status.FAILED:
            messages.error(
                request,
                f"Could not propose rules: {imp.error_message or 'unknown error'}",
            )
            return redirect("review:playbook_import")
        form = PlaybookActivateForm.from_proposed(imp.proposed_json or {})
        meta = (imp.proposed_json or {}).get("_meta") or {}
        audit = audit_playbook(imp.proposed_json or {})
        return render(
            request,
            self.template_name,
            {
                "import_obj": imp,
                "form": form,
                "rule_rows": _rule_rows(form),
                "is_proposed_not_active": True,
                "is_starter": imp.source == PlaybookImport.Source.STARTER
                or meta.get("origin") == "starter",
                "audit": audit,
            },
        )

    def post(self, request, pk):
        imp = get_object_or_404(PlaybookImport, pk=pk)
        if imp.status == PlaybookImport.Status.HALTED:
            messages.error(request, "Cannot activate a security-halted playbook.")
            return redirect("review:playbook_import_detail", pk=imp.pk)
        if imp.status == PlaybookImport.Status.FAILED:
            messages.error(request, "This import failed; upload again.")
            return redirect("review:playbook_import")
        if imp.status in (
            PlaybookImport.Status.UPLOADED,
            PlaybookImport.Status.PROCESSING,
        ):
            return redirect("review:playbook_import_processing", pk=imp.pk)

        proposed = imp.proposed_json or {}
        rule_count = len(proposed.get("rules") or [])
        form = PlaybookActivateForm(request.POST, rule_count=rule_count)
        if not form.is_valid():
            meta = (imp.proposed_json or {}).get("_meta") or {}
            return render(
                request,
                self.template_name,
                {
                    "import_obj": imp,
                    "form": form,
                    "rule_rows": _rule_rows(form),
                    "is_proposed_not_active": True,
                    "is_starter": imp.source == PlaybookImport.Source.STARTER
                    or meta.get("origin") == "starter",
                },
                status=400,
            )

        doc = document_from_form(
            name=form.cleaned_data["name"],
            preferred_governing_law=form.cleaned_data["preferred_governing_law"],
            rules=form.cleaned_rules(),
        )
        audit = audit_playbook(doc.model_dump())
        if not audit["ok"]:
            messages.error(
                request,
                "Playbook failed audit: " + "; ".join(audit["errors"][:5]),
            )
            meta = (imp.proposed_json or {}).get("_meta") or {}
            return render(
                request,
                self.template_name,
                {
                    "import_obj": imp,
                    "form": form,
                    "rule_rows": _rule_rows(form),
                    "is_proposed_not_active": True,
                    "is_starter": imp.source == PlaybookImport.Source.STARTER
                    or meta.get("origin") == "starter",
                    "audit": audit,
                },
                status=400,
            )
        activate_playbook(imp, doc)
        messages.success(
            request,
            "Playbook activated. Previous golden file versioned under media/playbooks/versions/.",
        )
        return redirect("review:playbook_active")


class RewriteView(View):
    template_name = "review/rewrite.html"

    def get(self, request, contract_id, finding_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        finding = get_object_or_404(
            Finding.objects.select_related("draft", "review_run"),
            pk=finding_id,
            review_run__contract=contract,
        )
        draft = getattr(finding, "draft", None)
        copilot = None
        reject_warn = ""
        if draft:
            from apps.review.services.playbook_import import load_active_playbook
            from apps.review.services.rewrite_copilot import build_rewrite_copilot

            playbook = load_active_playbook()
            rule = next(
                (
                    r
                    for r in (playbook.get("rules") or [])
                    if r.get("id") == finding.playbook_rule_id
                ),
                {},
            )
            if draft.copilot_json and draft.copilot_json.get("options"):
                copilot = draft.copilot_json
            else:
                result = build_rewrite_copilot(
                    playbook_rule=rule,
                    finding={
                        "playbook_rule_id": finding.playbook_rule_id,
                        "clause_excerpt": finding.clause_excerpt,
                        "deviation_reason": finding.deviation_reason,
                        "clause_name": finding.clause_name,
                    },
                    draft_text=draft.draft_text or "",
                )
                copilot = result.model_dump()
                draft.copilot_json = copilot
                draft.save(update_fields=["copilot_json"])
            if (draft.provenance or {}).get("warn_reject_nearby"):
                reject_warn = (draft.provenance or {}).get("reject_note") or (
                    "A nearby Reject exists for similar language - Accept carefully."
                )
        initial = {
            "final_text": (draft.draft_text if draft else "")
            or finding.suggested_counter
            or "",
        }
        react_trace = []
        if draft and isinstance(draft.provenance, dict):
            react_trace = draft.provenance.get("react_trace") or []
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "finding": finding,
                "draft": draft,
                "copilot": copilot,
                "reject_warn": reject_warn,
                "react_trace": react_trace,
                "form": DecisionForm(initial=initial),
            },
        )

    def post(self, request, contract_id, finding_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        finding = get_object_or_404(
            Finding.objects.select_related("draft"),
            pk=finding_id,
            review_run__contract=contract,
        )
        form = DecisionForm(request.POST)
        if not form.is_valid():
            draft = getattr(finding, "draft", None)
            return render(
                request,
                self.template_name,
                {
                    "contract": contract,
                    "finding": finding,
                    "draft": draft,
                    "form": form,
                },
                status=400,
            )
        record_decision(
            finding=finding,
            contract=contract,
            action=form.cleaned_data["action"],
            final_text=form.cleaned_data.get("final_text") or "",
            reasoning=form.cleaned_data.get("reasoning") or "",
        )
        messages.success(request, f"Recorded {form.cleaned_data['action']}.")
        return redirect("contracts:review", pk=contract.pk)


class DecisionBriefJsonView(View):
    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        run = (
            contract.review_runs.prefetch_related("findings__draft", "findings__decisions")
            .first()
        )
        findings_payload = []
        if run:
            for f in run.findings.all():
                last = f.decisions.first()
                findings_payload.append(
                    {
                        "playbook_rule_id": f.playbook_rule_id,
                        "clause_name": f.clause_name or f.playbook_rule_id,
                        "plain_english": f.plain_english or "",
                        "severity": f.severity,
                        "status": f.status,
                        "deviation_reason": f.deviation_reason,
                        "decision": last.action if last else "",
                    }
                )
        from apps.review.services.decision_brief import build_decision_brief

        brief = build_decision_brief(
            contract_filename=contract.filename,
            playbook_name=(run.playbook_name if run else ""),
            findings=findings_payload,
        )
        return JsonResponse(
            {"subject": brief.subject, "body_markdown": brief.body_markdown}
        )


class FindingAskView(View):
    def post(self, request, contract_id, finding_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        finding = get_object_or_404(
            Finding,
            pk=finding_id,
            review_run__contract=contract,
        )
        question = (request.POST.get("question") or "").strip()
        if not question:
            return JsonResponse({"error": "question required"}, status=400)
        playbook = load_active_playbook()
        rule = next(
            (
                r
                for r in (playbook.get("rules") or [])
                if r.get("id") == finding.playbook_rule_id
            ),
            {},
        )
        from apps.review.services.scoped_ask import ask_about_finding

        ans = ask_about_finding(
            question=question,
            playbook_rule=rule,
            finding={
                "playbook_rule_id": finding.playbook_rule_id,
                "clause_excerpt": finding.clause_excerpt,
                "deviation_reason": finding.deviation_reason,
            },
        )
        return JsonResponse(ans.model_dump())


class GapSuggestView(View):
    def get(self, request):
        from apps.decisions.models import Decision
        from apps.review.services.gap_suggest import suggest_gaps_from_decisions

        playbook = load_active_playbook()
        existing = [str(r.get("id")) for r in (playbook.get("rules") or []) if r.get("id")]
        qs = Decision.objects.filter(action__in=["reject", "edit"]).order_by(
            "-created_at"
        )[:40]
        decisions = [
            {
                "action": d.action,
                "rule_id": d.finding.playbook_rule_id,
                "final_text": (d.final_text or "")[:300],
                "reasoning": (d.reasoning or "")[:200],
            }
            for d in qs.select_related("finding")
        ]
        suggestion = suggest_gaps_from_decisions(
            decisions=decisions, existing_rule_ids=existing
        )
        return render(
            request,
            "review/gap_suggest.html",
            {
                "suggestion": suggestion,
                "rules": [r.model_dump() for r in suggestion.rules],
            },
        )


class MissedClauseCreateView(View):
    """POST from Review - flag a missed clause and propose a rule."""

    def post(self, request, contract_id):
        from apps.decisions.models import AuditEvent
        from apps.decisions.services.lifecycle import log_audit
        from apps.review.models import MissedClause
        from apps.review.services.missed_clause import propose_rule_from_missed

        contract = get_object_or_404(Contract, pk=contract_id)
        excerpt = (request.POST.get("excerpt") or "").strip()
        note = (request.POST.get("note") or "").strip()
        if len(excerpt) < 20:
            messages.error(request, "Paste at least ~20 characters of the missed clause.")
            return redirect("contracts:review", pk=contract.pk)
        rule = propose_rule_from_missed(excerpt=excerpt, note=note)
        mc = MissedClause.objects.create(
            contract=contract,
            excerpt=excerpt,
            note=note,
            proposed_rule=rule,
            status=MissedClause.Status.PROPOSED,
        )
        log_audit(
            kind=AuditEvent.Kind.MISSED_CLAUSE,
            summary=f"Missed clause proposed · {rule.get('id')}",
            payload={"missed_clause_id": str(mc.id), "rule_id": rule.get("id")},
            contract=contract,
        )
        messages.info(request, "Proposed a new playbook rule - review before Activate.")
        return redirect("review:missed_clause_detail", pk=mc.pk)


class MissedClauseDetailView(View):
    template_name = "review/missed_clause_detail.html"

    def get(self, request, pk):
        from apps.review.models import MissedClause
        from apps.review.services.playbook_audit import audit_playbook

        mc = get_object_or_404(MissedClause, pk=pk)
        trial = load_active_playbook()
        if trial.get("empty"):
            trial = {"name": "Company playbook", "rules": []}
        rules = list(trial.get("rules") or []) + [mc.proposed_rule]
        audit = audit_playbook({**trial, "rules": rules, "name": trial.get("name") or "X"})
        return render(
            request,
            self.template_name,
            {"missed": mc, "rule": mc.proposed_rule, "audit": audit},
        )

    def post(self, request, pk):
        from apps.decisions.models import AuditEvent
        from apps.decisions.services.lifecycle import log_audit
        from apps.review.models import MissedClause
        from apps.review.services.activate_missed import activate_missed_rule

        mc = get_object_or_404(MissedClause, pk=pk)
        action = (request.POST.get("action") or "").strip()
        if action == "dismiss":
            mc.status = MissedClause.Status.DISMISSED
            mc.save(update_fields=["status"])
            messages.info(request, "Missed-clause proposal dismissed.")
            return redirect("contracts:review", pk=mc.contract_id)
        try:
            activate_missed_rule(mc.proposed_rule)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("review:missed_clause_detail", pk=mc.pk)
        mc.status = MissedClause.Status.ACTIVATED
        mc.save(update_fields=["status"])
        log_audit(
            kind=AuditEvent.Kind.ACTIVATE,
            summary=f"Activated missed-clause rule · {mc.proposed_rule.get('id')}",
            payload={"missed_clause_id": str(mc.id)},
            contract=mc.contract,
        )
        messages.success(request, "Rule activated into the company playbook.")
        return redirect("review:playbook_active")
