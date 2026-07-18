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
            "filename": (record.filename or "")[:512],
            "doc_kind": (record.doc_kind or "")[:64],
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

    def delete_decision(self, record_id: str) -> bool:
        """Remove a precedent by id. Returns True if collection still usable."""
        try:
            self._col.delete(ids=[record_id])
            return True
        except Exception:
            return False

    def get_decision(self, record_id: str) -> Optional[DecisionRecord]:
        try:
            raw = self._col.get(
                ids=[record_id],
                include=["documents", "metadatas"],
            )
        except Exception:
            return None
        ids = raw.get("ids") or []
        if not ids:
            return None
        metas = raw.get("metadatas") or []
        docs = raw.get("documents") or []
        return self._record_from_row(ids[0], docs[0] if docs else "", metas[0] if metas else {})

    def list_decisions(self, limit: int = 200) -> list[DecisionRecord]:
        if self.count() == 0:
            return []
        raw = self._col.get(
            include=["documents", "metadatas"],
            limit=min(limit, max(self.count(), 1)),
        )
        ids = raw.get("ids") or []
        metas = raw.get("metadatas") or []
        docs = raw.get("documents") or []
        out: list[DecisionRecord] = []
        for i, _id in enumerate(ids):
            out.append(
                self._record_from_row(
                    _id,
                    docs[i] if i < len(docs) else "",
                    metas[i] if i < len(metas) else {},
                )
            )
        out.sort(key=lambda r: r.created_at or "", reverse=True)
        return out

    def _record_from_row(
        self, _id: str, doc: str, meta: dict | None
    ) -> DecisionRecord:
        meta = meta or {}
        record_json = meta.get("record_json")
        if record_json:
            try:
                return DecisionRecord.model_validate_json(record_json)
            except Exception:
                pass
        return DecisionRecord(
            id=_id,
            clause_text=doc or "",
            decision=meta.get("decision") or "accept",
            final_text=meta.get("final_text") or "",
            playbook_rule_id=meta.get("playbook_rule_id") or None,
            contract_id=meta.get("contract_id") or "unknown",
            reasoning=meta.get("reasoning") or None,
            filename=meta.get("filename") or None,
            doc_kind=meta.get("doc_kind") or None,
            created_at=meta.get("created_at") or "",
        )

    def search_precedents(
        self,
        query: str,
        top_k: int = 3,
        playbook_rule_id: Optional[str] = None,
    ) -> list[PrecedentHit]:
        if self.count() == 0:
            return []
        emb = self.embedder.embed([query])[0]
        # Fetch extra so rule-filter / reject filtering still has candidates
        n = min(max(top_k * 4, top_k), self.count())
        kwargs: dict = {
            "query_embeddings": [emb],
            "n_results": n,
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
            record = self._record_from_row(
                _id,
                docs[i] if docs and i < len(docs) else "",
                metas[i] if metas and i < len(metas) else {},
            )
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
