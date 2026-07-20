"""L0 — regex / substring playbook needles."""

from __future__ import annotations

import re
from typing import Any

from apps.review.services.compare.models import FindingCandidate


def first_match_span(text: str, rule: dict) -> tuple[int, int, str]:
    """Return (start, end, excerpt) for first match_any hit; empty if none."""
    for pat in rule.get("match_any") or []:
        try:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        except re.error:
            idx = text.lower().find(str(pat).lower())
            if idx < 0:
                continue
            start = max(0, idx - 120)
            end = min(len(text), idx + len(pat) + 120)
            return start, end, text[start:end].strip()
        if m:
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + 120)
            return start, end, text[start:end].strip()
    return 0, 0, ""


def layer_rule(text: str, playbook: dict[str, Any]) -> list[FindingCandidate]:
    out: list[FindingCandidate] = []
    for rule in playbook.get("rules") or []:
        rid = rule.get("id")
        if not rid:
            continue
        start, end, excerpt = first_match_span(text, rule)
        if not excerpt:
            continue
        out.append(
            FindingCandidate(
                playbook_rule_id=str(rid),
                clause_name=str(rule.get("clause_type") or rid),
                severity=str(rule.get("severity") or "medium"),
                clause_excerpt=excerpt[:2000],
                start_offset=start,
                end_offset=end,
                sources=["rule"],
                confidence=1.0,
                match_distance=None,
                fallback_text=rule.get("fallback_text"),
                preferred=str(rule.get("preferred") or ""),
                hard_ceiling=str(rule.get("hard_ceiling") or ""),
            )
        )
    return out
