"""Step 3 — Importance Scoring: recurrence, relevance, future usefulness."""

from __future__ import annotations

import math
import re
from collections import Counter

from noesis.core.models import SemanticConcept


class ImportanceScorer:
    """
    Scores memory importance using:
    - recurrence frequency (cluster history)
    - contextual relevance (concept density)
    - content quality signals
    - reinforcement (access count)
    """

    LOW_VALUE_PATTERNS = [
        r"^(ok|yes|no|thanks|thank you|hi|hello|hey)\.?$",
        r"^\s*$",
        r"^.{1,3}$",  # very short
        r"\b(typo|oops|sorry)\b",
    ]

    def __init__(self, min_importance: float = 0.15):
        self.min_importance = min_importance
        self._concept_history: Counter[str] = Counter()

    def score(
        self,
        text: str,
        concepts: list[SemanticConcept],
        cluster_recurrence: int = 0,
        access_count: int = 0,
    ) -> float:
        if self._is_low_value(text):
            return 0.05

        scores = []

        # Recurrence — repeated topics matter
        recurrence_score = min(1.0, math.log1p(cluster_recurrence) / math.log1p(20))
        scores.append(recurrence_score * 0.35)

        # Concept density — richer semantics = higher value
        concept_density = min(1.0, len(concepts) / 8)
        scores.append(concept_density * 0.25)

        # Content length signal (not too short, not noise)
        word_count = len(text.split())
        length_score = min(1.0, word_count / 50) if word_count > 5 else 0.2
        scores.append(length_score * 0.15)

        # Technical depth — frameworks, problems score higher
        tech_weight = sum(
            0.15 for c in concepts if c.concept_type in ("framework", "technology", "problem", "concept")
        )
        scores.append(min(1.0, tech_weight))

        # Personal identity — names and profile facts are high value
        if any(c.concept_type in ("person", "profile") for c in concepts):
            scores.append(0.55)
        if re.search(r"\b(my name is|call me|what is my name|who am i|remember my name)\b", text, re.I):
            scores.append(0.35)

        # Reinforcement from prior access
        reinforcement = min(0.2, access_count * 0.03)
        scores.append(reinforcement)

        # Update history for future recurrence
        for c in concepts:
            self._concept_history[c.label.lower()] += 1

        final = sum(scores)
        return round(min(1.0, max(0.0, final)), 3)

    def get_recurrence(self, concepts: list[SemanticConcept]) -> int:
        return sum(self._concept_history[c.label.lower()] for c in concepts)

    def _is_low_value(self, text: str) -> bool:
        stripped = text.strip().lower()
        for pattern in self.LOW_VALUE_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                return True
        return False
