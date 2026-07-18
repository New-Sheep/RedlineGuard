from __future__ import annotations

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.contracts.models import Contract
from apps.decisions.forms import DecisionForm
from apps.decisions.services.decide import record_decision
from apps.review.forms import PlaybookActivateForm, PlaybookIngestForm
from apps.review.models import Finding, PlaybookImport
from apps.review.services.import_job import start_import_async
from apps.review.services.playbook_import import (
    activate_playbook,
    document_from_form,
    load_active_playbook,
)

PLAYBOOK_PROGRESS_STEPS = [
    ("queued", "Queued"),
    ("reading", "Reading playbook PDF"),
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
        return render(request, self.template_name, {"playbook": playbook})


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
        return render(
            request,
            self.template_name,
            {
                "import_obj": imp,
                "form": form,
                "rule_rows": _rule_rows(form),
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
            return render(
                request,
                self.template_name,
                {
                    "import_obj": imp,
                    "form": form,
                    "rule_rows": _rule_rows(form),
                },
                status=400,
            )

        doc = document_from_form(
            name=form.cleaned_data["name"],
            preferred_governing_law=form.cleaned_data["preferred_governing_law"],
            rules=form.cleaned_rules(),
        )
        activate_playbook(imp, doc)
        messages.success(
            request,
            "Playbook activated. Previous golden file saved as playbook_config.json.bak.",
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
        initial = {
            "final_text": (draft.draft_text if draft else "")
            or finding.suggested_counter
            or "",
        }
        return render(
            request,
            self.template_name,
            {
                "contract": contract,
                "finding": finding,
                "draft": draft,
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
