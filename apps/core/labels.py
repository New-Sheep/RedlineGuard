"""Plain-English labels for snake_case / technical ids (lawyer-facing UI)."""

from __future__ import annotations

import re

_SPECIALS = {
    "ip": "IP",
    "nda": "NDA",
    "sla": "SLA",
    "uk": "UK",
    "us": "US",
    "ai": "AI",
}


def humanize_label(value: str, *, empty: str = "Untitled") -> str:
    """governing_law / confidentiality_term_d3f75f → Governing law / Confidentiality term."""
    raw = (value or "").strip()
    if not raw:
        return empty
    parts = [p for p in re.split(r"[_\-\s]+", raw) if p]
    # Drop trailing short hex ids from generated rule names
    if len(parts) >= 2 and re.fullmatch(r"[a-f0-9]{5,10}", parts[-1], re.I):
        parts = parts[:-1]
    if not parts:
        return empty
    out: list[str] = []
    for i, part in enumerate(parts):
        key = part.lower()
        if key in _SPECIALS:
            out.append(_SPECIALS[key])
        elif i == 0:
            out.append(part.capitalize())
        else:
            out.append(part.lower())
    return " ".join(out)
