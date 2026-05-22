"""Tests for Phases 2-5 innovations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from noesis import NoesisEngine
from noesis.semantic.insights import InsightExtractor
from noesis.semantic.clustering import SemanticClusterManager
from noesis.semantic.embeddings import EmbeddingEngine


@pytest.fixture
def engine(tmp_path):
    return NoesisEngine(db_path=str(tmp_path / "test.db"))


class TestSemanticCompression:
    def test_cluster_insight_compression(self):
        ext = InsightExtractor()
        from noesis.core.models import SemanticConcept
        concepts = [
            SemanticConcept("Fastapi", "framework"),
            SemanticConcept("Redis", "technology"),
            SemanticConcept("Scaling", "concept"),
        ]
        raw = [
            "User asked about Redis",
            "User asked about async workers",
            "User asked about scaling",
        ]
        insight = ext.extract_cluster_insight("backend", raw, concepts, 3)
        assert "expertise" in insight.lower() or "proficiency" in insight.lower() or "Redis" in insight
        stats = ext.compress_vs_raw_size(raw, insight)
        assert stats["compression_ratio"] > 1.0

    def test_compare_with_traditional(self, engine):
        result = engine.compare_with_traditional([
            "User asked about Redis caching for API performance",
            "User asked about async workers and bottlenecks in production",
            "User asked about FastAPI scaling with Redis and workers",
        ])
        assert result["unique_clusters"] <= result["raw_inputs"]
        assert result["events_per_insight"] >= 1.0
        assert "traditional_would_store" in result


class TestPortableMemory:
    def test_import_creates_collective_memory(self, engine, tmp_path):
        r = engine.remember("Redis improves FastAPI scalability in production")
        export = engine.export_memory(r["memory_id"])

        engine2 = NoesisEngine(db_path=str(tmp_path / "agent2.db"))
        imported = engine2.import_memory(export, source_agent="agent-alpha")
        assert imported["collective_memory"] is True
        assert engine2.stats()["total_memories"] >= 1


class TestGraphRecall:
    def test_explain_recall(self, engine):
        engine.remember("FastAPI connects to Redis for async worker scaling")
        explanation = engine.explain_recall("FastAPI Redis")
        assert explanation["innovation"] == "Knowledge graph associative recall"
        assert "vs_traditional_ai" in explanation

    def test_graph_mode_recall(self, engine):
        engine.remember("FastAPI async scaling with Redis cache")
        contexts = engine.recall("scaling", mode="graph")
        assert isinstance(contexts, list)


class TestAdaptiveForgetting:
    def test_forgetting_cycle_returns_dict(self, engine):
        engine.remember("trivial")
        result = engine.run_forgetting_cycle()
        assert "forgotten" in result
        assert "redundancy_merged" in result
