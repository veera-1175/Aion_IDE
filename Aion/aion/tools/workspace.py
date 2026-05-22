"""Isolated workspace per engineering task."""

from __future__ import annotations

import re
from pathlib import Path


def resolve_output_dir(custom: str | None, default_root: str | Path) -> Path:
    """User-selected folder or default workspace root (absolute path)."""
    if custom and str(custom).strip():
        path = Path(str(custom).strip()).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(default_root).expanduser().resolve()


class WorkspaceManager:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project_path(self, name: str) -> Path:
        safe = re.sub(r"[^\w\-]", "_", name.lower())[:48]
        path = self.root / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_file(self, project: Path, relative: str, content: str) -> Path:
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_file(self, project: Path, relative: str) -> str:
        return (project / relative).read_text(encoding="utf-8")

    SKIP_DIRS = {
        ".pytest_cache", "__pycache__", ".venv", "venv", "node_modules", ".git",
        ".cursor", "dist", "build", ".mypy_cache", "agent-tools",
    }

    def list_files(self, project: Path, max_files: int = 2500) -> list[str]:
        skip = self.SKIP_DIRS
        out: list[str] = []
        for p in project.rglob("*"):
            if len(out) >= max_files:
                break
            if not p.is_file():
                continue
            rel = str(p.relative_to(project)).replace("\\", "/")
            if any(part in skip for part in p.parts):
                continue
            out.append(rel)
        return sorted(out)

    def read_project_files(self, project: Path, max_total_chars: int = 24000) -> dict[str, str]:
        """Load existing source for edit mode (truncated if huge)."""
        files: dict[str, str] = {}
        total = 0
        for rel in self.list_files(project):
            if not rel.endswith((
                ".py", ".html", ".css", ".js", ".ts", ".tsx", ".json", ".md", ".txt", ".yaml", ".yml"
            )):
                continue
            try:
                text = self.read_file(project, rel)
            except OSError:
                continue
            if total + len(text) > max_total_chars:
                text = text[: max(500, max_total_chars - total)] + "\n/* ... truncated ... */"
            files[rel] = text
            total += len(text)
            if total >= max_total_chars:
                break
        return files

    @staticmethod
    def is_project_dir(path: Path) -> bool:
        if not path.is_dir():
            return False
        markers = ("main.py", "index.html", "app.py", "package.json", "pyproject.toml")
        return any((path / m).exists() for m in markers)

    def detect_context(
        self,
        output_dir: str | Path | None,
        default_root: Path,
        active_file: str | None = None,
        project_name: str | None = None,
    ) -> dict[str, str]:
        """
        Resolve workspace root and active project without manual naming.
        Prefers: explicit project_name child, active_file's top folder, direct project root, single child.
        """
        if isinstance(output_dir, Path):
            base = output_dir.expanduser().resolve()
        else:
            base = resolve_output_dir(output_dir, default_root)
        projects = self.list_projects(base)

        # Open file / @mention wins over stale project_name from a prior agent run
        if active_file:
            rel = active_file.replace("\\", "/").lstrip("/")
            if "/" in rel:
                top = rel.split("/")[0]
                cand = base / top
                if cand.is_dir():
                    return {
                        "project": top,
                        "path": str(cand.resolve()),
                        "root": str(base),
                    }

        if project_name and str(project_name).strip():
            name = str(project_name).strip()
            named = base / name
            if not named.is_dir():
                named.mkdir(parents=True, exist_ok=True)
            return {
                "project": name,
                "path": str(named.resolve()),
                "root": str(base),
            }

        if self.is_project_dir(base):
            return {"project": base.name, "path": str(base), "root": str(base)}

        if len(projects) == 1:
            p = projects[0]
            return {"project": p["name"], "path": p["path"], "root": str(base)}

        if projects:
            p = projects[0]
            return {"project": p["name"], "path": p["path"], "root": str(base)}

        return {"project": base.name, "path": str(base), "root": str(base)}

    def resolve_project(
        self,
        project_name: str | None,
        output_dir: str | Path | None = None,
        active_file: str | None = None,
    ) -> Path:
        """Find project folder from output_dir and optional hints (no manual name required)."""
        ctx = self.detect_context(
            output_dir,
            self.root,
            active_file=active_file,
            project_name=project_name,
        )
        return Path(ctx["path"]).resolve()

    def list_projects(self, search_root: Path | None = None) -> list[dict[str, str]]:
        root = search_root or self.root
        root = Path(root).expanduser().resolve()
        if not root.exists():
            return []
        projects: list[dict[str, str]] = []
        if self.is_project_dir(root):
            projects.append({"name": root.name, "path": str(root)})
            return projects
        for child in sorted(root.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                if any(child.rglob("*")):
                    projects.append({"name": child.name, "path": str(child)})
        return projects
