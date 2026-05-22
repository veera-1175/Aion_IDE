"""Step 5 — Memory Categorization: episodic, semantic, procedural, insight."""

from __future__ import annotations

import re

from noesis.core.models import MemoryCategory, RawInput, InputType


class MemoryCategorizer:
    """Assigns hierarchical memory type based on content signals."""

    EPISODIC_SIGNALS = [
        r"\b(deployed|installed|ran|executed|happened|on \w+ \d+|today|yesterday|may \d+)\b",
        r"\b(event|incident|session|meeting)\b",
    ]
    PROCEDURAL_SIGNALS = [
        r"→",
        r"\b(step|sequence|workflow|pipeline|process|first.*then)\b",
        r"\b(docker|setup|configure|install).*(redis|nginx|gunicorn)\b",
    ]
    IDENTITY_SIGNALS = [
        r"\b(my name is|i am|i'm|call me|my name's)\b",
        r"\b(what is my name|who am i|remember my name)\b",
    ]
    INSIGHT_SIGNALS = [
        r"\b(specializ|expertise|transitioning|pattern|trend|overall|conclusion)\b",
        r"\b(always|usually|typically|prefers)\b",
    ]

    def categorize(self, text: str, input_type: InputType, recurrence: int = 0) -> MemoryCategory:
        lower = text.lower()

        if any(re.search(p, lower) for p in self.IDENTITY_SIGNALS):
            return MemoryCategory.SEMANTIC

        if any(re.search(p, lower) for p in self.INSIGHT_SIGNALS) or recurrence >= 5:
            return MemoryCategory.INSIGHT

        if any(re.search(p, lower) for p in self.PROCEDURAL_SIGNALS):
            return MemoryCategory.PROCEDURAL

        if any(re.search(p, lower) for p in self.EPISODIC_SIGNALS):
            return MemoryCategory.EPISODIC

        if input_type in (InputType.LOG, InputType.EVENT, InputType.SENSOR):
            return MemoryCategory.EPISODIC

        if input_type == InputType.DOCUMENT:
            return MemoryCategory.SEMANTIC

        # Default: semantic for knowledge-like content
        return MemoryCategory.SEMANTIC

    def derive_cluster_id(self, concepts: list) -> str:
        """Create stable cluster ID from dominant concepts."""
        labels = sorted({c.label.lower().replace(" ", "_") for c in concepts if c.concept_type != "relationship"})
        if not labels:
            return "general"
        return "_".join(labels[:3])[:64]
