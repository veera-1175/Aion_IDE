"""Phase 5 — Memory evolution: memories strengthen and refine over time."""

from __future__ import annotations

from datetime import datetime, timezone

from noesis.core.models import MemoryCategory, MemoryRecord, ParsedMemory
from noesis.semantic.insights import InsightExtractor


class MemoryEvolutionEngine:
    """
    Memories are not static snapshots — they evolve:
    - importance increases with reinforcement
    - category promotes episodic -> semantic -> insight
    - abstracted content refines with new evidence
    """

    PROMOTION_THRESHOLDS = {
        MemoryCategory.EPISODIC: 2,
        MemoryCategory.SEMANTIC: 4,
        MemoryCategory.PROCEDURAL: 3,
    }

    def __init__(self):
        self.insights = InsightExtractor()

    def evolve(self, record: MemoryRecord, parsed: ParsedMemory, cluster_input_count: int) -> MemoryRecord:
        record.access_count += 1
        record.updated_at = datetime.now(timezone.utc)

        # Importance grows with use (reinforcement learning signal)
        record.importance = round(min(1.0, record.importance + 0.04 * (1 - record.importance)), 3)
        record.retention_score = min(1.0, record.retention_score + 0.1)

        # Category promotion
        record.category = self._promote_category(record.category, cluster_input_count)

        # Re-abstract if cluster has enough history
        if cluster_input_count >= 2:
            all_concepts = list({c.label: c for c in record.concepts + parsed.concepts}.values())
            insight = self.insights.extract_cluster_insight(
                record.cluster_id,
                [record.content, parsed.raw_text],
                all_concepts,
                cluster_input_count,
            )
            if self.insights.should_promote_to_insight(cluster_input_count, record.category):
                record.abstracted_content = f"Insight: {insight.removeprefix('Insight: ')}"
                record.category = MemoryCategory.INSIGHT
            else:
                record.abstracted_content = insight

        record.concepts = list({c.label: c for c in record.concepts + parsed.concepts}.values())
        record.tags = list(set(record.tags + parsed.tags))
        record.content = parsed.raw_text
        record.metadata["evolution_count"] = record.metadata.get("evolution_count", 0) + 1
        record.metadata["last_evolved"] = record.updated_at.isoformat()

        return record

    def _promote_category(self, current: MemoryCategory, input_count: int) -> MemoryCategory:
        if current == MemoryCategory.INSIGHT:
            return current
        threshold = self.PROMOTION_THRESHOLDS.get(current, 5)
        if input_count >= threshold + 2:
            order = [MemoryCategory.EPISODIC, MemoryCategory.SEMANTIC, MemoryCategory.INSIGHT]
            try:
                idx = order.index(current)
                if idx < len(order) - 1:
                    return order[idx + 1]
            except ValueError:
                pass
        if input_count >= 5:
            return MemoryCategory.INSIGHT
        return current
