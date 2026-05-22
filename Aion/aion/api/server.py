"""AION Web API + IDE UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError:
    FastAPI = None  # type: ignore

from aion.coordinator import AionCoordinator
from aion.codegen.file_sanitizer import (
    inject_preview_base,
    repair_html_asset_links,
    resolve_web_asset,
)
from aion.tools.run_manager import RunManager
from aion.tools.workspace import resolve_output_dir

_run_manager = RunManager()

from aion.ide import (  # noqa: E402
    BackgroundJobManager,
    CheckpointManager,
    CodebaseIndex,
    DebugSessionManager,
)
from aion.ide.lsp_bridge import document_symbols, get_completions, get_diagnostics, hover_info

_codebase_index = CodebaseIndex()
_checkpoints = CheckpointManager(Path("data/checkpoints"))
_bg_jobs = BackgroundJobManager()
_debug_mgr = DebugSessionManager()


def _open_browser(url: str) -> None:
    """Open default system browser (backup when IDE popup is blocked)."""
    try:
        import webbrowser
        webbrowser.open(url, new=1)
    except Exception:
        pass

STATIC = Path(__file__).parent.parent / "ui" / "static"
_coordinator: AionCoordinator | None = None


class TaskRequest(BaseModel):
    description: str
    project_name: str | None = None
    output_dir: str | None = None
    mode: str = Field("auto", description="auto | create | edit (auto detects)")
    active_file: str | None = None


class SaveFileRequest(BaseModel):
    output_dir: str | None = None
    path: str
    content: str


class OpenPathRequest(BaseModel):
    path: str


class ImportFolderRequest(BaseModel):
    folder_name: str
    files: dict[str, str] = Field(default_factory=dict)


class NewFileRequest(BaseModel):
    output_dir: str | None = None
    path: str
    content: str = ""


class TerminalRequest(BaseModel):
    output_dir: str | None = None
    command: str
    cwd: str | None = None


class RunRequest(BaseModel):
    output_dir: str | None = None
    project: str | None = None
    file_path: str | None = None
    active_file: str | None = None
    background: bool = True


class InlineEditRequest(BaseModel):
    output_dir: str | None = None
    path: str | None = None
    selection: str
    instruction: str
    language: str = "plaintext"


class ChatRequest(BaseModel):
    message: str
    output_dir: str | None = None
    project: str | None = None
    active_file: str | None = None
    context_files: list[str] = Field(default_factory=list)
    mode: str = "chat"


class CompleteRequest(BaseModel):
    output_dir: str | None = None
    path: str
    prefix: str
    suffix: str = ""
    language: str = "python"


class BackgroundTaskRequest(BaseModel):
    description: str
    output_dir: str | None = None
    project_name: str | None = None
    mode: str = "create"
    active_file: str | None = None


class CheckpointRequest(BaseModel):
    output_dir: str | None = None
    project: str | None = None
    label: str = ""


class DebugBreakpointRequest(BaseModel):
    session_id: str
    path: str
    lines: list[int] = Field(default_factory=list)


class DebugRunRequest(BaseModel):
    session_id: str
    output_dir: str | None = None
    file_path: str


def create_app(coordinator: AionCoordinator | None = None) -> "FastAPI":
    if FastAPI is None:
        raise ImportError("pip install fastapi uvicorn")

    global _coordinator
    _coordinator = coordinator or AionCoordinator()
    api_port = int(_coordinator.config.get("api", {}).get("port", 8090))
    _run_manager.set_api_port(api_port)
    app = FastAPI(title="AION", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    if STATIC.exists():
        from starlette.staticfiles import StaticFiles as StarletteStaticFiles

        class NoCacheStaticFiles(StarletteStaticFiles):
            async def get_response(self, path, scope):
                response = await super().get_response(path, scope)
                if response.status_code == 200:
                    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                return response

        app.mount("/static", NoCacheStaticFiles(directory=str(STATIC)), name="static")

    def _root(output_dir: str | None) -> Path:
        return resolve_output_dir(output_dir, _coordinator.workspace.root)

    @app.get("/", response_class=HTMLResponse)
    def ui():
        index = STATIC / "index.html"
        body = index.read_text(encoding="utf-8") if index.exists() else "<h1>AION</h1>"
        return HTMLResponse(
            body,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    def _preview_file_response(asset: str):
        root = _run_manager.get_preview_root()
        if not root or not root.is_dir():
            raise HTTPException(
                404,
                "No preview active. In AION press F5 (Run Project) with a web folder open.",
            )
        root = root.resolve()
        rel = (asset or "index.html").replace("\\", "/").lstrip("/")
        target = resolve_web_asset(root, rel)
        if not target:
            raise HTTPException(404, f"Not found: {rel}")
        if target.suffix.lower() in (".html", ".htm"):
            body = target.read_text(encoding="utf-8")
            body = repair_html_asset_links(body, project_dir=root)
            body = inject_preview_base(body)
            return HTMLResponse(body, media_type="text/html; charset=utf-8")
        import mimetypes

        media_type, _ = mimetypes.guess_type(str(target))
        return FileResponse(target, media_type=media_type or "application/octet-stream")

    @app.get("/preview")
    def preview_redirect():
        return RedirectResponse(url="/preview/")

    @app.get("/preview/")
    def preview_index():
        return _preview_file_response("index.html")

    @app.get("/preview/{asset:path}")
    def preview_assets(asset: str):
        return _preview_file_response(asset)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "api_port": api_port,
            "preview_url": f"http://127.0.0.1:{api_port}/preview/",
            "noesis": _coordinator.memory_stats(),
            "llm": _coordinator.llm.status()
            | {
                "openai_key_set": bool(__import__("os").getenv("OPENAI_API_KEY")),
                "groq_key_set": bool(__import__("os").getenv("GROQ_API_KEY")),
            },
            "default_workspace": str(_coordinator.workspace.root),
            "suggested_workspace": str(Path(__file__).resolve().parents[2].parent),
        }

    @app.get("/workspace/detect")
    def detect_workspace(
        output_dir: str | None = None,
        active_file: str | None = None,
        project: str | None = None,
    ):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir,
            _coordinator.workspace.root,
            active_file=active_file,
            project_name=project,
        )
        ctx["projects"] = _coordinator.workspace.list_projects(base)
        return ctx

    @app.get("/workspace/projects")
    def list_projects(output_dir: str | None = None):
        return _coordinator.workspace.list_projects(_root(output_dir))

    @app.get("/workspace/files")
    def list_files(
        output_dir: str | None = None,
        active_file: str | None = None,
        project: str | None = None,
        scope: str = "auto",
    ):
        base = _root(output_dir)
        # scope=full → entire opened folder tree (like Cursor Aion_IDE view)
        if scope == "full" or (scope == "auto" and not project):
            if not base.exists():
                raise HTTPException(404, "Workspace not found")
            return {
                "project": base.name,
                "path": str(base),
                "root": str(base),
                "scope": "full",
                "files": _coordinator.workspace.list_files(base),
            }
        ctx = _coordinator.workspace.detect_context(
            output_dir,
            _coordinator.workspace.root,
            active_file=active_file,
            project_name=project,
        )
        project_root = Path(ctx["path"])
        if not project_root.exists():
            raise HTTPException(404, "Workspace not found")
        prefix = ""
        if project_root.resolve() != base.resolve():
            prefix = str(project_root.resolve().relative_to(base.resolve())).replace("\\", "/") + "/"
        rel_files = _coordinator.workspace.list_files(project_root)
        return {
            "project": ctx["project"],
            "path": ctx["path"],
            "root": ctx["root"],
            "scope": "project",
            "files": [f"{prefix}{rel}" for rel in rel_files],
        }

    @app.get("/workspace/diagnostics")
    def workspace_diagnostics(
        output_dir: str | None = None,
        project: str | None = None,
    ):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        root = Path(ctx["path"])
        issues = _run_manager.collect_diagnostics(base, project)
        seen = {(i.get("path"), i.get("line"), i.get("message")) for i in issues}
        for item in get_diagnostics(root):
            key = (item.get("path"), item.get("line"), item.get("message"))
            if key not in seen:
                issues.append(item)
                seen.add(key)
        errors = sum(1 for i in issues if i.get("severity") == "error")
        warnings = sum(1 for i in issues if i.get("severity") == "warning")
        return {"issues": issues, "errors": errors, "warnings": warnings}

    @app.get("/workspace/snapshot")
    def workspace_snapshot(output_dir: str | None = None):
        """All text file contents under workspace root (for client-side diff fallback)."""
        base = _root(output_dir)
        snap: dict[str, str] = {}
        for rel in _coordinator.workspace.list_files(base):
            if not rel.endswith((
                ".py", ".html", ".css", ".js", ".ts", ".json", ".md", ".txt", ".yaml", ".yml", ".env"
            )):
                continue
            try:
                snap[rel] = (base / rel).read_text(encoding="utf-8")
            except OSError:
                continue
        return {"root": str(base), "files": snap}

    @app.get("/workspace/file")
    def read_file(
        path: str = Query(..., alias="path"),
        output_dir: str | None = None,
    ):
        base = _root(output_dir)
        target = (base / path).resolve()
        if not str(target).startswith(str(base.resolve())):
            raise HTTPException(403, "Invalid path")
        if not target.is_file():
            raise HTTPException(404, "File not found")
        return {"path": path.replace("\\", "/"), "content": target.read_text(encoding="utf-8")}

    @app.put("/workspace/file")
    def save_file(req: SaveFileRequest):
        base = _root(req.output_dir)
        rel = req.path.replace("\\", "/").lstrip("/")
        target = (base / rel).resolve()
        if not str(target).startswith(str(base.resolve())):
            raise HTTPException(403, "Invalid path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        return {"path": rel, "saved": True}

    @app.post("/tasks")
    def create_task(req: TaskRequest):
        task = _coordinator.run_task(
            req.description,
            req.project_name,
            output_dir=req.output_dir,
            mode=req.mode,
            active_file=req.active_file,
        )
        return task.to_dict()

    @app.get("/tasks")
    def list_tasks():
        return [t.to_dict() for t in _coordinator.list_tasks()]

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str):
        t = _coordinator.get_task(task_id)
        if not t:
            raise HTTPException(404, "Task not found")
        return t.to_dict()

    @app.post("/memory/reset")
    def reset_memory():
        return _coordinator.memory.reset_all()

    @app.post("/recall")
    def recall(req: TaskRequest):
        ctx = _coordinator.memory.recall_for_task(req.description)
        return {
            "summaries": ctx.summaries,
            "confidence": ctx.confidence,
            "explanation": _coordinator.memory.explain_recall(req.description),
        }

    @app.post("/workspace/open-path")
    def open_path(req: OpenPathRequest):
        """Open a folder by absolute path on the server machine (local AION)."""
        raw = req.path.strip().strip('"')
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise HTTPException(404, f"Path not found: {path}")
        if not path.is_dir():
            raise HTTPException(400, "Path must be a folder")
        return {
            "path": str(path),
            "project": path.name,
            "files": _coordinator.workspace.list_files(path),
        }

    @app.post("/workspace/import")
    def import_folder(req: ImportFolderRequest):
        """Import dropped folder files into workspace (browser drag-and-drop)."""
        import re

        safe = re.sub(r"[^\w\-.]", "_", req.folder_name)[:48] or "dropped_project"
        target = _coordinator.workspace.root / safe
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for rel, content in req.files.items():
            rel_clean = rel.replace("\\", "/").lstrip("/")
            if ".." in rel_clean.split("/"):
                continue
            _coordinator.workspace.write_file(target, rel_clean, content)
            written += 1
        return {
            "path": str(target.resolve()),
            "project": safe,
            "files_written": written,
            "files": _coordinator.workspace.list_files(target),
        }

    @app.get("/workspace/search")
    def search_workspace(
        q: str = Query(..., min_length=1),
        output_dir: str | None = None,
        project: str | None = None,
    ):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir,
            _coordinator.workspace.root,
            project_name=project,
        )
        project_root = Path(ctx["path"])
        needle = q.lower()
        hits: list[dict[str, Any]] = []
        for rel in _coordinator.workspace.list_files(project_root):
            if not rel.endswith((
                ".py", ".html", ".css", ".js", ".ts", ".tsx", ".json", ".md", ".txt", ".yaml", ".yml"
            )):
                continue
            try:
                text = (project_root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle in rel.lower() or needle in text.lower():
                line_no = 1
                snippet = ""
                for i, line in enumerate(text.splitlines(), 1):
                    if needle in line.lower():
                        line_no = i
                        snippet = line.strip()[:120]
                        break
                prefix = ""
                if project_root.resolve() != base.resolve():
                    prefix = str(project_root.resolve().relative_to(base.resolve())).replace("\\", "/") + "/"
                hits.append({"path": f"{prefix}{rel}", "line": line_no, "snippet": snippet})
                if len(hits) >= 80:
                    break
        return {"query": q, "results": hits, "project": ctx["project"]}

    @app.post("/workspace/new-file")
    def new_file(req: NewFileRequest):
        base = _root(req.output_dir)
        rel = req.path.replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            raise HTTPException(403, "Invalid path")
        target = (base / rel).resolve()
        if not str(target).startswith(str(base.resolve())):
            raise HTTPException(403, "Invalid path")
        if target.exists():
            raise HTTPException(409, "File already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        return {"path": rel, "created": True}

    @app.post("/run/project")
    def run_project(req: RunRequest):
        base = _root(req.output_dir)
        try:
            result = _run_manager.run_project(
                base,
                project_name=req.project,
                active_file=req.active_file or req.file_path,
                background=req.background,
                api_port=api_port,
            )
            if result.get("auto_open") and result.get("url") and result.get("ready", True):
                _open_browser(result["url"])
            return result
        except (ValueError, FileNotFoundError, PermissionError) as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/run/file")
    def run_file(req: RunRequest):
        if not req.file_path:
            raise HTTPException(400, "file_path required")
        base = _root(req.output_dir)
        try:
            result = _run_manager.run_file(
                base, req.file_path, background=req.background, api_port=api_port
            )
            if result.get("auto_open") and result.get("url") and result.get("ready", True):
                _open_browser(result["url"])
            return result
        except (ValueError, FileNotFoundError, PermissionError) as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/run/stop")
    def run_stop(job_id: str | None = None):
        _run_manager.stop_job(job_id)
        _run_manager._stop_http_servers()
        _run_manager.clear_preview()
        return {"stopped": True, "job_id": job_id}

    @app.get("/run/status")
    def run_status():
        return {"jobs": _run_manager.list_jobs()}

    @app.get("/run/output/{job_id}")
    def run_output(job_id: str):
        return _run_manager.get_output(job_id)

    @app.post("/terminal/run")
    def run_terminal(req: TerminalRequest):
        import subprocess

        base = _root(req.output_dir)
        cwd = Path(req.cwd).expanduser().resolve() if req.cwd else base
        if not str(cwd).startswith(str(base.resolve())):
            cwd = base
        cmd = (req.command or "").strip()
        if not cmd:
            raise HTTPException(400, "Empty command")
        blocked = ("rm ", "del ", "format ", "shutdown", "rmdir /s")
        if any(b in cmd.lower() for b in blocked):
            raise HTTPException(403, "Command not allowed")
        try:
            import sys as _sys

            if _sys.platform == "win32":
                proc = subprocess.run(
                    ["cmd", "/c", cmd],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(cwd),
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    encoding="utf-8",
                    errors="replace",
                )
            out = (proc.stdout or "") + (proc.stderr or "")
            return {
                "command": cmd,
                "cwd": str(cwd),
                "exit_code": proc.returncode,
                "output": out[-12000:],
            }
        except subprocess.TimeoutExpired:
            return {"command": cmd, "cwd": str(cwd), "exit_code": -1, "output": "Command timed out (30s)"}

    @app.get("/workspace/git/status")
    def git_status(output_dir: str | None = None, project: str | None = None):
        import subprocess

        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        root = Path(ctx["path"])
        if not (root / ".git").exists():
            return {
                "is_repo": False,
                "branch": None,
                "changes": [],
                "ahead": 0,
                "behind": 0,
            }

        def _git(*args: str) -> str:
            try:
                proc = subprocess.run(
                    ["git", *args],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=str(root),
                    encoding="utf-8",
                    errors="replace",
                )
                return (proc.stdout or proc.stderr or "").strip()
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                return ""

        branch = _git("branch", "--show-current") or "HEAD"
        status = _git("status", "--porcelain")
        changes = []
        for line in status.splitlines():
            if not line.strip():
                continue
            code = line[:2]
            path = line[3:].strip()
            changes.append({"path": path, "status": code.strip() or "?"})
        return {
            "is_repo": True,
            "branch": branch,
            "changes": changes[:200],
            "ahead": 0,
            "behind": 0,
            "root": str(root),
        }

    @app.get("/workspace/rules")
    def workspace_rules(output_dir: str | None = None, project: str | None = None):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        root = Path(ctx["path"])
        rules: list[dict[str, str]] = []
        for folder in (root, base):
            for pattern in (".cursor/rules", ".cursorrules", "AGENTS.md", ".aion/rules"):
                p = folder / pattern
                if p.is_file():
                    rules.append({"path": str(p.relative_to(base)), "content": p.read_text(encoding="utf-8")[:8000]})
                elif p.is_dir():
                    for f in sorted(p.glob("*.md"))[:20]:
                        rules.append(
                            {
                                "path": str(f.relative_to(base)),
                                "content": f.read_text(encoding="utf-8")[:8000],
                            }
                        )
        return {"rules": rules, "project": ctx["project"]}

    @app.get("/ai/models")
    def ai_models():
        llm = _coordinator.llm
        cfg = _coordinator.config.get("llm", {})
        models = [
            {"id": "auto", "label": "Auto", "provider": cfg.get("provider", "groq")},
            {"id": cfg.get("model", "openai/gpt-oss-20b"), "label": cfg.get("model", "Default"), "provider": cfg.get("provider")},
            {"id": "gpt-4o-mini", "label": "GPT-4o mini", "provider": "openai"},
            {"id": "claude-sonnet-4", "label": "Claude Sonnet (BYOK)", "provider": "anthropic"},
            {"id": "llama3.2", "label": "Llama 3.2", "provider": "ollama"},
        ]
        return {"models": models, "active": cfg.get("model"), "llm_enabled": llm.enabled, "status": llm.status()}

    @app.post("/ai/inline-edit")
    def ai_inline_edit(req: InlineEditRequest):
        if not _coordinator.llm.enabled:
            raise HTTPException(503, _coordinator.llm.last_error or "LLM not configured")
        system = (
            "You are Cursor inline edit. Apply the user's instruction to the code selection only. "
            "Return ONLY the replacement code, no markdown fences, no explanation."
        )
        user = f"Language: {req.language}\nInstruction: {req.instruction}\n\nSelection:\n{req.selection}"
        result = _coordinator.llm.complete(system, user, max_tokens=2000)
        if not result:
            raise HTTPException(502, _coordinator.llm.last_error or "LLM failed")
        text = result.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return {"replacement": text}

    @app.post("/ai/chat")
    def ai_chat(req: ChatRequest):
        if not _coordinator.llm.enabled:
            raise HTTPException(503, _coordinator.llm.last_error or "LLM not configured")
        base = _root(req.output_dir)
        ctx = _coordinator.workspace.detect_context(
            req.output_dir, _coordinator.workspace.root, project_name=req.project
        )
        root = Path(ctx["path"])
        snippets: list[str] = []
        for rel in (req.context_files or [])[:8]:
            try:
                p = (root / rel.replace("\\", "/")).resolve()
                if p.is_file() and str(p).startswith(str(root.resolve())):
                    snippets.append(f"--- {rel} ---\n{p.read_text(encoding='utf-8')[:4000]}")
            except OSError:
                pass
        if req.active_file and not snippets:
            try:
                p = (root / req.active_file).resolve()
                if p.is_file():
                    snippets.append(f"--- {req.active_file} ---\n{p.read_text(encoding='utf-8')[:4000]}")
            except OSError:
                pass
        context_block = "\n\n".join(snippets) if snippets else "(no files attached)"
        system = (
            "You are AION AI assistant (Cursor-style). Answer concisely. "
            "Use markdown. When suggesting code changes, show clear diffs or file paths."
        )
        user = f"Project: {ctx['project']}\n\nContext:\n{context_block}\n\nUser:\n{req.message}"
        result = _coordinator.llm.complete(system, user, max_tokens=3000)
        if not result:
            raise HTTPException(502, _coordinator.llm.last_error or "LLM failed")
        return {"reply": result, "project": ctx["project"]}

    @app.get("/ide/features")
    def ide_features():
        ide_cfg = _coordinator.config.get("ide", {})
        return {
            "tab_completion": ide_cfg.get("tab_completion", True),
            "checkpoints": ide_cfg.get("checkpoints", True),
            "background_agents": ide_cfg.get("background_agents", True),
            "openvscode_url": ide_cfg.get("openvscode_url", ""),
            "noesis_enabled": True,
            "noesis_db": str(_coordinator.memory.db_path),
            "debugger": True,
            "semantic_index": True,
            "lsp_bridge": True,
        }

    @app.post("/index/rebuild")
    def index_rebuild(output_dir: str | None = None, project: str | None = None):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        root = Path(ctx["path"])
        return _codebase_index.rebuild(root)

    @app.get("/index/search")
    def index_search(
        q: str = Query(..., min_length=1),
        output_dir: str | None = None,
        project: str | None = None,
        limit: int = 20,
    ):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        root = Path(ctx["path"])
        if not _codebase_index._docs:
            _codebase_index.rebuild(root)
        hits = _codebase_index.search(q, limit=limit)
        nm_hits: list[dict] = []
        try:
            mem = _coordinator.memory.recall_for_task(q, limit=3)
            for i, s in enumerate(mem.summaries):
                nm_hits.append({"source": "noesis", "summary": s, "rank": i})
        except Exception:
            pass
        return {"query": q, "results": hits, "noesis": nm_hits, "project": ctx["project"]}

    @app.post("/checkpoints/create")
    def checkpoint_create(req: CheckpointRequest):
        base = _root(req.output_dir)
        ctx = _coordinator.workspace.detect_context(
            req.output_dir, _coordinator.workspace.root, project_name=req.project
        )
        return _checkpoints.create(Path(ctx["path"]), req.label)

    @app.get("/checkpoints")
    def checkpoint_list():
        return {"checkpoints": _checkpoints.list_all()}

    @app.post("/checkpoints/{checkpoint_id}/restore")
    def checkpoint_restore(checkpoint_id: str):
        try:
            return _checkpoints.restore(checkpoint_id)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e

    @app.post("/jobs/background")
    def job_background(req: BackgroundTaskRequest):
        desc = req.description

        def runner() -> dict:
            task = _coordinator.run_task(
                desc,
                req.project_name,
                output_dir=req.output_dir,
                mode=req.mode,
                active_file=req.active_file,
            )
            return task.to_dict()

        job = _bg_jobs.enqueue(desc, runner)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "description": job.description,
        }

    @app.get("/jobs/background")
    def job_background_list():
        return {"jobs": _bg_jobs.list_jobs()}

    @app.get("/jobs/background/{job_id}")
    def job_background_get(job_id: str):
        job = _bg_jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return {
            "job_id": job.job_id,
            "status": job.status,
            "description": job.description,
            "result": job.result,
            "error": job.error,
        }

    @app.post("/ai/complete")
    def ai_complete(req: CompleteRequest):
        if not _coordinator.llm.enabled:
            return {"suggestions": []}
        base = _root(req.output_dir)
        ctx = _coordinator.workspace.detect_context(req.output_dir, _coordinator.workspace.root)
        root = Path(ctx["path"])
        path = (root / req.path.replace("\\", "/")).resolve()
        file_ctx = ""
        if path.is_file() and str(path).startswith(str(root.resolve())):
            file_ctx = path.read_text(encoding="utf-8")[-3000:]
        system = (
            "You are Tab autocomplete. Continue code at cursor. "
            "Return ONLY the insertion text (1-8 lines), no fences."
        )
        user = (
            f"File: {req.path}\nLanguage: {req.language}\n"
            f"Before cursor:\n{req.prefix[-800:]}\n\nAfter cursor:\n{req.suffix[:200]}\n\n"
            f"File tail context:\n{file_ctx[-1500:]}"
        )
        result = _coordinator.llm.complete(system, user, max_tokens=400)
        if not result:
            return {"suggestions": []}
        text = result.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return {"suggestions": [{"text": text, "display": text.splitlines()[0][:60]}]}

    @app.post("/debug/session")
    def debug_session(output_dir: str | None = None, file_path: str = Query(...)):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(output_dir, _coordinator.workspace.root)
        root = Path(ctx["path"])
        sess = _debug_mgr.create(root, file_path)
        return {"session_id": sess.session_id, "file_path": sess.file_path}

    @app.post("/debug/breakpoints")
    def debug_breakpoints(req: DebugBreakpointRequest):
        sess = _debug_mgr.get(req.session_id)
        if not sess:
            raise HTTPException(404, "Debug session not found")
        _debug_mgr.set_breakpoints(req.session_id, req.path, req.lines)
        return {"session_id": req.session_id, "breakpoints": sess.breakpoints}

    @app.post("/debug/run")
    def debug_run(req: DebugRunRequest):
        sess = _debug_mgr.get(req.session_id)
        if not sess:
            raise HTTPException(404, "Debug session not found")
        return _debug_mgr.run(req.session_id)

    @app.get("/ide/lsp/hover")
    def lsp_hover(
        path: str = Query(...),
        line: int = Query(1),
        output_dir: str | None = None,
        project: str | None = None,
    ):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        return hover_info(Path(ctx["path"]), path, line)

    @app.get("/ide/lsp/symbols")
    def lsp_symbols(
        path: str = Query(...),
        output_dir: str | None = None,
        project: str | None = None,
    ):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        return {"symbols": document_symbols(Path(ctx["path"]), path)}

    @app.get("/ide/lsp/diagnostics")
    def lsp_diagnostics(output_dir: str | None = None, project: str | None = None):
        base = _root(output_dir)
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        issues = get_diagnostics(Path(ctx["path"]))
        return {"issues": issues}

    @app.get("/ide/lsp/completions")
    def lsp_completions(
        path: str = Query(...),
        line: int = Query(1),
        column: int = Query(1),
        prefix: str = Query(""),
        output_dir: str | None = None,
        project: str | None = None,
    ):
        ctx = _coordinator.workspace.detect_context(
            output_dir, _coordinator.workspace.root, project_name=project
        )
        items = get_completions(Path(ctx["path"]), path, line, column, prefix)
        return {"completions": items}

    @app.post("/memory/recall")
    def memory_recall(q: str = Query(...), limit: int = 5):
        ctx = _coordinator.memory.recall_for_task(q, limit=limit)
        return {
            "summaries": ctx.summaries,
            "graph_paths": ctx.graph_paths,
            "confidence": ctx.confidence,
        }

    @app.get("/pick-folder")
    def pick_folder():
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askdirectory(title="Open folder")
            root.destroy()
            if not path:
                return {"cancelled": True, "path": None}
            return {"cancelled": False, "path": path}
        except Exception as e:
            raise HTTPException(500, f"Folder picker unavailable: {e}") from e

    return app
