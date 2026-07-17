"""CLI: record an Accept / Edit / Reject into vector memory."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("FAKE_EMBED", "1")

from scratch.poc06_memory.models import DecisionRecord
from scratch.poc06_memory.store import DecisionStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Record a human decision into vector memory")
    p.add_argument("--clause", required=True, help="Original clause / finding context text")
    p.add_argument(
        "--decision",
        required=True,
        choices=["accept", "edit", "reject"],
    )
    p.add_argument(
        "--final",
        required=True,
        help="Final wording (accepted/edited text, or original if reject)",
    )
    p.add_argument("--rule-id", default=None, help="Playbook rule id if known")
    p.add_argument("--contract-id", default="manual")
    p.add_argument("--reasoning", default=None)
    p.add_argument("--persist-dir", type=Path, default=None)
    p.add_argument("--collection", default="decisions")
    args = p.parse_args(argv)

    store = DecisionStore(
        persist_dir=args.persist_dir,
        collection_name=args.collection,
    )
    rec = DecisionRecord(
        clause_text=args.clause,
        decision=args.decision,
        final_text=args.final,
        playbook_rule_id=args.rule_id,
        contract_id=args.contract_id,
        reasoning=args.reasoning,
    )
    store.add_decision(rec)
    print(f"Stored decision {rec.id} ({rec.decision}) collection={args.collection} count={store.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
