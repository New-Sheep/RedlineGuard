"""Review pipeline: security → triage → playbook → memory retrieve → draft (+ LLM)."""

from __future__ import annotations

from apps.contracts.models import Contract
from apps.core.llm_complete import provider_label
from apps.review.models import Draft, Finding, ReviewRun
from apps.review.services.compare import compare_layered
from apps.review.services.context_agent import build_agent_assist
from apps.review.services.drafting import draft_for_finding
from apps.review.services.overrides import merge_playbook_with_overrides
from apps.review.services.plain_english import coverage_gaps, plain_english_for_finding
from apps.review.services.playbook_import import load_active_playbook
from apps.security.services.gate import run_security_gate
from scratch.poc01_extract.extract import IMAGE_ONLY_HINT
from scratch.poc03_triage.triage import triage_text


def run_pipeline(
    contract: Contract,
    *,
    skip_security: bool = False,
) -> Contract:
    """Analyze an extracted contract. Updates status, progress, and related rows.

    skip_security: after human Override & continue on a hard halt — do not re-detect.
    """
    if contract.status == Contract.Status.FAILED:
        return contract
    if not (contract.extracted_text or "").strip():
        contract.status = Contract.Status.FAILED
        contract.error_message = IMAGE_ONLY_HINT
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
        event = run_security_gate(contract, skip_detection=skip_security)
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
        report = compare_layered(contract.extracted_text, playbook=playbook)

        matched_ids = {f.playbook_rule_id for f in report.reviews}
        gaps = (
            []
            if empty
            else coverage_gaps(
                playbook=playbook,
                matched_rule_ids=matched_ids,
                contract_text=contract.extracted_text or "",
            )
        )

        run = ReviewRun.objects.create(
            contract=contract,
            risk_score=int(report.overall_risk_score),
            score_breakdown=dict(report.score_breakdown or {}),
            playbook_name=playbook.get("name") or "",
            playbook_empty=empty,
            coverage_gaps=gaps,
            triage_kind=contract.triage_kind,
            triage_stakes=contract.triage_stakes,
        )

        contract.set_progress(
            Contract.ProgressStep.MEMORY, "Looking up past decisions"
        )

        contract.set_progress(
            Contract.ProgressStep.DRAFT, "Drafting counters"
        )
        rule_by_id = {
            r.get("id"): r for r in (playbook.get("rules") or []) if r.get("id")
        }
        for item in report.reviews:
            sources = list(getattr(item, "sources", None) or ["rule"])
            rule = rule_by_id.get(item.playbook_rule_id) or {}
            finding_payload = {
                "playbook_rule_id": item.playbook_rule_id,
                "status": item.status,
                "suggested_counter_proposal": item.suggested_counter_proposal,
                "deviation_reason": item.deviation_reason,
                "clause_name": item.clause_name,
                "clause_excerpt": getattr(item, "clause_excerpt", "") or "",
            }
            gloss = plain_english_for_finding(
                playbook_rule=rule, finding=finding_payload
            )
            finding = Finding.objects.create(
                review_run=run,
                playbook_rule_id=item.playbook_rule_id,
                clause_name=item.clause_name,
                status=item.status,
                severity=item.severity or "medium",
                deviation_reason=item.deviation_reason or "",
                suggested_counter=item.suggested_counter_proposal or "",
                clause_excerpt=finding_payload["clause_excerpt"],
                start_offset=int(getattr(item, "start_offset", 0) or 0),
                end_offset=int(getattr(item, "end_offset", 0) or 0),
                sources=sources,
                confidence=float(getattr(item, "confidence", 1.0) or 1.0),
                match_distance=getattr(item, "match_distance", None),
                plain_english=gloss,
            )
            result = draft_for_finding(
                finding_payload=finding_payload,
                playbook_rule=rule,
                contract_text=contract.extracted_text,
                playbook_empty=empty,
            )
            prov = dict(result.provenance or {})
            label = prov.get("provider") or (
                "Memory"
                if result.draft_source == "memory_precedent"
                else "Playbook"
                if result.draft_source == "playbook_fallback"
                else provider_label()
            )
            Draft.objects.create(
                finding=finding,
                draft_text=result.draft_text or "",
                draft_source=result.draft_source,
                precedent_ids=list(result.precedent_ids or []),
                rationale=result.rationale or "",
                provenance=prov,
                provider_label=str(label),
                memory_explain=str(prov.get("memory_explain") or ""),
            )

        finding_count = run.findings.count()
        assist = build_agent_assist(
            playbook_empty=empty,
            finding_count=finding_count,
            contract_text=contract.extracted_text or "",
            filename=contract.filename or "",
            playbook_name=playbook.get("name") or "",
            coverage_gaps=gaps,
        )
        if assist:
            run.agent_assist = assist
            run.save(update_fields=["agent_assist"])

        try:
            from apps.core.llm_complete import last_pii_meta

            meta = last_pii_meta()
            if meta.get("pii_redacted"):
                bd = dict(run.score_breakdown or {})
                bd["pii_meta"] = meta
                run.score_breakdown = bd
                run.save(update_fields=["score_breakdown"])
        except Exception:
            pass

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
