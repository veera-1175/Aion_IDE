"""Innovation #2 & #3 — Full portable memory integration from remote agents."""

from __future__ import annotations

from datetime import datetime, timezone

from noesis.core.models import MemoryCategory, MemoryRecord, MemoryPacket, SemanticConcept
from noesis.graph.memory_graph import MemoryGraphEngine
from noesis.storage.sqlite_store import SQLiteMemoryStore
from noesis.symbolic.compression import SymbolicCompressionEngine


class PacketMergeEngine:
    """
    Import symbolic packets from other agents into local cognition.
    Remote experience becomes collective memory.
    """

    def __init__(
        self,
        store: SQLiteMemoryStore,
        graph: MemoryGraphEngine,
        symbolic: SymbolicCompressionEngine,
        agent_id: str,
    ):
        self.store = store
        self.graph = graph
        self.symbolic = symbolic
        self.agent_id = agent_id

    def merge_packet(
        self,
        packet: MemoryPacket,
        source_agent: str,
        embedding: list[float] | None = None,
    ) -> MemoryRecord:
        """Integrate foreign memory packet into local store + graph."""
        payload = self.symbolic.decompress(packet)

        concepts = [
            SemanticConcept(label=c["label"], concept_type=c["type"])
            for c in payload.get("concepts", [])
        ]

        # Avoid ID collision — namespace foreign memories
        local_id = f"{packet.memory_id}@{source_agent}" if "@" not in packet.memory_id else packet.memory_id
        existing = self.store.get_memory(local_id)

        now = datetime.now(timezone.utc)
        if existing:
            existing.importance = max(existing.importance, packet.importance)
            existing.access_count += 1
            existing.updated_at = now
            existing.metadata["synced_from"] = source_agent
            record = existing
        else:
            record = MemoryRecord(
                memory_id=local_id,
                content=payload.get("raw_excerpt", packet.semantic_summary),
                abstracted_content=packet.semantic_summary,
                category=MemoryCategory(packet.category),
                importance=packet.importance,
                cluster_id=packet.semantic_cluster,
                concepts=concepts,
                tags=packet.tags + [f"synced:{source_agent}"],
                created_at=now,
                updated_at=now,
                metadata={
                    "synced_from": source_agent,
                    "original_id": packet.memory_id,
                    "portable_cognition": True,
                },
            )

        self.store.save_memory(record, embedding)
        self.graph.add_memory_concepts(record.memory_id, concepts)

        for from_n, to_n, rel in packet.graph_edges:
            self.store.save_graph_edge(from_n, to_n, rel, record.memory_id)

        new_packet = self.symbolic.compress(record, packet.graph_edges)
        new_packet.metadata["imported_from"] = source_agent
        self.store.save_packet(new_packet)

        return record
