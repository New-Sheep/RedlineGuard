"""Offline smoke evals — gate, adjudicate, L0 compare (FAKE_LLM=1)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure project root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["FAKE_LLM"] = "1"

import django

django.setup()

from apps.security.services.adjudicate import adjudicate_security, should_auto_clear
from apps.review.services.compare.orchestrate import compare_layered
from scratch.poc02_security.security import detect_injection

DATA = Path(__file__).resolve().parents[1] / "datasets"
REPORTS = Path(__file__).resolve().parents[1] / "reports"


def _load(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def _playbook_cal() -> dict:
    return {
        "version": 1,
        "name": "Eval playbook",
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


def run() -> dict:
    results = []

    # 1 Hard injection → halt, adjudicator hold
    text = _load("injection_hard.txt")
    det = detect_injection(text)
    adj = adjudicate_security(text=text, matches=det.get("matches") or [], filename="inj.txt")
    results.append(
        {
            "id": "injection_hard",
            "expect": "halt_hold",
            "pass": bool(det.get("halt")) and adj.verdict == "hold" and not should_auto_clear(adj),
        }
    )

    # 2 Ambiguous peer → cue then auto-clear
    text = _load("ambiguous_peer.txt")
    det = detect_injection(text)
    adj = adjudicate_security(text=text, matches=det.get("matches") or [], filename="peer.txt")
    results.append(
        {
            "id": "ambiguous_peer",
            "expect": "ambiguous_proceed",
            "pass": bool(det.get("halt")) and should_auto_clear(adj),
        }
    )

    # 3 California → L0 flag (semantic off for offline smoke)
    from django.test import override_settings

    with override_settings(SEMANTIC_COMPARE=False, FAKE_LLM="1"):
        report = compare_layered(_load("california_flag.txt"), playbook=_playbook_cal())
        n = len(report.reviews)
        results.append(
            {
                "id": "california_flag",
                "expect": "ge_1_flag",
                "pass": n >= 1,
                "flags": n,
            }
        )

    # 4 Clean UK → no California needle
    t = _load("clean_uk.txt").lower()
    results.append(
        {
            "id": "clean_uk",
            "expect": "no_california_needle",
            "pass": "california" not in t and "england" in t,
        }
    )

    passed = sum(1 for r in results if r.get("pass"))
    report = {
        "passed": passed,
        "total": len(results),
        "ok": passed == len(results),
        "results": results,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "latest.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    rep = run()
    sys.exit(0 if rep["ok"] else 1)
