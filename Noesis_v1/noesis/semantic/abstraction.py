"""Step 4 — Semantic Compression: abstract experiences into insights."""

from __future__ import annotations

from noesis.core.models import MemoryCategory, SemanticConcept


class SemanticAbstractor:
    """
    Compresses raw experiences into semantic abstractions.
    Instead of storing every conversation verbatim, generates insight-level summaries.
    """

    CATEGORY_TEMPLATES = {
        MemoryCategory.EPISODIC: "Event: {detail}",
        MemoryCategory.SEMANTIC: "Knowledge: {detail}",
        MemoryCategory.PROCEDURAL: "Workflow: {detail}",
        MemoryCategory.INSIGHT: "Insight: {detail}",
    }

    def abstract(
        self,
        texts: list[str],
        concepts: list[SemanticConcept],
        category: MemoryCategory,
    ) -> str:
        if len(texts) == 1 and category != MemoryCategory.INSIGHT:
            return self._single_abstraction(texts[0], concepts, category)

        return self._multi_abstraction(texts, concepts, category)

    def _single_abstraction(self, text: str, concepts: list[SemanticConcept], category: MemoryCategory) -> str:
        concept_labels = [c.label for c in concepts if c.concept_type != "relationship"][:5]
        persons = [c.label for c in concepts if c.concept_type == "person"]
        if persons:
            return f"Profile: User's name is {persons[0]}."
        if category == MemoryCategory.EPISODIC:
            detail = text[:120] + ("..." if len(text) > 120 else "")
        elif category == MemoryCategory.PROCEDURAL:
            steps = self._extract_steps(text)
            detail = " → ".join(steps) if steps else text[:80]
        elif category == MemoryCategory.INSIGHT:
            detail = self._generate_insight(concept_labels)
        else:
            detail = self._generate_semantic_fact(concept_labels, text)

        return self.CATEGORY_TEMPLATES[category].format(detail=detail)

    def _multi_abstraction(self, texts: list[str], concepts: list[SemanticConcept], category: MemoryCategory) -> str:
        concept_labels = list({c.label for c in concepts if c.concept_type != "relationship"})
        topics = [c.label for c in concepts if c.concept_type == "topic"]
        techs = [c.label for c in concepts if c.concept_type in ("framework", "technology")]

        if category == MemoryCategory.INSIGHT:
            if topics and techs:
                return f"Insight: User is developing expertise in {topics[0]} using {', '.join(techs[:3])}."
            if techs:
                return f"Insight: User is building proficiency with {', '.join(techs[:4])}."
            return f"Insight: Recurring focus on {', '.join(concept_labels[:4])} across {len(texts)} interactions."

        if category == MemoryCategory.SEMANTIC:
            return f"Knowledge: {', '.join(concept_labels[:5])} are related concepts in this domain."

        if category == MemoryCategory.PROCEDURAL:
            all_steps = []
            for t in texts:
                all_steps.extend(self._extract_steps(t))
            unique_steps = list(dict.fromkeys(all_steps))[:6]
            return f"Workflow: {' → '.join(unique_steps)}" if unique_steps else f"Workflow: {len(texts)} related operations."

        return f"Event: {len(texts)} related events involving {', '.join(concept_labels[:3])}."

    def _generate_insight(self, concepts: list[str]) -> str:
        if not concepts:
            return "General learning pattern detected."
        return f"User shows growing specialization in {', '.join(concepts[:4])}."

    def _generate_semantic_fact(self, concepts: list[str], text: str) -> str:
        if concepts:
            return f"{concepts[0]} relates to {', '.join(concepts[1:4])} in backend/system design."
        return text[:100]

    def _extract_steps(self, text: str) -> list[str]:
        import re
        # Arrow chains: Docker → Redis → Nginx
        arrows = re.findall(r"(\w+)\s*→\s*(\w+)", text)
        if arrows:
            steps = [arrows[0][0]]
            steps.extend(a[1] for a in arrows)
            return steps
        # Numbered or bulleted steps
        steps = re.findall(r"(?:\d+\.|[-*])\s*(\w+)", text)
        return steps[:6]
