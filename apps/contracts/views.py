from __future__ import annotations

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.contracts.forms import ContractIngestForm
from apps.contracts.models import Contract
from apps.contracts.services.analyze import start_analyze_async
from apps.review.models import ReviewRun


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"

PROGRESS_STEPS = [
    ("queued", "Queued"),
    ("reading", "Reading document"),
    ("security", "Security check"),
    ("playbook", "Comparing to playbook"),
    ("memory", "Looking up past decisions"),
    ("draft", "Drafting counters"),
    ("done", "Done"),
]


class UploadView(View):
    template_name = "contracts/upload.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ContractIngestForm()})

    def post(self, request):
        form = ContractIngestForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)

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
            messages.error(request, "Security halt — this file looks hostile.")
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
    """Legacy extract preview — redirects to review when ready."""

    template_name = "contracts/detail.html"

    def get(self, request, pk):
        contract = get_object_or_404(Contract, pk=pk)
        if contract.status == Contract.Status.HALTED:
            return redirect("security:alert", pk=contract.pk)
        if contract.status == Contract.Status.READY:
            return redirect("contracts:review", pk=contract.pk)
        if contract.status == Contract.Status.PROCESSING:
            return redirect("contracts:processing", pk=contract.pk)
        preview = contract.extracted_text[:12000]
        truncated = len(contract.extracted_text) > len(preview)
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "preview": preview,
                "truncated": truncated,
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
        preview = contract.extracted_text[:14000]
        highlight = []
        for f in findings:
            highlight.append(
                {
                    "id": str(f.id),
                    "severity": (f.severity or "medium").lower(),
                    "excerpt": f.clause_excerpt or "",
                    "start": int(f.start_offset or 0),
                    "end": int(f.end_offset or 0),
                    "clause_name": f.clause_name or f.playbook_rule_id,
                }
            )
        score = int(run.risk_score) if run else 0
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
                "playbook_empty": bool(run and run.playbook_empty),
                "preview": preview,
                "truncated": len(contract.extracted_text) > 14000,
                "risk_level": _risk_level(score),
                "highlight_data": highlight,
                "gauge_offset": gauge_offset,
            },
        )
