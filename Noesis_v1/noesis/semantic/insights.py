"""Phase 2 — Insight extraction: compress many raw events into one semantic insight."""

from __future__ import annotations

from noesis.core.models import MemoryCategory, SemanticConcept


class InsightExtractor:
    """
    Innovation #1 — Semantic Compression
    Transforms repeated raw experiences into a single evolving insight.
    """

    def extract_cluster_insight(
        self,
        cluster_id: str,
        raw_texts: list[str],
        concepts: list[SemanticConcept],
        input_count: int,
    ) -> str:
        """Generate insight-level summary from cluster history."""
        topics = [c.label for c in concepts if c.concept_type == "topic"]
        techs = [c.label for c in concepts if c.concept_type in ("framework", "technology")]
        concepts_only = [c.label for c in concepts if c.concept_type == "concept"]
        problems = [c.label for c in concepts if c.concept_type == "problem"]

        unique_techs = list(dict.fromkeys(techs))[:5]
        unique_concepts = list(dict.fromkeys(concepts_only))[:5]

        if input_count >= 3 and unique_techs:
            tech_str = ", ".join(unique_techs)
            if topics:
                return f"User is developing expertise in {topics[0]} using {tech_str}."
            return f"User is building scalable backend proficiency with {tech_str}."

        if problems and unique_techs:
            return (
                f"User is learning to resolve {problems[0]} issues using "
                f"{', '.join(unique_techs[:3])}."
            )

        if unique_concepts:
            return (
                f"User is acquiring knowledge in {', '.join(unique_concepts[:4])} "
                f"({input_count} related experiences)."
            )

        if len(raw_texts) >= 2:
            return f"Recurring focus on {cluster_id.replace('_', ' ')} across {input_count} interactions."

        return raw_texts[-1][:120] if raw_texts else "General learning pattern."

    def should_promote_to_insight(self, input_count: int, category: MemoryCategory) -> bool:
        return input_count >= 3 or category == MemoryCategory.INSIGHT

    def compress_vs_raw_size(self, raw_texts: list[str], insight: str) -> dict:
        """Demonstrate compression — key innovation metric."""
        raw_chars = sum(len(t) for t in raw_texts)
        insight_chars = len(insight)
        ratio = raw_chars / max(insight_chars, 1)
        return {
            "raw_total_chars": raw_chars,
            "insight_chars": insight_chars,
            "compression_ratio": round(ratio, 2),
            "raw_event_count": len(raw_texts),
            "stored_as": "1 semantic insight",
        }
