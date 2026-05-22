"""Coordinator — orchestrates multi-agent software engineering pipeline."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from aion.agents import CodingAgent, DebugAgent, MemoryAgent, SummaryAgent, TestingAgent
from aion.config import load_config
from aion.llm import LLMClient
from aion.noesis_bridge import NoesisBridge
from aion.models import AgentResult, AgentRole, EngineeringTask, TaskMode, TaskStatus
from aion.utils.intent import infer_task_mode
from aion.utils.names import infer_project_name
from aion.tools.workspace import WorkspaceManager, resolve_output_dir
from aion.utils.retry import is_retryable_error

logger = logging.getLogger(__name__)


class AionCoordinator:
    """
    Autonomous Multi-Agent Software Engineering System
    with Noesis as shared persistent semantic memory.

    Pipeline: Memory recall → Coding → Debug → Testing → Memory store
    """

    def __init__(self, config_path: str | Path | None = None):
        self.config = load_config(config_path)
        nm = self.config["noesis"]
        ws = self.config["workspace"]

        recall_limit = int(self.config.get("coordinator", {}).get("recall_limit", 0))
        self.memory = NoesisBridge(
            db_path=str(Path(nm["db_path"])),
            agent_id=nm.get("agent_id", "AION-collective"),
            recall_limit=recall_limit,
        )
        self.workspace = WorkspaceManager(ws["root"])
        llm_cfg = self.config.get("llm", {})
        self.llm = LLMClient(
            enabled=llm_cfg.get("enabled", False),
            model=llm_cfg.get("model", "gpt-4o-mini"),
            provider=llm_cfg.get("provider", "openai"),
            base_url=llm_cfg.get("base_url"),
            max_retries=int(llm_cfg.get("max_retries", 4)),
            retry_base_seconds=float(llm_cfg.get("retry_base_seconds", 2.0)),
        )

        self.memory_agent = MemoryAgent(self.memory, self.workspace)
        self.coding_agent = CodingAgent(
            self.memory, self.workspace, llm=self.llm, llm_config=llm_cfg
        )
        self.debug_agent = DebugAgent(self.memory, self.workspace)
        self.testing_agent = TestingAgent(self.memory, self.workspace, llm=self.llm)
        self.summary_agent = SummaryAgent(self.memory, self.workspace, llm=self.llm)

        self._tasks: dict[str, EngineeringTask] = {}

    @staticmethod
    def _resolve_edit_project(
        project_name: str | None,
        active_file: str | None,
        output_dir: str,
        ctx: dict[str, str],
    ) -> str:
        """Target the folder for the open/@ file, not a stale project from an earlier run."""
        base = Path(output_dir)
        if active_file:
            rel = active_file.replace("\\", "/").lstrip("/")
            if "/" in rel:
                top = rel.split("/")[0]
                if (base / top).is_dir():
                    return top
        if project_name and str(project_name).strip():
            name = str(project_name).strip()
            if (base / name).is_dir():
                return name
        return ctx.get("project") or base.name

    def run_task(
        self,
        description: str,
        project_name: str | None = None,
        output_dir: str | None = None,
        mode: str = "auto",
        active_file: str | None = None,
    ) -> EngineeringTask:
        """Execute full multi-agent pipeline for an engineering request."""
        task_id = f"T-{uuid.uuid4().hex[:8].upper()}"
        resolved_out = str(resolve_output_dir(output_dir, self.workspace.root))
        ctx_pre = self.workspace.detect_context(
            output_dir,
            self.workspace.root,
            active_file=active_file,
            project_name=project_name,
        )
        project_root_pre = Path(ctx_pre["path"])
        if mode in ("auto", "", "infer"):
            mode = infer_task_mode(
                description,
                project_root_pre,
                has_open_workspace=bool(output_dir),
                active_file=active_file,
            )
        is_edit = mode == TaskMode.EDIT.value
        ctx = ctx_pre
        if is_edit and output_dir:
            project = self._resolve_edit_project(
                project_name, active_file, resolved_out, ctx_pre
            )
        else:
            project = infer_project_name(
                description,
                project_name,
                output_dir=resolved_out if output_dir else None,
                active_file=active_file,
                workspace=self.workspace,
                prefer_existing=False,
            )

        task = EngineeringTask(
            task_id=task_id,
            description=description,
            project_name=project,
            status=TaskStatus.RUNNING,
            output_dir=resolved_out,
            mode=mode if mode in (TaskMode.CREATE.value, TaskMode.EDIT.value) else TaskMode.CREATE.value,
            active_file=active_file or "",
        )
        self._tasks[task_id] = task

        context = self.memory.recall_for_task(description)

        pipeline: list[tuple[str, Any]] = [
            ("memory", self.memory_agent),
            ("coding", self.coding_agent),
            ("debug", self.debug_agent),
            ("testing", self.testing_agent),
        ]

        for name, agent in pipeline:
            if not self.config.get("agents", {}).get(name, {}).get("enabled", True):
                continue
            logger.info("Running %s agent for %s", name, task_id)
            result = agent.run(task, context)

            if name == "coding" and not result.success:
                coding_retries = int(self.config.get("coordinator", {}).get("coding_retries", 2))
                err_text = " ".join(result.errors) + result.summary
                for retry in range(coding_retries):
                    if not is_retryable_error(err_text):
                        break
                    logger.info("Auto-retry coding agent (%s/%s)", retry + 1, coding_retries)
                    result = agent.run(task, context)
                    if result.success:
                        break
                    err_text = " ".join(result.errors) + result.summary

            task.results.append(result)

            if name == "coding" and not result.success:
                task.status = TaskStatus.FAILED
                break

        # Final memory: task completion summary
        # Core pipeline: coding + debug must pass; testing best-effort
        critical = [r for r in task.results if r.role in (AgentRole.CODING, AgentRole.DEBUG)]
        success = all(r.success for r in critical) and any(
            r.role == AgentRole.CODING for r in task.results
        )
        task.status = TaskStatus.SUCCESS if success else TaskStatus.FAILED

        if self.config.get("agents", {}).get("summary", {}).get("enabled", True):
            logger.info("Running summary agent for %s", task_id)
            try:
                task.results.append(self.summary_agent.run(task, context))
            except Exception as e:
                logger.exception("Summary agent failed")
                task.results.append(
                    AgentResult(
                        role=AgentRole.SUMMARY,
                        success=False,
                        summary=f"Could not generate summary: {e}",
                        errors=[str(e)],
                    )
                )

        self.memory.remember_agent_work(
            AgentRole.COORDINATOR,
            f"Task {task_id} completed: {task.status.value}. "
            f"{description[:100]}. Agents: {[r.role.value for r in task.results]}",
            input_type="event",
            task_id=task_id,
            success=success,
        )

        return task

    def get_task(self, task_id: str) -> EngineeringTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[EngineeringTask]:
        return list(self._tasks.values())

    def memory_stats(self) -> dict[str, Any]:
        return self.memory.stats()
