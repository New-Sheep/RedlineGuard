"""Unit tests for FakeDraftEngine."""

from __future__ import annotations

from scratch.poc06_memory.models import DecisionRecord, PrecedentHit
from scratch.poc07_draft.engine import FakeDraftEngine


def test_precedent_wins_over_playbook():
    engine = FakeDraftEngine()
    finding = {
        "playbook_rule_id": "governing_law_preferred",
        "status": "FLAGGED",
        "suggested_counter_proposal": "PLAYBOOK FALLBACK TEXT",
    }
    hits = [
        PrecedentHit(
            record=DecisionRecord(
                id="p1",
                clause_text="law",
                decision="accept",
                final_text="MEMORY DRAFT TEXT",
                playbook_rule_id="governing_law_preferred",
            ),
            distance=0.1,
        )
    ]
    result = engine.draft(finding, hits)
    assert result.draft_source == "memory_precedent"
    assert result.draft_text == "MEMORY DRAFT TEXT"
    assert "p1" in result.precedent_ids


def test_playbook_fallback_when_memory_empty():
    engine = FakeDraftEngine()
    finding = {
        "playbook_rule_id": "indemnity_mutual",
        "status": "FLAGGED",
        "suggested_counter_proposal": "Mutual indemnity as per playbook.",
    }
    result = engine.draft(finding, [])
    assert result.draft_source == "playbook_fallback"
    assert "Mutual indemnity" in (result.draft_text or "")


def test_none_when_both_missing():
    engine = FakeDraftEngine()
    finding = {
        "playbook_rule_id": "equity_hard_ceiling",
        "status": "REQUIRES_HUMAN",
        "suggested_counter_proposal": None,
    }
    result = engine.draft(finding, [])
    assert result.draft_source == "none"
    assert result.draft_text is None


def test_reject_precedents_ignored():
    engine = FakeDraftEngine()
    finding = {
        "playbook_rule_id": "equity_hard_ceiling",
        "status": "REQUIRES_HUMAN",
        "suggested_counter_proposal": None,
    }
    hits = [
        PrecedentHit(
            record=DecisionRecord(
                id="rej1",
                clause_text="equity",
                decision="reject",
                final_text="SHOULD NOT BE USED",
                playbook_rule_id="equity_hard_ceiling",
            ),
            distance=0.0,
        )
    ]
    result = engine.draft(finding, hits)
    assert result.draft_source == "none"
    assert result.draft_text is None


def test_nearest_accept_chosen_among_mixed():
    engine = FakeDraftEngine()
    finding = {
        "playbook_rule_id": "r1",
        "status": "FLAGGED",
        "suggested_counter_proposal": "fallback",
    }
    hits = [
        {
            "id": "far",
            "decision": "accept",
            "final_text": "FAR",
            "distance": 0.9,
        },
        {
            "id": "near",
            "decision": "edit",
            "final_text": "NEAR",
            "distance": 0.05,
        },
        {
            "id": "rej",
            "decision": "reject",
            "final_text": "NOPE",
            "distance": 0.0,
        },
    ]
    result = engine.draft(finding, hits)
    assert result.draft_text == "NEAR"
    assert result.draft_source == "memory_precedent"
