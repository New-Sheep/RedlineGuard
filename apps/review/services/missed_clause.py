"""F22 — propose a playbook rule from a lawyer-flagged missed clause."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from apps.core.agent_flags import fake_llm
from apps.core.llm_complete import complete_json
from apps.review.services.playbook_bootstrap import PlaybookRule, _slug

logger = logging.getLogger(__name__)

SYSTEM = (
    "A lawyer flagged a contract excerpt that the playbook missed. "
    "Propose ONE new playbook rule. Return ONLY JSON: "
    '{"id":str,"clause_type":str,"preferred":str,"hard_ceiling":str,'
    '"fallback_text":str,"severity":"low"|"medium"|"high","match_any":[str]}. '
    "match_any must include short needles from the excerpt. "
    "Do not invent company policy beyond the excerpt + note."
)


def _fake_rule(excerpt: str, note: str) -> dict[str, Any]:
    words = re.findall(r"[A-Za-z]{5,}", excerpt or "")
    needles = list(dict.fromkeys(words[:4])) or ["missed clause"]
    clause = (note or "missed_clause").strip()[:40] or "missed_clause"
    rid = _slug(clause)
    return PlaybookRule(
        id=rid,
        clause_type=clause.replace(" ", "_")[:64] or "missed_clause",
        preferred=f"Align with firm position regarding: {(excerpt or '')[:120]}",
        hard_ceiling="Flag language like the excerpt when it conflicts with preferred.",
        fallback_text="",
        severity="medium",
        match_any=needles,
    ).model_dump()


def propose_rule_from_missed(*, excerpt: str, note: str = "") -> dict[str, Any]:
    if fake_llm():
        return _fake_rule(excerpt, note)
    try:
        data = complete_json(
            system=SYSTEM,
            user=json.dumps({"excerpt": (excerpt or "")[:4000], "note": note or ""}),
        )
        rule = PlaybookRule.model_validate(data)
        return rule.model_dump()
    except Exception as exc:  # noqa: BLE001
        logger.warning("missed clause propose failed: %s", exc)
        return _fake_rule(excerpt, note)
