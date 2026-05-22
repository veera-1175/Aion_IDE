"""Summary Agent — explains what was done after the pipeline completes."""

from __future__ import annotations

from aion.agents.base import BaseAgent
from aion.llm import LLMClient
from aion.models import AgentResult, AgentRole, EngineeringTask, MemoryContext, TaskStatus


class SummaryAgent(BaseAgent):
    role = AgentRole.SUMMARY

    def __init__(self, memory, workspace, llm: LLMClient | None = None):
        super().__init__(memory, workspace)
        self.llm = llm or LLMClient(enabled=False)

    def run(self, task: EngineeringTask, context: MemoryContext) -> AgentResult:
        brief = self._build_brief(task, context)
        explanation = self._llm_explain(task, brief) or self._fallback_explain(task, brief)

        self.memory.remember_agent_work(
            self.role,
            f"Summary for {task.task_id}: {explanation[:200]}",
            input_type="event",
            task_id=task.task_id,
            success=task.status == TaskStatus.SUCCESS,
        )

        return AgentResult(
            role=self.role,
            success=True,
            summary=explanation,
            memory_stored=True,
            metadata={"explanation": explanation, "task_status": task.status.value},
        )

    def _build_brief(self, task: EngineeringTask, context: MemoryContext) -> str:
        lines = [
            f"User request: {task.description}",
            f"Outcome: {task.status.value}",
            f"Project folder: {task.project_name}",
            f"Mode: {task.mode}",
            f"Workspace: {task.workspace_path or task.output_dir}",
        ]
        if task.active_file:
            lines.append(f"Active file when started: {task.active_file}")

        file_changes: list[dict] = []
        for r in task.results:
            status = "ok" if r.success else "failed"
            lines.append(f"Agent [{r.role.value}] ({status}): {r.summary}")
            if r.errors:
                lines.append(f"  Errors: {'; '.join(r.errors[:5])}")
            if r.role == AgentRole.CODING:
                file_changes = r.metadata.get("file_changes") or []
                if r.metadata.get("files_created"):
                    lines.append(f"  Files written: {r.metadata.get('files_created')}")

        if file_changes:
            lines.append("Files changed:")
            for ch in file_changes[:25]:
                lines.append(
                    f"  - {ch.get('path', '?')} "
                    f"(+{ch.get('additions', 0)} / -{ch.get('deletions', 0)})"
                )

        if context.summaries:
            lines.append("Relevant Noesis memories used:")
            for s in context.summaries[:3]:
                lines.append(f"  - {s[:160]}")

        return "\n".join(lines)

    def _llm_explain(self, task: EngineeringTask, brief: str) -> str | None:
        if not self.llm.enabled:
            return None
        system = (
            "You are the Summary Agent for AION, an AI IDE. "
            "Other agents (memory, coding, debug, testing) just finished. "
            "Write a clear explanation for the user in markdown.\n\n"
            "Structure:\n"
            "1. One short opening sentence (success or what went wrong).\n"
            "2. ## What I did — bullet points of concrete actions.\n"
            "3. ## Files changed — list paths (or say none).\n"
            "4. ## How to run or view it — F5, open index.html, etc.\n"
            "5. ## Notes — only if debug/testing had issues or tips.\n\n"
            "Be specific and helpful. 120–350 words. No filler. No raw JSON."
        )
        user = f"Explain the completed engineering task to the user.\n\n{brief}"
        text = self.llm.complete(system, user, max_tokens=1400, json_mode=False)
        if text and text.strip():
            return text.strip()
        return None

    def _fallback_explain(self, task: EngineeringTask, brief: str) -> str:
        ok = task.status == TaskStatus.SUCCESS
        lines = [
            "## Done" if ok else "## Task finished with issues",
            "",
            f"I worked on **{task.project_name}** in **{task.mode}** mode.",
            "",
            "### What happened",
        ]
        for r in task.results:
            if r.role == AgentRole.SUMMARY:
                continue
            icon = "✓" if r.success else "✗"
            lines.append(f"- {icon} **{r.role.value}**: {r.summary}")

        coding = next((r for r in task.results if r.role == AgentRole.CODING), None)
        changes = (coding.metadata.get("file_changes") or []) if coding else []
        if changes:
            lines.extend(["", "### Files changed", ""])
            for ch in changes[:15]:
                lines.append(
                    f"- `{ch.get('path', '?')}` (+{ch.get('additions', 0)} / -{ch.get('deletions', 0)})"
                )
            if len(changes) > 15:
                lines.append(f"- …and {len(changes) - 15} more")

        lines.extend([
            "",
            "### Next steps",
            "- Press **F5** or **Run Project** to preview a web app.",
            "- Open changed files in the explorer to review edits.",
            "- Use **Review** in the agent panel to see diffs.",
        ])
        if not ok:
            lines.append("- Fix any errors above and run the agent again.")
        return "\n".join(lines)
