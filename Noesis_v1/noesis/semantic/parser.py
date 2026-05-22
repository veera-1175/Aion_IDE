"""Step 2 — Semantic Parsing Engine: entity extraction, relationship detection."""

from __future__ import annotations

import re
from noesis.core.models import SemanticConcept

# Technology & domain vocabulary for rule-based extraction (works offline, no spaCy required)
TECH_PATTERNS = {
    r"\b(fastapi|flask|django|express|spring)\b": ("framework", "Framework"),
    r"\b(redis|postgresql|mongodb|mysql|sqlite|kafka)\b": ("technology", "Technology"),
    r"\b(docker|kubernetes|k8s|nginx|gunicorn|uvicorn)\b": ("technology", "Technology"),
    r"\b(python|javascript|typescript|rust|go|java)\b": ("technology", "Technology"),
    r"\b(async|await|worker|scaling|scalability|cache|api)\b": ("concept", "Concept"),
    r"\b(deploy|deployment|cluster|microservice|backend|frontend)\b": ("concept", "Concept"),
    r"\b(error|bug|bottleneck|timeout|crash|fail)\b": ("problem", "Problem"),
    r"\b(user|agent|system|server|client)\b": ("entity", "Entity"),
}

IDENTITY_PATTERNS = [
    (r"\bmy name is\s+([A-Za-z][A-Za-z0-9_-]{1,30})\b", "person"),
    (r"\bcall me\s+([A-Za-z][A-Za-z0-9_-]{1,30})\b", "person"),
    (r"\bmy name's\s+([A-Za-z][A-Za-z0-9_-]{1,30})\b", "person"),
]

# Verbs to ignore after "I am" (avoid "I am learning" -> person "Learning")
IDENTITY_VERB_BLOCK = {
    "learning", "working", "building", "using", "trying", "going",
    "doing", "making", "looking", "asking", "testing", "running",
}

TOPIC_KEYWORDS = {
    "backend": "Backend Engineering",
    "frontend": "Frontend Development",
    "database": "Database Systems",
    "devops": "DevOps & Infrastructure",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "security": "Security",
    "networking": "Networking",
    "memory": "Memory Systems",
    "distributed": "Distributed Systems",
}


class SemanticParser:
    """Extracts semantic concepts from raw text using NLP patterns + optional embeddings."""

    def parse(self, text: str) -> list[SemanticConcept]:
        concepts: list[SemanticConcept] = []
        lower = text.lower()

        # Identity / personal facts (names, profiles)
        for pattern, ctype in IDENTITY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                name = m.group(1).strip().title()
                if name.lower() not in IDENTITY_VERB_BLOCK:
                    concepts.append(SemanticConcept(label=name, concept_type=ctype, confidence=0.95))
                    concepts.append(SemanticConcept(label="User Identity", concept_type="profile", confidence=0.9))

        m = re.search(r"\bi am\s+([A-Za-z][A-Za-z0-9_-]{1,30})\b", text, re.IGNORECASE)
        if m and m.group(1).lower() not in IDENTITY_VERB_BLOCK:
            name = m.group(1).strip().title()
            concepts.append(SemanticConcept(label=name, concept_type="person", confidence=0.9))
            concepts.append(SemanticConcept(label="User Identity", concept_type="profile", confidence=0.9))

        # Topic detection
        for keyword, topic_label in TOPIC_KEYWORDS.items():
            if keyword in lower:
                concepts.append(SemanticConcept(label=topic_label, concept_type="topic", confidence=0.85))

        # Technology / framework / concept extraction
        seen = set()
        for pattern, (ctype, _) in TECH_PATTERNS.items():
            for match in re.finditer(pattern, lower, re.IGNORECASE):
                label = match.group(1).title()
                key = (label, ctype)
                if key not in seen:
                    seen.add(key)
                    concepts.append(SemanticConcept(label=label, concept_type=ctype, confidence=0.9))

        # Relationship hints from conjunction patterns
        labels = [c.label for c in concepts]
        if len(labels) >= 2:
            for i, a in enumerate(labels):
                for b in labels[i + 1 :]:
                    concepts.append(
                        SemanticConcept(
                            label=f"{a} ↔ {b}",
                            concept_type="relationship",
                            confidence=0.7,
                            related=[a, b],
                        )
                    )

        if not concepts:
            # Fallback: first significant phrase
            words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", text)[:5]]
            if words:
                concepts.append(SemanticConcept(label=" ".join(words[:3]), concept_type="topic", confidence=0.5))

        return concepts

    def extract_summary_phrases(self, text: str) -> list[str]:
        """Extract key phrases for clustering."""
        sentences = re.split(r"[.!?\n]+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10][:5]
