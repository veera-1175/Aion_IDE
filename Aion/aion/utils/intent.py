"""Detect whether the user wants to create a new project or edit an existing one."""

from __future__ import annotations

import re
from pathlib import Path

from aion.models import TaskMode

_EDIT_HINTS = re.compile(
    r"\b(fix|edit|update|change|modify|refactor|patch|adjust|correct|debug|"
    r"improve|tweak|rename|move|delete|remove|add\s+to|extend|continue|"
    r"in\s+this\s+project|existing|current\s+file|these\s+files)\b",
    re.I,
)
_CREATE_HINTS = re.compile(
    r"\b(create|build|scaffold|generate\s+(a\s+)?new|from\s+scratch|"
    r"new\s+project|start\s+fresh|empty\s+project)\b",
    re.I,
)

_SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def _count_project_files(project_root: Path) -> int:
    if not project_root.is_dir():
        return 0
    n = 0
    for p in project_root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_PARTS for part in p.parts):
            continue
        if p.suffix.lower() in {".py", ".html", ".css", ".js", ".ts", ".json", ".md", ".go", ".java", ".rs"}:
            n += 1
            if n >= 3:
                return n
    return n


def infer_task_mode(
    description: str,
    project_root: Path | None,
    *,
    has_open_workspace: bool = False,
    active_file: str | None = None,
) -> str:
    """
    Auto-detect create vs edit. User does not pick a mode in the UI.
    """
    text = (description or "").strip()
    file_count = _count_project_files(project_root) if project_root else 0

    if "@" in text or "referenced files" in text.lower():
        return TaskMode.EDIT.value

    if _CREATE_HINTS.search(text) and not _EDIT_HINTS.search(text):
        return TaskMode.CREATE.value

    if file_count >= 2 or (has_open_workspace and active_file):
        if _EDIT_HINTS.search(text) or not _CREATE_HINTS.search(text):
            return TaskMode.EDIT.value

    if file_count >= 1 and has_open_workspace:
        return TaskMode.EDIT.value

    return TaskMode.CREATE.value
