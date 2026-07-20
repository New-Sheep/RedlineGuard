from __future__ import annotations

from django.core.paginator import Paginator
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.contracts.forms import ContractIngestForm
from apps.contracts.models import Contract
from apps.contracts.services.analyze import start_analyze_async
from apps.review.models import Finding, ReviewRun


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _review_verdict(
    *,
    playbook_empty: bool,
    finding_count: int,
    score: int,
) -> dict:
    """Product verdict for Review header - especially clean-pass (0 flags)."""
    if playbook_empty:
        return {
            "key": "empty_playbook",
            "title": "No active playbook",
            "blurb": "Activate company rules before treating this as a real first-pass.",
            "score_label": "Deviation score",
        }
    if finding_count == 0:
        return {
            "key": "clean_pass",
            "title": "Looks clear",
            "blurb": (
                "Nothing in this contract conflicted with your active playbook. "
                "Still worth a quick human skim."
            ),
            "score_label": "Risk score",
        }
    level = _risk_level(score)
    return {
        "key": "flagged",
        "title": f"{level.title()} risk",
        "blurb": (
            f"{finding_count} issue{'s' if finding_count != 1 else ''} to review against your playbook. "
            "Open each flag, then Accept, Edit, or Reject."
        ),
        "score_label": "Risk score",
    }

PROGRESS_STEPS = [
    ("queued", "Queued"),
    ("reading", "Reading document"),
    ("security", "Security check"),
    ("playbook", "Comparing to playbook"),
    ("memory", "Looking up past decisions"),
    ("draft", "Drafting counters"),
    ("done", "Done"),
]

PAGE_SIZE = 25


class ContractListView(View):
    """Paginated catalogue of all contracts (Sprint 1)."""

    template_name = "contracts/list.html"

    def get(self, request):
        qs = Contract.objects.all().order_by("-created_at")
        status_filter = (request.GET.get("status") or "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page") or 1)
        rows = []
        for c in page_obj.object_list:
            run = (
                ReviewRun.objects.filter(contract=c)
                .order_by("-created_at")
                .first()
            )
            flag_count = 0
            score = None
            playbook_name = ""
            if run:
                score = run.risk_score
                playbook_name = run.playbook_name or ""
                flag_count = Finding.objects.filter(review_run=run).count()
            rows.append(
                {
                    "contract": c,
                    "score": score,
                    "flag_count": flag_count,
                    "playbook_name": playbook_name,
                }
            )
        # Re-bind page_obj iteration to row wrappers
        page_obj.object_list = rows
        q = []
        if status_filter:
            q.append(f"status={status_filter}")
        return render(
            request,
            self.template_name,
            {
                "page_obj": page_obj,
                "status_filter": status_filter,
                "status_choices": Contract.Status.choices,
                "querystring": "&".join(q),
            },
        )


class UploadView(View):
    template_name = "contracts/upload.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ContractIngestForm()})

    def post(self, request):
        form = ContractIngestForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)

        from apps.core.rate_limit import check_analyze_rate

        ok, err = check_analyze_rate(request.session)
        if not ok:
            messages.error(request, err)
            return render(request, self.template_name, {"form": form}, status=429)

        sample_key = (form.cleaned_data.get("sample_key") or "").strip()
        upload = form.cleaned_data.get("upload")

        if sample_key:
            contract = Contract.objects.create(
                filename=sample_key,
                source=Contract.Source.SAMPLE,
                sample_key=sample_key,
                status=Contract.Status.UPLOADED,
            )
        else:
            contract = Contract(
                filename=upload.name,
                source=Contract.Source.UPLOAD,
                status=Contract.Status.UPLOADED,
            )
            contract.file = upload
            contract.save()

        start_analyze_async(contract)
        contract.refresh_from_db()
        if contract.status == Contract.Status.HALTED:
            messages.error(request, "Upload stopped. This file looks unsafe for AI review.")
            return redirect("security:alert", pk=contract.pk)
        if contract.status == Contract.Status.READY:
            messages.success(request, "Review ready.")
            return redirect("contracts:review", pk=contract.pk)
        if contract.status == Contract.Status.FAILED:
            messages.error(request, f"Analysis failed: {contract.error_message}")
            return redirect("contracts:processing", pk=contract.pk)

        messages.info(request, "Analyzing… you’ll see live progress on the next screen.")
        return redirect("contracts:processing", pk=contract.pk)


