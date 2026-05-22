"""Project naming from task description and workspace context."""

from __future__ import annotations

from pathlib import Path

from aion.tools.workspace import WorkspaceManager


def infer_project_name(
    description: str,
    project_name: str | None = None,
    *,
    output_dir: str | None = None,
    active_file: str | None = None,
    workspace: WorkspaceManager | None = None,
    prefer_existing: bool = False,
) -> str:
    if project_name and project_name.strip():
        return project_name.strip().replace(" ", "_")

    # Edit mode only — create always gets a new subfolder from the task text
    if prefer_existing and workspace and output_dir:
        ctx = workspace.detect_context(output_dir, workspace.root, active_file=active_file)
        if ctx.get("project"):
            return ctx["project"]
        if Path(ctx["path"]).exists() and any(Path(ctx["path"]).iterdir()):
            return Path(ctx["path"]).name

    lower = description.lower()
    if any(w in lower for w in ("portfolio", "personal site", "personal website")):
        return "portfolio"
    if any(w in lower for w in ("calendar", "calender")):
        return "calendar"
    if any(w in lower for w in ("bmi", "body mass", "weight finder")):
        return "bmi_weight_finder"
    if any(w in lower for w in ("calculator", "calc")):
        return "calculator"
    if "auth" in lower:
        return "fastapi_auth_api"
    if "api" in lower:
        return "generated_api"
    return "generated_app"
