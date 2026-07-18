"""Contract security gate — wraps scratch poc02 (full chrome-on path)."""

from __future__ import annotations

from apps.contracts.models import Contract
from apps.security.models import SecurityEvent
from scratch.poc02_security.security import detect_injection, sanitize


def run_security_gate(contract: Contract) -> SecurityEvent:
    """Sanitize + detect injection on contract text. Persist SecurityEvent."""
    text = contract.extracted_text or ""
    cleaned = sanitize(text)
    if cleaned != text:
        contract.extracted_text = cleaned
        contract.char_count = len(cleaned)
        contract.save(update_fields=["extracted_text", "char_count"])

    detection = detect_injection(cleaned, include_llm_export_chrome=True)
    event = SecurityEvent.objects.create(
        contract=contract,
        halt=bool(detection.get("halt")),
        matches=list(detection.get("matches") or []),
        summary=detection.get("summary") or "",
    )
    return event
