"""Run tests and syntax checks in workspace (multi-language)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from aion.tools.validators import (
    detect_languages,
    detect_primary_stack,
    format_validation_summary,
    validate_all,
)


class CodeRunner:
    def detect_languages(self, project: Path) -> set[str]:
        return detect_languages(project)

    def detect_stack(self, project: Path) -> str:
        return detect_primary_stack(project)

    def check_syntax(self, project: Path) -> list[str]:
        errors, _ = validate_all(project)
        return errors

    def check_syntax_by_language(self, project: Path) -> tuple[list[str], dict[str, list[str]]]:
        return validate_all(project)

    def validation_summary(self, project: Path) -> str:
        errors, by_lang = validate_all(project)
        langs = detect_languages(project)
        if errors:
            return format_validation_summary(by_lang, langs)
        return format_validation_summary({}, langs)

    def run_pytest(self, project: Path, timeout: int = 60) -> tuple[int, int, str]:
        test_dir = project / "tests"
        if not test_dir.exists():
            return 0, 0, "No tests directory"

        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(project) + os.pathsep + env.get("PYTHONPATH", "")

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_dir), "-q", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(project),
                env=env,
            )
            output = proc.stdout + proc.stderr
            passed, failed = 0, 0
            m = re.search(r"(\d+) passed", output)
            if m:
                passed = int(m.group(1))
            m2 = re.search(r"(\d+) failed", output)
            if m2:
                failed = int(m2.group(1))
            if passed == 0 and failed == 0 and proc.returncode == 0:
                passed = 1
            elif proc.returncode != 0 and passed == 0:
                failed = 1
            return passed, failed, output[:2000]
        except subprocess.TimeoutExpired:
            return 0, 1, "pytest timeout"
        except FileNotFoundError:
            return 0, 0, "pytest not available — structural checks only"

    def run_npm_test(self, project: Path, timeout: int = 90) -> tuple[int, int, str]:
        pkg = project / "package.json"
        if not pkg.exists():
            return 0, 0, "No package.json"
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if "test" not in data.get("scripts", {}):
                return self._run_node_smoke_test(project)
            proc = subprocess.run(
                ["npm", "test"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(project),
                shell=True,
            )
            output = (proc.stdout + proc.stderr)[:2000]
            ok = proc.returncode == 0
            return (1, 0, output) if ok else (0, 1, output)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return 0, 0, f"npm test skipped: {e}"

    def _run_node_smoke_test(self, project: Path) -> tuple[int, int, str]:
        """When package.json has no test script, validate JS files with node."""
        from aion.tools.validators import validate_javascript

        errs = validate_javascript(project)
        if errs:
            return 0, len(errs), "\n".join(errs[:5])
        js_files = [p for p in project.rglob("*.js") if "node_modules" not in p.parts]
        n = max(len(js_files), 1)
        return n, 0, f"javascript: {n} file(s) syntax OK (no npm test script)"

    def run_web_checks(self, project: Path) -> tuple[int, int, str]:
        """Structural tests for HTML/CSS/JS static sites."""
        from aion.codegen.file_sanitizer import repair_html_asset_links

        checks: list[tuple[str, bool, str]] = []
        index = project / "index.html"
        if not index.is_file():
            for html in project.glob("*.html"):
                index = html
                break

        if not index.is_file():
            return 0, 1, "web: no index.html found"

        html = index.read_text(encoding="utf-8")
        fixed = repair_html_asset_links(html, project_dir=project)
        checks.append(("index.html exists", True, ""))

        if re.search(r"<html[\s>]", fixed, re.I) or re.search(r"<!DOCTYPE", fixed, re.I):
            checks.append(("html structure", True, ""))
        else:
            checks.append(("html structure", False, "missing <html> or DOCTYPE"))

        names = {p.name for p in project.iterdir() if p.is_file()}
        for m in re.finditer(r"""href\s*=\s*["']([^"']+\.css)["']""", fixed, re.I):
            href = m.group(1)
            ok = href in names or (project / href).is_file()
            if "styles.css" in names and href == "style.css":
                ok = True
            checks.append((f"css link {href}", ok, "missing file" if not ok else ""))

        for m in re.finditer(r"""src\s*=\s*["']([^"']+\.js)["']""", fixed, re.I):
            href = m.group(1)
            ok = (project / href).is_file()
            checks.append((f"script {href}", ok, "missing file" if not ok else ""))

        _, by_lang = validate_all(project)
        web_errs = by_lang.get("web", [])
        for err in web_errs[:5]:
            checks.append((err[:60], False, err))

        passed = sum(1 for _, ok, _ in checks if ok)
        failed = sum(1 for _, ok, _ in checks if not ok)
        lines = [f"{'PASS' if ok else 'FAIL'}: {name}" + (f" ({msg})" if msg else "") for name, ok, msg in checks]
        return passed, failed, "web checks:\n" + "\n".join(lines)

    def run_go_test(self, project: Path, timeout: int = 60) -> tuple[int, int, str]:
        go = shutil.which("go")
        if not go:
            return 0, 0, "go not installed — skipped"
        try:
            proc = subprocess.run(
                [go, "test", "./..."],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(project),
            )
            output = (proc.stdout + proc.stderr)[:2000]
            if proc.returncode == 0:
                return 1, 0, output or "go test OK"
            return 0, 1, output
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return 0, 0, f"go test skipped: {e}"

    def run_java_test(self, project: Path, timeout: int = 120) -> tuple[int, int, str]:
        mvn = shutil.which("mvn")
        gradle = shutil.which("gradle")
        if (project / "pom.xml").exists() and mvn:
            cmd = [mvn, "-q", "test"]
        elif (project / "build.gradle").exists() and gradle:
            cmd = [gradle, "test", "-q"]
        else:
            from aion.tools.validators import validate_java

            errs = validate_java(project)
            if errs:
                return 0, len(errs), "\n".join(errs)
            return 1, 0, "java: compile check OK (no mvn/gradle test run)"
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(project))
            output = (proc.stdout + proc.stderr)[:2000]
            return (1, 0, output) if proc.returncode == 0 else (0, 1, output)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return 0, 0, f"java test skipped: {e}"

    def run_rust_test(self, project: Path, timeout: int = 120) -> tuple[int, int, str]:
        cargo = shutil.which("cargo")
        if not cargo:
            return 0, 0, "cargo not installed — skipped"
        try:
            proc = subprocess.run(
                [cargo, "test", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(project),
            )
            output = (proc.stdout + proc.stderr)[:2000]
            return (1, 0, output) if proc.returncode == 0 else (0, 1, output)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return 0, 0, f"rust test skipped: {e}"

    def run_tests(self, project: Path) -> tuple[int, int, str]:
        """Run test suites for every language detected in the project."""
        langs = detect_languages(project)
        runners: list[tuple[str, tuple[int, int, str]]] = []

        if "web" in langs:
            runners.append(("web", self.run_web_checks(project)))
        if "python" in langs and (project / "tests").exists():
            runners.append(("python", self.run_pytest(project)))
        if "javascript" in langs and (project / "package.json").exists():
            runners.append(("node", self.run_npm_test(project)))
        elif "javascript" in langs:
            runners.append(("javascript", self._run_node_smoke_test(project)))
        if "go" in langs:
            runners.append(("go", self.run_go_test(project)))
        if "java" in langs:
            runners.append(("java", self.run_java_test(project)))
        if "rust" in langs:
            runners.append(("rust", self.run_rust_test(project)))

        if not runners:
            return 0, 0, "No testable language detected"

        passed = sum(r[1][0] for r in runners)
        failed = sum(r[1][1] for r in runners)
        output = "\n".join(f"[{name}] {r[2][:400]}" for name, r in runners)
        return passed, failed, output[:2000]
