"""Plain-English one-liner for findings + playbook coverage report."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from apps.core.agent_flags import fake_llm, llm_plain_english
from apps.core.llm_complete import complete_json

logger = logging.getLogger(__name__)

PLAIN_SYSTEM = (
    "Explain in one plain English sentence why this clause is a playbook risk for "
    "in-house counsel. Return ONLY JSON: {\"plain_english\": str}. "
    "Cite the preferred/ceiling idea without inventing new policy."
)


def plain_english_for_finding(
    *,
    playbook_rule: dict[str, Any],
    finding: dict[str, Any],
) -> str:
    preferred = (playbook_rule.get("preferred") or "").strip()
    ceiling = (playbook_rule.get("hard_ceiling") or "").strip()
    fallback = (
        f"This language conflicts with our preferred position "
        f"({preferred or 'see playbook'})"
        f"{f'; ceiling: {ceiling}' if ceiling else ''}."
    )
    if fake_llm() or not llm_plain_english():
        return fallback
    try:
        data = complete_json(
            system=PLAIN_SYSTEM,
            user=json.dumps(
                {
                    "preferred": preferred,
                    "hard_ceiling": ceiling,
                    "deviation_reason": finding.get("deviation_reason"),
                    "clause_excerpt": (finding.get("clause_excerpt") or "")[:1200],
                }
            ),
        )
        text = (data.get("plain_english") or "").strip()
        return text or fallback
    except Exception as exc:  # noqa: BLE001
        logger.warning("plain_english failed: %s", exc)
        return fallback


def _preferred_cues(preferred: str) -> list[str]:
    """Token-ish cues from preferred text for soft 'aligned' detection."""
    p = (preferred or "").strip().lower()
    if not p:
        return []
    cues = [p]
    # Common jurisdiction / IP phrases
    for phrase in (
        "england and wales",
        "english law",
        "united kingdom",
        "background ip",
        "pre-existing",
        "confidentiality",
        "three (3) years",
        "3–5 years",
        "3-5 years",
        "majority ownership",
        "50%",
    ):
        if phrase in p:
            cues.append(phrase)
    # Significant words (>4 letters)
    words = re.findall(r"[a-z]{5,}", p)
    cues.extend(words[:6])
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for c in cues:
        if c not in seen and len(c) >= 4:
            seen.add(c)
            out.append(c)
    return out[:10]


def coverage_gaps(
    *,
    playbook: dict[str, Any],
    matched_rule_ids: set[str],
    contract_text: str = "",
) -> list[dict[str, str]]:
    """Rules with no finding - classify aligned vs no_signal for clean-pass UX."""
    lower = (contract_text or "").lower()
    gaps: list[dict[str, str]] = []
    for r in playbook.get("rules") or []:
        rid = str(r.get("id") or "")
        if not rid or rid in matched_rule_ids:
            continue
        preferred = str(r.get("preferred") or "")
        needles = [str(n) for n in (r.get("match_any") or []) if n]
        risk_hit = any(
            len(n) >= 4 and n.lower() in lower for n in needles
        )
        cues = _preferred_cues(preferred)
        pref_hit = any(c in lower for c in cues) if cues and lower else False

        if pref_hit and not risk_hit:
            status = "aligned"
            note = "Looks consistent with your preferred position."
        elif risk_hit:
            # Needle present but L0 missed (regex edge) - still surface
            status = "signal_unchecked"
            note = "Risky wording may be present; double-check this rule."
        else:
            status = "no_signal"
            note = "This topic did not appear in the document."

        gaps.append(
            {
                "playbook_rule_id": rid,
                "clause_type": str(r.get("clause_type") or rid),
                "preferred": preferred[:200],
                "status": status,
                "note": note,
            }
        )
    return gaps[:12]


# Back-compat alias used by older call sites
def coverage_report(
    *,
    playbook: dict[str, Any],
    matched_rule_ids: set[str],
    contract_text: str = "",
) -> list[dict[str, str]]:
    return coverage_gaps(
        playbook=playbook,
        matched_rule_ids=matched_rule_ids,
        contract_text=contract_text,
    )
