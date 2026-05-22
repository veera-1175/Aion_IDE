"""Phase 5 — Predictive recall: anticipate what memory context is needed."""

from __future__ import annotations

from collections import Counter

from noesis.storage.sqlite_store import SQLiteMemoryStore


class PredictiveRecallEngine:
    """
    Tracks query patterns and predicts likely-needed memory clusters.
    Reinforcement: frequently recalled clusters get retention boost.
    """

    def __init__(self, store: SQLiteMemoryStore):
        self.store = store
        self._query_history: Counter[str] = Counter()
        self._cluster_affinity: Counter[str] = Counter()

    def record_query(self, query: str, recalled_clusters: list[str]) -> None:
        tokens = [t.lower() for t in query.split() if len(t) > 3]
        for t in tokens:
            self._query_history[t] += 1
        for cluster in recalled_clusters:
            self._cluster_affinity[cluster] += 1

    def predict_clusters(self, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Predict which memory clusters are likely relevant before full search."""
        tokens = [t.lower() for t in query.split() if len(t) > 3]
        scores: Counter[str] = Counter()

        for token in tokens:
            for cluster_id, count in self._cluster_affinity.items():
                if token in cluster_id or any(token in c for c in cluster_id.split("_")):
                    scores[cluster_id] += count * 0.5
            self._query_history[token]  # touch history

        # Boost high-importance clusters from store
        for record in self.store.list_memories(limit=50):
            for token in tokens:
                if token in record.cluster_id or any(token in t for t in record.tags):
                    scores[record.cluster_id] += record.importance

        ranked = scores.most_common(top_k)
        total = max(sum(s for _, s in ranked), 1)
        return [(cid, round(score / total, 3)) for cid, score in ranked]

    def get_hot_clusters(self, limit: int = 5) -> list[str]:
        return [c for c, _ in self._cluster_affinity.most_common(limit)]
