"""Layer 1 — Semantic Cognition Engine: orchestrates parsing, scoring, abstraction."""

from __future__ import annotations

from datetime import datetime, timezone

from noesis.core.models import MemoryCategory, MemoryRecord, ParsedMemory, RawInput
from noesis.semantic.abstraction import SemanticAbstractor
from noesis.semantic.categorization import MemoryCategorizer
from noesis.semantic.clustering import SemanticClusterManager
from noesis.semantic.embeddings import EmbeddingEngine
from noesis.semantic.evolution import MemoryEvolutionEngine
from noesis.semantic.importance import ImportanceScorer
from noesis.semantic.insights import InsightExtractor
from noesis.semantic.parser import SemanticParser
from noesis.storage.sqlite_store import SQLiteMemoryStore


class SemanticCognitionEngine:
    """
    Layer 1 — Semantic Cognition Engine
    Innovation: compresses meaning, not raw text.
    """

    def __init__(self, config: dict, store: SQLiteMemoryStore):
        sem_cfg = config.get("semantic", {})
        self.parser = SemanticParser()
        self.scorer = ImportanceScorer(min_importance=sem_cfg.get("min_importance", 0.15))
        self.abstractor = SemanticAbstractor()
        self.categorizer = MemoryCategorizer()
        self.embeddings = EmbeddingEngine(sem_cfg.get("embedding_model", "all-MiniLM-L6-v2"))
        self.clusters = SemanticClusterManager(
            self.embeddings,
            similarity_threshold=sem_cfg.get("cluster_threshold", 0.72),
        )
        self.insights = InsightExtractor()
        self.evolution = MemoryEvolutionEngine()
        self.store = store
        self.similarity_threshold = sem_cfg.get("similarity_threshold", 0.75)
        self._cluster_text_cache: dict[str, list[str]] = {}

    def process(self, raw: RawInput) -> ParsedMemory | None:
        concepts = self.parser.parse(raw.content)
        recurrence = self.scorer.get_recurrence(concepts)
        importance = self.scorer.score(raw.content, concepts, cluster_recurrence=recurrence)

        if importance < self.scorer.min_importance:
            return None

        category = self.categorizer.categorize(raw.content, raw.input_type, recurrence)
        proposed_cluster = self.categorizer.derive_cluster_id(concepts)

        # Provisional embedding for clustering
        provisional_summary = self.abstractor.abstract([raw.content], concepts, category)
        embedding = self.embeddings.encode(provisional_summary)

        cluster_id, is_new = self.clusters.find_or_create_cluster(
            proposed_cluster, embedding, [c.label for c in concepts]
        )

        cluster_texts = self._cluster_text_cache.get(cluster_id, [])
        cluster_texts.append(raw.content)
        self._cluster_text_cache[cluster_id] = cluster_texts[-20:]

        cluster_count = len(cluster_texts)
        insight = self.insights.extract_cluster_insight(
            cluster_id, cluster_texts, concepts, cluster_count
        )

        if self.insights.should_promote_to_insight(cluster_count, category):
            category = MemoryCategory.INSIGHT
            abstracted = f"Insight: {insight.removeprefix('Insight: ')}"
        else:
            abstracted = self.abstractor.abstract(cluster_texts, concepts, category)

        self.clusters.set_cluster_insight(cluster_id, abstracted)
        tags = list({c.label.lower() for c in concepts if c.concept_type != "relationship"})

        return ParsedMemory(
            raw_text=raw.content,
            concepts=concepts,
            importance=importance,
            semantic_summary=abstracted,
            category=category,
            cluster_id=cluster_id,
            embedding=embedding,
            tags=tags,
        )

    def to_memory_record(self, parsed: ParsedMemory, source_type: str = "conversation") -> MemoryRecord:
        now = datetime.now(timezone.utc)
        compression = self.insights.compress_vs_raw_size(
            self._cluster_text_cache.get(parsed.cluster_id, [parsed.raw_text]),
            parsed.semantic_summary,
        )
        return MemoryRecord(
            memory_id=MemoryRecord.new_id(),
            content=parsed.raw_text,
            abstracted_content=parsed.semantic_summary,
            category=parsed.category,
            importance=parsed.importance,
            cluster_id=parsed.cluster_id,
            concepts=parsed.concepts,
            tags=parsed.tags,
            created_at=now,
            updated_at=now,
            source_input_type=source_type,
            metadata={"compression": compression},
        )

    def merge_with_existing(self, parsed: ParsedMemory, record: MemoryRecord) -> MemoryRecord:
        cluster_count = len(self._cluster_text_cache.get(parsed.cluster_id, []))
        return self.evolution.evolve(record, parsed, cluster_count)

    def get_compression_stats(self, cluster_id: str) -> dict | None:
        cluster = self.clusters.get_cluster(cluster_id)
        texts = self._cluster_text_cache.get(cluster_id, [])
        if cluster and texts:
            return self.insights.compress_vs_raw_size(texts, cluster.insight_summary or "")
        return None
