from __future__ import annotations

from pathlib import Path

import pytest

from scratch._io import CORPUS
from scratch.poc01_extract.extract import assess_quality, extract_pdf

MASTER = CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf"
YALE = CORPUS / "Startup revised 11-22 patented.pdf"
TIPPETT = CORPUS / "Tippett 3 Tenancy Agreement 2025-26 BW100.pdf"
FOUNDERS = CORPUS / "founders-agreement.pdf"


@pytest.mark.skipif(not MASTER.exists(), reason="corpus PDF missing")
def test_master_extract_ok():
    r = extract_pdf(MASTER)
    assert r["quality"] == "ok"
    assert r["page_count"] >= 1
    assert "Summary of Major Terms" in r["text"]


@pytest.mark.skipif(not YALE.exists(), reason="corpus PDF missing")
def test_yale_extract_ok():
    r = extract_pdf(YALE)
    assert r["quality"] == "ok"
    assert "YALE UNIVERSITY" in r["text"] or "YALE" in r["text"]


@pytest.mark.skipif(not TIPPETT.exists(), reason="corpus PDF missing")
def test_tippett_quality_poor():
    r = extract_pdf(TIPPETT)
    assert r["quality"] == "poor"


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_pdf(CORPUS / "no-such-file.pdf")


def test_assess_quality_empty():
    assert assess_quality("") == "poor"
    assert assess_quality("a b c d e f g h") == "poor"
