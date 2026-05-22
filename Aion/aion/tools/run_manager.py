"""Run code and projects from the IDE (Cursor-style Run / Debug)."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from aion.codegen.file_sanitizer import repair_project_on_disk


@dataclass
class RunningProcess:
    job_id: str
    command: str
    cwd: str
    proc: subprocess.Popen
    output: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    def append_output(self, text: str) -> None:
        for line in text.splitlines():
            self.output.append(line)
        if len(self.output) > 500:
            self.output = self.output[-500:]


class RunManager:
    """Execute files and projects; track background terminals."""

    DEFAULT_HTTP_PORT = 8765

    def __init__(self) -> None:
        self._jobs: dict[str, RunningProcess] = {}
        self._lock = threading.Lock()
        self._http_port: int | None = None
        self._preview_root: Path | None = None
        self._api_port: int = 8090

    def set_api_port(self, port: int) -> None:
        self._api_port = port

    def get_preview_root(self) -> Path | None:
        return self._preview_root

    def clear_preview(self) -> None:
        self._preview_root = None

    def _find_free_port(self, start: int | None = None) -> int:
        base = start or self.DEFAULT_HTTP_PORT
        for port in range(base, base + 50):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free port for preview server (8765-8814)")

    def _stop_http_servers(self) -> None:
        """Stop prior preview servers so port is not shared by zombie processes."""
        with self._lock:
            for job in list(self._jobs.values()):
                if "http.server" in job.command and job.proc.poll() is None:
                    try:
                        job.proc.terminate()
                        job.proc.wait(timeout=2)
                    except Exception:
                        try:
                            job.proc.kill()
                        except Exception:
                            pass
            self._jobs = {
                k: v for k, v in self._jobs.items() if v.proc.poll() is not None
            }
        self._http_port = None

    def _wait_for_http(self, port: int, timeout: float = 10.0) -> bool:
        url = f"http://127.0.0.1:{port}/"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.25)
        return False

    def _wait_for_url(self, url: str, timeout: float = 8.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.2)
        return False

    def _start_builtin_preview(self, cwd: Path, api_port: int | None = None) -> dict:
        """Serve HTML/CSS/JS through AION on :8090/preview/ (no separate http.server)."""
        self._stop_http_servers()
        cwd = cwd.resolve()
        index = cwd / "index.html"
        if not index.exists():
            raise FileNotFoundError(f"No index.html in {cwd}")

        port = api_port or self._api_port
        self._preview_root = cwd
        base = f"http://127.0.0.1:{port}/preview/"
        repaired = repair_project_on_disk(cwd)

        return {
            "job_id": "builtin-preview",
            "command": f"Preview via AION :{port}/preview/",
            "cwd": str(cwd),
            "background": False,
            "running": False,
            "url": base,
            "port": port,
            "auto_open": True,
            "ready": True,
            "preview_mode": "builtin",
            "output": f"Serving {index.name} from {cwd}"
            + (f" (repaired: {', '.join(repaired)})" if repaired else ""),
        }

    def _start_http_server(self, cwd: Path, background: bool = True, api_port: int | None = None) -> dict:
        return self._start_builtin_preview(cwd, api_port=api_port)

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "job_id": j.job_id,
                    "command": j.command,
                    "cwd": j.cwd,
                    "running": j.proc.poll() is None,
                    "exit_code": j.proc.poll(),
                }
                for j in self._jobs.values()
            ]

    def stop_job(self, job_id: str | None = None) -> bool:
        with self._lock:
            if job_id:
                job = self._jobs.get(job_id)
                if job and job.proc.poll() is None:
                    job.proc.terminate()
                    return True
                return False
            stopped = False
            for job in list(self._jobs.values()):
                if job.proc.poll() is None:
                    job.proc.terminate()
                    stopped = True
            return stopped

    def get_output(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {"job_id": job_id, "output": "", "running": False}
            return {
                "job_id": job_id,
                "output": "\n".join(job.output),
                "running": job.proc.poll() is None,
                "exit_code": job.proc.poll(),
                "command": job.command,
            }

    def _reader(self, job: RunningProcess) -> None:
        assert job.proc.stdout
        for line in iter(job.proc.stdout.readline, ""):
            if not line:
                break
            job.append_output(line.rstrip("\n\r"))

    def _spawn(self, command: str, cwd: Path, background: bool = True) -> dict:
        cwd = cwd.resolve()
        if not cwd.is_dir():
            raise FileNotFoundError(f"Not a directory: {cwd}")

        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = RunningProcess(job_id=job_id, command=command, cwd=str(cwd), proc=proc)
        with self._lock:
            self._jobs[job_id] = job
        if background and proc.stdout:
            threading.Thread(target=self._reader, args=(job,), daemon=True).start()
            return {
                "job_id": job_id,
                "command": command,
                "cwd": str(cwd),
                "background": True,
                "running": True,
            }

        out, _ = proc.communicate(timeout=120)
        job.append_output(out or "")
        return {
            "job_id": job_id,
            "command": command,
            "cwd": str(cwd),
            "background": False,
            "running": False,
            "exit_code": proc.returncode,
            "output": "\n".join(job.output),
        }

    def resolve_project_dir(self, workspace: Path, project_name: str | None = None) -> Path:
        if project_name and project_name.strip():
            cand = workspace / project_name.strip()
            if cand.is_dir():
                return cand.resolve()
        for name in ("main.py", "index.html", "app.py", "package.json"):
            if (workspace / name).exists():
                return workspace.resolve()
        for child in sorted(workspace.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                if (child / "main.py").exists() or (child / "index.html").exists():
                    return child.resolve()
        return workspace.resolve()

    def detect_run_command(self, project: Path, active_file: str | None = None) -> tuple[str, str]:
        """Return (command, label) for Run Project."""
        project = project.resolve()
        rel = (active_file or "").replace("\\", "/").lstrip("/")

        if rel.endswith(".html"):
            return ("__http_server__", "Serve index.html in browser")

        if rel.endswith(".py"):
            target = (project.parent if "/" in rel else project) / rel.split("/")[-1]
            if not target.is_file():
                target = project / rel
            if target.is_file():
                return f'"{sys.executable}" "{target}"', f"Python: {rel}"

        # Web portfolio: prefer browser preview when index.html exists
        if (project / "index.html").exists():
            return ("__http_server__", "Serve index.html in browser")

        for entry in ("main.py", "app.py", "run.py"):
            if (project / entry).exists():
                return f'"{sys.executable}" "{project / entry}"', f"Python: {entry}"

        if rel.endswith(".py") and (project / rel).is_file():
            return f'"{sys.executable}" "{project / rel}"', f"Python: {rel}"

        pkg = project / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                scripts = data.get("scripts", {})
                if "start" in scripts:
                    return "npm start", "npm start"
                if "dev" in scripts:
                    return "npm run dev", "npm run dev"
            except json.JSONDecodeError:
                pass

        py_files = list(project.glob("*.py"))
        if len(py_files) == 1:
            return f'"{sys.executable}" "{py_files[0]}"', f"Python: {py_files[0].name}"

        raise ValueError(
            "No runnable entry found. Add main.py, index.html, or open a .py file and press F5."
        )

    def run_project(
        self,
        workspace: Path,
        project_name: str | None = None,
        active_file: str | None = None,
        background: bool = True,
        api_port: int | None = None,
    ) -> dict:
        workspace = workspace.resolve()
        rel = (active_file or "").replace("\\", "/").lstrip("/")
        if rel.endswith(".py"):
            target = workspace / rel
            if target.is_file():
                return self.run_file(
                    workspace, rel, background=background, api_port=api_port
                )

        project = self.resolve_project_dir(workspace, project_name)
        cmd, label = self.detect_run_command(project, rel or None)
        if cmd == "__http_server__":
            if not (project / "index.html").exists():
                raise FileNotFoundError(f"No index.html in {project}")
            result = self._start_http_server(project, background=background, api_port=api_port)
            result["label"] = label
            result["kind"] = "project"
            return result
        result = self._spawn(cmd, project, background=background)
        result["label"] = label
        result["kind"] = "project"
        return result

    def run_file(
        self,
        workspace: Path,
        file_path: str,
        background: bool = False,
        api_port: int | None = None,
    ) -> dict:
        rel = file_path.replace("\\", "/").lstrip("/")
        target = (workspace / rel).resolve()
        if not str(target).startswith(str(workspace.resolve())):
            raise PermissionError("Invalid path")
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {rel}")

        ext = target.suffix.lower()
        cwd = target.parent
        if ext == ".py":
            cmd = f'"{sys.executable}" "{target}"'
        elif ext == ".html":
            return self._start_http_server(cwd, background=True, api_port=api_port)
        elif ext == ".js" and "node" in sys.executable.lower():
            cmd = f'node "{target}"'
        else:
            raise ValueError(f"Cannot run .{ext} files directly")

        result = self._spawn(cmd, cwd, background=background)
        result["label"] = rel
        result["kind"] = "file"
        return result

    def collect_diagnostics(self, workspace: Path, project_name: str | None = None) -> list[dict]:
        import ast

        project = self.resolve_project_dir(workspace, project_name)
        issues: list[dict] = []
        for py in project.rglob("*.py"):
            if any(p in py.parts for p in (".venv", "node_modules", "__pycache__", ".git")):
                continue
            try:
                text = py.read_text(encoding="utf-8")
                ast.parse(text)
            except SyntaxError as e:
                rel = str(py.relative_to(workspace.resolve())).replace("\\", "/")
                issues.append({
                    "path": rel,
                    "line": e.lineno or 1,
                    "message": str(e.msg or e),
                    "severity": "error",
                })
        return issues[:100]
