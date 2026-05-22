"""Noesis Memory Engine — Full orchestrator (Phases 1-5)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from noesis.config import load_config
from noesis.core.models import MemoryCategory, MemoryPacket, MemoryRecord, RawInput, ReconstructedContext
from noesis.forgetting.adaptive import AdaptiveForgettingEngine
from noesis.forgetting.redundancy import RedundancyEliminator
from noesis.graph.memory_graph import MemoryGraphEngine
from noesis.graph.recall import GraphRecallEngine
from noesis.ingestion.collector import InputCollector
from noesis.recall.predictive import PredictiveRecallEngine
from noesis.semantic.cognition import SemanticCognitionEngine
from noesis.storage.sqlite_store import SQLiteMemoryStore
from noesis.symbolic.compression import SymbolicCompressionEngine
from noesis.sync.distributed import DistributedSyncLayer
from noesis.sync.mesh_client import MeshClient
from noesis.sync.mesh_server import MeshServer
from noesis.sync.packet_merge import PacketMergeEngine

logger = logging.getLogger(__name__)


class NoesisEngine:
    """
    Noesis Memory Engine — Semantic + Symbolic Distributed AI Memory

    Innovations over traditional AI memory:
    1. Semantic compression (meaning, not raw text)
    2. Symbolic portable packets (transferable cognition)
    3. Distributed shared memory (multi-agent sync)
    4. Knowledge graph recall (associative, not chunk retrieval)
    5. Adaptive forgetting (evolving, not accumulating)
    """

    def __init__(self, config_path: str | Path | None = None, db_path: str | None = None):
        self.config = load_config(config_path)
        storage_path = db_path or self.config["storage"]["path"]
        Path(storage_path).parent.mkdir(parents=True, exist_ok=True)

        self.store = SQLiteMemoryStore(storage_path)
        self.collector = InputCollector(self.store)
        self.semantic = SemanticCognitionEngine(self.config, self.store)
        self.symbolic = SymbolicCompressionEngine(self.config)
        self.graph = MemoryGraphEngine(
            self.store,
            max_depth=self.config.get("graph", {}).get("max_traversal_depth", 4),
        )
        self.graph_recall = GraphRecallEngine(self.graph, self.store)
        self.forgetting = AdaptiveForgettingEngine(self.config, self.store)
        self.redundancy = RedundancyEliminator(
            self.store,
            self.semantic.embeddings,
            threshold=self.config.get("semantic", {}).get("redundancy_threshold", 0.88),
        )
        self.predictive = PredictiveRecallEngine(self.store)
        self.sync = DistributedSyncLayer(self.config)
        self.packet_merge = PacketMergeEngine(
            self.store, self.graph, self.symbolic, self.config.get("engine", {}).get("agent_id", "agent-default")
        )
        self.agent_id = self.config.get("engine", {}).get("agent_id", "agent-default")

        self._embedding_cache: dict[str, list[float]] = self.store.get_all_embeddings()
        self._mesh_server: MeshServer | None = None

    # ── Core Memory API ───────────────────────────────────────────

    def remember(self, text: str, input_type: str = "conversation", source: str = "user", **metadata) -> dict[str, Any]:
        type_handlers = {
            "conversation": self.collector.from_conversation,
            "log": self.collector.from_log,
            "observation": self.collector.from_observation,
            "document": self.collector.from_document,
            "event": self.collector.from_event,
            "sensor": self.collector.from_sensor,
        }
        handler = type_handlers.get(input_type, self.collector.from_conversation)
        raw = handler(text, source=source, **metadata)
        return self._process_raw(raw)

    def remember_batch(self, items: list[dict]) -> list[dict[str, Any]]:
        return [r for raw in self.collector.ingest_batch(items) if (r := self._process_raw(raw))]

    def recall(self, query: str, limit: int = 5, mode: str = "hybrid") -> list[ReconstructedContext]:
        """
        Recall memories. Modes:
        - hybrid: graph + embedding (default, best quality)
        - graph: associative concept traversal only
        - semantic: embedding similarity only
        """
        parsed_concepts = self.semantic.parser.parse(query)
        predicted = self.predictive.predict_clusters(query)
        contexts: list[ReconstructedContext] = []
        seen: set[str] = set()

        if mode in ("hybrid", "graph"):
            for ctx in self.graph_recall.recall_by_concepts(parsed_concepts, limit=limit):
                if ctx.memory_id not in seen:
                    seen.add(ctx.memory_id)
                    contexts.append(ctx)
                    if ctx.memory_id != "graph-recall":
                        self.forgetting.reinforce_on_recall(ctx.memory_id)

        if mode in ("hybrid", "semantic") and len(contexts) < limit:
            query_emb = self.semantic.embeddings.encode(query)
            similar = self.semantic.embeddings.find_similar(
                query_emb, list(self._embedding_cache.items()), self.semantic.similarity_threshold
            )
            for mem_id, _ in similar:
                if mem_id in seen:
                    continue
                record = self.store.get_memory(mem_id)
                if record:
                    seen.add(mem_id)
                    self.forgetting.reinforce_on_recall(mem_id)
                    ctx = self.graph.reconstruct_context(
                        mem_id, record.abstracted_content, [c.label for c in record.concepts]
                    )
                    contexts.append(ctx)

        # Text fallback — names, personal facts, queries embedding similarity misses
        if len(contexts) < limit:
            for record in self.store.search_by_text(query, limit=limit):
                if record.memory_id in seen:
                    continue
                seen.add(record.memory_id)
                self.forgetting.reinforce_on_recall(record.memory_id)
                contexts.append(
                    ReconstructedContext(
                        memory_id=record.memory_id,
                        summary=record.abstracted_content,
                        related_memories=[],
                        concepts=[c.label for c in record.concepts],
                        graph_path=[],
                        confidence=0.75,
                    )
                )

        clusters_recalled = [c for c, _ in predicted]
        self.predictive.record_query(query, clusters_recalled)
        contexts.sort(key=lambda c: c.confidence, reverse=True)
        return contexts[:limit]

    def explain_recall(self, query: str) -> dict:
        """Explain WHY recall works differently than vector DB chunk search."""
        concepts = self.semantic.parser.parse(query)
        return {
            "innovation": "Knowledge graph associative recall",
            "query_concepts": [c.label for c in concepts],
            "graph_explanation": self.graph_recall.explain_recall([c.label for c in concepts]),
            "predicted_clusters": self.predictive.predict_clusters(query),
            "vs_traditional_ai": {
                "traditional": "Store raw chunks -> embed query -> cosine similarity -> return text",
                "noesis": "Compress to insight -> build concept graph -> traverse relationships -> reconstruct context",
            },
        }

    def compare_with_traditional(self, texts: list[str]) -> dict:
        """Demonstrate semantic compression vs storing raw conversations."""
        for t in texts:
            self.remember(t)

        insights = self.list_memories(limit=20)
        raw_total = sum(len(t) for t in texts)

        # Unique cluster insights — the actual compression unit
        cluster_insights: dict[str, str] = {}
        for m in insights:
            if m.cluster_id not in cluster_insights:
                cluster_insights[m.cluster_id] = m.abstracted_content

        compressed_total = sum(len(v) for v in cluster_insights.values())
        traditional_storage = raw_total  # N full chunks
        noesis_storage = compressed_total  # 1 insight per cluster

        return {
            "raw_inputs": len(texts),
            "raw_chars": raw_total,
            "unique_clusters": len(cluster_insights),
            "compressed_chars": compressed_total,
            "compression_ratio": round(traditional_storage / max(noesis_storage, 1), 2),
            "events_per_insight": round(len(texts) / max(len(cluster_insights), 1), 1),
            "insight_examples": list(cluster_insights.values())[:3],
            "traditional_would_store": f"{len(texts)} full text chunks ({raw_total} chars)",
            "noesis_stores": f"{len(cluster_insights)} semantic insights ({compressed_total} chars)",
            "example_insight": list(cluster_insights.values())[0] if cluster_insights else "",
        }

    # ── Distributed Sync (Innovation #3) ──────────────────────────

    def export_memory(self, memory_id: str) -> Path | None:
        packet = self.store.get_packet(memory_id)
        if not packet:
            record = self.store.get_memory(memory_id)
            if not record:
                return None
            edges = [(e[0], e[1], e[2]) for e in self.store.get_graph_edges_full() if e[3] == memory_id]
            packet = self.symbolic.compress(record, edges)
        return self.sync.export_packet(packet, self.agent_id)

    def import_memory(self, path: str | Path, source_agent: str = "remote") -> dict[str, Any]:
        packet = self.sync.import_packet(path)
        return self._integrate_packet(packet, source_agent)

    def sync_to_peer(self, peer_url: str, memory_id: str | None = None) -> dict:
        """Push memory packet(s) to another Noesis agent."""
        client = MeshClient(peer_url)
        if not client.health():
            return {"success": False, "error": f"Peer unreachable: {peer_url}"}

        pushed = []
        if memory_id:
            packet = self.store.get_packet(memory_id)
            if packet:
                client.push_packet(packet.to_dict())
                pushed.append(memory_id)
        else:
            for summary in self.store.list_packet_summaries():
                pkt = self.store.get_packet(summary["memory_id"])
                if pkt:
                    client.push_packet(pkt.to_dict())
                    pushed.append(summary["memory_id"])

        return {"success": True, "pushed": pushed, "peer": peer_url}

    def sync_from_peer(self, peer_url: str) -> dict:
        """Pull and integrate all memory packets from a peer agent."""
        client = MeshClient(peer_url)
        if not client.health():
            return {"success": False, "error": f"Peer unreachable: {peer_url}"}

        imported = []
        for summary in client.pull_all():
            try:
                full = client.get_packet(summary["memory_id"])
                packet = self.sync.import_packet_from_dict(full)
                record = self._integrate_packet(packet, full.get("metadata", {}).get("agent_id", "peer"))
                imported.append(record.memory_id)
            except Exception as e:
                logger.warning("Failed to import %s: %s", summary.get("memory_id"), e)

        return {"success": True, "imported": imported, "peer": peer_url}

    def start_mesh_server(self, port: int | None = None) -> None:
        """Start LAN mesh server for other agents to sync."""
        port = port or self.config.get("sync", {}).get("mesh_port", 8765)
        self._mesh_server = MeshServer(port=port)
        self._mesh_server.register_handlers(
            list_packets=lambda: self.store.list_packet_summaries(),
            get_packet=lambda mid: self.store.get_packet(mid).to_dict() if self.store.get_packet(mid) else None,
            push_packet=lambda data: self._handle_push(data),
            sync_all=lambda agent_id: self.sync_from_peer(f"http://127.0.0.1:{port}"),
        )
        self._mesh_server.start(background=True)

    # ── Memory Maintenance (Innovation #5) ────────────────────────

    def run_forgetting_cycle(self) -> dict:
        forgotten = self.forgetting.apply_decay_cycle()
        for mem_id in forgotten:
            self.store.delete_memory(mem_id)
            self._embedding_cache.pop(mem_id, None)

        redundant = self.redundancy.eliminate(self._embedding_cache)
        return {"forgotten": forgotten, "redundancy_merged": redundant}

    def evolve_memories(self) -> int:
        """Re-run insight extraction on all clusters."""
        count = 0
        for record in self.store.list_memories(limit=200):
            texts = [record.content]
            insight = self.semantic.insights.extract_cluster_insight(
                record.cluster_id, texts, record.concepts, record.access_count + 1
            )
            if record.category == MemoryCategory.INSIGHT or record.access_count >= 3:
                record.abstracted_content = f"Insight: {insight.removeprefix('Insight: ')}"
                self.store.save_memory(record)
                count += 1
        return count

    # ── Query API ─────────────────────────────────────────────────

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        return self.store.get_memory(memory_id)

    def list_memories(self, cluster: str | None = None, limit: int = 20) -> list[MemoryRecord]:
        return self.store.list_memories(cluster_id=cluster, limit=limit)

    def get_graph(self, concept: str) -> dict:
        return self.graph.get_subgraph(concept)

    def get_packet(self, memory_id: str) -> MemoryPacket | None:
        return self.store.get_packet(memory_id)

    def stats(self) -> dict[str, Any]:
        memories = self.store.list_memories(limit=1000)
        categories: dict[str, int] = {}
        total_raw_estimate = 0
        total_compressed = 0
        for m in memories:
            categories[m.category.value] = categories.get(m.category.value, 0) + 1
            total_compressed += len(m.abstracted_content)
            comp = m.metadata.get("compression", {})
            total_raw_estimate += comp.get("raw_total_chars", len(m.content))

        return {
            "total_memories": len(memories),
            "graph_nodes": self.graph.graph.number_of_nodes(),
            "graph_edges": self.graph.graph.number_of_edges(),
            "categories": categories,
            "agent_id": self.agent_id,
            "estimated_compression_ratio": round(total_raw_estimate / max(total_compressed, 1), 2),
            "hot_clusters": self.predictive.get_hot_clusters(),
            "innovations_active": [
                "semantic_compression",
                "symbolic_portable_packets",
                "distributed_sync",
                "knowledge_graph_recall",
                "adaptive_forgetting",
            ],
        }

    # ── Internal ──────────────────────────────────────────────────

    def _process_raw(self, raw: RawInput) -> dict[str, Any] | None:
        parsed = self.semantic.process(raw)
        if not parsed:
            return None

        existing_id = self._find_similar_memory(parsed.embedding)
        merged = False
        if existing_id:
            record = self.store.get_memory(existing_id)
            if record:
                record = self.semantic.merge_with_existing(parsed, record)
                merged = True
        else:
            record = self.semantic.to_memory_record(parsed, raw.input_type.value)

        self.semantic.clusters.add_to_cluster(parsed.cluster_id, record.memory_id, parsed.embedding or [])
        graph_edges = self.graph.add_memory_concepts(record.memory_id, record.concepts)
        self.store.save_memory(record, parsed.embedding)
        if parsed.embedding:
            self._embedding_cache[record.memory_id] = parsed.embedding

        packet = self.symbolic.compress(record, graph_edges)
        packet.metadata["agent_id"] = self.agent_id
        self.store.save_packet(packet)

        compression_stats = self.semantic.get_compression_stats(parsed.cluster_id)

        return {
            "memory_id": record.memory_id,
            "importance": record.importance,
            "category": record.category.value,
            "cluster": record.cluster_id,
            "summary": record.abstracted_content,
            "concepts": [c.label for c in record.concepts],
            "tags": record.tags,
            "token_count": len(packet.token_ids),
            "bytecode_bytes": len(packet.bytecode),
            "merged": merged,
            "compression": compression_stats,
        }

    def _find_similar_memory(self, embedding: list[float] | None) -> str | None:
        if not embedding:
            return None
        similar = self.semantic.embeddings.find_similar(
            embedding, list(self._embedding_cache.items()), self.semantic.similarity_threshold
        )
        return similar[0][0] if similar else None

    def _integrate_packet(self, packet: MemoryPacket, source_agent: str) -> dict[str, Any]:
        payload = self.symbolic.decompress(packet)
        embedding = None
        if payload.get("summary"):
            embedding = self.semantic.embeddings.encode(payload["summary"])
        record = self.packet_merge.merge_packet(packet, source_agent, embedding)
        if embedding:
            self._embedding_cache[record.memory_id] = embedding
        return {
            "memory_id": record.memory_id,
            "summary": record.abstracted_content,
            "importance": record.importance,
            "synced_from": source_agent,
            "collective_memory": True,
        }

    def _handle_push(self, data: dict) -> dict:
        packet = self.sync.import_packet_from_dict(data)
        result = self._integrate_packet(packet, data.get("metadata", {}).get("agent_id", "peer"))
        return {"status": "integrated", **result}
