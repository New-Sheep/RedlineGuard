"""F5 — Gap suggest: propose playbook patches from repeated Rejects."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from apps.core.agent_flags import fake_llm, llm_gap_suggest
from apps.core.llm_complete import complete_json
from apps.review.services.playbook_bootstrap import PlaybookRule, _slug

logger = logging.getLogger(__name__)


class GapSuggestion(BaseModel):
    rationale: str = ""
    rules: list[PlaybookRule] = Field(default_factory=list)


GAP_SYSTEM = (
    "From repeated lawyer Rejects/Needs-human gaps, propose NEW playbook rules "
    "for human Activate. Return ONLY JSON: {\"rationale\": str, \"rules\": [same shape "
    "as playbook rules with id, clause_type, preferred, hard_ceiling, fallback_text, "
    "severity, match_any]}. Do not duplicate existing_rule_ids."
)


def suggest_gaps_from_decisions(
    *,
    decisions: list[dict[str, Any]],
    existing_rule_ids: list[str],
) -> GapSuggestion:
    if fake_llm() or not llm_gap_suggest():
        return GapSuggestion(
            rationale="Suggestions need live AI (ask your admin), or reject a few more issues first.",
            rules=[],
        )
    try:
        data = complete_json(
            system=GAP_SYSTEM,
            user=json.dumps(
                {
                    "existing_rule_ids": existing_rule_ids,
                    "decisions": decisions[:30],
                }
            ),
        )
        raw_rules = data.get("rules") or []
        rules: list[PlaybookRule] = []
        existing = set(existing_rule_ids)
        for r in raw_rules[:5]:
            try:
                rule = PlaybookRule.model_validate(r)
            except Exception:
                continue
            if rule.id in existing:
                rule.id = _slug(rule.clause_type or "gap")
            rules.append(rule)
        return GapSuggestion(
            rationale=str(data.get("rationale") or ""),
            rules=rules,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("GapSuggest failed: %s", exc)
        return GapSuggestion(rationale=str(exc), rules=[])
