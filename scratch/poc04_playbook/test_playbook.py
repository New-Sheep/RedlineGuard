from __future__ import annotations

import pytest

from scratch._io import CORPUS, PLAYBOOK_PATH
from scratch.poc01_extract.extract import extract_pdf
from scratch.poc04_playbook.playbook import Finding, compare, load_playbook


def test_playbook_loads():
    pb = load_playbook(PLAYBOOK_PATH)
    assert pb["rules"]
    assert any(r["id"] == "equity_control_cap" for r in pb["rules"])


@pytest.mark.skipif(
    not (CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf").exists(),
    reason="missing corpus",
)
def test_master_hits_equity_rule():
    r = extract_pdf(CORPUS / "MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf")
    report = compare(r["text"])
    ids = {f.playbook_rule_id for f in report.reviews}
    assert "equity_control_cap" in ids
    # no fallback on equity_control → REQUIRES_HUMAN
    equity = next(f for f in report.reviews if f.playbook_rule_id == "equity_control_cap")
    assert equity.status == "REQUIRES_HUMAN"


@pytest.mark.skipif(
    not (CORPUS / "Startup revised 11-22 patented.pdf").exists(),
    reason="missing corpus",
)
def test_yale_hits_non_negotiable_or_indemnity():
    r = extract_pdf(CORPUS / "Startup revised 11-22 patented.pdf")
    report = compare(r["text"])
    ids = {f.playbook_rule_id for f in report.reviews}
    assert ids & {"non_negotiable_stamp", "uncapped_or_broad_indemnity", "governing_law_preferred"}


def test_unknown_topic_not_flagged():
    text = "The parties agree to meet on Tuesdays for pizza."
    report = compare(text)
    assert report.reviews == []


def test_finding_with_fallback_is_flagged():
    text = "Licensee shall indemnify and hold harmless Yale from all claims."
    report = compare(text)
    assert any(f.status == "FLAGGED" and f.suggested_counter_proposal for f in report.reviews)


def test_pydantic_rejects_bad_status():
    with pytest.raises(Exception):
        Finding(
            clause_name="x",
            status="YES",  # type: ignore[arg-type]
            playbook_rule_id="r",
            deviation_reason="n/a",
        )
