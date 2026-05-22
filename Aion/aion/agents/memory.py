"""Memory Agent — Noesis recall reporting (separate from coding injection)."""

from __future__ import annotations

from aion.agents.base import BaseAgent
from aion.models import AgentResult, AgentRole, EngineeringTask, MemoryContext


class MemoryAgent(BaseAgent):
    role = AgentRole.MEMORY

    def run(self, task: EngineeringTask, context: MemoryContext) -> AgentResult:
        self.memory.remember_agent_work(
            AgentRole.COORDINATOR,
            f"Task started ({task.mode}): {task.description}",
            input_type="event",
            task_id=task.task_id,
            project=task.project_name,
        )

        stats = self.memory.stats()
        total = int(stats.get("total_memories", 0))
        recalled = len(context.summaries)

        if recalled > 0:
            summary = (
                f"Noesis found {recalled} related memories (confidence {context.confidence:.2f}). "
                f"Total stored: {total}. "
            )
            if task.mode == "edit":
                summary += "Edit mode: agents will change your open project files."
            else:
                summary += "Coding uses your task + Groq (not old code from memory)."
        elif total > 0:
            summary = (
                f"Noesis has {total} memories from past runs, but none matched this exact query. "
                "Your previous BMI project is still stored — try Search memory with 'BMI' or use Edit mode on that folder."
            )
        else:
            summary = "First task — Noesis will store results after this run."

        return AgentResult(
            role=self.role,
            success=True,
            summary=summary,
            artifacts=[s[:100] for s in context.summaries[:3]],
            memory_stored=True,
            metadata={
                "recalled_count": recalled,
                "total_memories": total,
                "mode": task.mode,
            },
        )
