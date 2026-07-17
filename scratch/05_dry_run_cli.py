"""POC 05 — full pipeline: extract → security → triage → playbook → memory → draft.

Prints each step as it finishes and writes scratch/out/<stem>/<run_id>/journey.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("FAKE_EMBED", "1")

from scratch._io import (
    CORPUS,
    new_run_dir,
    print_banner,
    sync_latest,
    write_json,
    write_skipped,
    write_text,
)
from scratch.poc01_extract.extract import run as run_extract
from scratch.poc02_security.security import run as run_security
from scratch.poc03_triage.triage import run as run_triage
from scratch.poc04_playbook.playbook import run as run_playbook
from scratch.poc06_memory.store import DecisionStore
from scratch.poc07_draft.engine import FakeDraftEngine


def _retrieve_for_findings(
    findings: list[dict],
    store: DecisionStore,
    top_k: int = 3,
) -> list[dict]:
    rows: list[dict] = []
    for f in findings:
        query = (
            f"[{f.get('playbook_rule_id')}] {f.get('deviation_reason', '')} "
            f"{f.get('suggested_counter_proposal') or ''}"
        ).strip()
        hits = store.search_precedents(
            query,
            top_k=top_k,
            playbook_rule_id=f.get("playbook_rule_id"),
        )
        note = None
        if f.get("status") == "REQUIRES_HUMAN" and any(
            h.record.decision in ("accept", "edit") for h in hits
        ):
            note = "Prior human decision available - would draft from memory"
        rows.append(
            {
                "playbook_rule_id": f.get("playbook_rule_id"),
                "finding_status": f.get("status"),
                "suggested_counter_proposal": f.get("suggested_counter_proposal"),
                "deviation_reason": f.get("deviation_reason"),
                "note": note,
                "precedents": [
                    {
                        "id": h.record.id,
                        "decision": h.record.decision,
                        "final_text": h.record.final_text,
                        "playbook_rule_id": h.record.playbook_rule_id,
                        "contract_id": h.record.contract_id,
                        "distance": h.distance,
                        "reasoning": h.record.reasoning,
                    }
                    for h in hits
                ],
            }
        )
    return rows


def _draft_for_findings(
    findings: list[dict],
    memory_rows: list[dict],
    engine: FakeDraftEngine | None = None,
) -> list[dict]:
    engine = engine or FakeDraftEngine()
    by_rule = {r.get("playbook_rule_id"): r for r in memory_rows}
    drafts: list[dict] = []
    for f in findings:
        row = by_rule.get(f.get("playbook_rule_id")) or {}
        result = engine.draft(f, row.get("precedents") or [])
        drafts.append(result.model_dump())
    return drafts


def render_precedents_md(rows: list[dict]) -> str:
    lines = ["# Step 05 - Memory (precedents)\n"]
    if not rows:
        lines.append("_No findings to query, or memory empty._\n")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            f"## Rule `{row.get('playbook_rule_id')}` "
            f"[{row.get('finding_status')}]"
        )
        if row.get("note"):
            lines.append(f"> {row['note']}")
        prec = row.get("precedents") or []
        if not prec:
            lines.append("- _(no precedents retrieved)_")
        for i, p in enumerate(prec, 1):
            snippet = (p.get("final_text") or "")[:200]
            lines.append(
                f"- **{i}.** `{p.get('decision')}` from `{p.get('contract_id')}` "
                f"(dist={p.get('distance')})"
            )
            lines.append(f"  - {snippet}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_drafts_md(drafts: list[dict]) -> str:
    lines = ["# Step 06 - Draft (FAKE_LLM)\n"]
    if not drafts:
        lines.append("_No drafts._\n")
        return "\n".join(lines)
    for d in drafts:
        snippet = (d.get("draft_text") or "")[:240] or "_(none)_"
        lines.append(
            f"## `{d.get('playbook_rule_id')}` [{d.get('finding_status')}] "
            f"- source=`{d.get('draft_source')}`"
        )
        lines.append(f"- {d.get('rationale')}")
        lines.append(f"- Draft: {snippet}")
        lines.append("")
    return "\n".join(lines) + "\n"


def build_journey_md(
    source: Path,
    run_dir: Path,
    extract: dict,
    security: dict,
    triage: dict,
    playbook: dict,
    memory: dict | None = None,
    drafts: dict | None = None,
) -> str:
    parts = [
        f"# Journey - `{source.name}`\n",
        f"Run directory: `{run_dir}`\n",
        "## Step 01 - Extract\n",
        f"- Pages: {extract.get('page_count')}",
        f"- Chars: {extract.get('char_count')}",
        f"- Quality: **{extract.get('quality')}**\n",
        "## Step 02 - Security\n",
        f"- Verdict: **{'HALT' if security.get('halt') else 'PASS'}**",
        f"- {security.get('summary')}\n",
        "## Step 03 - Triage\n",
    ]
    if triage.get("skipped"):
        parts.append(f"- Skipped: {triage.get('reason')}\n")
    else:
        parts.append(f"- Kind: `{triage.get('kind')}`")
        parts.append(f"- Stakes: `{triage.get('stakes')}`")
        parts.append("- Major terms:")
        for t in triage.get("major_terms") or []:
            parts.append(f"  - {t}")
        parts.append("")

    parts.append("## Step 04 - Playbook\n")
    if playbook.get("skipped"):
        parts.append(f"- Skipped: {playbook.get('reason')}\n")
    else:
        report = playbook.get("report") or {}
        parts.append(f"- Risk score: {report.get('overall_risk_score')}")
        parts.append(f"- Findings: {len(report.get('reviews') or [])}")
        for f in report.get("reviews") or []:
            parts.append(
                f"  - [{f['status']}] `{f['playbook_rule_id']}` - {f['deviation_reason']}"
            )
        parts.append("")

    parts.append("## Step 05 - Memory\n")
    if not memory or memory.get("skipped"):
        parts.append(f"- Skipped: {(memory or {}).get('reason', 'n/a')}\n")
    else:
        rows = memory.get("rows") or []
        total_hits = sum(len(r.get("precedents") or []) for r in rows)
        parts.append(f"- Precedent hits: **{total_hits}** across {len(rows)} findings")
        for r in rows:
            n = len(r.get("precedents") or [])
            extra = f" - {r['note']}" if r.get("note") else ""
            parts.append(
                f"  - `{r.get('playbook_rule_id')}` [{r.get('finding_status')}]: "
                f"{n} precedent(s){extra}"
            )
        parts.append("")

    parts.append("## Step 06 - Draft\n")
    if not drafts or drafts.get("skipped"):
        parts.append(f"- Skipped: {(drafts or {}).get('reason', 'n/a')}\n")
    else:
        items = drafts.get("drafts") or []
        by_src: dict[str, int] = {}
        for d in items:
            src = d.get("draft_source") or "none"
            by_src[src] = by_src.get(src, 0) + 1
        parts.append(
            f"- Drafts: **{len(items)}** "
            f"(memory={by_src.get('memory_precedent', 0)}, "
            f"playbook={by_src.get('playbook_fallback', 0)}, "
            f"none={by_src.get('none', 0)})"
        )
        for d in items:
            snippet = (d.get("draft_text") or "")[:120] or "_(none)_"
            parts.append(
                f"  - `{d.get('playbook_rule_id')}` source=`{d.get('draft_source')}`: "
                f"{snippet}"
            )
        parts.append("")

    parts.append(
        "\n---\n_Generated by scratch dry-run "
        "(playbook + vector memory + FAKE_LLM draft)._\n"
    )
    return "\n".join(parts)


def run_pipeline(
    path: Path,
    *,
    store: DecisionStore | None = None,
    memory_collection: str = "decisions",
) -> Path:
    path = Path(path)
    run_dir = new_run_dir(path)
    store = store or DecisionStore(collection_name=memory_collection)

    print_banner("STEP 01", "EXTRACT")
    extract = run_extract(path, run_dir)
    print(f"Quality={extract['quality']} pages={extract['page_count']} chars={extract['char_count']}")

    print_banner("STEP 02", "SECURITY")
    security = run_security(
        text=extract["text"],
        source_name=path.name,
        run_dir=run_dir,
    )
    print(f"Verdict={'HALT' if security['halt'] else 'PASS'} | {security['summary']}")

    print_banner("STEP 03", "TRIAGE")
    if security.get("halt"):
        write_skipped(
            run_dir,
            "03",
            "Security halt - triage skipped (hostile input must not get a clean review card).",
        )
        triage = {
            "skipped": True,
            "reason": "security halt",
            "kind": None,
            "stakes": None,
            "major_terms": [],
        }
        print("Skipped: security halt")
    else:
        triage = run_triage(
            text=extract["text"],
            source_name=path.name,
            quality=extract["quality"],
            run_dir=run_dir,
        )
        if triage.get("skipped"):
            print(f"Skipped: {triage.get('reason')}")
        else:
            print(f"Kind={triage.get('kind')} stakes={triage.get('stakes')}")

    print_banner("STEP 04", "PLAYBOOK")
    playbook = run_playbook(
        text=extract["text"],
        source_name=path.name,
        quality=extract["quality"],
        halt=bool(security.get("halt")),
        run_dir=run_dir,
    )
    if playbook.get("skipped"):
        print(f"Skipped: {playbook.get('reason')}")
    else:
        n = len((playbook.get("report") or {}).get("reviews") or [])
        print(f"Findings={n}")

    print_banner("STEP 05", "MEMORY")
    memory: dict
    findings: list[dict] = []
    if security.get("halt"):
        write_skipped(run_dir, "05", "Security halt - memory retrieval skipped (no pollution).")
        memory = {"skipped": True, "reason": "security halt", "rows": []}
        print("Skipped: security halt (no memory write/read pollution)")
    elif playbook.get("skipped"):
        write_skipped(run_dir, "05", f"Playbook skipped - {playbook.get('reason')}")
        memory = {"skipped": True, "reason": playbook.get("reason"), "rows": []}
        print(f"Skipped: {playbook.get('reason')}")
    else:
        findings = (playbook.get("report") or {}).get("reviews") or []
        rows = _retrieve_for_findings(findings, store)
        memory = {"skipped": False, "rows": rows, "store_count": store.count()}
        write_json(run_dir / "05_precedents.json", memory)
        write_text(run_dir / "05_precedents.md", render_precedents_md(rows))
        total_hits = sum(len(r.get("precedents") or []) for r in rows)
        print(f"Precedents retrieved={total_hits} store_count={store.count()}")

    print_banner("STEP 06", "DRAFT (FAKE_LLM)")
    drafts: dict
    if security.get("halt"):
        write_skipped(run_dir, "06", "Security halt - draft skipped (no pollution).")
        drafts = {"skipped": True, "reason": "security halt", "drafts": []}
        print("Skipped: security halt")
    elif memory.get("skipped") or not findings:
        reason = memory.get("reason") if memory.get("skipped") else "no findings"
        write_skipped(run_dir, "06", f"Draft skipped - {reason}")
        drafts = {"skipped": True, "reason": reason, "drafts": []}
        print(f"Skipped: {reason}")
    else:
        draft_list = _draft_for_findings(findings, memory.get("rows") or [])
        drafts = {"skipped": False, "drafts": draft_list, "engine": "FakeDraftEngine"}
        write_json(run_dir / "06_drafts.json", drafts)
        write_text(run_dir / "06_drafts.md", render_drafts_md(draft_list))
        mem_n = sum(1 for d in draft_list if d.get("draft_source") == "memory_precedent")
        pb_n = sum(1 for d in draft_list if d.get("draft_source") == "playbook_fallback")
        print(f"Drafts={len(draft_list)} memory_precedent={mem_n} playbook_fallback={pb_n}")

    journey = build_journey_md(
        path, run_dir, extract, security, triage, playbook, memory, drafts
    )
    write_text(run_dir / "journey.md", journey)
    sync_latest(run_dir)

    print_banner("DONE", f"Journey written -> {run_dir / 'journey.md'}")
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full RedlineGuard scratch dry-run")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"),
    )
    parser.add_argument(
        "--all-corpus",
        action="store_true",
        help="Run every PDF/txt in data/scratch_corpus",
    )
    parser.add_argument("--collection", default="decisions")
    parser.add_argument(
        "--real-embed",
        action="store_true",
        help="Use MiniLM (FAKE_EMBED=0). Requires sentence-transformers. Reset Chroma if switching from hash.",
    )
    args = parser.parse_args(argv)

    if args.real_embed:
        os.environ["FAKE_EMBED"] = "0"
        print("Embeddings: MiniLM (FAKE_EMBED=0)")
    else:
        os.environ.setdefault("FAKE_EMBED", "1")

    store = DecisionStore(collection_name=args.collection)

    if args.all_corpus:
        files = sorted(CORPUS.glob("*.pdf")) + sorted(CORPUS.glob("*.txt"))
        for f in files:
            print("\n" + "#" * 60)
            print(f"# CORPUS FILE: {f.name}")
            print("#" * 60)
            run_pipeline(f, store=store, memory_collection=args.collection)
        return 0

    run_pipeline(Path(args.path), store=store, memory_collection=args.collection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
