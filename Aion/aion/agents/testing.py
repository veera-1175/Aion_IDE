"""Testing Agent — multi-language test generation and execution."""

from __future__ import annotations

from pathlib import Path

from aion.agents.base import BaseAgent
from aion.codegen.test_generator import TestGenerator
from aion.llm import LLMClient
from aion.models import AgentResult, AgentRole, EngineeringTask, MemoryContext
from aion.tools.runner import CodeRunner
from aion.tools.validators import detect_languages


class TestingAgent(BaseAgent):
    role = AgentRole.TESTING

    def __init__(self, memory, workspace, llm: LLMClient | None = None):
        super().__init__(memory, workspace)
        self.llm = llm or LLMClient(enabled=False)
        self.runner = CodeRunner()
        self.test_generator = TestGenerator()

    def run(self, task: EngineeringTask, context: MemoryContext) -> AgentResult:
        project = Path(task.workspace_path)
        if not project.exists():
            return AgentResult(
                role=self.role,
                success=False,
                summary="No project to test.",
                errors=["workspace missing"],
            )

        langs = detect_languages(project)
        generated_tests: list[str] = []

        auto_tests = self.test_generator.generate_for_project(project, langs)
        for rel, content in auto_tests.items():
            dest = project / rel
            if not dest.exists():
                self.workspace.write_file(project, rel, content)
                generated_tests.append(rel)

        passed, failed, output = self.runner.run_tests(project)
        _, by_lang = self.runner.check_syntax_by_language(project)
        syntax_errors: list[str] = []
        for errs in by_lang.values():
            syntax_errors.extend(errs)

        success = not syntax_errors and failed == 0 and (passed > 0 or "skipped" in output.lower())

        lang_label = ", ".join(sorted(langs)) if langs else "unknown"
        summary = f"Testing Agent ({lang_label}): {passed} passed, {failed} failed."
        if generated_tests:
            summary += f" Auto-generated: {', '.join(generated_tests)}."
        if syntax_errors:
            summary += f" Validation errors: {len(syntax_errors)}."

        mem = self.memory.remember_test_result(passed, failed, summary)

        test_path = project / "tests"
        artifacts = (
            [str(p.relative_to(project)) for p in test_path.rglob("*") if p.is_file()]
            if test_path.exists()
            else []
        )

        return AgentResult(
            role=self.role,
            success=success,
            summary=summary,
            artifacts=artifacts,
            errors=syntax_errors,
            memory_stored=mem is not None,
            metadata={
                "pytest_output": output[:500],
                "passed": passed,
                "failed": failed,
                "languages": sorted(langs),
                "auto_generated_tests": generated_tests,
            },
        )
