"""POC 01 — PDF extract + text quality gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python -m scratch.01_extract.extract` and direct script runs
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
    write_text,
)

# Below this after probing early pages → treat as image-only / empty.
_MIN_USEFUL_CHARS = 40
# Stop walking image-heavy PDFs after this many empty pages (+ one peek).
_EARLY_EMPTY_PAGES = 2

IMAGE_ONLY_HINT = (
    "No selectable text found. E-signed or scanned PDFs are often image-only — "
    "RedlineGuard needs a text layer. Use a Sample contract on the upload page, "
    "or OCR/export the PDF to text first."
)


def assess_quality(text: str) -> str:
    """Return 'ok' or 'poor' based on printable / token heuristics."""
    import re

    if not text or len(text.strip()) < 80:
        return "poor"
    sample = text[:8000]
    printable = sum(1 for c in sample if c.isprintable() or c in "\n\r\t")
    ratio = printable / max(len(sample), 1)
    tokens = sample.split()
    if not tokens:
        return "poor"
    single_char = sum(1 for t in tokens if len(t) == 1)
    single_ratio = single_char / len(tokens)
    avg_len = sum(len(t) for t in tokens) / len(tokens)

    def looks_like_word(tok: str) -> bool:
        letters = sum(c.isalpha() for c in tok)
        if letters < 2:
            return False
        if letters / len(tok) < 0.75:
            return False
        if not re.search(r"[aeiouAEIOU]", tok):
            return False
        return True

    good_ratio = sum(1 for t in tokens if looks_like_word(t)) / len(tokens)

    # Scanned garbage: few vowel-y letter tokens even if avg length looks fine
    if ratio < 0.85 or single_ratio > 0.35 or avg_len < 2.8 or good_ratio < 0.55:
        return "poor"
    return "ok"


def _joined_len(parts: list[str]) -> int:
    return len("\n".join(parts).strip())


def _extract_pdf_pypdf(path: Path) -> tuple[str, int, bool]:
    """Fast text-layer extract. Returns (text, page_count, image_only_suspected)."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    page_count = len(reader.pages)
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        parts.append(page.extract_text() or "")
        if i + 1 >= _EARLY_EMPTY_PAGES and _joined_len(parts) < _MIN_USEFUL_CHARS:
            # One more peek before giving up (cover-page edge case)
            if i + 1 < page_count:
                parts.append(reader.pages[i + 1].extract_text() or "")
            if _joined_len(parts) < _MIN_USEFUL_CHARS:
                return "", page_count, True
    text = "\n".join(parts)
    if _joined_len(parts) < _MIN_USEFUL_CHARS:
        return text, page_count, True
    return text, page_count, False


def _extract_pdf_pdfplumber(path: Path) -> tuple[str, int, bool]:
    """Fallback extract with early abort on char-less (image) pages."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        empty_streak = 0
        for i, page in enumerate(pdf.pages):
            # page.chars is cheaper than full layout extract when empty
            n_chars = len(page.chars or [])
            if n_chars == 0:
                parts.append("")
                empty_streak += 1
                if (
                    empty_streak >= _EARLY_EMPTY_PAGES
                    and _joined_len(parts) < _MIN_USEFUL_CHARS
                ):
                    if i + 1 < page_count:
                        nxt = pdf.pages[i + 1]
                        if len(nxt.chars or []) == 0:
                            return "", page_count, True
                        parts.append(nxt.extract_text() or "")
                        if _joined_len(parts) < _MIN_USEFUL_CHARS:
                            return "", page_count, True
                    else:
                        return "", page_count, True
                continue
            empty_streak = 0
            parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    return text, page_count, _joined_len(parts) < _MIN_USEFUL_CHARS


def extract_pdf(path: Path | str) -> dict:
    """Extract text from PDF or plain .txt; assess quality.

    Image-only / e-sign PDFs abort after a few empty pages so analyze fails
    in seconds instead of walking every page with pdfplumber (~45s+).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    image_only = False
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        page_count = 1
    elif suffix == ".pdf":
        text = ""
        page_count = 0
        try:
            text, page_count, image_only = _extract_pdf_pypdf(path)
        except Exception:
            text, page_count, image_only = _extract_pdf_pdfplumber(path)
        if not text.strip() and not image_only:
            # pypdf returned empty without early flag — try plumber once
            try:
                text, page_count, image_only = _extract_pdf_pdfplumber(path)
            except Exception:
                pass
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    quality = assess_quality(text)
    out = {
        "source": str(path.resolve()),
        "filename": path.name,
        "page_count": page_count,
        "char_count": len(text),
        "quality": quality,
        "text": text,
        "image_only_suspected": bool(image_only or (not text.strip() and suffix == ".pdf")),
    }
    if out["image_only_suspected"]:
        out["hint"] = IMAGE_ONLY_HINT
    return out


def preview_markdown(result: dict, max_lines: int = 80) -> str:
    lines = result["text"].splitlines()
    head = "\n".join(lines[:max_lines])
    banner = (
        f"# Step 01 — Extract preview\n\n"
        f"- **File:** `{result['filename']}`\n"
        f"- **Pages:** {result['page_count']}\n"
        f"- **Chars:** {result['char_count']}\n"
        f"- **Quality:** **{result['quality']}**\n\n"
    )
    if result.get("image_only_suspected"):
        banner += f"> {IMAGE_ONLY_HINT}\n\n"
    elif result["quality"] == "poor":
        banner += (
            "> Text quality looks poor (possible scan/OCR). "
            "Do not auto-approve or deep-review until human/OCR pass.\n\n"
        )
    banner += "## First lines\n\n```\n" + head + "\n```\n"
    if len(lines) > max_lines:
        banner += f"\n_… truncated ({len(lines) - max_lines} more lines in 01_raw.txt)_\n"
    return banner


def run(path: Path | str, run_dir: Path | None = None) -> dict:
    path = Path(path)
    result = extract_pdf(path)
    out = ensure_run_dir(run_dir, path)
    write_json(
        out / "01_meta.json",
        {k: v for k, v in result.items() if k != "text"},
    )
    write_text(out / "01_raw.txt", result["text"])
    write_text(out / "01_preview.md", preview_markdown(result))
    sync_latest(out)
    return {**result, "run_dir": str(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POC 01: extract PDF text + quality")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"),
        help="PDF or txt path",
    )
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    print_banner("STEP 01", "EXTRACT")
    result = run(args.path, args.run_dir)
    print(f"Source:   {result['filename']}")
    print(f"Pages:    {result['page_count']}")
    print(f"Chars:    {result['char_count']}")
    print(f"Quality:  {result['quality']}")
    if result.get("image_only_suspected"):
        print(f"Hint:     {IMAGE_ONLY_HINT}")
    print(f"Artifacts:{result['run_dir']}")
    print("\n--- preview (first 15 lines) ---")
    for line in result["text"].splitlines()[:15]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
