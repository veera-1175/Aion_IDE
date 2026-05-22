"""Step 8 — Portable Memory Packets."""

from __future__ import annotations

from datetime import datetime, timezone

from noesis.core.models import MemoryPacket, MemoryRecord


class PacketBuilder:
    """Assembles portable memory capsules for distribution."""

    def build(
        self,
        record: MemoryRecord,
        token_ids: list[int],
        bytecode: bytes,
        graph_edges: list[tuple[str, str, str]] | None = None,
    ) -> MemoryPacket:
        return MemoryPacket(
            memory_id=record.memory_id,
            importance=record.importance,
            semantic_cluster=record.cluster_id,
            category=record.category.value,
            semantic_summary=record.abstracted_content,
            bytecode=bytecode,
            token_ids=token_ids,
            graph_edges=graph_edges or [],
            tags=record.tags,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "access_count": record.access_count,
                "retention_score": record.retention_score,
                "concept_count": len(record.concepts),
            },
        )
