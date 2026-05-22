"""Debug session — breakpoints, run-under-debug, stack capture."""

from __future__ import annotations

import subprocess
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DebugSession:
    session_id: str
    cwd: Path
    file_path: str
    breakpoints: dict[str, list[int]] = field(default_factory=dict)
    running: bool = False
    last_output: str = ""
    last_stack: list[dict] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)


class DebugSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, DebugSession] = {}

    def create(self, cwd: Path, file_path: str) -> DebugSession:
        sid = f"DBG-{uuid.uuid4().hex[:8]}"
        sess = DebugSession(session_id=sid, cwd=cwd.resolve(), file_path=file_path.replace("\\", "/"))
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> DebugSession | None:
        return self._sessions.get(session_id)

    def set_breakpoints(self, session_id: str, file_path: str, lines: list[int]) -> None:
        sess = self._sessions[session_id]
        sess.breakpoints[file_path.replace("\\", "/")] = sorted(set(lines))

    def run(self, session_id: str) -> dict:
        sess = self._sessions[session_id]
        target = sess.cwd / sess.file_path
        if not target.is_file():
            raise FileNotFoundError(sess.file_path)
        sess.running = True
        sess.last_stack = []
        sess.variables = {}
        try:
            proc = subprocess.run(
                [sys.executable, str(target)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(sess.cwd),
                encoding="utf-8",
                errors="replace",
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            sess.last_output = out[-8000:]
            if proc.returncode != 0 and "Traceback" in out:
                sess.last_stack = self._parse_traceback(out)
            return {
                "session_id": session_id,
                "exit_code": proc.returncode,
                "output": sess.last_output,
                "stack": sess.last_stack,
                "breakpoints": sess.breakpoints,
            }
        except subprocess.TimeoutExpired:
            sess.last_output = "Debug run timed out (60s)"
            return {"session_id": session_id, "exit_code": -1, "output": sess.last_output, "stack": []}
        finally:
            sess.running = False

    def _parse_traceback(self, text: str) -> list[dict]:
        frames: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('File "') and ", line " in line:
                try:
                    part = line[6:]
                    path, rest = part.split('", line ', 1)
                    line_no = int(rest.split(",")[0])
                    frames.append({"file": path, "line": line_no, "text": line})
                except ValueError:
                    continue
        return frames[-12:]
