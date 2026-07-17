"""End-to-end learning demo: seed memory, re-run corpora, assert no malicious pollution."""

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
from scratch.poc01_extract.extract import extract_pdf
from scratch.poc02_security.security import detect_injection
from scratch.poc06_memory.seed_from_findings import seed_from_pdf
from scratch.poc06_memory.store import DecisionStore

import importlib

cli = importlib.import_module("scratch.05_dry_run_cli")

MASTER = CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"
YALE = CORPUS / "Startup revised 11-22 patented.pdf"
MALICIOUS = ROOT / "data" / "malicious_corpus"
COLLECTION = "decisions_demo"


def _precedent_count(run_dir: Path) -> int:
    p = run_dir / "05_precedents.json"
    if not p.exists():
        return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("skipped"):
        return 0
    return sum(len(r.get("precedents") or []) for r in data.get("rows") or [])


def main() -> int:
    persist = ROOT / "data" / "vector_memory"
    store = DecisionStore(persist_dir=persist, collection_name=COLLECTION)
    store.reset()
    print(f"Reset collection={COLLECTION}")

    # Pass 1 - seed
    print("\n=== PASS 1: SEED ===")
    n = seed_from_pdf(MASTER, store)
    if YALE.exists():
        n += seed_from_pdf(YALE, store)
    print(f"Seeded decisions={n} store_count={store.count()}")
    assert n >= 1, "Expected at least one FLAGGED accept seed from Master/Yale"
    assert store.count() >= 1

    # Pass 2 - prove learning on Master
    print("\n=== PASS 2: SECOND DRY-RUN (learning) ===")
    run_dir = cli.run_pipeline(MASTER, store=store, memory_collection=COLLECTION)
    hits = _precedent_count(run_dir)
    print(f"Master second pass precedent hits={hits}")
    assert hits >= 1, "Expected Step 05 precedents after seeding"
    journey = (run_dir / "journey.md").read_text(encoding="utf-8")
    assert "Step 05 - Memory" in journey

    # Pass 3 - clean corpus
    print("\n=== PASS 3: CLEAN CORPUS ===")
    summary = []
    for pdf in sorted(CORPUS.glob("*.pdf")):
        rd = cli.run_pipeline(pdf, store=store, memory_collection=COLLECTION)
        meta = {}
        mp = rd / "01_meta.json"
        if mp.exists():
            meta = json.loads(mp.read_text(encoding="utf-8"))
        sec = json.loads((rd / "02_security.json").read_text(encoding="utf-8"))
        pb_path = rd / "04_findings.json"
        findings = 0
        if pb_path.exists():
            findings = len(json.loads(pb_path.read_text(encoding="utf-8")).get("reviews") or [])
        skipped05 = (rd / "05_SKIPPED.md").exists()
        prec = _precedent_count(rd)
        summary.append(
            {
                "file": pdf.name,
                "quality": meta.get("quality"),
                "halt": sec.get("halt"),
                "findings": findings,
                "precedents": prec,
                "mem_skipped": skipped05,
            }
        )
        print(
            f"  {pdf.name}: quality={meta.get('quality')} findings={findings} "
            f"precedents={prec} mem_skipped={skipped05}"
        )

    tippett = next((s for s in summary if "Tippett" in s["file"]), None)
    if tippett:
        assert tippett["quality"] == "poor"
        assert tippett["mem_skipped"] or tippett["precedents"] == 0

    count_before_mal = store.count()

    # Pass 4 - malicious: halt, no new writes
    print("\n=== PASS 4: MALICIOUS (no pollution) ===")
    for pdf in sorted(MALICIOUS.glob("*.pdf")):
        text = extract_pdf(pdf)["text"]
        assert detect_injection(text)["halt"] is True, f"{pdf.name} should halt"
        rd = cli.run_pipeline(pdf, store=store, memory_collection=COLLECTION)
        assert (rd / "05_SKIPPED.md").exists() or _precedent_count(rd) == 0
        print(f"  {pdf.name}: HALT ok, mem not polluted")

    assert store.count() == count_before_mal, "Malicious runs must not add_decision"

    print("\n=== SUMMARY ===")
    print(f"{'file':50} {'findings':>8} {'precedents':>10}")
    for s in summary:
        print(f"{s['file'][:50]:50} {s['findings']:8} {s['precedents']:10}")
    print(f"\nMemory store_count (unchanged after malicious)={store.count()}")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
