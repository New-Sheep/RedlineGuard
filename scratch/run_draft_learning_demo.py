"""Journey B demo: draft from playbook/memory → decide accept → next draft from memory."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ["FAKE_EMBED"] = "1"

from scratch._io import CORPUS, ROOT
from scratch.poc06_memory.store import DecisionStore
from scratch.poc07_draft.decide_cli import apply_decisions

import importlib

cli = importlib.import_module("scratch.05_dry_run_cli")

MASTER = CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"
MALICIOUS = ROOT / "data" / "malicious_corpus"
COLLECTION = "drafts_demo"


def _draft_sources(run_dir: Path) -> list[str]:
    p = run_dir / "06_drafts.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("skipped"):
        return []
    return [d.get("draft_source") for d in data.get("drafts") or []]


def main() -> int:
    persist = ROOT / "data" / "vector_memory"
    store = DecisionStore(persist_dir=persist, collection_name=COLLECTION)
    store.reset()
    print(f"Reset collection={COLLECTION}")

    # Pass 1 — empty memory: drafts should use playbook fallback
    print("\n=== PASS 1: DRY-RUN (empty memory -> playbook_fallback) ===")
    run1 = cli.run_pipeline(MASTER, store=store, memory_collection=COLLECTION)
    sources1 = _draft_sources(run1)
    print(f"Draft sources: {sources1}")
    assert sources1, "Expected at least one draft"
    assert any(s in ("playbook_fallback", "memory_precedent") for s in sources1), (
        "Expected playbook_fallback or memory_precedent drafts"
    )
    journey1 = (run1 / "journey.md").read_text(encoding="utf-8")
    assert "Step 06 - Draft" in journey1

    count_before = store.count()
    print("\n=== PASS 2: DECIDE --all-accept ===")
    n = apply_decisions(run1, store, all_accept=True)
    print(f"Accepted {n}; store_count={store.count()}")
    assert n >= 1, "Expected at least one accept write-back"
    assert store.count() == count_before + n

    # Pass 3 — second dry-run should draft from memory
    print("\n=== PASS 3: SECOND DRY-RUN (memory_precedent) ===")
    run2 = cli.run_pipeline(MASTER, store=store, memory_collection=COLLECTION)
    sources2 = _draft_sources(run2)
    print(f"Draft sources: {sources2}")
    assert "memory_precedent" in sources2, (
        "Expected at least one draft_source=memory_precedent after accept"
    )
    journey2 = (run2 / "journey.md").read_text(encoding="utf-8")
    assert "memory_precedent" in journey2 or "memory=" in journey2

    count_after_decide = store.count()

    # Pass 4 — malicious: halt, no draft, no new decisions
    print("\n=== PASS 4: MALICIOUS HALT ===")
    mal_files = sorted(MALICIOUS.glob("*.pdf"))
    assert mal_files, "malicious_corpus empty"
    mal = mal_files[0]
    run_m = cli.run_pipeline(mal, store=store, memory_collection=COLLECTION)
    assert (run_m / "06_SKIPPED.md").exists() or not (run_m / "06_drafts.json").exists()
    skipped = run_m / "06_SKIPPED.md"
    if (run_m / "06_drafts.json").exists():
        data = json.loads((run_m / "06_drafts.json").read_text(encoding="utf-8"))
        assert data.get("skipped") is True
    assert store.count() == count_after_decide, "Malicious must not write memory"
    print(f"  {mal.name}: HALT ok, mem not polluted")

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
