"""Real MiniLM learning on cyber docs: dry-run -> Accept -> second dry-run proves memory.

Requires: pip install sentence-transformers
Uses FAKE_EMBED=0 (all-MiniLM-L6-v2). Resets collection cyber_minilm first
so hash vectors are never mixed with MiniLM.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Must be set before DecisionStore / get_embedder
os.environ["FAKE_EMBED"] = "0"

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scratch._io import CORPUS, ROOT
from scratch.poc06_memory.embeddings import SentenceEmbedder, get_embedder
from scratch.poc06_memory.store import DecisionStore
from scratch.poc07_draft.decide_cli import apply_decisions

import importlib

cli = importlib.import_module("scratch.05_dry_run_cli")

COLLECTION = "cyber_minilm"

CYBER_PDFS = [
    "676888790122090-terms-and-conditions-2024-05-07-1329.pdf",
    "B2B-Terms-of-Service_Sept23.pdf",
    "contract_negotiation_guide_1901.pdf",
    "cyber-security-contract-template.pdf",
    "Cybersecurity Agreement-Ingram Micro-CURRENT-REDACTED (2023).pdf",
    "dpsa-supplier-security-addendum.pdf",
    "Partnership_Agreement_Hardsecure_11e721a58f.pdf",
    "SES-Cybersecurity-Contract-Clauses-November-2024.pdf",
    "Terms-and-Conditions-Bureau-Veritas-Cybersecurity-Europe-BV_1.0.pdf",
    "The-Managed-Services-Agreement-V1.0-1.pdf",
    "vendor-information-security-requirements-september-2018.pdf",
]


def _findings_count(run_dir: Path) -> int:
    p = run_dir / "04_findings.json"
    if not p.exists():
        return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    return len(data.get("reviews") or [])


def _draft_sources(run_dir: Path) -> list[str]:
    p = run_dir / "06_drafts.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("skipped"):
        return []
    return [d.get("draft_source") or "none" for d in data.get("drafts") or []]


def _memory_draft_count(run_dir: Path) -> int:
    return sum(1 for s in _draft_sources(run_dir) if s == "memory_precedent")


def main() -> int:
    print("=== REAL MiniLM cyber learning ===")
    print(f"FAKE_EMBED={os.environ.get('FAKE_EMBED')}")

    t0 = time.perf_counter()
    emb = get_embedder()
    assert isinstance(emb, SentenceEmbedder), f"Expected SentenceEmbedder, got {type(emb)}"
    _ = emb.embed(["smoke test liability indemnity governing law"])
    cold = time.perf_counter() - t0
    print(f"MiniLM cold load+embed: {cold:.2f}s")

    t1 = time.perf_counter()
    _ = emb.embed(["second embed should be warm"])
    warm = time.perf_counter() - t1
    print(f"MiniLM warm embed: {warm:.3f}s")

    persist = ROOT / "data" / "vector_memory"
    store = DecisionStore(
        persist_dir=persist,
        collection_name=COLLECTION,
        embedder=emb,
    )
    store.reset()
    print(f"Reset collection={COLLECTION}")

    paths = []
    for name in CYBER_PDFS:
        p = CORPUS / name
        if not p.exists():
            print(f"MISSING (skip): {name}")
            continue
        paths.append(p)
    assert paths, "No cyber PDFs found in scratch_corpus"

    # Pass A - first dry-runs
    print("\n=== PASS A: FIRST DRY-RUNS (empty memory) ===")
    first_runs: dict[str, Path] = {}
    summary = []
    for pdf in paths:
        t = time.perf_counter()
        rd = cli.run_pipeline(pdf, store=store, memory_collection=COLLECTION)
        elapsed = time.perf_counter() - t
        first_runs[pdf.name] = rd
        findings = _findings_count(rd)
        sources = _draft_sources(rd)
        summary.append(
            {
                "file": pdf.name,
                "findings": findings,
                "sources_pass_a": sources,
                "t_a": round(elapsed, 2),
                "accepts": 0,
                "memory_pass_c": None,
            }
        )
        print(
            f"  {pdf.name[:55]:55} findings={findings} "
            f"drafts={sources} {elapsed:.1f}s"
        )

    # Pass B - Accept all non-empty drafts
    print("\n=== PASS B: ACCEPT ALL DRAFTS ===")
    total_accepts = 0
    for row in summary:
        rd = first_runs[row["file"]]
        if not (rd / "06_drafts.json").exists():
            continue
        data = json.loads((rd / "06_drafts.json").read_text(encoding="utf-8"))
        if data.get("skipped"):
            continue
        before = store.count()
        try:
            n = apply_decisions(rd, store, all_accept=True)
        except SystemExit as e:
            print(f"  skip decide {row['file']}: {e}")
            n = 0
        row["accepts"] = n
        total_accepts += n
        print(f"  {row['file'][:55]:55} accepts={n} store={store.count()}")

    print(f"Total accepts written={total_accepts} store_count={store.count()}")
    assert total_accepts >= 1, "Expected at least one Accept from cyber FLAGGED drafts"
    assert store.count() >= 1

    # Pass C - second dry-run on files that accepted
    print("\n=== PASS C: SECOND DRY-RUN (expect memory_precedent) ===")
    recheck = [r for r in summary if r["accepts"] > 0][:3]
    if len(recheck) < 1:
        recheck = summary[:3]

    any_memory = False
    for row in recheck:
        pdf = CORPUS / row["file"]
        t = time.perf_counter()
        rd = cli.run_pipeline(pdf, store=store, memory_collection=COLLECTION)
        elapsed = time.perf_counter() - t
        mem_n = _memory_draft_count(rd)
        row["memory_pass_c"] = mem_n
        row["sources_pass_c"] = _draft_sources(rd)
        row["t_c"] = round(elapsed, 2)
        if mem_n >= 1:
            any_memory = True
        print(
            f"  {row['file'][:55]:55} memory_precedent={mem_n} "
            f"sources={row['sources_pass_c']} {elapsed:.1f}s"
        )

    assert any_memory, (
        "Expected at least one draft_source=memory_precedent after Accept"
    )

    print("\n=== SUMMARY ===")
    print(
        f"{'file':50} {'find':>4} {'acc':>3} {'memC':>4} {'tA':>5} {'tC':>5}"
    )
    for r in summary:
        mem = r["memory_pass_c"]
        mem_s = "-" if mem is None else str(mem)
        tc = r.get("t_c")
        tc_s = "-" if tc is None else f"{tc:.1f}"
        print(
            f"{r['file'][:50]:50} {r['findings']:4} {r['accepts']:3} "
            f"{mem_s:>4} {r['t_a']:5.1f} {tc_s:>5}"
        )
    print(f"\nMiniLM cold={cold:.2f}s warm={warm:.3f}s store_count={store.count()}")
    print("ALL CHECKS PASSED (real MiniLM learning)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
