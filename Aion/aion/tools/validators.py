"""Syntax and structure validation for multiple languages (stdlib + optional CLIs)."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path


_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".mypy_cache",
}


def _iter_source_files(project: Path, *suffixes: str) -> list[Path]:
    out: list[Path] = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in suffixes:
            out.append(path)
    return out


def detect_languages(project: Path) -> set[str]:
    """Languages present in the project (may be multiple)."""
    langs: set[str] = set()
    if (project / "package.json").exists() or _iter_source_files(project, ".js", ".mjs", ".cjs", ".ts", ".tsx"):
        langs.add("javascript")
    if _iter_source_files(project, ".py"):
        langs.add("python")
    if (project / "index.html").exists() or _iter_source_files(project, ".html", ".htm"):
        langs.add("web")
    if _iter_source_files(project, ".css"):
        langs.add("web")
    if (project / "pom.xml").exists() or (project / "build.gradle").exists() or _iter_source_files(
        project, ".java"
    ):
        langs.add("java")
    if (project / "go.mod").exists() or _iter_source_files(project, ".go"):
        langs.add("go")
    if (project / "Cargo.toml").exists() or _iter_source_files(project, ".rs"):
        langs.add("rust")
    if list(project.glob("*.csproj")) or _iter_source_files(project, ".cs"):
        langs.add("csharp")
    return langs


def _has_app_python(project: Path) -> bool:
    """Python outside tests/ (app code, not pytest stubs only)."""
    for py in _iter_source_files(project, ".py"):
        if "tests" in py.parts or py.name.startswith("test_"):
            continue
        return True
    return False


def detect_primary_stack(project: Path) -> str:
    """Primary stack label for logging (tests may still run for all detected langs)."""
    langs = detect_languages(project)
    if "javascript" in langs and (project / "package.json").exists():
        return "node"
    if "web" in langs and (project / "index.html").exists() and not _has_app_python(project):
        return "web"
    if "python" in langs:
        return "python"
    if "go" in langs:
        return "go"
    if "java" in langs:
        return "java"
    if "rust" in langs:
        return "rust"
    if "csharp" in langs:
        return "csharp"
    if "javascript" in langs:
        return "javascript"
    if "web" in langs:
        return "web"
    return "unknown"


class _HTMLStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "html" and not getattr(self, "_saw_html", False):
            self._saw_html = True

    def error(self, message: str) -> None:
        self.errors.append(message)


def validate_python(project: Path) -> list[str]:
    errors: list[str] = []
    for py in _iter_source_files(project, ".py"):
        if py.name.startswith("test_") and "tests" in py.parts:
            continue
        try:
            ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            rel = py.relative_to(project)
            errors.append(f"python {rel}: {e.msg} (line {e.lineno})")
    return errors


def validate_javascript(project: Path) -> list[str]:
    node = shutil.which("node")
    if not node:
        return []  # skip silently; runner notes tool missing
    errors: list[str] = []
    checker = (
        "const fs=require('fs');const vm=require('vm');"
        "const f=process.argv[1];"
        "try{new vm.Script(fs.readFileSync(f,'utf8'),{filename:f});}"
        "catch(e){console.error(e.message);process.exit(1);}"
    )
    for js in _iter_source_files(project, ".js", ".mjs", ".cjs"):
        if "node_modules" in js.parts:
            continue
        try:
            proc = subprocess.run(
                [node, "-e", checker, str(js)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(project),
            )
            if proc.returncode != 0:
                rel = js.relative_to(project)
                msg = (proc.stderr or proc.stdout or "syntax error").strip().splitlines()[0]
                errors.append(f"javascript {rel}: {msg}")
        except (subprocess.TimeoutExpired, OSError) as e:
            errors.append(f"javascript {js.name}: check failed ({e})")
    return errors


def _css_brace_balance(text: str) -> bool:
    depth = 0
    in_str: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def validate_css(project: Path) -> list[str]:
    errors: list[str] = []
    for css in _iter_source_files(project, ".css"):
        text = css.read_text(encoding="utf-8")
        if not _css_brace_balance(text):
            rel = css.relative_to(project)
            errors.append(f"css {rel}: unbalanced braces")
    return errors


def validate_html(project: Path) -> list[str]:
    errors: list[str] = []
    for html in _iter_source_files(project, ".html", ".htm"):
        text = html.read_text(encoding="utf-8")
        rel = html.relative_to(project)
        if not re.search(r"<html[\s>]", text, re.I) and not re.search(r"<!DOCTYPE", text, re.I):
            errors.append(f"html {rel}: missing <!DOCTYPE> or <html>")
        parser = _HTMLStructureParser()
        try:
            parser.feed(text)
            parser.close()
        except Exception as e:
            errors.append(f"html {rel}: {e}")
        if parser.errors:
            errors.append(f"html {rel}: {parser.errors[0]}")
        # Linked assets (project root-relative)
        root = html.parent
        for attr, pat in (("href", r'href\s*=\s*["\']([^"\']+)["\']'), ("src", r'src\s*=\s*["\']([^"\']+)["\']')):
            for m in re.finditer(pat, text, re.I):
                link = m.group(1).split("#")[0].split("?")[0]
                if not link or link.startswith(("http://", "https://", "//", "data:", "mailto:", "#")):
                    continue
                if not link.endswith((".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico")):
                    continue
                target = (root / link).resolve()
                if not target.is_file():
                    # try project root
                    target = (project / link).resolve()
                if not target.is_file():
                    errors.append(f"html {rel}: broken {attr} → {link}")
    return errors


def validate_go(project: Path) -> list[str]:
    go = shutil.which("go")
    if not go or not (project / "go.mod").exists():
        return []
    try:
        proc = subprocess.run(
            [go, "vet", "./..."],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project),
        )
        if proc.returncode != 0:
            return [f"go: {(proc.stderr or proc.stdout)[:500]}"]
    except (subprocess.TimeoutExpired, OSError) as e:
        return [f"go: vet failed ({e})"]
    return []


def validate_java(project: Path) -> list[str]:
    if not shutil.which("javac"):
        return []
    sources = _iter_source_files(project, ".java")
    if not sources:
        return []
    try:
        proc = subprocess.run(
            ["javac", "-Xlint:none", *[str(s) for s in sources[:20]]],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(project),
        )
        if proc.returncode != 0:
            return [f"java: {(proc.stderr or proc.stdout)[:500]}"]
    except (subprocess.TimeoutExpired, OSError) as e:
        return [f"java: compile check failed ({e})"]
    return []


def validate_rust(project: Path) -> list[str]:
    cargo = shutil.which("cargo")
    if not cargo or not (project / "Cargo.toml").exists():
        return []
    try:
        proc = subprocess.run(
            [cargo, "check", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project),
        )
        if proc.returncode != 0:
            return [f"rust: {(proc.stderr or proc.stdout)[:500]}"]
    except (subprocess.TimeoutExpired, OSError) as e:
        return [f"rust: check failed ({e})"]
    return []


def validate_all(project: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Run validators for every language detected in the project."""
    langs = detect_languages(project)
    by_lang: dict[str, list[str]] = {}

    validators = {
        "python": validate_python,
        "javascript": validate_javascript,
        "web": lambda p: validate_html(p) + validate_css(p),
        "java": validate_java,
        "go": validate_go,
        "rust": validate_rust,
    }

    for lang in sorted(langs):
        fn = validators.get(lang)
        if not fn:
            continue
        errs = fn(project)
        if errs:
            by_lang[lang] = errs

    flat: list[str] = []
    for lang in sorted(by_lang):
        flat.extend(by_lang[lang])
    return flat, by_lang


def format_validation_summary(by_lang: dict[str, list[str]], langs: set[str]) -> str:
    if not langs:
        return "No source files found to validate."
    checked = ", ".join(sorted(langs))
    if not by_lang:
        return f"All checks passed ({checked})."
    parts = [f"{lang}: {len(errs)} issue(s)" for lang, errs in sorted(by_lang.items())]
    return f"Issues found — {checked} — " + "; ".join(parts)
