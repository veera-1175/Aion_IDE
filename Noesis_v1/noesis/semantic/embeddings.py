"""Embedding utilities for semantic similarity and clustering."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingEngine:
    """Lazy-loaded sentence-transformers for edge-compatible local embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model: %s", self.model_name)
                self._model = SentenceTransformer(self.model_name)
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers required. Install: pip install sentence-transformers"
                ) from e
        return self._model

    def encode(self, text: str) -> list[float]:
        vec = self.model.encode(text, convert_to_numpy=True)
        return vec.tolist()

    def similarity(self, a: list[float], b: list[float]) -> float:
        va, vb = np.array(a), np.array(b)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom == 0:
            return 0.0
        return float(np.dot(va, vb) / denom)

    def find_similar(
        self,
        query_embedding: list[float],
        candidates: list[tuple[str, list[float]]],
        threshold: float = 0.75,
    ) -> list[tuple[str, float]]:
        results = []
        for mem_id, emb in candidates:
            sim = self.similarity(query_embedding, emb)
            if sim >= threshold:
                results.append((mem_id, sim))
        return sorted(results, key=lambda x: x[1], reverse=True)
