"""Phase 5 — Adaptive Forgetting Engine: memory decay & redundancy elimination."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from noesis.core.models import MemoryRecord
from noesis.storage.sqlite_store import SQLiteMemoryStore


class AdaptiveForgettingEngine:
    """
    Human-inspired forgetting curves with reinforcement boost on recall.
    Ebbinghaus-style decay: R = e^(-t/S) adjusted by importance and access.
    """

    def __init__(self, config: dict, store: SQLiteMemoryStore):
        fg = config.get("forgetting", {})
        self.enabled = fg.get("enabled", True)
        self.decay_rate = fg.get("decay_rate", 0.02)
        self.min_retention = fg.get("min_retention_score", 0.1)
        self.review_boost = fg.get("review_boost", 0.15)
        self.store = store

    def compute_retention(self, record: MemoryRecord) -> float:
        if not self.enabled:
            return 1.0

        age_days = (datetime.now(timezone.utc) - record.updated_at).total_seconds() / 86400
        stability = 1.0 + record.importance * 10 + record.access_count * 0.5
        decay = math.exp(-age_days * self.decay_rate / stability)
        retention = decay * record.importance
        return round(max(0.0, min(1.0, retention)), 3)

    def apply_decay_cycle(self) -> list[str]:
        """Run forgetting pass — returns memory IDs marked for deletion."""
        to_forget = []
        memories = self.store.list_memories(limit=500)

        for record in memories:
            retention = self.compute_retention(record)
            self.store.update_retention(record.memory_id, retention)

            if retention < self.min_retention and record.importance < 0.3:
                to_forget.append(record.memory_id)

        return to_forget

    def reinforce_on_recall(self, memory_id: str) -> None:
        """Boost retention when memory is accessed."""
        record = self.store.get_memory(memory_id)
        if record:
            new_retention = min(1.0, record.retention_score + self.review_boost)
            self.store.update_retention(memory_id, new_retention)
            self.store.increment_access(memory_id)
