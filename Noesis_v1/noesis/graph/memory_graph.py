"""Step 6 — Knowledge Graph Construction & associative recall."""

from __future__ import annotations

from noesis.core.models import ReconstructedContext, SemanticConcept
from noesis.storage.sqlite_store import SQLiteMemoryStore

try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore


class MemoryGraphEngine:
    """
    Memory Graph Engine — relationship mapping, associative recall, contextual linking.
    Phase 3 ready for Neo4j backend; MVP uses NetworkX.
    """

    def __init__(self, store: SQLiteMemoryStore, max_depth: int = 4):
        if nx is None:
            raise ImportError("networkx required. Install: pip install networkx")
        self.store = store
        self.max_depth = max_depth
        self.graph = nx.DiGraph()
        self.hydrate_from_store()

    def hydrate_from_store(self) -> int:
        """Reload knowledge graph from persistent storage."""
        self.graph.clear()
        count = 0
        for from_n, to_n, relation, mem_id, weight in self.store.get_graph_edges_full():
            self.graph.add_node(from_n)
            self.graph.add_node(to_n)
            self.graph.add_edge(from_n, to_n, relation=relation, memory_id=mem_id, weight=weight)
            count += 1
        return count

    def add_memory_concepts(self, memory_id: str, concepts: list[SemanticConcept]) -> list[tuple[str, str, str]]:
        """Build graph edges from semantic concepts."""
        edges = []
        entity_nodes = [
            c for c in concepts
            if c.concept_type in ("framework", "technology", "concept", "topic", "person", "profile", "entity")
        ]

        for i, a in enumerate(entity_nodes):
            self.graph.add_node(a.label, type=a.concept_type)
            for b in entity_nodes[i + 1 :]:
                self.graph.add_node(b.label, type=b.concept_type)
                relation = "relates_to"
                self.graph.add_edge(a.label, b.label, relation=relation, memory_id=memory_id)
                edges.append((a.label, b.label, relation))
                self.store.save_graph_edge(a.label, b.label, relation, memory_id)

        # Relationship concepts
        for c in concepts:
            if c.concept_type == "relationship" and len(c.related) >= 2:
                a, b = c.related[0], c.related[1]
                self.graph.add_edge(a, b, relation="associated", memory_id=memory_id)
                edges.append((a, b, "associated"))
                self.store.save_graph_edge(a, b, "associated", memory_id)

        return edges

    def recall_associative(self, query_concept: str, depth: int | None = None) -> list[str]:
        """Traverse graph from a concept node."""
        depth = depth or self.max_depth
        if query_concept not in self.graph:
            # Try case-insensitive match
            match = next((n for n in self.graph.nodes if n.lower() == query_concept.lower()), None)
            if not match:
                return []
            query_concept = match

        visited = set()
        queue = [(query_concept, 0)]
        results = []

        while queue:
            node, d = queue.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            results.append(node)

            for neighbor in self.graph.successors(node):
                if neighbor not in visited:
                    queue.append((neighbor, d + 1))
            for predecessor in self.graph.predecessors(node):
                if predecessor not in visited:
                    queue.append((predecessor, d + 1))

        return results

    def reconstruct_context(self, memory_id: str, summary: str, concepts: list[str]) -> ReconstructedContext:
        """Step 10 — Context reconstruction via graph traversal."""
        graph_path: list[str] = []
        related_memories: list[str] = []

        for concept in concepts[:3]:
            path = self.recall_associative(concept, depth=2)
            graph_path.extend(path)
            for mid in self.store.get_memory_ids_for_concept(concept):
                if mid != memory_id and mid not in related_memories:
                    related_memories.append(mid)

        graph_path = list(dict.fromkeys(graph_path))[:15]
        confidence = min(1.0, 0.5 + len(graph_path) * 0.05 + len(related_memories) * 0.05)

        return ReconstructedContext(
            memory_id=memory_id,
            summary=summary,
            related_memories=related_memories[:5],
            concepts=concepts,
            graph_path=graph_path,
            confidence=round(confidence, 2),
        )

    def get_subgraph(self, center: str) -> dict:
        """Export subgraph for visualization or sync."""
        nodes = self.recall_associative(center)
        edges = []
        for u, v, data in self.graph.edges(data=True):
            if u in nodes and v in nodes:
                edges.append({"from": u, "to": v, "relation": data.get("relation", "relates_to")})
        return {"center": center, "nodes": nodes, "edges": edges}
