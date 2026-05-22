"""Phase 5 — Redundancy elimination: merge duplicate semantic clusters."""

from __future__ import annotations

from noesis.semantic.embeddings import EmbeddingEngine
from noesis.storage.sqlite_store import SQLiteMemoryStore


class RedundancyEliminator:
    """
    Innovation #5 — Adaptive Forgetting (redundancy branch)
    Detects semantically duplicate memories and merges them.
    """

    def __init__(self, store: SQLiteMemoryStore, embeddings: EmbeddingEngine, threshold: float = 0.88):
        self.store = store
        self.embeddings = embeddings
        self.threshold = threshold

    def find_redundant_pairs(self, embedding_cache: dict[str, list[float]]) -> list[tuple[str, str, float]]:
        """Find memory pairs that are near-duplicates."""
        ids = list(embedding_cache.keys())
        pairs = []
        for i, id_a in enumerate(ids):
            for id_b in ids[i + 1 :]:
                sim = self.embeddings.similarity(embedding_cache[id_a], embedding_cache[id_b])
                if sim >= self.threshold:
                    pairs.append((id_a, id_b, sim))
        return sorted(pairs, key=lambda x: x[2], reverse=True)

    def merge_redundant(self, keep_id: str, remove_id: str) -> None:
        """Keep higher-importance memory, absorb the other, delete duplicate."""
        keep = self.store.get_memory(keep_id)
        remove = self.store.get_memory(remove_id)
        if not keep or not remove:
            return

        if remove.importance > keep.importance:
            keep_id, remove_id = remove_id, keep_id
            keep, remove = remove, keep

        keep.concepts = list({c.label: c for c in keep.concepts + remove.concepts}.values())
        keep.tags = list(set(keep.tags + remove.tags))
        keep.importance = round(min(1.0, max(keep.importance, remove.importance) + 0.02), 3)
        keep.metadata["merged_from"] = remove_id
        keep.metadata["redundancy_merged"] = True

        self.store.save_memory(keep)
        self.store.delete_memory(remove_id)

    def eliminate(self, embedding_cache: dict[str, list[float]]) -> list[str]:
        """Run redundancy pass — returns IDs of removed memories."""
        removed = []
        pairs = self.find_redundant_pairs(embedding_cache)
        processed: set[str] = set()

        for id_a, id_b, _ in pairs:
            if id_a in processed or id_b in processed:
                continue
            if id_a not in embedding_cache or id_b not in embedding_cache:
                continue
            keep = self.store.get_memory(id_a)
            drop = self.store.get_memory(id_b)
            if not keep or not drop:
                continue
            drop_id = id_b if keep.importance >= drop.importance else id_a
            self.merge_redundant(id_a, id_b)
            removed.append(drop_id)
            processed.add(id_a)
            processed.add(id_b)
            embedding_cache.pop(drop_id, None)

        return removed
