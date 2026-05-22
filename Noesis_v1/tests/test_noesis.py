"""Noesis unit tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from noesis.core.engine import NoesisEngine
from noesis.core.models import MemoryCategory
from noesis.semantic.parser import SemanticParser
from noesis.semantic.importance import ImportanceScorer
from noesis.semantic.categorization import MemoryCategorizer
from noesis.symbolic.bytecode import BytecodeEncoder


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def engine(db_path):
    return NoesisEngine(db_path=db_path)


class TestSemanticParser:
    def test_extracts_fastapi_redis(self):
        parser = SemanticParser()
        concepts = parser.parse("User asked about FastAPI scaling with Redis cache")
        labels = [c.label for c in concepts]
        assert any("Fastapi" in l or "Redis" in l for l in labels)

    def test_extracts_relationships(self):
        parser = SemanticParser()
        concepts = parser.parse("FastAPI and Redis for async scaling")
        types = {c.concept_type for c in concepts}
        assert "framework" in types or "technology" in types


class TestImportanceScorer:
    def test_low_value_typo(self):
        scorer = ImportanceScorer()
        score = scorer.score("ok", [])
        assert score <= 0.1

    def test_high_value_technical(self):
        scorer = ImportanceScorer()
        from noesis.core.models import SemanticConcept
        concepts = [
            SemanticConcept("FastAPI", "framework"),
            SemanticConcept("Redis", "technology"),
            SemanticConcept("Scaling", "concept"),
        ]
        score = scorer.score(
            "User deployed Redis cluster for FastAPI async scaling in production",
            concepts,
            cluster_recurrence=10,
        )
        assert score >= 0.5


class TestMemoryCategorizer:
    def test_procedural_detection(self):
        cat = MemoryCategorizer()
        from noesis.core.models import InputType
        result = cat.categorize("Docker → Redis → Nginx → Gunicorn", InputType.LOG)
        assert result == MemoryCategory.PROCEDURAL

    def test_episodic_detection(self):
        cat = MemoryCategorizer()
        from noesis.core.models import InputType
        result = cat.categorize("User deployed Redis cluster on May 20", InputType.EVENT)
        assert result == MemoryCategory.EPISODIC


class TestBytecodeEncoder:
    def test_roundtrip(self):
        enc = BytecodeEncoder()
        payload = {"summary": "test", "token_ids": [1, 2, 3]}
        bytecode = enc.encode(payload)
        decoded = enc.decode(bytecode)
        assert decoded["summary"] == "test"
        assert decoded["token_ids"] == [1, 2, 3]


class TestNoesisEngine:
    def test_remember_returns_memory(self, engine):
        result = engine.remember("User asked about FastAPI scaling with Redis")
        assert result is not None
        assert "memory_id" in result
        assert result["importance"] > 0.15

    def test_skip_low_value(self, engine):
        result = engine.remember("ok")
        assert result is None

    def test_list_memories(self, engine):
        engine.remember("FastAPI async worker scaling with Redis cache")
        engine.remember("Deployed Docker and Redis for API performance")
        memories = engine.list_memories()
        assert len(memories) >= 1

    def test_semantic_merge(self, engine):
        engine.remember("User asked about FastAPI scaling")
        r2 = engine.remember("User asked about FastAPI async patterns again")
        assert r2 is not None

    def test_stats(self, engine):
        engine.remember("Backend distributed systems with Redis")
        stats = engine.stats()
        assert stats["total_memories"] >= 1
        assert "categories" in stats

    def test_export_import(self, engine, tmp_path):
        result = engine.remember("Redis improves FastAPI API scalability")
        assert result
        export_path = engine.export_memory(result["memory_id"])
        assert export_path and export_path.exists()
        imported = engine.import_memory(export_path)
        assert "summary" in imported

    def test_graph_subgraph(self, engine):
        engine.remember("FastAPI connects to Redis for caching and async workers")
        subgraph = engine.get_graph("Fastapi")
        assert "nodes" in subgraph
