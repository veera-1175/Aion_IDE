"""Debug Agent — multi-language syntax validation and automatic fixes."""

from __future__ import annotations

from pathlib import Path

from aion.agents.base import BaseAgent
from aion.models import AgentResult, AgentRole, EngineeringTask, MemoryContext
from aion.tools.runner import CodeRunner
from aion.tools.validators import detect_languages


class DebugAgent(BaseAgent):
    role = AgentRole.DEBUG

    def __init__(self, memory, workspace):
        super().__init__(memory, workspace)
        self.runner = CodeRunner()

    def run(self, task: EngineeringTask, context: MemoryContext) -> AgentResult:
        project = Path(task.workspace_path)
        if not project.exists():
            return AgentResult(
                role=self.role,
                success=False,
                summary="No workspace to debug.",
                errors=["workspace missing"],
            )

        langs = self.runner.detect_languages(project)
        if not langs:
            return AgentResult(
                role=self.role,
                success=True,
                summary="No source files to validate.",
                metadata={"languages": []},
            )

        errors, by_lang = self.runner.check_syntax_by_language(project)
        fixes_applied: list[str] = []

        for summary in context.summaries:
            if "fix" in summary.lower() or "error" in summary.lower():
                fixes_applied.append(f"Recalled prior fix context: {summary[:80]}")

        # Auto-fix: Python tabs → spaces; web CSS link typos on disk
        if "python" in langs:
            fixed_count = 0
            for py in project.rglob("*.py"):
                if any(p in _SKIP for p in py.parts):
                    continue
                text = py.read_text(encoding="utf-8")
                cleaned = text.replace("\t", "    ")
                if cleaned != text:
                    py.write_text(cleaned, encoding="utf-8")
                    fixed_count += 1
            if fixed_count:
                fixes_applied.append(f"python: normalized tabs in {fixed_count} file(s)")

        if "web" in langs:
            from aion.codegen.file_sanitizer import repair_project_on_disk

            repaired = repair_project_on_disk(project)
            fixes_applied.extend(repaired)

        if not errors:
            checked = ", ".join(sorted(langs))
            self.memory.remember_agent_work(
                self.role,
                f"Validation passed for {task.project_name} ({checked})",
                input_type="log",
            )
            return AgentResult(
                role=self.role,
                success=True,
                summary=f"All checks passed ({checked}).",
                artifacts=fixes_applied,
                metadata={"languages": sorted(langs), "by_language": {}},
                memory_stored=True,
            )

        errors_after, by_lang_after = self.runner.check_syntax_by_language(project)
        summary = self.runner.validation_summary(project)

        if errors_after:
            self.memory.remember_bug_fix(
                "; ".join(errors_after[:2]),
                "Partial fix attempted; review remaining issues",
                ",".join(sorted(langs)),
            )
            return AgentResult(
                role=self.role,
                success=False,
                summary=summary,
                errors=errors_after,
                artifacts=fixes_applied,
                metadata={"languages": sorted(langs), "by_language": by_lang_after},
                memory_stored=True,
            )

        self.memory.remember_bug_fix(
            "; ".join(errors[:2]),
            f"Auto-fixed: {', '.join(fixes_applied) or 'formatting'}",
            ",".join(sorted(langs)),
        )
        return AgentResult(
            role=self.role,
            success=True,
            summary=f"Fixed issues ({', '.join(fixes_applied) or 'auto-repair'}).",
            errors=errors,
            artifacts=fixes_applied,
            metadata={"languages": sorted(langs)},
            memory_stored=True,
        )


_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