class ContractDetailView(View):
    """Contract hub: links to review / security / download (Sprint 1)."""

    template_name = "contracts/detail.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        run = (
            ReviewRun.objects.filter(contract=contract)
            .order_by("-created_at")
            .first()
        )
        preview = (contract.extracted_text or "")[:12000]
        truncated = len(contract.extracted_text or "") > len(preview)
        is_pdf = False
        if contract.file and contract.filename:
            is_pdf = contract.filename.lower().endswith(".pdf")
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "run": run,
                "preview": preview,
                "truncated": truncated,
                "is_pdf": is_pdf,
            },
        )


class ProcessingView(View):
    template_name = "contracts/processing.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        if contract.status == Contract.Status.HALTED:
            return redirect("security:alert", pk=contract.pk)
        if contract.status == Contract.Status.READY:
            return redirect("contracts:review", pk=contract.pk)
        if contract.status == Contract.Status.FAILED:
            return render(
                request,
                self.template_name,
                {
                    "contract": contract,
                    "steps": PROGRESS_STEPS,
                    "current_step": contract.progress_step,
                },
            )
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "steps": PROGRESS_STEPS,
                "current_step": contract.progress_step or "queued",
            },
        )


class ContractStatusJsonView(View):
    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        return JsonResponse(
            {
                "id": str(contract.id),
                "status": contract.status,
                "progress_step": contract.progress_step,
                "progress_label": contract.progress_label,
                "error_message": contract.error_message,
            }
        )


class ReviewView(View):
    template_name = "contracts/review.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        if contract.status == Contract.Status.HALTED:
            return redirect("security:alert", pk=contract.pk)
        if contract.status != Contract.Status.READY:
            return redirect("contracts:processing", pk=contract.pk)

        run = (
            ReviewRun.objects.filter(contract=contract)
            .prefetch_related("findings__draft", "findings__decisions")
            .first()
        )
        findings = list(run.findings.all()) if run else []
        # Highlight pane needs offsets into THIS string - keep generous (was 14k).
        _DOC_CAP = 120_000
        full = contract.extracted_text or ""
        preview = full[:_DOC_CAP]
        truncated = len(full) > len(preview)
        highlight = []
        for f in findings:
            start = int(f.start_offset or 0)
            end = int(f.end_offset or 0)
            # If span is past the pane, clamp so JS can still try excerpt fallback
            if start >= len(preview):
                start, end = 0, 0
            elif end > len(preview):
                end = len(preview)
            highlight.append(
                {
                    "id": str(f.id),
                    "severity": (f.severity or "medium").lower(),
                    "excerpt": f.clause_excerpt or "",
                    "start": start,
                    "end": end,
                    "clause_name": f.clause_name or f.playbook_rule_id,
                }
            )
        score = int(run.risk_score) if run else 0
        breakdown = dict(run.score_breakdown or {}) if run else {}
        playbook_empty = bool(run and run.playbook_empty)
        verdict = _review_verdict(
            playbook_empty=playbook_empty,
            finding_count=len(findings),
            score=score,
        )
        coverage = list(run.coverage_gaps or []) if run else []
        # Fresh classify when rows lack status (pre-clean-pass runs) or always refresh
        if not playbook_empty and full.strip():
            try:
                from apps.review.services.overrides import merge_playbook_with_overrides
                from apps.review.services.plain_english import coverage_gaps
                from apps.review.services.playbook_import import load_active_playbook

                pb = merge_playbook_with_overrides(load_active_playbook())
                matched = {f.playbook_rule_id for f in findings}
                coverage = coverage_gaps(
                    playbook=pb,
                    matched_rule_ids=matched,
                    contract_text=full,
                )
            except Exception:
                pass
        coverage_aligned = [g for g in coverage if g.get("status") == "aligned"]
        coverage_other = [g for g in coverage if g.get("status") != "aligned"]
        # Circumference of gauge circle r=46 ≈ 289
        gauge_c = 289.0
        gauge_offset = round(gauge_c * (1 - min(100, max(0, score)) / 100.0), 1)
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "run": run,
                "findings": findings,
                "playbook_empty": playbook_empty,
                "preview": preview,
                "truncated": truncated,
                "risk_level": _risk_level(score),
                "verdict": verdict,
                "clean_pass": verdict["key"] == "clean_pass",
                "highlight_data": highlight,
                "gauge_offset": gauge_offset,
                "score_breakdown": breakdown,
                "coverage_gaps": coverage,
                "coverage_aligned": coverage_aligned,
                "coverage_other": coverage_other,
                "char_count": len(full),
                "agent_assist": dict(run.agent_assist or {}) if run else {},
                "is_pdf": bool(
                    contract.file
                    and (contract.filename or "").lower().endswith(".pdf")
                ),
                "pdf_url": contract.file.url if contract.file else "",
            },
        )
