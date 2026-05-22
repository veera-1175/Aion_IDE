"""Coding Agent planning — understands task before writing code."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TaskPlan:
    """What the Coding Agent will build."""

    app_type: str
    description: str
    language: str = "python"
    modules: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    needs_tests: bool = True
    memory_hints: list[str] = field(default_factory=list)

    def to_brief(self) -> str:
        return (
            f"Build {self.app_type} in {self.language}: "
            f"{', '.join(self.features) or self.description}. "
            f"Modules: {', '.join(self.modules)}"
        )


class TaskPlanner:
    """Analyzes user request — agents decide what to create."""

    LANG_PATTERNS: list[tuple[str, str]] = [
        (r"\b(typescript|ts)\b", "typescript"),
        (r"\bjavascript\b|\bnode\.?js\b|\breact\b|\bvue\b", "javascript"),
        (r"\bjava\b(?!script)", "java"),
        (r"\bc\+\+\b|\bcpp\b", "cpp"),
        (r"\bc#\b|\bcsharp\b", "csharp"),
        (r"\bgo\b|\bgolang\b", "go"),
        (r"\brust\b", "rust"),
        (r"\bphp\b", "php"),
        (r"\bruby\b", "ruby"),
        (r"\bswift\b", "swift"),
        (r"\bkotlin\b", "kotlin"),
        (r"\bhtml\b|\bcss\b|\bweb\s+page\b|\bweb\s+app\b", "web"),
        (r"\bsql\b", "sql"),
        (r"\bpython\b", "python"),
    ]

    def plan(self, description: str, project_name: str = "", memory_summaries: list[str] | None = None) -> TaskPlan:
        text = f"{description} {project_name}".lower()
        memory_hints = (memory_summaries or [])[:5]
        language = self._detect_language(text)

        app_type = "python_app"
        operations: list[str] = []
        features: list[str] = []
        modules: list[str] = ["app"]

        if any(w in text for w in ("portfolio", "personal site", "personal website")):
            app_type = "static_web"
            language = "web"
            features = ["hero_section", "projects_grid", "modern_colors", "responsive"]
            modules = ["index", "styles", "script"]
        elif any(w in text for w in ("calendar", "calender")):
            app_type = "calendar_html"
            language = "web"
            features = ["month_grid", "styled_layout", "navigation"]
            modules = ["index", "styles"]
        elif any(w in text for w in ("bmi", "body mass", "weight finder", "weight calculator")):
            app_type = "bmi"
            features = ["height_weight_input", "bmi_formula", "category_labels"]
            modules = ["bmi"]
        elif any(w in text for w in ("calculator", "calc", "arithmetic")):
            app_type = "calculator"
            features = ["interactive_cli", "basic_arithmetic"]
            operations = ["+", "-", "*", "/"]
            modules = ["calculator"]
        elif any(w in text for w in ("auth", "jwt", "login")) and ("api" in text or "fastapi" in text):
            app_type = "fastapi_auth"
            features = ["jwt_login", "protected_routes"]
            modules = ["main"]
        elif any(w in text for w in ("fastapi", "rest api", " api")):
            app_type = "fastapi_api"
            features = ["rest_endpoints"]
            modules = ["main"]
        elif any(w in text for w in ("todo", "task list")):
            app_type = "todo_cli"
            features = ["add", "list", "remove"]
            modules = ["todo"]
        else:
            features = ["core_logic"]
            modules = ["app"]

        if language == "web" and app_type == "python_app":
            app_type = "static_web"
            features = ["html", "css", "responsive"]

        return TaskPlan(
            app_type=app_type,
            description=description,
            language=language,
            modules=modules,
            features=features,
            operations=operations,
            memory_hints=memory_hints,
        )

    def _detect_language(self, text: str) -> str:
        # Typos like "java" for JavaScript — prefer web when HTML/CSS/portfolio/website present
        web_signals = (
            r"\bhtml\b",
            r"\bcss\b",
            r"\bcc\b",
            r"\bstylesheet\b",
            r"\bportfolio\b",
            r"\bwebsite\b",
            r"\bweb\s+page\b",
            r"\bweb\s+app\b",
            r"\bjavascript\b",
            r"\bjs\b",
            r"java\s*script",
        )
        if any(re.search(p, text) for p in web_signals):
            return "web"
        for pattern, lang in self.LANG_PATTERNS:
            if re.search(pattern, text):
                return lang
        return "python"
