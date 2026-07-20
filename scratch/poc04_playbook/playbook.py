"""POC 04 — playbook load + heuristic compare (FAKE / no LLM).

L0 regex lives in apps.review.services.compare.layer_rule; this module keeps
the scratch CLI + ContractReviewReport shape and scores with BASE=0.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

_SCRATCH = Path(__file__).resolve().parents[1]
_ROOT = _SCRATCH.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scratch._io import (  # noqa: E402
    CORPUS,
    PLAYBOOK_PATH,
    ensure_run_dir,
    print_banner,
    sync_latest,
    write_json,
    write_skipped,
    write_text,
)
from scratch.poc01_extract.extract import extract_pdf  # noqa: E402
from apps.review.services.compare.layer_rule import (  # noqa: E402
    first_match_span,
    layer_rule,
)
from apps.review.services.compare.merge import merge_candidates  # noqa: E402
from apps.review.services.compare.score import score_findings  # noqa: E402

Status = Literal["APPROVED", "FLAGGED", "REQUIRES_HUMAN"]


class Finding(BaseModel):
    clause_name: str
    status: Status
    playbook_rule_id: str
    deviation_reason: str
    suggested_counter_proposal: Optional[str] = None
    severity: str = "medium"
    clause_excerpt: str = ""
    start_offset: int = 0
    end_offset: int = 0


class ContractReviewReport(BaseModel):
    overall_risk_score: int = Field(ge=0, le=100)
    reviews: list[Finding]


def load_playbook(path: Path | None = None) -> dict:
    path = path or PLAYBOOK_PATH
    return json.loads(path.read_text(encoding="utf-8"))


# Back-compat alias used by older scratch helpers
_first_match_span = first_match_span


def compare(text: str, playbook: dict | None = None) -> ContractReviewReport:
    """L0-only compare for scratch CLI (semantic lives in compare_layered)."""
    playbook = playbook or load_playbook()
    rule_hits = layer_rule(text, playbook)
    layered = merge_candidates(rule_hits, [])
    score, _breakdown = score_findings(layered)
    findings = [
        Finding(
            clause_name=f.clause_name,
            status=f.status,
            playbook_rule_id=f.playbook_rule_id,
            deviation_reason=f.deviation_reason,
            suggested_counter_proposal=f.suggested_counter_proposal,
            severity=f.severity,
            clause_excerpt=f.clause_excerpt,
            start_offset=f.start_offset,
            end_offset=f.end_offset,
        )
        for f in layered
    ]
    return ContractReviewReport(overall_risk_score=score, reviews=findings)


def render_findings_md(report: ContractReviewReport, source_name: str) -> str:
    lines = [
        "# Step 04 — Playbook findings\n",
        f"- **Source:** `{source_name}`",
        f"- **Overall risk score (heuristic):** {report.overall_risk_score}/100",
        f"- **Findings:** {len(report.reviews)}\n",
    ]
    if not report.reviews:
        lines.append("_No playbook rules matched. (Closed-book: unlisted topics stay quiet.)_\n")
        return "\n".join(lines)

    for i, f in enumerate(report.reviews, 1):
        lines.append(f"## {i}. {f.clause_name} — `{f.status}` ({f.severity})")
        lines.append(f"- **Rule:** `{f.playbook_rule_id}`")
        lines.append(f"- **Why:** {f.deviation_reason}")
        if f.suggested_counter_proposal:
            lines.append(f"- **Suggested counter:** {f.suggested_counter_proposal}")
        else:
            lines.append("- **Suggested counter:** _(none — REQUIRES_HUMAN)_")
        lines.append("")
    return "\n".join(lines) + "\n"


def run(
    path: Path | str | None = None,
    *,
    text: str | None = None,
    source_name: str = "input",
    quality: str = "ok",
    halt: bool = False,
    run_dir: Path | None = None,
    playbook_path: Path | None = None,
) -> dict:
    if text is None:
        path = Path(path)  # type: ignore[arg-type]
        extracted = extract_pdf(path)
        text = extracted["text"]
        quality = extracted["quality"]
        source_name = path.name
        out = ensure_run_dir(run_dir, path)
    else:
        out = ensure_run_dir(run_dir, source_name)

    if quality == "poor":
        write_skipped(out, "04", "Text quality poor - playbook compare skipped.")
        sync_latest(out)
        return {"skipped": True, "reason": "poor quality", "run_dir": str(out)}
    if halt:
        write_skipped(out, "04", "Security halt - playbook compare skipped.")
        sync_latest(out)
        return {"skipped": True, "reason": "security halt", "run_dir": str(out)}

    playbook = load_playbook(playbook_path)
    report = compare(text, playbook)
    payload = report.model_dump()
    write_json(out / "04_findings.json", payload)
    write_text(out / "04_findings.md", render_findings_md(report, source_name))
    sync_latest(out)
    return {
        "skipped": False,
        "source_name": source_name,
        "report": payload,
        "run_dir": str(out),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POC 04: playbook heuristic compare")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"),
    )
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--from-out", type=Path, default=None)
    args = parser.parse_args(argv)

    print_banner("STEP 04", "PLAYBOOK COMPARE")
    if args.from_out:
        import json as _json

        meta = {}
        mp = Path(args.from_out) / "01_meta.json"
        if mp.exists():
            meta = _json.loads(mp.read_text(encoding="utf-8"))
        sec = {}
        sp = Path(args.from_out) / "02_security.json"
        if sp.exists():
            sec = _json.loads(sp.read_text(encoding="utf-8"))
        text = (Path(args.from_out) / "01_raw.txt").read_text(encoding="utf-8", errors="replace")
        result = run(
            text=text,
            source_name=meta.get("filename", "from-out"),
            quality=meta.get("quality", "ok"),
            halt=bool(sec.get("halt")),
            run_dir=args.from_out,
        )
    else:
        result = run(args.path, run_dir=args.run_dir)

    if result.get("skipped"):
        print(f"Skipped: {result.get('reason')}")
    else:
        report = result["report"]
        print(f"Risk score: {report['overall_risk_score']}")
        print(f"Findings:   {len(report['reviews'])}")
        for f in report["reviews"]:
            print(f"  - [{f['status']}] {f['playbook_rule_id']}: {f['deviation_reason'][:90]}...")
    print(f"Artifacts: {result['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
