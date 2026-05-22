"""Phase 2 — Semantic clustering: group related experiences into evolving clusters."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from noesis.semantic.embeddings import EmbeddingEngine


@dataclass
class MemoryCluster:
    """A semantic cluster of related memories — the unit of compressed cognition."""

    cluster_id: str
    centroid_embedding: list[float]
    member_ids: list[str] = field(default_factory=list)
    insight_summary: str = ""
    total_inputs: int = 0
    dominant_concepts: list[str] = field(default_factory=list)


class SemanticClusterManager:
    """
    Clusters memories by semantic similarity.
    Enables compression: many raw inputs -> one cluster insight.
    """

    def __init__(self, embeddings: EmbeddingEngine, similarity_threshold: float = 0.72):
        self.embeddings = embeddings
        self.threshold = similarity_threshold
        self._clusters: dict[str, MemoryCluster] = {}

    def find_or_create_cluster(
        self,
        proposed_id: str,
        embedding: list[float],
        concepts: list[str],
    ) -> tuple[str, bool]:
        """Return (cluster_id, is_new). Assign to nearest cluster or create new."""
        best_id, best_sim = proposed_id, 0.0

        for cid, cluster in self._clusters.items():
            sim = self.embeddings.similarity(embedding, cluster.centroid_embedding)
            if sim > best_sim and sim >= self.threshold:
                best_sim = sim
                best_id = cid

        if best_id != proposed_id and best_id in self._clusters:
            return best_id, False

        self._clusters[proposed_id] = MemoryCluster(
            cluster_id=proposed_id,
            centroid_embedding=embedding,
            dominant_concepts=concepts[:6],
        )
        return proposed_id, True

    def add_to_cluster(self, cluster_id: str, memory_id: str, embedding: list[float]) -> None:
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return
        cluster.member_ids.append(memory_id)
        cluster.total_inputs += 1
        # Update centroid (running average)
        old = np.array(cluster.centroid_embedding)
        new = np.array(embedding)
        n = len(cluster.member_ids)
        cluster.centroid_embedding = ((old * (n - 1) + new) / n).tolist()

    def set_cluster_insight(self, cluster_id: str, insight: str) -> None:
        if cluster_id in self._clusters:
            self._clusters[cluster_id].insight_summary = insight

    def get_cluster(self, cluster_id: str) -> MemoryCluster | None:
        return self._clusters.get(cluster_id)

    def list_clusters(self) -> list[MemoryCluster]:
        return list(self._clusters.values())

    def compression_ratio(self, cluster_id: str) -> float:
        """How many raw inputs were compressed into this cluster."""
        cluster = self._clusters.get(cluster_id)
        if not cluster or cluster.total_inputs == 0:
            return 1.0
        return float(cluster.total_inputs)  # N inputs -> 1 insight
