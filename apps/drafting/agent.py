"""Narrow ReAct loop for Needs-human drafting (max N tool steps)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from django.conf import settings

from apps.core.llm_complete import complete_json, provider_label
from apps.drafting import tools as T
from scratch.poc07_draft.models import DraftResult

logger = logging.getLogger(__name__)

MAX_ITERS_DEFAULT = 6

TOOLS = (
    "search_precedents",
    "check_playbook_rule",
    "redact_pii",
    "propose_draft",
    "escalate_human",
    "finish",
)


def _react_on() -> bool:
    return bool(getattr(settings, "REACT_DRAFT", True))


def _real_llm_on() -> bool:
    raw = str(getattr(settings, "FAKE_LLM", os.environ.get("FAKE_LLM", "1"))).strip()
    return raw in ("0", "false", "False")


def _max_iters() -> int:
    return int(getattr(settings, "REACT_DRAFT_MAX_ITERS", MAX_ITERS_DEFAULT))


def _prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n{user}".encode("utf-8")).hexdigest()[:16]


def _fake_react(
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
) -> DraftResult:
    """Canned multi-step trace for offline / Fake demos."""
    rule_id = str(finding_payload.get("playbook_rule_id") or playbook_rule.get("id") or "unknown")
    excerpt = finding_payload.get("clause_excerpt") or ""
    query = (excerpt or finding_payload.get("deviation_reason") or rule_id)[:200]

    trace: list[dict[str, Any]] = []
    obs1 = T.search_precedents_tool(query=query, playbook_rule_id=rule_id)
    trace.append({"tool": "search_precedents", "args": {"query": query[:80]}, "observe": obs1})

    obs2 = T.check_playbook_rule_tool(playbook_rule)
    trace.append({"tool": "check_playbook_rule", "args": {"rule_id": rule_id}, "observe": obs2})

    obs3 = T.redact_pii_tool(excerpt)
    trace.append({"tool": "redact_pii", "args": {"len": len(excerpt)}, "observe": obs3})

    memory_hint = ""
    if obs1.get("top"):
        memory_hint = obs1["top"][0].get("snippet") or ""
    obs4 = T.propose_draft_tool(
        playbook_rule=playbook_rule,
        finding=finding_payload,
        memory_hint=memory_hint,
    )
    trace.append(
        {
            "tool": "propose_draft",
            "args": {"source_hint": obs4.get("source")},
            "observe": {"source": obs4.get("source")},
        }
    )
    trace.append({"tool": "finish", "args": {}, "observe": {"ok": True}})

    return DraftResult(
        playbook_rule_id=rule_id,
        finding_status=str(finding_payload.get("status") or "needs_human"),
        draft_text=obs4.get("draft_text") or "",
        draft_source="llm_suggested",
        precedent_ids=[t["id"] for t in (obs1.get("top") or []) if t.get("id")],
        rationale=(
            obs4.get("rationale")
            or "ReAct Fake agent: searched memory, checked playbook, redacted PII, proposed draft."
        ),
        provenance={
            "provider": "Fake-ReAct",
            "react_trace": trace,
            "react_iters": len(trace),
            "prompt_hash": "fake",
        },
    )


def _run_tool(
    name: str,
    args: dict[str, Any],
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    if name == "search_precedents":
        q = (args.get("query") or finding_payload.get("clause_excerpt") or "")[:400]
        rid = args.get("playbook_rule_id") or finding_payload.get("playbook_rule_id") or ""
        out = T.search_precedents_tool(query=q, playbook_rule_id=str(rid))
        if out.get("top"):
            state["memory_hint"] = out["top"][0].get("snippet") or ""
            state["precedent_ids"] = [t["id"] for t in out["top"] if t.get("id")]
        return out
    if name == "check_playbook_rule":
        return T.check_playbook_rule_tool(playbook_rule)
    if name == "redact_pii":
        text = args.get("text") or finding_payload.get("clause_excerpt") or ""
        return T.redact_pii_tool(str(text))
    if name == "propose_draft":
        out = T.propose_draft_tool(
            playbook_rule=playbook_rule,
            finding=finding_payload,
            memory_hint=state.get("memory_hint") or "",
        )
        state["draft_text"] = out.get("draft_text") or ""
        state["rationale"] = out.get("rationale") or ""
        return {"source": out.get("source"), "len": len(state["draft_text"])}
    if name == "escalate_human":
        out = T.escalate_human_tool(reason=str(args.get("reason") or ""))
        state["escalated"] = True
        state["rationale"] = out.get("reason") or ""
        return out
    if name == "finish":
        return {"ok": True}
    return {"error": f"unknown tool {name}"}


def _live_react(
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
) -> DraftResult:
    rule_id = str(finding_payload.get("playbook_rule_id") or playbook_rule.get("id") or "unknown")
    system = (
        "You are a drafting agent for contract counters. "
        "Choose ONE tool per turn from: "
        + ", ".join(TOOLS)
        + ". Respond JSON: {\"tool\": \"name\", \"args\": {}}. "
        "Never invent secrets. End with tool finish after propose_draft or escalate_human. "
        "Max tools before finish: " + str(_max_iters())
    )
    user = json.dumps(
        {
            "finding": {
                "playbook_rule_id": rule_id,
                "clause_excerpt": (finding_payload.get("clause_excerpt") or "")[:800],
                "deviation_reason": finding_payload.get("deviation_reason"),
                "status": finding_payload.get("status"),
            },
            "playbook_rule_id": rule_id,
        },
        ensure_ascii=False,
    )
    ph = _prompt_hash(system, user)
    trace: list[dict[str, Any]] = []
    state: dict[str, Any] = {}
    observations: list[str] = []

    for i in range(_max_iters()):
        turn_user = user + "\nObservations so far:\n" + "\n".join(observations[-4:])
        try:
            step = complete_json(system=system, user=turn_user)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ReAct step failed: %s", exc)
            break
        tool = str(step.get("tool") or "").strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        safe_args = {k: (str(v)[:80] if not isinstance(v, (int, float, bool)) else v) for k, v in args.items()}
        if tool not in TOOLS:
            trace.append({"tool": tool or "invalid", "args": safe_args, "observe": {"error": "bad tool"}})
            observations.append(f"{tool}: bad tool")
            continue
        obs = _run_tool(
            tool,
            args,
            finding_payload=finding_payload,
            playbook_rule=playbook_rule,
            state=state,
        )
        trace.append({"tool": tool, "args": safe_args, "observe": obs})
        observations.append(f"{tool}: {json.dumps(obs, ensure_ascii=False)[:200]}")
        if tool in ("finish", "escalate_human"):
            break
        if tool == "propose_draft" and state.get("draft_text"):
            # one more chance to finish
            continue

    if not state.get("draft_text") and not state.get("escalated"):
        # force propose
        out = T.propose_draft_tool(
            playbook_rule=playbook_rule,
            finding=finding_payload,
            memory_hint=state.get("memory_hint") or "",
        )
        state["draft_text"] = out.get("draft_text") or ""
        state["rationale"] = out.get("rationale") or ""
        trace.append({"tool": "propose_draft", "args": {"forced": True}, "observe": {"source": out.get("source")}})

    return DraftResult(
        playbook_rule_id=rule_id,
        finding_status=str(finding_payload.get("status") or "needs_human"),
        draft_text=state.get("draft_text") or "[Needs human] Unable to propose automatically.",
        draft_source="llm_suggested",
        precedent_ids=list(state.get("precedent_ids") or []),
        rationale=state.get("rationale") or "ReAct draft agent completed.",
        provenance={
            "provider": f"ReAct/{provider_label()}",
            "react_trace": trace,
            "react_iters": len(trace),
            "prompt_hash": ph,
            "escalated": bool(state.get("escalated")),
        },
    )


def react_draft(
    *,
    finding_payload: dict[str, Any],
    playbook_rule: dict[str, Any],
    contract_text: str = "",
) -> DraftResult | None:
    """Run ReAct draft when enabled. Always works offline via Fake path."""
    if not _react_on():
        return None
    if not _real_llm_on():
        return _fake_react(finding_payload=finding_payload, playbook_rule=playbook_rule)
    try:
        return _live_react(finding_payload=finding_payload, playbook_rule=playbook_rule)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Live ReAct failed, Fake fallback: %s", exc)
        result = _fake_react(finding_payload=finding_payload, playbook_rule=playbook_rule)
        result.provenance["fallback_error"] = str(exc)[:200]
        return result
