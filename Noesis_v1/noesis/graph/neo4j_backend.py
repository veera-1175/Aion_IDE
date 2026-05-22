"""Phase 3 — Optional Neo4j backend for production graph storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noesis.core.models import SemanticConcept


class Neo4jGraphBackend:
    """
    Optional Neo4j integration for large-scale knowledge graphs.
    Install: pip install neo4j
    Configure: graph.backend = neo4j in settings.yaml
    """

    def __init__(self, uri: str, user: str, password: str):
        try:
            from neo4j import GraphDatabase
        except ImportError as e:
            raise ImportError("neo4j package required: pip install neo4j") from e

        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def add_concepts(self, memory_id: str, concepts: list[SemanticConcept]) -> None:
        with self.driver.session() as session:
            for c in concepts:
                session.run(
                    "MERGE (n:Concept {name: $name}) SET n.type = $type",
                    name=c.label,
                    type=c.concept_type,
                )
                session.run(
                    "MERGE (m:Memory {id: $id})",
                    id=memory_id,
                )
                session.run(
                    "MATCH (m:Memory {id: $id}), (n:Concept {name: $name}) "
                    "MERGE (m)-[:REMEMBERS]->(n)",
                    id=memory_id,
                    name=c.label,
                )

    def close(self) -> None:
        self.driver.close()
