"""CLI: Accept / Edit / Reject drafts from a dry-run into vector memory."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("FAKE_EMBED", "1")

from scratch.poc06_memory.models import DecisionRecord
from scratch.poc06_memory.store import DecisionStore


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _findings_by_rule(run_dir: Path) -> dict[str, dict]:
    path = run_dir / "04_findings.json"
    if not path.exists():
        return {}
    data = _load_json(path)
    reviews = data.get("reviews") or []
    return {f.get("playbook_rule_id"): f for f in reviews if f.get("playbook_rule_id")}


def _clause_context(finding: dict | None, rule_id: str, draft: dict) -> str:
    if finding:
        return (
            f"[{finding.get('playbook_rule_id')}] {finding.get('deviation_reason', '')}\n"
            f"severity={finding.get('severity')} status={finding.get('status')}"
        )
    return f"[{rule_id}] draft_source={draft.get('draft_source')}"


def apply_decisions(
    run_dir: Path,
    store: DecisionStore,
    *,
    all_accept: bool = False,
    rule_id: str | None = None,
    decision: str | None = None,
    final_text: str | None = None,
    contract_id: str | None = None,
) -> int:
    """Apply Accept/Edit/Reject for drafts in run_dir. Returns count written."""
    run_dir = Path(run_dir)
    sec_path = run_dir / "02_security.json"
    if sec_path.exists():
        sec = _load_json(sec_path)
        if sec.get("halt"):
            raise SystemExit("Refuse decide: security HALT run - would pollute memory")

    drafts_path = run_dir / "06_drafts.json"
    if not drafts_path.exists():
        raise SystemExit(f"No 06_drafts.json in {run_dir}")
    drafts_data = _load_json(drafts_path)
    if drafts_data.get("skipped"):
        raise SystemExit(f"Drafts skipped: {drafts_data.get('reason')}")

    drafts = drafts_data.get("drafts") or []
    findings = _findings_by_rule(run_dir)
    cid = contract_id or run_dir.parent.name
    written = 0

    targets: list[tuple[dict, str, str | None]]
    if all_accept:
        targets = []
        for d in drafts:
            if not d.get("draft_text"):
                continue
            targets.append((d, "accept", d.get("draft_text")))
    else:
        if not rule_id or not decision:
            raise SystemExit("Provide --rule-id and --decision, or --all-accept")
        match = next(
            (d for d in drafts if d.get("playbook_rule_id") == rule_id),
            None,
        )
        if match is None:
            raise SystemExit(f"No draft for rule_id={rule_id}")
        if decision == "accept":
            text = match.get("draft_text")
            if not text:
                raise SystemExit("Cannot accept: draft_text is empty")
            targets = [(match, "accept", text)]
        elif decision == "edit":
            if not final_text:
                raise SystemExit("--final required for edit")
            targets = [(match, "edit", final_text)]
        elif decision == "reject":
            finding = findings.get(rule_id)
            text = final_text or (
                (finding or {}).get("deviation_reason")
                or match.get("draft_text")
                or rule_id
            )
            targets = [(match, "reject", text)]
        else:
            raise SystemExit(f"Unknown decision: {decision}")

    for draft, dec, final in targets:
        rid = draft.get("playbook_rule_id") or "unknown"
        finding = findings.get(rid)
        store.add_decision(
            DecisionRecord(
                clause_text=_clause_context(finding, rid, draft),
                decision=dec,  # type: ignore[arg-type]
                final_text=final or "",
                playbook_rule_id=rid,
                contract_id=cid,
                reasoning=f"decide_cli: {dec} from run {run_dir.name}",
            )
        )
        written += 1
        print(f"  Wrote {dec} for `{rid}`")

    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Accept/Edit/Reject Step 06 drafts into vector memory"
    )
    p.add_argument(
        "--from-out",
        type=Path,
        required=True,
        help="Path to a dry-run out dir (.../latest or timestamped)",
    )
    p.add_argument("--all-accept", action="store_true")
    p.add_argument("--rule-id", default=None)
    p.add_argument(
        "--decision",
        choices=["accept", "edit", "reject"],
        default=None,
    )
    p.add_argument("--final", default=None, help="Final wording (required for edit)")
    p.add_argument("--contract-id", default=None)
    p.add_argument("--persist-dir", type=Path, default=None)
    p.add_argument("--collection", default="decisions")
    p.add_argument(
        "--real-embed",
        action="store_true",
        help="Use MiniLM (FAKE_EMBED=0). Must match the embedder used when writing/searching.",
    )
    args = p.parse_args(argv)

    if args.real_embed:
        os.environ["FAKE_EMBED"] = "0"
        print("Embeddings: MiniLM (FAKE_EMBED=0)")
    else:
        os.environ.setdefault("FAKE_EMBED", "1")

    store = DecisionStore(
        persist_dir=args.persist_dir,
        collection_name=args.collection,
    )
    n = apply_decisions(
        args.from_out,
        store,
        all_accept=args.all_accept,
        rule_id=args.rule_id,
        decision=args.decision,
        final_text=args.final,
        contract_id=args.contract_id,
    )
    print(f"Stored {n} decision(s); store_count={store.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
