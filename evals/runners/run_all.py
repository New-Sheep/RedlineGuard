"""Run all offline eval suites (FAKE_LLM=1). Exit 0 iff all pass."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["FAKE_LLM"] = "1"
os.environ.setdefault("FAKE_EMBED", "1")
os.environ.setdefault("SEMANTIC_COMPARE", "0")

import django

django.setup()

from evals.runners import suites

REPORTS = Path(__file__).resolve().parents[1] / "reports"


def run() -> dict:
    all_results = []
    for name, fn in suites.SUITE_FUNCS:
        rows = fn()
        for r in rows:
            r["suite"] = name
        all_results.extend(rows)

    passed = sum(1 for r in all_results if r.get("pass"))
    failed = [r for r in all_results if not r.get("pass")]
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "fake_llm": True,
        "total": len(all_results),
        "passed": passed,
        "failed": len(failed),
        "results": all_results,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = REPORTS / f"all_{stamp}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (REPORTS / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{passed}/{len(all_results)} passed -> {out}")
    for f in failed:
        print(f"  FAIL {f.get('suite')}/{f.get('id')}: {f.get('expect')}")
    return report


if __name__ == "__main__":
    rep = run()
    sys.exit(0 if rep["failed"] == 0 else 1)
