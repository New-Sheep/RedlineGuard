"""Extract service — wraps scratch poc01 (no duplicate pdfplumber logic)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from apps.contracts.models import Contract
from scratch.poc01_extract.extract import extract_pdf


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


def run_extract(contract: Contract) -> Contract:
    """Extract text into the Contract row. Sync; updates status."""
    try:
        path = resolve_contract_path(contract)
        result = extract_pdf(path)
        contract.extracted_text = result.get("text") or ""
        contract.quality = result.get("quality") or ""
        contract.page_count = int(result.get("page_count") or 0)
        contract.char_count = int(result.get("char_count") or 0)
        contract.status = Contract.Status.EXTRACTED
        contract.error_message = ""
    except Exception as exc:  # noqa: BLE001 — surface to UI
        contract.status = Contract.Status.FAILED
        contract.error_message = str(exc)
    contract.save()
    return contract
