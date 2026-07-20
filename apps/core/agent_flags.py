"""Per-agent feature toggles (default on when FAKE_LLM=0)."""

from __future__ import annotations

import os

from django.conf import settings


def fake_llm() -> bool:
    return str(getattr(settings, "FAKE_LLM", os.environ.get("FAKE_LLM", "1"))).strip() not in (
        "0",
        "false",
        "False",
    )


def _flag(name: str, *, default_when_real: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        try:
            raw = getattr(settings, name, None)
        except Exception:
            raw = None
    if raw is None or str(raw).strip() == "":
        return (not fake_llm()) if default_when_real else False
    return str(raw).strip() not in ("0", "false", "False")


def llm_playbook_propose() -> bool:
    return _flag("LLM_PLAYBOOK_PROPOSE")


def llm_rewrite_copilot() -> bool:
    return _flag("LLM_REWRITE_COPILOT")


def llm_memory_explain() -> bool:
    return _flag("LLM_MEMORY_EXPLAIN")


def llm_decision_brief() -> bool:
    return _flag("LLM_DECISION_BRIEF")


def llm_memory_enrich() -> bool:
    return _flag("LLM_MEMORY_ENRICH")


def llm_gap_suggest() -> bool:
    return _flag("LLM_GAP_SUGGEST", default_when_real=False)


def llm_discover() -> bool:
    return _flag("LLM_DISCOVER", default_when_real=False)


def llm_plain_english() -> bool:
    return _flag("LLM_PLAIN_ENGLISH")


def llm_scoped_ask() -> bool:
    return _flag("LLM_SCOPED_ASK")


def llm_security_adjudicate() -> bool:
    return _flag("LLM_SECURITY_ADJUDICATE")


def llm_context_agent() -> bool:
    return _flag("LLM_CONTEXT_AGENT")
