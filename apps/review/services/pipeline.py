"""Review pipeline: security → triage → playbook → memory retrieve → draft (+ LLM)."""

from __future__ import annotations

from apps.contracts.models import Contract
from apps.review.models import Draft, Finding, ReviewRun
from apps.review.services.drafting import draft_for_finding
from apps.review.services.overrides import merge_playbook_with_overrides
from apps.review.services.playbook_import import load_active_playbook
from apps.security.services.gate import run_security_gate
from scratch.poc03_triage.triage import triage_text
from scratch.poc04_playbook.playbook import compare


def run_pipeline(contract: Contract) -> Contract:
    """Analyze an extracted contract. Updates status, progress, and related rows."""
    if contract.status == Contract.Status.FAILED:
        return contract
    if not (contract.extracted_text or "").strip():
        contract.status = Contract.Status.FAILED
        contract.error_message = "No extracted text to analyze"
        contract.progress_step = Contract.ProgressStep.DONE
        contract.progress_label = "Failed"
        contract.save(
            update_fields=[
                "status",
                "error_message",
                "progress_step",
                "progress_label",
            ]
        )
        return contract

    if contract.status != Contract.Status.PROCESSING:
        contract.status = Contract.Status.PROCESSING
        contract.error_message = ""
        contract.save(update_fields=["status", "error_message"])

    try:
        contract.set_progress(
            Contract.ProgressStep.SECURITY, "Security check"
        )
        event = run_security_gate(contract)
        if event.halt:
            contract.status = Contract.Status.HALTED
            contract.error_message = event.summary or "Security halt"
            contract.progress_step = Contract.ProgressStep.DONE
            contract.progress_label = "Security halt"
            contract.save(
                update_fields=[
                    "status",
                    "error_message",
                    "progress_step",
                    "progress_label",
                ]
            )
            return contract

        contract.set_progress(
            Contract.ProgressStep.PLAYBOOK, "Comparing to playbook"
        )
        triage = triage_text(
            contract.extracted_text,
            source_name=contract.filename,
            quality=contract.quality or "ok",
        )
        contract.triage_kind = triage.get("kind") or ""
        contract.triage_stakes = triage.get("stakes") or ""
        contract.save(update_fields=["triage_kind", "triage_stakes"])

        playbook = merge_playbook_with_overrides(load_active_playbook())
        empty = bool(playbook.get("empty"))
        report = compare(contract.extracted_text, playbook=playbook)

        run = ReviewRun.objects.create(
            contract=contract,
            risk_score=int(report.overall_risk_score),
            playbook_name=playbook.get("name") or "",
            playbook_empty=empty,
            triage_kind=contract.triage_kind,
            triage_stakes=contract.triage_stakes,
        )

        contract.set_progress(
            Contract.ProgressStep.MEMORY, "Looking up past decisions"
        )
        # Memory searches happen per finding inside draft loop; label is intentional UX step.

        contract.set_progress(
            Contract.ProgressStep.DRAFT, "Drafting counters"
        )
        rule_by_id = {
            r.get("id"): r for r in (playbook.get("rules") or []) if r.get("id")
        }
        for item in report.reviews:
            finding = Finding.objects.create(
                review_run=run,
                playbook_rule_id=item.playbook_rule_id,
                clause_name=item.clause_name,
                status=item.status,
                severity=item.severity or "medium",
                deviation_reason=item.deviation_reason or "",
                suggested_counter=item.suggested_counter_proposal or "",
                clause_excerpt=getattr(item, "clause_excerpt", "") or "",
                start_offset=int(getattr(item, "start_offset", 0) or 0),
                end_offset=int(getattr(item, "end_offset", 0) or 0),
            )
            result = draft_for_finding(
                finding_payload={
                    "playbook_rule_id": item.playbook_rule_id,
                    "status": item.status,
                    "suggested_counter_proposal": item.suggested_counter_proposal,
                    "deviation_reason": item.deviation_reason,
                    "clause_name": item.clause_name,
                    "clause_excerpt": finding.clause_excerpt,
                },
                playbook_rule=rule_by_id.get(item.playbook_rule_id) or {},
                contract_text=contract.extracted_text,
                playbook_empty=empty,
            )
            Draft.objects.create(
                finding=finding,
                draft_text=result.draft_text or "",
                draft_source=result.draft_source,
                precedent_ids=list(result.precedent_ids or []),
                rationale=result.rationale or "",
                provenance=dict(result.provenance or {}),
            )

        contract.status = Contract.Status.READY
        contract.error_message = ""
        contract.progress_step = Contract.ProgressStep.DONE
        contract.progress_label = "Review ready"
        contract.save(
            update_fields=[
                "status",
                "error_message",
                "progress_step",
                "progress_label",
            ]
        )
    except Exception as exc:  # noqa: BLE001
        contract.status = Contract.Status.FAILED
        contract.error_message = str(exc)
        contract.progress_step = Contract.ProgressStep.DONE
        contract.progress_label = "Failed"
        contract.save(
            update_fields=[
                "status",
                "error_message",
                "progress_step",
                "progress_label",
            ]
        )
    return contract
