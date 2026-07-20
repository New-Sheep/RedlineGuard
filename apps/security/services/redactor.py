"""PII redaction before LLM payloads (PRD F21-lite / vision)."""

from __future__ import annotations

import re
from typing import Any

# Order matters — longer / more specific first where needed
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "PHONE",
        re.compile(
            r"(?<!\w)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}(?!\w)"
        ),
    ),
    (
        "IBAN",
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
    ),
    (
        "SSN_ISH",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
]


def redact_pii(text: str) -> tuple[str, dict[str, str]]:
    """Replace PII with placeholders. Returns (redacted, mapping placeholder→original)."""
    if not text:
        return "", {}
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}
    out = text

    def _sub(kind: str, match: re.Match[str]) -> str:
        original = match.group(0)
        # Avoid re-redacting placeholders
        if original.startswith("[REDACTED_"):
            return original
        n = counters.get(kind, 0) + 1
        counters[kind] = n
        token = f"[REDACTED_{kind}_{n}]"
        mapping[token] = original
        return token

    for kind, pat in _PATTERNS:
        out = pat.sub(lambda m, k=kind: _sub(k, m), out)
    return out, mapping


def redact_for_llm(system: str, user: str) -> tuple[str, str, dict[str, Any]]:
    """Redact system+user; return redacted strings + meta for audit/UI."""
    sys_r, map_s = redact_pii(system or "")
    usr_r, map_u = redact_pii(user or "")
    mapping = {**map_s, **map_u}
    meta = {
        "pii_redacted": bool(mapping),
        "pii_count": len(mapping),
        "pii_kinds": sorted({k.split("_")[1] for k in mapping if k.startswith("[REDACTED_")}),
    }
    return sys_r, usr_r, meta
