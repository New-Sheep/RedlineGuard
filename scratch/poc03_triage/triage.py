"""POC 03 — Friday 5pm triage card (heuristic)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
_ROOT = _SCRATCH.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scratch._io import (  # noqa: E402
    CORPUS,
    ensure_run_dir,
    print_banner,
    sync_latest,
    write_json,
    write_skipped,
    write_text,
)
from scratch.poc01_extract.extract import extract_pdf  # noqa: E402


def _first(text: str, n: int = 6000) -> str:
    return text[:n]


def classify_kind(text: str) -> str:
    head = _first(text, 8000)
    if re.search(r"Founders['’] Agreement Overview|Conversation Guide|Model Founders", head, re.I):
        return "founders_template"
    if re.search(r"YALE UNIVERSITY|Start-up License agreement|Non-Negotiable", head, re.I):
        return "university_license_sample"
    if re.search(
        r"INTELLECTUAL PROPERTY LICENSE AND DEVELOPMENT|Summary of Major Terms|Leonhardt",
        head,
        re.I,
    ):
        return "ip_license"
    if re.search(r"tenancy|assured shorthold|Housing Act|landlord|tenant", head, re.I):
        return "tenancy"
    if re.search(r"mutual\s+non-?disclosure|\bNDA\b", head, re.I):
        return "nda"
    return "unknown"


def stakes_for(kind: str, text: str) -> str:
    if kind in ("ip_license", "university_license_sample"):
        return "do_not_auto_approve"
    if kind == "founders_template":
        return "elevated"  # wrong queue item — don't treat as vendor NDA
    if kind == "tenancy":
        return "elevated"
    if re.search(r"50\.1\s*%|change of control fee|anti-dilution", text, re.I):
        return "do_not_auto_approve"
    return "routine_queue"


def extract_major_terms(text: str) -> list[str]:
    terms: list[str] = []
    # Pull bullets under Summary of Major Terms when present
    m = re.search(
        r"Summary of Major Terms\s*(.+?)(?:NOW, THEREFORE|1\.\s*Definitions)",
        text,
        re.I | re.S,
    )
    block = m.group(1) if m else text[:3500]
    patterns = [
        (r"50\.1\s*%[^\n.]{0,80}", "Equity/control: 50.1% ownership mentioned"),
        (r"9\s*%\s*seed[^\n.]{0,60}", "Accelerator seed equity ~9%"),
        (r"anti-dilution floor[^\n.]{0,40}", "Anti-dilution floor present"),
        (r"\$\s*50,000[^\n.]{0,80}", "$50,000 license fee trigger"),
        (r"1\s*%\s*change of control[^\n.]{0,40}", "1% change-of-control fee"),
        (r"laws of the State of California|laws of California", "Governing law: California"),
        (r"laws of the State of Connecticut|Connecticut", "Governing law: Connecticut (Yale sample)"),
        (r"Non-Negotiable", "Marked Non-Negotiable"),
        (r"shall indemnify[^\n.]{0,60}", "Indemnity obligation language present"),
    ]
    seen: set[str] = set()
    for pat, label in patterns:
        if re.search(pat, block, re.I) and label not in seen:
            terms.append(label)
            seen.add(label)
    return terms


def render_triage_md(card: dict) -> str:
    bullets = "\n".join(f"- {t}" for t in card.get("major_terms") or ["_(none extracted)_"])
    warning = ""
    if card["stakes"] == "do_not_auto_approve":
        warning = (
            "\n> **Friday 5pm warning:** This does **not** look like a routine NDA/order form. "
            "Do not rubber-stamp.\n"
        )
    elif card["kind"] == "founders_template":
        warning = (
            "\n> **Queue fit:** This looks like a teaching/template founders pack, "
            "not counterparty commercial paper.\n"
        )
    return (
        f"# Step 03 — Triage card (Sarah view)\n\n"
        f"- **Document kind:** `{card['kind']}`\n"
        f"- **Stakes:** `{card['stakes']}`\n"
        f"- **Source:** `{card.get('source_name', '')}`\n"
        f"{warning}\n"
        f"## Shape of the deal / notable signals\n\n{bullets}\n"
    )


def triage_text(text: str, source_name: str = "input", quality: str = "ok") -> dict:
    if quality == "poor":
        return {
            "source_name": source_name,
            "kind": "unreadable",
            "stakes": "elevated",
            "major_terms": [],
            "skipped": True,
            "reason": "Text quality poor — cannot triage reliably (possible scan). Needs OCR/human.",
        }
    kind = classify_kind(text)
    stakes = stakes_for(kind, text)
    terms = extract_major_terms(text)
    return {
        "source_name": source_name,
        "kind": kind,
        "stakes": stakes,
        "major_terms": terms,
        "skipped": False,
        "reason": None,
    }


def run(
    path: Path | str | None = None,
    *,
    text: str | None = None,
    source_name: str = "input",
    quality: str = "ok",
    run_dir: Path | None = None,
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

    card = triage_text(text, source_name, quality)
    if card.get("skipped"):
        write_skipped(out, "03", card["reason"])
        write_json(out / "03_triage.json", card)
        sync_latest(out)
        return {**card, "run_dir": str(out)}

    write_json(out / "03_triage.json", card)
    write_text(out / "03_triage.md", render_triage_md(card))
    sync_latest(out)
    return {**card, "run_dir": str(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POC 03: triage card")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"),
    )
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--from-out", type=Path, default=None)
    args = parser.parse_args(argv)

    print_banner("STEP 03", "TRIAGE")
    if args.from_out:
        meta = {}
        meta_path = Path(args.from_out) / "01_meta.json"
        if meta_path.exists():
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        text = (Path(args.from_out) / "01_raw.txt").read_text(encoding="utf-8", errors="replace")
        result = run(
            text=text,
            source_name=meta.get("filename", "from-out"),
            quality=meta.get("quality", "ok"),
            run_dir=args.from_out,
        )
    else:
        result = run(args.path, run_dir=args.run_dir)

    print(f"Kind:    {result.get('kind')}")
    print(f"Stakes:  {result.get('stakes')}")
    if result.get("skipped"):
        print(f"Skipped: {result.get('reason')}")
    else:
        print("Major terms:")
        for t in result.get("major_terms") or []:
            print(f"  - {t}")
    print(f"Artifacts: {result['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
