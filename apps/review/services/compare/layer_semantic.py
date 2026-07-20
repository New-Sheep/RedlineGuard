"""L1 — local embedding retrieve of segments vs playbook rules (no LLM)."""

from __future__ import annotations

from typing import Any

from apps.review.services.compare.models import FindingCandidate
from apps.review.services.compare.segment import segment_paragraphs
from apps.review.services.compare.synonyms import expand_query_text, has_keyword_overlap
from scratch.poc06_memory.embeddings import Embedder, get_embedder


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance = 1 - cosine similarity (vectors assumed L2-normalized)."""
    if not a or not b or len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    # Clamp numerical drift
    sim = max(-1.0, min(1.0, dot))
    return 1.0 - sim


def _rule_query(rule: dict) -> str:
    parts = [
        str(rule.get("preferred") or ""),
        str(rule.get("hard_ceiling") or ""),
        str(rule.get("clause_type") or ""),
        " ".join(str(p) for p in (rule.get("match_any") or [])),
    ]
    return expand_query_text(" ".join(p for p in parts if p).strip())


def layer_semantic(
    text: str,
    playbook: dict[str, Any],
    *,
    max_distance: float,
    strict_distance: float,
    embedder: Embedder | None = None,
    skip_rule_ids: set[str] | None = None,
) -> list[FindingCandidate]:
    """Return semantic candidates for rules not already covered by skip_rule_ids (L0).

    L1-only findings must pass keyword overlap OR strict_distance.
    """
    rules = [r for r in (playbook.get("rules") or []) if r.get("id")]
    if not rules or not (text or "").strip():
        return []

    skip = skip_rule_ids or set()
    segments = segment_paragraphs(text)
    # Drop tiny noise
    segments = [s for s in segments if len(s.text.strip()) >= 40]
    if not segments:
        return []

    emb = embedder or get_embedder()
    seg_vecs = emb.embed([s.text for s in segments])

    out: list[FindingCandidate] = []
    for rule in rules:
        rid = str(rule["id"])
        if rid in skip:
            continue
        query = _rule_query(rule)
        if not query.strip():
            continue
        q_vec = emb.embed([query])[0]
        best_i = -1
        best_dist = 999.0
        for i, sv in enumerate(seg_vecs):
            d = _cosine_distance(q_vec, sv)
            if d < best_dist:
                best_dist = d
                best_i = i
        if best_i < 0 or best_dist > max_distance:
            continue

        seg = segments[best_i]
        # False-positive guard for L1-only
        overlap = has_keyword_overlap(seg.text, rule)
        if not overlap and best_dist > strict_distance:
            continue

        conf = max(0.5, min(1.0, 1.0 - best_dist))
        out.append(
            FindingCandidate(
                playbook_rule_id=rid,
                clause_name=str(rule.get("clause_type") or rid),
                severity=str(rule.get("severity") or "medium"),
                clause_excerpt=seg.text[:2000],
                start_offset=seg.start,
                end_offset=seg.end,
                sources=["semantic"],
                confidence=conf,
                match_distance=round(best_dist, 4),
                fallback_text=rule.get("fallback_text"),
                preferred=str(rule.get("preferred") or ""),
                hard_ceiling=str(rule.get("hard_ceiling") or ""),
            )
        )
    return out
