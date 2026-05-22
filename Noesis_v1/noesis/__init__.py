"""
Noesis Memory Engine
A Semantic + Symbolic Distributed AI Memory Architecture
"""

from noesis.core.engine import NoesisEngine
from noesis.core.models import (
    MemoryCategory,
    MemoryPacket,
    MemoryRecord,
    SemanticConcept,
)

__version__ = "1.0.0"
__all__ = [
    "NoesisEngine",
    "MemoryCategory",
    "MemoryPacket",
    "MemoryRecord",
    "SemanticConcept",
]

def __getattr__(name: str):
    if name == "PersistentAgent":
        from noesis.agents.persistent_agent import PersistentAgent
        return PersistentAgent
    if name == "NoesisMemory":
        from noesis.agents.langchain_memory import NoesisMemory
        return NoesisMemory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
