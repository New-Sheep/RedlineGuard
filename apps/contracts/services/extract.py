"""Extract service — PDF / DOCX / TXT."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.contracts.models import Contract
from scratch.poc01_extract.extract import IMAGE_ONLY_HINT, assess_quality, extract_pdf


def resolve_contract_path(contract: Contract) -> Path:
    if contract.source == Contract.Source.SAMPLE:
        if not contract.sample_key:
            raise ValueError("sample_key required for sample contracts")
        path = Path(settings.SCRATCH_CORPUS_DIR) / contract.sample_key
        path = path.resolve()
        corpus = Path(settings.SCRATCH_CORPUS_DIR).resolve()
        if not str(path).startswith(str(corpus)) or not path.is_file():
            raise FileNotFoundError(f"Sample not found: {contract.sample_key}")
        return path

    if not contract.file:
        raise ValueError("Uploaded contract has no file")
    return Path(contract.file.path)


def _extract_txt(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "text": text,
        "quality": assess_quality(text),
        "page_count": 1,
        "char_count": len(text),
        "hint": "",
    }


def _extract_docx(path: Path) -> dict:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError(
            "DOCX support requires python-docx. pip install python-docx"
        ) from exc
    try:
        doc = Document(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not read DOCX: {exc}") from exc
    parts = [p.text for p in doc.paragraphs if (p.text or "").strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts).strip()
    return {
        "text": text,
        "quality": assess_quality(text) if text else "poor",
        "page_count": max(1, len(doc.paragraphs) // 40),
        "char_count": len(text),
        "hint": IMAGE_ONLY_HINT if not text else "",
    }


def extract_path(path: Path) -> dict:
    """Dispatch by suffix."""
    suf = path.suffix.lower()
    if suf == ".txt":
        return _extract_txt(path)
    if suf == ".docx":
        return _extract_docx(path)
    return extract_pdf(path)


def run_extract(contract: Contract) -> Contract:
    """Extract text into the Contract row. Sync; updates status."""
    try:
        path = resolve_contract_path(contract)
        result = extract_path(path)
        contract.extracted_text = result.get("text") or ""
        contract.quality = result.get("quality") or ""
        contract.page_count = int(result.get("page_count") or 0)
        contract.char_count = int(result.get("char_count") or 0)
        if not (contract.extracted_text or "").strip():
            contract.status = Contract.Status.FAILED
            contract.error_message = result.get("hint") or IMAGE_ONLY_HINT
        else:
            contract.status = Contract.Status.EXTRACTED
            contract.error_message = ""
    except Exception as exc:  # noqa: BLE001 — surface to UI
        contract.status = Contract.Status.FAILED
        contract.error_message = str(exc)
    contract.save()
    return contract
