"""Base agent with Noesis context injection."""

from __future__ import annotations

from abc import ABC, abstractmethod

from aion.noesis_bridge import NoesisBridge
from aion.models import AgentResult, AgentRole, EngineeringTask, MemoryContext
from aion.tools.workspace import WorkspaceManager


class BaseAgent(ABC):
    role: AgentRole

    def __init__(self, memory: NoesisBridge, workspace: WorkspaceManager):
        self.memory = memory
        self.workspace = workspace

    @abstractmethod
    def run(self, task: EngineeringTask, context: MemoryContext) -> AgentResult:
        pass

    def _workspace_for_task(self, task: EngineeringTask) -> WorkspaceManager:
        root = task.output_dir if task.output_dir else str(self.workspace.root)
        return WorkspaceManager(root)

    def _apply_memory_hints(self, context: MemoryContext) -> str:
        if not context.summaries:
            return ""
        hints = []
        for s in context.summaries:
            sl = s.lower()
            if "redis" in sl or "bug" in sl or "fix" in sl:
                hints.append(f"Prior fix/pattern: {s}")
            if "fastapi" in sl or "auth" in sl:
                hints.append(f"Prior architecture: {s}")
        return "\n".join(hints[:5])
