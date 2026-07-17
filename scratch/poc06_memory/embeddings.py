"""Embedding backends for vector memory."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-tokens hash embedding (no model download)."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            tokens = ["empty"]
        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            # Use several bytes to spread mass
            for i in range(0, 16, 4):
                idx = int.from_bytes(h[i : i + 4], "little") % self.dim
                sign = 1.0 if h[i] % 2 == 0 else -1.0
                vec[idx] += sign
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class SentenceEmbedder:
    """Semantic embeddings via sentence-transformers (FAKE_EMBED=0)."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


def get_embedder() -> Embedder:
    """FAKE_EMBED=1 (default) -> HashEmbedder; 0 -> SentenceEmbedder."""
    fake = os.environ.get("FAKE_EMBED", "1").strip() not in ("0", "false", "False")
    if fake:
        return HashEmbedder()
    return SentenceEmbedder()
