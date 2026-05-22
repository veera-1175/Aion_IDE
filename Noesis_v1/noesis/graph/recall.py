"""Phase 3 — Graph-first associative recall (Innovation #4)."""

from __future__ import annotations

from noesis.core.models import MemoryRecord, ReconstructedContext, SemanticConcept
from noesis.graph.memory_graph import MemoryGraphEngine
from noesis.storage.sqlite_store import SQLiteMemoryStore


class GraphRecallEngine:
    """
    Unlike vector DB chunk retrieval, Noesis recalls via concept graph traversal.
    FastAPI -> Redis -> Async Workers -> Scalability
    """

    def __init__(self, graph: MemoryGraphEngine, store: SQLiteMemoryStore):
        self.graph = graph
        self.store = store

    def recall_by_concepts(
        self,
        concepts: list[SemanticConcept],
        limit: int = 5,
    ) -> list[ReconstructedContext]:
        """Traverse graph from query concepts, collect related memories."""
        seen_memories: set[str] = set()
        contexts: list[ReconstructedContext] = []

        for concept in concepts:
            if concept.concept_type == "relationship":
                continue

            path = self.graph.recall_associative(concept.label, depth=3)
            memory_ids = self.store.get_memory_ids_for_concept(concept.label)

            for mem_id in memory_ids:
                if mem_id in seen_memories:
                    continue
                seen_memories.add(mem_id)
                record = self.store.get_memory(mem_id)
                if not record:
                    continue

                ctx = ReconstructedContext(
                    memory_id=mem_id,
                    summary=record.abstracted_content,
                    related_memories=self._find_related(mem_id, path),
                    concepts=[c.label for c in record.concepts],
                    graph_path=path,
                    confidence=self._score_confidence(path, record),
                )
                contexts.append(ctx)

        contexts.sort(key=lambda c: c.confidence, reverse=True)
        return contexts[:limit]

    def recall_path_between(self, concept_a: str, concept_b: str) -> list[str]:
        """Find associative path between two concepts."""
        import networkx as nx

        g = self.graph.graph
        a = self._resolve_node(concept_a)
        b = self._resolve_node(concept_b)
        if not a or not b:
            return []
        try:
            path = nx.shortest_path(g.to_undirected(), a, b)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def explain_recall(self, query_concepts: list[str]) -> dict:
        """Human-readable explanation of graph-based recall."""
        paths = []
        for i, a in enumerate(query_concepts[:3]):
            for b in query_concepts[i + 1 : i + 2]:
                path = self.recall_path_between(a, b)
                if path:
                    paths.append(" <-> ".join(path))

        return {
            "method": "graph_traversal",
            "description": "Concept relationships, not raw text similarity",
            "associative_paths": paths,
            "advantage_vs_vector_db": "Structured reasoning over concept links",
        }

    def _find_related(self, memory_id: str, path: list[str]) -> list[str]:
        related = []
        for node in path:
            for mid in self.store.get_memory_ids_for_concept(node):
                if mid != memory_id and mid not in related:
                    related.append(mid)
        return related[:5]

    def _score_confidence(self, path: list[str], record: MemoryRecord) -> float:
        base = 0.4 + min(0.4, len(path) * 0.05)
        base += min(0.2, record.importance * 0.2)
        return round(min(1.0, base), 2)

    def _resolve_node(self, name: str) -> str | None:
        if name in self.graph.graph:
            return name
        return next((n for n in self.graph.graph.nodes if n.lower() == name.lower()), None)
