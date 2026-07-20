"""Eval suite implementations (offline / FAKE_LLM=1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

DATA = Path(__file__).resolve().parents[1] / "datasets"


def _load(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def suite_injection() -> list[dict[str, Any]]:
    from scratch.poc02_security.security import detect_injection

    results = []
    text = _load("injection_hard.txt")
    det = detect_injection(text)
    results.append(
        {
            "id": "injection_hard_halt",
            "expect": "halt",
            "pass": bool(det.get("halt")),
        }
    )
    clean = "This NDA is governed by the laws of England and Wales."
    det2 = detect_injection(clean)
    results.append(
        {
            "id": "clean_no_halt",
            "expect": "no_halt",
            "pass": not bool(det2.get("halt")),
        }
    )
    return results


def suite_adjudicate() -> list[dict[str, Any]]:
    from apps.security.services.adjudicate import adjudicate_security, should_auto_clear
    from scratch.poc02_security.security import detect_injection

    results = []
    text = _load("injection_hard.txt")
    det = detect_injection(text)
    adj = adjudicate_security(text=text, matches=det.get("matches") or [], filename="inj.txt")
    results.append(
        {
            "id": "hard_hold",
            "expect": "hold_no_autoclear",
            "pass": adj.verdict == "hold" and not should_auto_clear(adj),
        }
    )
    text2 = _load("ambiguous_peer.txt")
    det2 = detect_injection(text2)
    adj2 = adjudicate_security(
        text=text2, matches=det2.get("matches") or [], filename="peer.txt"
    )
    results.append(
        {
            "id": "ambiguous_autoclear",
            "expect": "ambiguous_proceed",
            "pass": bool(det2.get("halt")) and should_auto_clear(adj2),
        }
    )
    return results


def suite_compare_l0() -> list[dict[str, Any]]:
    from django.test import override_settings

    from apps.review.services.compare.orchestrate import compare_layered

    playbook = {
        "version": 1,
        "name": "Eval",
        "empty": False,
        "rules": [
            {
                "id": "governing_law_preferred",
                "clause_type": "governing_law",
                "preferred": "England and Wales",
                "hard_ceiling": "Flag non-UK",
                "fallback_text": "Governed by England and Wales.",
                "severity": "medium",
                "match_any": ["laws of the State of California", "laws of California"],
            }
        ],
    }
    text = _load("california_flag.txt")
    with override_settings(SEMANTIC_COMPARE=False, FAKE_LLM="1"):
        report = compare_layered(text, playbook=playbook)
        n = len(report.reviews)
    return [
        {
            "id": "california_l0",
            "expect": "ge_1_flag",
            "pass": n >= 1,
            "flags": n,
        }
    ]


def suite_draft_react() -> list[dict[str, Any]]:
    from apps.drafting.agent import react_draft

    finding = {
        "playbook_rule_id": "governing_law_preferred",
        "clause_excerpt": "Governed by the laws of California.",
        "deviation_reason": "Non-UK governing law",
        "status": "needs_human",
    }
    rule = {
        "id": "governing_law_preferred",
        "preferred": "England and Wales law.",
        "fallback_text": "This Agreement is governed by England and Wales.",
        "hard_ceiling": "No California",
    }
    result = react_draft(finding_payload=finding, playbook_rule=rule)
    trace = (result.provenance or {}).get("react_trace") or []
    tools = [t.get("tool") for t in trace if isinstance(t, dict)]
    return [
        {
            "id": "react_has_trace",
            "expect": "trace_and_draft",
            "pass": bool(result and result.draft_text and len(trace) >= 3),
        },
        {
            "id": "react_max_iters",
            "expect": "lte_6",
            "pass": len(trace) <= 6,
        },
        {
            "id": "react_uses_tools",
            "expect": "search_or_propose",
            "pass": "propose_draft" in tools or "search_precedents" in tools,
        },
    ]


def suite_pii_redact() -> list[dict[str, Any]]:
    from apps.security.services.redactor import redact_pii

    raw = "Contact jane.doe@example.com or +1-415-555-0100 about IBAN GB82WEST12345698765432."
    redacted, mapping = redact_pii(raw)
    return [
        {
            "id": "pii_email_gone",
            "expect": "redacted",
            "pass": "jane.doe@example.com" not in redacted and bool(mapping),
        },
        {
            "id": "pii_placeholder",
            "expect": "REDACTED_token",
            "pass": "REDACTED_" in redacted,
        },
    ]


SUITE_FUNCS: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = [
    ("injection", suite_injection),
    ("adjudicate", suite_adjudicate),
    ("compare_l0", suite_compare_l0),
    ("draft_react", suite_draft_react),
    ("pii_redact", suite_pii_redact),
]
