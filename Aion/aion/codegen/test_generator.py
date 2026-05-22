"""Testing Agent autonomously creates tests for Python, web, and JavaScript projects."""

from __future__ import annotations

import ast
import re
from pathlib import Path


class TestGenerator:
    """Analyzes agent-created source and writes matching tests."""

    def generate_for_project(self, project: Path, languages: set[str] | None = None) -> dict[str, str]:
        langs = languages or set()
        if not langs:
            from aion.tools.validators import detect_languages

            langs = detect_languages(project)

        tests: dict[str, str] = {}
        if "python" in langs:
            tests.update(self._generate_python_tests(project))
        if "web" in langs:
            tests.update(self._generate_web_tests(project))
        if "javascript" in langs and "web" not in langs:
            tests.update(self._generate_js_smoke_tests(project))
        return tests

    def _generate_python_tests(self, project: Path) -> dict[str, str]:
        tests: dict[str, str] = {}
        for py in project.glob("*.py"):
            if py.name.startswith("test_") or py.name in ("main.py", "__init__.py"):
                continue
            module = py.stem
            funcs = self._public_functions(py)
            if not funcs:
                continue
            body = [f'"""Auto-generated tests for {module}.py — AION Testing Agent."""']
            body.append("import pytest")
            body.append(f"from {module} import {', '.join(funcs[:8])}\n")

            for fn in funcs[:8]:
                if fn == "calculate":
                    body.append(self._test_calculate())
                elif fn in ("add", "subtract", "multiply", "divide"):
                    body.append(f"def test_{fn}_exists():\n    assert callable({fn})\n")
                else:
                    body.append(f"def test_{fn}_callable():\n    assert callable({fn})\n")

            tests[f"tests/test_{module}.py"] = "\n".join(body) + "\n"
        return tests

    def _generate_web_tests(self, project: Path) -> dict[str, str]:
        index = project / "index.html"
        if not index.is_file():
            html_files = list(project.glob("*.html"))
            if not html_files:
                return {}
            index = html_files[0]

        rel_index = index.relative_to(project).as_posix()
        body = [
            '"""Auto-generated web project checks — AION Testing Agent."""',
            "from pathlib import Path",
            "import re",
            "",
            "PROJECT = Path(__file__).resolve().parent.parent",
            "",
            f'def test_index_html_exists():',
            f"    assert (PROJECT / '{rel_index}').is_file()",
            "",
            "def test_index_has_html_structure():",
            f"    text = (PROJECT / '{rel_index}').read_text(encoding='utf-8')",
            "    assert re.search(r'<html[\\s>]', text, re.I) or re.search(r'<!DOCTYPE', text, re.I)",
            "",
            "def test_stylesheet_linked_file_exists():",
            f"    text = (PROJECT / '{rel_index}').read_text(encoding='utf-8')",
            "    names = {p.name for p in PROJECT.iterdir() if p.is_file()}",
            "    links = re.findall(r'href=[\"\\']([^\"\\']+\\.css)[\"\\']', text, re.I)",
            "    assert links, 'no CSS link in index.html'",
            "    for href in links:",
            "        assert href in names or (PROJECT / href).is_file(), f'missing {href}'",
        ]
        if (project / "script.js").is_file():
            body.extend(
                [
                    "",
                    "def test_script_js_exists():",
                    "    assert (PROJECT / 'script.js').is_file()",
                ]
            )
        return {"tests/test_web_project.py": "\n".join(body) + "\n"}

    def _generate_js_smoke_tests(self, project: Path) -> dict[str, str]:
        if (project / "package.json").exists():
            return {}
        js_files = [p for p in project.glob("*.js") if "node_modules" not in p.parts]
        if not js_files:
            return {}
        names = ", ".join(repr(p.name) for p in js_files[:5])
        body = [
            '"""Auto-generated JS file presence checks — AION Testing Agent."""',
            "from pathlib import Path",
            "",
            "PROJECT = Path(__file__).resolve().parent.parent",
            "EXPECTED = [" + names + "]",
            "",
            "def test_js_files_exist():",
            "    for name in EXPECTED:",
            "        assert (PROJECT / name).is_file(), name",
        ]
        return {"tests/test_javascript.py": "\n".join(body) + "\n"}

    def _public_functions(self, path: Path) -> list[str]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            return [
                n.name for n in tree.body
                if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
            ]
        except SyntaxError:
            return []

    def _test_calculate(self) -> str:
        return """def test_calculate_add():
    assert calculate('+', 1, 2) == 3

def test_calculate_div_zero():
    with pytest.raises(ValueError):
        calculate('/', 1, 0)
"""
