"""SQLite persistence layer for memories and packets."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from noesis.core.models import MemoryCategory, MemoryRecord, MemoryPacket, SemanticConcept


class SQLiteMemoryStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    abstracted_content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    importance REAL NOT NULL,
                    cluster_id TEXT NOT NULL,
                    concepts_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    embedding_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    retention_score REAL DEFAULT 1.0,
                    source_input_type TEXT DEFAULT 'conversation',
                    metadata_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS memory_packets (
                    packet_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    bytecode BLOB NOT NULL,
                    token_ids_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES memories(memory_id)
                );

                CREATE TABLE IF NOT EXISTS raw_inputs (
                    input_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    input_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL,
                    processed INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node TEXT NOT NULL,
                    to_node TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    memory_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_cluster ON memories(cluster_id);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
                CREATE INDEX IF NOT EXISTS idx_graph_from ON graph_edges(from_node);
            """)

    def save_memory(self, record: MemoryRecord, embedding: list[float] | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (memory_id, content, abstracted_content, category, importance, cluster_id,
                 concepts_json, tags_json, embedding_json, created_at, updated_at,
                 access_count, retention_score, source_input_type, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.memory_id,
                    record.content,
                    record.abstracted_content,
                    record.category.value,
                    record.importance,
                    record.cluster_id,
                    json.dumps([self._concept_to_dict(c) for c in record.concepts]),
                    json.dumps(record.tags),
                    json.dumps(embedding) if embedding else None,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.access_count,
                    record.retention_score,
                    record.source_input_type,
                    json.dumps(record.metadata),
                ),
            )

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,)).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_memories(
        self,
        cluster_id: str | None = None,
        min_importance: float = 0.0,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        query = "SELECT * FROM memories WHERE importance >= ?"
        params: list[Any] = [min_importance]
        if cluster_id:
            query += " AND cluster_id = ?"
            params.append(cluster_id)
        query += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def save_packet(self, packet: MemoryPacket) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_packets
                (packet_id, memory_id, bytecode, token_ids_json, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    packet.memory_id,
                    packet.memory_id,
                    packet.bytecode,
                    json.dumps(packet.token_ids),
                    json.dumps(packet.to_dict()),
                    packet.timestamp,
                ),
            )

    def get_packet(self, memory_id: str) -> MemoryPacket | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM memory_packets WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        if not row:
            return None
        data = json.loads(row["payload_json"])
        return MemoryPacket(
            memory_id=data["memory_id"],
            importance=data["importance"],
            semantic_cluster=data["semantic_cluster"],
            category=data["category"],
            semantic_summary=data["semantic_summary"],
            bytecode=bytes.fromhex(data["bytecode"]),
            token_ids=[],  # loaded separately if needed
            graph_edges=[tuple(e) for e in data.get("graph_edges", [])],
            tags=data.get("tags", []),
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
        )

    def log_raw_input(self, content: str, input_type: str, source: str, metadata: dict) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO raw_inputs (content, input_type, source, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (content, input_type, source, json.dumps(metadata), datetime.now(timezone.utc).isoformat()),
            )
            return cur.lastrowid or 0

    def save_graph_edge(self, from_node: str, to_node: str, relation: str, memory_id: str, weight: float = 1.0) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_edges (from_node, to_node, relation, weight, memory_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (from_node, to_node, relation, weight, memory_id, datetime.now(timezone.utc).isoformat()),
            )

    def get_graph_edges(self, node: str | None = None) -> list[tuple[str, str, str, float]]:
        with self._connect() as conn:
            if node:
                rows = conn.execute(
                    "SELECT from_node, to_node, relation, weight FROM graph_edges WHERE from_node = ? OR to_node = ?",
                    (node, node),
                ).fetchall()
            else:
                rows = conn.execute("SELECT from_node, to_node, relation, weight FROM graph_edges").fetchall()
        return [(r["from_node"], r["to_node"], r["relation"], r["weight"]) for r in rows]

    def get_graph_edges_full(self) -> list[tuple[str, str, str, str, float]]:
        """Returns (from, to, relation, memory_id, weight)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT from_node, to_node, relation, memory_id, weight FROM graph_edges"
            ).fetchall()
        return [
            (r["from_node"], r["to_node"], r["relation"], r["memory_id"] or "", r["weight"])
            for r in rows
        ]

    def get_memory_ids_for_concept(self, concept: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT memory_id FROM graph_edges
                WHERE from_node = ? OR to_node = ?
                AND memory_id IS NOT NULL
                """,
                (concept, concept),
            ).fetchall()
        return [r["memory_id"] for r in rows if r["memory_id"]]

    def get_all_embeddings(self) -> dict[str, list[float]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT memory_id, embedding_json FROM memories WHERE embedding_json IS NOT NULL"
            ).fetchall()
        result = {}
        for r in rows:
            result[r["memory_id"]] = json.loads(r["embedding_json"])
        return result

    def list_packet_summaries(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT memory_id, payload_json FROM memory_packets ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        summaries = []
        for r in rows:
            data = json.loads(r["payload_json"])
            summaries.append({
                "memory_id": data["memory_id"],
                "importance": data["importance"],
                "semantic_cluster": data["semantic_cluster"],
                "category": data["category"],
                "summary": data["semantic_summary"][:120],
            })
        return summaries

    def search_by_text(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Keyword search on raw content, summary, and tags — for names and personal facts."""
        import re
        stop = {"what", "is", "my", "the", "a", "an", "how", "who", "are", "was", "were", "tell", "about", "me", "do", "you", "know"}
        tokens = [
            t.lower()
            for t in re.findall(r"\b[A-Za-z]{2,}\b", query)
            if t.lower() not in stop
        ]
        # Name queries: search all profile memories when user asks about their name
        if re.search(r"\b(name|who am i)\b", query, re.I):
            tokens.append("name")
            tokens.append("profile")
        if not tokens:
            tokens = [t.lower() for t in re.findall(r"\b[A-Za-z]{3,}\b", query)]

        if not tokens:
            return []

        records = self.list_memories(limit=200)
        scored: list[tuple[float, MemoryRecord]] = []
        for rec in records:
            hay = " ".join([
                rec.content,
                rec.abstracted_content,
                " ".join(rec.tags),
                " ".join(c.label for c in rec.concepts),
            ]).lower()
            score = sum(2.0 if tok in hay else 0.0 for tok in tokens)
            if "name" in query.lower() and "name" in hay:
                score += 3.0
            if score > 0:
                scored.append((score + rec.importance, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def count_by_cluster(self, cluster_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM memories WHERE cluster_id = ?", (cluster_id,)
            ).fetchone()
        return row["cnt"] if row else 0

    def increment_access(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, updated_at = ? WHERE memory_id = ?",
                (datetime.now(timezone.utc).isoformat(), memory_id),
            )

    def update_retention(self, memory_id: str, retention_score: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET retention_score = ? WHERE memory_id = ?",
                (retention_score, memory_id),
            )

    def delete_memory(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memory_packets WHERE memory_id = ?", (memory_id,))
            conn.execute("DELETE FROM graph_edges WHERE memory_id = ?", (memory_id,))
            conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))

    @staticmethod
    def _concept_to_dict(c: SemanticConcept) -> dict:
        return {"label": c.label, "concept_type": c.concept_type, "confidence": c.confidence, "related": c.related}

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        concepts_data = json.loads(row["concepts_json"])
        concepts = [
            SemanticConcept(
                label=c["label"],
                concept_type=c["concept_type"],
                confidence=c.get("confidence", 1.0),
                related=c.get("related", []),
            )
            for c in concepts_data
        ]
        return MemoryRecord(
            memory_id=row["memory_id"],
            content=row["content"],
            abstracted_content=row["abstracted_content"],
            category=MemoryCategory(row["category"]),
            importance=row["importance"],
            cluster_id=row["cluster_id"],
            concepts=concepts,
            tags=json.loads(row["tags_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            access_count=row["access_count"],
            retention_score=row["retention_score"],
            source_input_type=row["source_input_type"],
            metadata=json.loads(row["metadata_json"]),
        )
