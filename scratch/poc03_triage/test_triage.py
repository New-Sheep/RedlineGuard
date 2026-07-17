from __future__ import annotations

import pytest

from scratch._io import CORPUS
from scratch.poc01_extract.extract import extract_pdf
from scratch.poc03_triage.triage import triage_text


@pytest.mark.skipif(
    not (CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf").exists(),
    reason="missing corpus",
)
def test_master_elevated_ip():
    r = extract_pdf(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf")
    card = triage_text(r["text"], r["filename"], r["quality"])
    assert card["kind"] == "ip_license"
    assert card["stakes"] == "do_not_auto_approve"
    assert any("50.1" in t or "Equity" in t for t in card["major_terms"])


@pytest.mark.skipif(
    not (CORPUS / "Startup revised 11-22 patented.pdf").exists(),
    reason="missing corpus",
)
def test_yale_university_sample():
    r = extract_pdf(CORPUS / "Startup revised 11-22 patented.pdf")
    card = triage_text(r["text"], r["filename"], r["quality"])
    assert card["kind"] == "university_license_sample"
    assert card["stakes"] == "do_not_auto_approve"


@pytest.mark.skipif(
    not (CORPUS / "founders-agreement.pdf").exists(),
    reason="missing corpus",
)
def test_founders_template():
    r = extract_pdf(CORPUS / "founders-agreement.pdf")
    card = triage_text(r["text"], r["filename"], r["quality"])
    assert card["kind"] == "founders_template"


@pytest.mark.skipif(
    not (CORPUS / "Tippett 3 Tenancy Agreement 2025-26 BW100.pdf").exists(),
    reason="missing corpus",
)
def test_tippett_skipped_when_poor():
    r = extract_pdf(CORPUS / "Tippett 3 Tenancy Agreement 2025-26 BW100.pdf")
    card = triage_text(r["text"], r["filename"], r["quality"])
    assert r["quality"] == "poor"
    assert card["skipped"] is True
