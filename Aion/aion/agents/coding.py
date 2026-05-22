"""Coding Agent — create new projects or edit existing ones via LLM."""

from __future__ import annotations

from pathlib import Path

from aion.agents.base import BaseAgent
from aion.codegen.file_sanitizer import normalize_files, sanitize_content
from aion.codegen.llm_coder import LLMCoder
from aion.codegen.planner import TaskPlanner
from aion.llm import LLMClient
from aion.models import AgentResult, AgentRole, EngineeringTask, MemoryContext, TaskMode
from aion.utils.diff_util import line_diff, trim_text


class CodingAgent(BaseAgent):
    role = AgentRole.CODING

    def __init__(self, memory, workspace, llm: LLMClient | None = None, llm_config: dict | None = None):
        super().__init__(memory, workspace)
        self.llm = llm or LLMClient(enabled=False)
        self.planner = TaskPlanner()
        cfg = llm_config or {}
        self.inject_memory = cfg.get("inject_memory_into_coding", False)
        self.llm_coder = LLMCoder(
            self.llm,
            auto_repair_web=cfg.get("auto_repair_web", False),
            use_structured_outputs=cfg.get("structured_outputs", True),
            max_attempts=int(cfg.get("max_generation_attempts", 3)),
        )

    def run(self, task: EngineeringTask, context: MemoryContext) -> AgentResult:
        ws = self._workspace_for_task(task)
        is_edit = task.mode == TaskMode.EDIT.value
        project = ws.resolve_project(
            None if is_edit else task.project_name,
            task.output_dir or None,
            active_file=task.active_file or None,
        )
        project.mkdir(parents=True, exist_ok=True)
        task.workspace_path = str(project)

        plan = self.planner.plan(task.description, task.project_name)
        existing = ws.read_project_files(project) if project.exists() else {}
        if is_edit and not existing:
            hint = (
                f"Edit mode: no code files in `{project.name}`. "
                "Open the project folder (folder icon on the left bar), open a file like main.py, "
                "set the pill to **Edit**, then run again. Or use **Create** for a new project."
            )
            return AgentResult(
                role=self.role,
                success=False,
                summary=hint,
                errors=["no_project_files"],
                metadata={"resolved_path": str(project)},
            )

        memory_block = ""
        if self.inject_memory and context.summaries:
            memory_block = "\n".join(context.summaries[:3])

        if is_edit:
            llm_result = self.llm_coder.edit_project(plan, task.description, existing)
            action = "edited"
        else:
            llm_result = self.llm_coder.create_project(plan, task.description, memory_block)
            action = "created"

        if not llm_result:
            if not self.llm.enabled:
                hint = self.llm.last_error or "Set GROQ_API_KEY in .env, pip install openai, restart."
            else:
                hint = self.llm_coder.last_error or self.llm.last_error or "Groq failed — try again."
            return AgentResult(
                role=self.role,
                success=False,
                summary=f"Coding Agent could not {action} the project. {hint}",
                errors=["llm_generation_failed"],
                metadata={"mode": "edit" if is_edit else "create", "llm_enabled": self.llm.enabled},
            )

        files, summary = llm_result
        files = normalize_files(files)
        files["PLAN.md"] = (
            f"# Build plan\n\n- **Task:** {task.description}\n"
            f"- **Mode:** {'edit' if is_edit else 'create'}\n"
            f"- **Type:** {plan.app_type}\n- **Source:** llm ({self.llm.provider})\n"
        )

        artifacts: list[str] = []
        file_changes: list[dict] = []
        for rel, content in files.items():
            clean = sanitize_content(rel, content)
            old = existing.get(rel, "")
            if old != clean:
                stats = line_diff(old, clean)
                file_changes.append({
                    "path": rel.replace("\\", "/"),
                    "additions": stats["additions"],
                    "deletions": stats["deletions"],
                    "before": trim_text(old),
                    "after": trim_text(clean),
                    "diff_lines": stats["lines"][:120],
                })
            path = ws.write_file(project, rel, clean)
            artifacts.append(str(path.relative_to(project)))

        self.memory.remember_agent_work(
            self.role,
            f"LLM {action} {plan.app_type}: {task.description[:120]}",
            input_type="event",
            app_type=plan.app_type,
            mode="edit" if is_edit else "create",
        )

        return AgentResult(
            role=self.role,
            success=True,
            summary=f"{summary} [{'EDIT' if is_edit else 'CREATE'}]",
            artifacts=artifacts,
            memory_stored=True,
            metadata={
                "files_created": len(artifacts),
                "file_changes": file_changes,
                "app_type": plan.app_type,
                "creation_source": "llm",
                "mode": "edit" if is_edit else "create",
                "provider": self.llm.provider,
            },
        )
