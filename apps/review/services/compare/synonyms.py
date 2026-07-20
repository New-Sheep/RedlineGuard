"""Small legal synonym expansion for semantic query text + token overlap."""

from __future__ import annotations

import re

# Bidirectional-ish expansions applied when building queries / overlap sets.
_SYNONYM_GROUPS: list[set[str]] = [
    {"assign", "transfer", "convey", "cede"},
    {"ownership", "title", "interest"},
    {"perpetual", "indefinite", "in perpetuity", "forever"},
    {"california", "calif", "ca"},
    {"confidentiality", "confidential", "non-disclosure", "nda"},
    {"majority", "controlling", "control"},
    {"intellectual", "ip", "copyright"},
]


def expand_query_text(text: str) -> str:
    """Append synonym tokens found in text to improve embedding/hash recall."""
    lower = (text or "").lower()
    extra: list[str] = []
    for group in _SYNONYM_GROUPS:
        if any(term in lower for term in group):
            extra.extend(sorted(group))
    if not extra:
        return text or ""
    return f"{text} " + " ".join(extra)


def token_set(text: str) -> set[str]:
    toks = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    # Light plural stem so transfer↔transfers / ownership↔ownerships overlap
    extra: set[str] = set()
    for t in list(toks):
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            extra.add(t[:-1])
        if len(t) > 5 and t.endswith("es"):
            extra.add(t[:-2])
    return toks | extra


def expand_tokens(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for group in _SYNONYM_GROUPS:
        flat = set()
        for term in group:
            flat |= token_set(term)
        if out & flat:
            out |= flat
    return out


def has_keyword_overlap(segment: str, rule: dict) -> bool:
    """True if segment shares meaningful tokens with rule preferred / match_any."""
    rule_blob = " ".join(
        [
            str(rule.get("preferred") or ""),
            str(rule.get("hard_ceiling") or ""),
            " ".join(str(p) for p in (rule.get("match_any") or [])),
            str(rule.get("clause_type") or ""),
        ]
    )
    rule_toks = expand_tokens(token_set(rule_blob))
    # Drop ultra-common noise
    noise = {"the", "a", "an", "of", "or", "and", "to", "in", "for", "by", "with", "all", "any"}
    rule_toks -= noise
    seg_toks = expand_tokens(token_set(segment)) - noise
    if not rule_toks or not seg_toks:
        return False
    return bool(rule_toks & seg_toks)
