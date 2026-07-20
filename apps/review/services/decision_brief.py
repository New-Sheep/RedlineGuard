"""F4 - Decision brief / cover note for counsel."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel

from apps.core.agent_flags import fake_llm, llm_decision_brief
from apps.core.llm_complete import complete_json
from apps.review.services.severity import sort_by_severity

logger = logging.getLogger(__name__)


class DecisionBrief(BaseModel):
    subject: str = ""
    body_markdown: str = ""


BRIEF_SYSTEM = (
    "You draft a short internal legal issues brief for in-house counsel. "
    "Return ONLY JSON: {\"subject\": str, \"body_markdown\": str}. "
    "Group findings High, then Medium, then Low. Use plain English titles "
    "(clause names), not bare rule ids. Short bullets a lawyer can skim. "
    "End with 'Not legal advice.'"
)

_STATUS_LABEL = {
    "FLAGGED": "Flagged - playbook counter available",
    "REQUIRES_HUMAN": "Needs human review",
    "APPROVED": "Approved",
}


def _human_reason(raw: str) -> str:
    """Strip backticks / machine phrasing for a skim-friendly line."""
    text = (raw or "").strip()
    if not text:
        return "Playbook deviation flagged."
    text = text.replace("`", "")
    text = re.sub(
        r"Semantic match to playbook rule \S+\s*\(preferred:\s*([^)]+)\)\.?\s*",
        r"Conflicts with preferred position (\1). ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"Playbook rule \S+ triggered\.?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"Preferred:\s*",
        "Preferred position: ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" -.")
    if text and not text.endswith("."):
        text += "."
    return text or "Playbook deviation flagged."


def _status_label(status: str) -> str:
    return _STATUS_LABEL.get((status or "").upper(), status or "Flagged")


def _template_brief(
    *,
    contract_filename: str,
    playbook_name: str,
    findings: list[dict[str, Any]],
) -> DecisionBrief:
    if not findings:
        lines = [
            f"Review brief: {contract_filename}",
            f"Playbook: {playbook_name or 'active'}",
            "",
            "Clean first-pass - no playbook deviations flagged.",
            "",
            "Suggested next steps:",
            "- Confirm this template should be quiet against the playbook",
            "- Proceed to countersignature / commercial review as appropriate",
            "",
            "Not legal advice. First-pass assistant only.",
        ]
        return DecisionBrief(
            subject=f"RedlineGuard clean pass: {contract_filename}",
            body_markdown="\n".join(lines),
        )

    ordered = sort_by_severity(
        list(findings),
        get_severity=lambda f: str(f.get("severity") or "medium"),
        tiebreak=lambda f: str(f.get("playbook_rule_id") or ""),
    )

    lines = [
        f"Review brief: {contract_filename}",
        f"Playbook: {playbook_name or 'active'}",
        "",
        f"{len(ordered)} issue(s), highest priority first.",
        "",
    ]

    current_band = ""
    n = 0
    for f in ordered:
        sev = (f.get("severity") or "medium").lower().strip()
        band = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}.get(sev, sev.upper())
        if band != current_band:
            if current_band:
                lines.append("")
            lines.append(f"--- {band} ---")
            current_band = band
        n += 1
        title = (
            (f.get("clause_name") or "").strip()
            or (f.get("plain_english") or "").strip()
            or f"Rule {f.get('playbook_rule_id')}"
        )
        reason = (f.get("plain_english") or "").strip() or _human_reason(
            str(f.get("deviation_reason") or "")
        )
        lines.append(f"{n}. {title}")
        lines.append(f"   {reason}")
        lines.append(f"   {_status_label(str(f.get('status') or ''))}")
        if f.get("decision"):
            lines.append(f"   Decision so far: {f['decision']}")

    lines.extend(["", "Not legal advice. First-pass assistant only."])
    return DecisionBrief(
        subject=f"RedlineGuard brief: {contract_filename}",
        body_markdown="\n".join(lines),
    )


def build_decision_brief(
    *,
    contract_filename: str,
    playbook_name: str,
    findings: list[dict[str, Any]],
) -> DecisionBrief:
    findings = sort_by_severity(
        list(findings),
        get_severity=lambda f: str(f.get("severity") or "medium"),
        tiebreak=lambda f: str(f.get("playbook_rule_id") or ""),
    )
    if fake_llm() or not llm_decision_brief():
        return _template_brief(
            contract_filename=contract_filename,
            playbook_name=playbook_name,
            findings=findings,
        )

    try:
        data = complete_json(
            system=BRIEF_SYSTEM,
            user=json.dumps(
                {
                    "contract": contract_filename,
                    "playbook": playbook_name,
                    "findings": findings[:20],
                }
            ),
        )
        brief = DecisionBrief.model_validate(data)
        if "not legal advice" not in (brief.body_markdown or "").lower():
            brief.body_markdown = (
                (brief.body_markdown or "").rstrip()
                + "\n\nNot legal advice. First-pass assistant only."
            )
        return brief
    except Exception as exc:  # noqa: BLE001
        logger.warning("DecisionBrief failed: %s", exc)
        return _template_brief(
            contract_filename=contract_filename,
            playbook_name=playbook_name,
            findings=findings,
        )
