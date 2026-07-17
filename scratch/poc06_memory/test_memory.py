"""Unit tests for vector memory (FAKE_EMBED=1 / HashEmbedder)."""

from __future__ import annotations

import os

import pytest

os.environ["FAKE_EMBED"] = "1"

from scratch.poc06_memory.embeddings import HashEmbedder, get_embedder
from scratch.poc06_memory.models import DecisionRecord
from scratch.poc06_memory.store import DecisionStore


@pytest.fixture
def store(tmp_path):
    return DecisionStore(
        persist_dir=tmp_path / "vm",
        collection_name="test_decisions",
        embedder=HashEmbedder(),
    )


def test_hash_embedder_stable():
    e = HashEmbedder(dim=64)
    a = e.embed(["liability cap twelve months"])[0]
    b = e.embed(["liability cap twelve months"])[0]
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-5


def test_get_embedder_defaults_to_hash():
    os.environ["FAKE_EMBED"] = "1"
    assert isinstance(get_embedder(), HashEmbedder)


def test_empty_search(store: DecisionStore):
    assert store.search_precedents("anything") == []


def test_add_and_retrieve_same_clause(store: DecisionStore):
    clause = "Supplier liability shall be uncapped for all claims."
    rec = DecisionRecord(
        clause_text=clause,
        decision="accept",
        final_text="Supplier liability capped at 12 months of fees.",
        playbook_rule_id="uncapped_or_broad_indemnity",
        contract_id="msa-1",
    )
    store.add_decision(rec)
    hits = store.search_precedents(clause, top_k=3)
    assert len(hits) >= 1
    assert hits[0].record.decision == "accept"
    assert "12 months" in hits[0].record.final_text


def test_reject_stored(store: DecisionStore):
    store.add_decision(
        DecisionRecord(
            clause_text="Weird jurisdiction on Mars",
            decision="reject",
            final_text="Weird jurisdiction on Mars",
            playbook_rule_id="governing_law_preferred",
            contract_id="x",
            reasoning="Not acceptable",
        )
    )
    hits = store.search_precedents("Weird jurisdiction on Mars")
    assert hits[0].record.decision == "reject"


def test_prefer_same_rule_id(store: DecisionStore):
    store.add_decision(
        DecisionRecord(
            clause_text="Indemnify and hold harmless forever",
            decision="accept",
            final_text="Capped mutual indemnity",
            playbook_rule_id="uncapped_or_broad_indemnity",
            contract_id="a",
        )
    )
    store.add_decision(
        DecisionRecord(
            clause_text="Governed by California law",
            decision="accept",
            final_text="England and Wales",
            playbook_rule_id="governing_law_preferred",
            contract_id="b",
        )
    )
    hits = store.search_precedents(
        "shall indemnify the university",
        top_k=3,
        playbook_rule_id="uncapped_or_broad_indemnity",
    )
    assert hits
    assert all(h.record.playbook_rule_id == "uncapped_or_broad_indemnity" for h in hits)
