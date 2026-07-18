"""Thin Django adapter over scratch DecisionStore (Chroma)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings

from scratch.poc06_memory.models import DecisionRecord, PrecedentHit
from scratch.poc06_memory.store import DecisionStore


@lru_cache(maxsize=1)
def get_decision_store() -> DecisionStore:
    # Respect FAKE_EMBED from Django settings / env (default MiniLM when not testing)
    persist = Path(getattr(settings, "CHROMA_PATH", settings.DATA_DIR / "vector_memory"))
    collection = getattr(settings, "CHROMA_COLLECTION", "django_decisions_v2")
    return DecisionStore(persist_dir=persist, collection_name=collection)


def reset_decision_store() -> None:
    """Drop cached Chroma client (needed on Windows so temp dirs can delete)."""
    get_decision_store.cache_clear()


def memory_max_distance() -> float:
    return float(getattr(settings, "MEMORY_MAX_DISTANCE", 0.45))


def search_precedents(
    query: str,
    *,
    playbook_rule_id: str | None = None,
    top_k: int = 3,
) -> list[PrecedentHit]:
    return get_decision_store().search_precedents(
        query,
        top_k=top_k,
        playbook_rule_id=playbook_rule_id or None,
    )


def add_decision_record(record: DecisionRecord) -> DecisionRecord:
    return get_decision_store().add_decision(record)


def list_decision_records(limit: int = 200) -> list[DecisionRecord]:
    return get_decision_store().list_decisions(limit=limit)


def get_decision_record(record_id: str) -> DecisionRecord | None:
    return get_decision_store().get_decision(record_id)


def delete_decision_record(record_id: str) -> bool:
    return get_decision_store().delete_decision(record_id)


def within_distance(hit: PrecedentHit, max_distance: float | None = None) -> bool:
    cap = memory_max_distance() if max_distance is None else max_distance
    if hit.distance is None:
        return False
    return float(hit.distance) <= cap


def filter_usable_accepts(
    hits: list[PrecedentHit],
    *,
    max_distance: float | None = None,
) -> tuple[list[PrecedentHit], PrecedentHit | None]:
    """Return (accept/edit hits under threshold, nearest reject under threshold).

    If a near reject exists, callers should skip memory reuse.
    """
    cap = memory_max_distance() if max_distance is None else max_distance
    accepts: list[PrecedentHit] = []
    near_reject: PrecedentHit | None = None

    for h in hits:
        if not within_distance(h, cap):
            continue
        if h.record.decision == "reject":
            if near_reject is None or (h.distance or 1e9) < (near_reject.distance or 1e9):
                near_reject = h
        elif h.record.decision in ("accept", "edit") and (h.record.final_text or "").strip():
            accepts.append(h)

    accepts.sort(
        key=lambda h: (
            h.distance is None,
            float(h.distance) if h.distance is not None else 1e9,
        )
    )
    return accepts, near_reject


def provenance_from_hit(hit: PrecedentHit) -> dict[str, Any]:
    rec = hit.record
    dist = hit.distance
    similarity = None if dist is None else round(max(0.0, 1.0 - float(dist)), 3)
    return {
        "precedent_id": rec.id,
        "filename": rec.filename or "",
        "contract_id": rec.contract_id,
        "decision": rec.decision,
        "date": (rec.created_at or "")[:10],
        "distance": dist,
        "similarity": similarity,
        "clause_quote": (rec.clause_text or "")[:280],
        "final_text": (rec.final_text or "")[:500],
        "doc_kind": rec.doc_kind or "",
        "playbook_rule_id": rec.playbook_rule_id or "",
    }
