"""Seed vector memory by simulating Accept on FLAGGED playbook findings."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("FAKE_EMBED", "1")

from scratch._io import CORPUS
from scratch.poc01_extract.extract import extract_pdf
from scratch.poc04_playbook.playbook import compare
from scratch.poc06_memory.models import DecisionRecord
from scratch.poc06_memory.store import DecisionStore


def seed_from_pdf(
    pdf_path: Path,
    store: DecisionStore,
    *,
    include_rejects: bool = False,
) -> int:
    extracted = extract_pdf(pdf_path)
    if extracted["quality"] == "poor":
        print(f"Skip seed (poor quality): {pdf_path.name}")
        return 0
    report = compare(extracted["text"])
    added = 0
    contract_id = pdf_path.stem
    for finding in report.reviews:
        clause_ctx = (
            f"[{finding.playbook_rule_id}] {finding.deviation_reason}\n"
            f"severity={finding.severity} status={finding.status}"
        )
        if finding.status == "FLAGGED" and finding.suggested_counter_proposal:
            store.add_decision(
                DecisionRecord(
                    clause_text=clause_ctx,
                    decision="accept",
                    final_text=finding.suggested_counter_proposal,
                    playbook_rule_id=finding.playbook_rule_id,
                    contract_id=contract_id,
                    reasoning="Seeded: simulated Accept of playbook fallback",
                )
            )
            added += 1
        elif finding.status == "REQUIRES_HUMAN" and include_rejects:
            store.add_decision(
                DecisionRecord(
                    clause_text=clause_ctx,
                    decision="reject",
                    final_text=finding.deviation_reason,
                    playbook_rule_id=finding.playbook_rule_id,
                    contract_id=contract_id,
                    reasoning="Seeded: REQUIRES_HUMAN left as reject placeholder",
                )
            )
            added += 1
    return added


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed vector memory from playbook findings")
    p.add_argument(
        "path",
        nargs="?",
        default=str(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"),
    )
    p.add_argument("--include-rejects", action="store_true")
    p.add_argument("--reset", action="store_true", help="Wipe collection before seeding")
    p.add_argument("--persist-dir", type=Path, default=None)
    p.add_argument("--collection", default="decisions")
    p.add_argument("--also-yale", action="store_true")
    args = p.parse_args(argv)

    store = DecisionStore(
        persist_dir=args.persist_dir,
        collection_name=args.collection,
    )
    if args.reset:
        store.reset()
        print(f"Reset collection {args.collection}")

    paths = [Path(args.path)]
    if args.also_yale:
        paths.append(CORPUS / "Startup revised 11-22 patented.pdf")

    total = 0
    for path in paths:
        if not path.exists():
            print(f"Missing: {path}")
            continue
        n = seed_from_pdf(path, store, include_rejects=args.include_rejects)
        print(f"Seeded {n} decisions from {path.name}")
        total += n
    print(f"Total added={total} store_count={store.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
