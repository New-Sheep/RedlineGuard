"""Contract security gate — heuristic cues + LLM adjudicator."""

from __future__ import annotations

from apps.contracts.models import Contract
from apps.security.models import SecurityEvent
from apps.security.services.adjudicate import adjudicate_security, should_auto_clear
from scratch.poc02_security.security import detect_injection, sanitize


def run_security_gate(
    contract: Contract,
    *,
    skip_detection: bool = False,
) -> SecurityEvent:
    """Sanitize + detect injection. Optionally adjudicate and auto-clear ambiguous FPs.

    skip_detection: used after an explicit human Override & continue — do not re-halt.
    """
    text = contract.extracted_text or ""
    cleaned = sanitize(text)
    if cleaned != text:
        contract.extracted_text = cleaned
        contract.char_count = len(cleaned)
        contract.save(update_fields=["extracted_text", "char_count"])

    if skip_detection:
        event = SecurityEvent.objects.create(
            contract=contract,
            halt=False,
            matches=[],
            summary="Security check skipped after human override.",
            adjudication={"overridden": True, "verdict": "proceed", "cue_class": "hard"},
        )
        return event

    detection = detect_injection(cleaned, include_llm_export_chrome=True)
    halt = bool(detection.get("halt"))
    matches = list(detection.get("matches") or [])
    summary = detection.get("summary") or ""
    adjudication: dict = {}

    if halt:
        from apps.core.agent_flags import fake_llm, llm_security_adjudicate

        # Always adjudicate under Fake (offline demos/tests); under real LLM when flag on.
        if fake_llm() or llm_security_adjudicate():
            adj = adjudicate_security(
                text=cleaned,
                matches=matches,
                filename=contract.filename or "",
            )
            adjudication = adj.as_dict()
            if should_auto_clear(adj):
                halt = False
                summary = (
                    "Heuristic cue cleared by AI adjudicator "
                    "(ambiguous / likely false positive). "
                    + (adj.plain_english or "")
                )[:500]
            else:
                summary = (adj.plain_english or summary)[:500]

    event = SecurityEvent.objects.create(
        contract=contract,
        halt=halt,
        matches=matches,
        summary=summary,
        adjudication=adjudication,
    )
    return event
