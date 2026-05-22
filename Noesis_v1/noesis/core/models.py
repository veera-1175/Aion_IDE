"""Core data models for Noesis memory architecture."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryCategory(str, Enum):
    """Hierarchical memory types inspired by cognitive science."""

    EPISODIC = "episodic"      # Specific events
    SEMANTIC = "semantic"      # General knowledge
    PROCEDURAL = "procedural"  # Learned workflows
    INSIGHT = "insight"        # High-level conclusions


class InputType(str, Enum):
    CONVERSATION = "conversation"
    LOG = "log"
    OBSERVATION = "observation"
    DOCUMENT = "document"
    SENSOR = "sensor"
    EVENT = "event"


@dataclass
class RawInput:
    """Step 1 — Input collection."""

    content: str
    input_type: InputType = InputType.CONVERSATION
    source: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SemanticConcept:
    """Extracted semantic unit from parsing."""

    label: str
    concept_type: str  # topic, entity, technology, problem, framework
    confidence: float = 1.0
    related: list[str] = field(default_factory=list)


@dataclass
class ParsedMemory:
    """Output of semantic parsing + scoring."""

    raw_text: str
    concepts: list[SemanticConcept]
    importance: float
    semantic_summary: str
    category: MemoryCategory
    cluster_id: str
    embedding: list[float] | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class MemoryRecord:
    """Stored memory entry in the cognition layer."""

    memory_id: str
    content: str
    abstracted_content: str
    category: MemoryCategory
    importance: float
    cluster_id: str
    concepts: list[SemanticConcept]
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    access_count: int = 0
    retention_score: float = 1.0
    source_input_type: str = "conversation"
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def new_id() -> str:
        return f"M-{uuid.uuid4().hex[:8].upper()}"


@dataclass
class MemoryPacket:
    """Step 8 — Portable memory capsule for distribution."""

    memory_id: str
    importance: float
    semantic_cluster: str
    category: str
    semantic_summary: str
    bytecode: bytes
    token_ids: list[int]
    graph_edges: list[tuple[str, str, str]]  # (from, to, relation)
    tags: list[str]
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "importance": self.importance,
            "semantic_cluster": self.semantic_cluster,
            "category": self.category,
            "semantic_summary": self.semantic_summary,
            "bytecode": self.bytecode.hex(),
            "token_count": len(self.token_ids),
            "graph_edges": self.graph_edges,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ReconstructedContext:
    """Step 10 — Reconstructed context from compressed memory."""

    memory_id: str
    summary: str
    related_memories: list[str]
    concepts: list[str]
    graph_path: list[str]
    confidence: float
