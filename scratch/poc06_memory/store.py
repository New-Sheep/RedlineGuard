"""Chroma-backed decision / precedent store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from scratch._io import ROOT
from scratch.poc06_memory.embeddings import Embedder, get_embedder
from scratch.poc06_memory.models import DecisionRecord, PrecedentHit

DEFAULT_PERSIST = ROOT / "data" / "vector_memory"
DEFAULT_COLLECTION = "decisions"


class DecisionStore:
    def __init__(
        self,
        persist_dir: Path | str | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        embedder: Embedder | None = None,
    ) -> None:
        import chromadb

        self.persist_dir = Path(persist_dir or DEFAULT_PERSIST)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or get_embedder()
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._col = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self._col.count()

    def reset(self) -> None:
        """Drop and recreate the collection (demo / tests)."""
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._col = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_decision(self, record: DecisionRecord) -> DecisionRecord:
        emb = self.embedder.embed([record.clause_text])[0]
        meta = {
            "decision": record.decision,
            "final_text": record.final_text[:2000],
            "playbook_rule_id": record.playbook_rule_id or "",
            "contract_id": record.contract_id,
            "reasoning": (record.reasoning or "")[:500],
            "created_at": record.created_at,
            "record_json": record.model_dump_json(),
        }
        self._col.add(
            ids=[record.id],
            documents=[record.clause_text],
            embeddings=[emb],
            metadatas=[meta],
        )
        return record

    def search_precedents(
        self,
        query: str,
        top_k: int = 3,
        playbook_rule_id: Optional[str] = None,
    ) -> list[PrecedentHit]:
        if self.count() == 0:
            return []
        emb = self.embedder.embed([query])[0]
        kwargs: dict = {
            "query_embeddings": [emb],
            "n_results": min(top_k, self.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if playbook_rule_id:
            kwargs["where"] = {"playbook_rule_id": playbook_rule_id}

        try:
            raw = self._col.query(**kwargs)
        except Exception:
            # Fallback if metadata filter yields empty / chroma quirks
            if playbook_rule_id:
                kwargs.pop("where", None)
                raw = self._col.query(**kwargs)
            else:
                raise

        hits: list[PrecedentHit] = []
        ids = (raw.get("ids") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]

        for i, _id in enumerate(ids):
            meta = metas[i] or {}
            record_json = meta.get("record_json")
            if record_json:
                record = DecisionRecord.model_validate_json(record_json)
            else:
                record = DecisionRecord(
                    id=_id,
                    clause_text=docs[i] or "",
                    decision=meta.get("decision") or "accept",
                    final_text=meta.get("final_text") or "",
                    playbook_rule_id=meta.get("playbook_rule_id") or None,
                    contract_id=meta.get("contract_id") or "unknown",
                    reasoning=meta.get("reasoning") or None,
                    created_at=meta.get("created_at") or "",
                )
            # If we filtered by rule id in where, keep; else prefer same rule when ranking
            hits.append(
                PrecedentHit(
                    record=record,
                    distance=float(dists[i]) if dists and dists[i] is not None else None,
                )
            )

        if playbook_rule_id:
            same = [h for h in hits if h.record.playbook_rule_id == playbook_rule_id]
            if same:
                return same[:top_k]
        return hits[:top_k]
