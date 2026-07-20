"""Unlearn / list helpers joining Chroma precedents with ORM Decisions."""

from __future__ import annotations

from typing import Any

from apps.core.labels import humanize_label
from apps.decisions.models import Decision
from apps.learning.services.memory import (
    delete_decision_record,
    filter_usable_accepts,
    get_decision_record,
    list_decision_records,
    provenance_from_hit,
    search_precedents,
)
from apps.review.services.overrides import load_overrides


def precedent_rows(limit: int = 200) -> list[dict[str, Any]]:
    """List Chroma precedents with optional ORM join for contract links."""
    records = list_decision_records(limit=limit)
    chroma_ids = [r.id for r in records]
    by_chroma = {
        d.chroma_id: d
        for d in Decision.objects.filter(chroma_id__in=chroma_ids).select_related(
            "contract", "finding"
        )
    }
    rows: list[dict[str, Any]] = []
    for rec in records:
        decision = by_chroma.get(rec.id)
        if decision and not decision.memory_active:
            continue
        label = "Avoid" if rec.decision == "reject" else rec.decision.title()
        rule_id = rec.playbook_rule_id or ""
        clause = (rec.clause_text or "").strip()
        final = (rec.final_text or "").strip()
        rows.append(
            {
                "id": rec.id,
                "rule_id": rule_id,
                "rule_label": humanize_label(rule_id, empty="General rule"),
                "clause_snippet": clause[:320],
                "clause_text": clause,
                "decision": rec.decision,
                "decision_label": label,
                "final_text": final[:500],
                "final_full": final,
                "filename": rec.filename
                or (decision.contract.filename if decision else ""),
                "contract_id": (
                    str(decision.contract_id)
                    if decision
                    else (rec.contract_id if rec.contract_id != "unknown" else "")
                ),
                "doc_kind": rec.doc_kind or "",
                "created_at": rec.created_at,
                "date": (rec.created_at or "")[:10],
            }
        )
    return rows


def search_memory(
    *,
    q: str = "",
    rule_id: str = "",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    query = (q or "").strip() or (rule_id or "contract clause")
    hits = search_precedents(query, playbook_rule_id=rule_id or None, top_k=top_k * 2)
    accepts, near_reject = filter_usable_accepts(hits)
    out: list[dict[str, Any]] = []
    for h in accepts[:top_k]:
        row = provenance_from_hit(h)
        row["usable"] = True
        row["blocked"] = False
        out.append(row)
    if near_reject:
        row = provenance_from_hit(near_reject)
        row["usable"] = False
        row["blocked"] = True
        row["note"] = "near reject - would skip memory reuse"
        out.insert(0, row)
    # Also surface out-of-threshold hits for API transparency
    for h in hits:
        if h in accepts or h is near_reject:
            continue
        if len(out) >= top_k + 1:
            break
        row = provenance_from_hit(h)
        row["usable"] = False
        row["blocked"] = False
        row["note"] = "above MEMORY_MAX_DISTANCE"
        out.append(row)
    return out[: top_k + 1]


def unlearn_precedent(record_id: str) -> bool:
    """Delete Chroma id and soft-flag matching ORM Decision."""
    rid = (record_id or "").strip()
    if not rid:
        return False
    deleted = delete_decision_record(rid)
    Decision.objects.filter(chroma_id=rid).update(memory_active=False)
    # Treat as success if ORM flagged even when chroma already gone
    if Decision.objects.filter(chroma_id=rid, memory_active=False).exists():
        return True
    return deleted and get_decision_record(rid) is None


def active_overrides() -> list[dict[str, Any]]:
    data = load_overrides()
    rows = []
    for o in data.get("overrides") or []:
        row = dict(o)
        rid = row.get("playbook_rule_id") or ""
        row["rule_label"] = humanize_label(rid, empty="Muted rule")
        rows.append(row)
    return rows
