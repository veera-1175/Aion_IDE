"""Shared models for AION orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    CODING = "coding"
    DEBUG = "debug"
    TESTING = "testing"
    MEMORY = "memory"
    SUMMARY = "summary"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskMode(str, Enum):
    CREATE = "create"
    EDIT = "edit"


@dataclass
class AgentMessage:
    role: AgentRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryContext:
    """Context recalled from Noesis before agent action."""
    summaries: list[str]
    graph_paths: list[list[str]]
    memory_ids: list[str]
    confidence: float = 0.0

    def to_prompt_block(self) -> str:
        if not self.summaries:
            return "No prior engineering memory available."
        lines = ["## Prior knowledge from Noesis (shared agent memory)"]
        for i, s in enumerate(self.summaries, 1):
            lines.append(f"{i}. {s}")
        return "\n".join(lines)


@dataclass
class AgentResult:
    role: AgentRole
    success: bool
    summary: str
    artifacts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    memory_stored: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineeringTask:
    """User request orchestrated across agents."""
    task_id: str
    description: str
    project_name: str
    status: TaskStatus = TaskStatus.PENDING
    results: list[AgentResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    workspace_path: str = ""
    output_dir: str = ""
    mode: str = "create"
    active_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "project_name": self.project_name,
            "active_file": self.active_file,
            "mode": self.mode,
            "status": self.status.value,
            "workspace_path": self.workspace_path,
            "output_dir": self.output_dir,
            "created_at": self.created_at.isoformat(),
            "results": [
                {
                    "role": r.role.value,
                    "success": r.success,
                    "summary": r.summary,
                    "artifacts": r.artifacts,
                    "errors": r.errors,
                    "memory_stored": r.memory_stored,
                    "metadata": r.metadata,
                }
                for r in self.results
            ],
        }
