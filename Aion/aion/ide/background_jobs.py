"""Background agent jobs (async multi-step tasks)."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class BackgroundJob:
    job_id: str
    description: str
    status: str  # queued | running | success | failed
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class BackgroundJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, BackgroundJob] = {}
        self._lock = threading.Lock()

    def enqueue(self, description: str, runner: Callable[[], dict]) -> BackgroundJob:
        job_id = f"BG-{uuid.uuid4().hex[:8].upper()}"
        job = BackgroundJob(job_id=job_id, description=description[:500], status="queued")
        with self._lock:
            self._jobs[job_id] = job

        def _run() -> None:
            with self._lock:
                job.status = "running"
            try:
                result = runner()
                with self._lock:
                    job.status = "success"
                    job.result = result
                    job.finished_at = time.time()
            except Exception as e:
                with self._lock:
                    job.status = "failed"
                    job.error = str(e)
                    job.finished_at = time.time()

        threading.Thread(target=_run, daemon=True).start()
        return job

    def get(self, job_id: str) -> BackgroundJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "job_id": j.job_id,
                    "description": j.description,
                    "status": j.status,
                    "created_at": j.created_at,
                    "finished_at": j.finished_at,
                    "error": j.error,
                    "task_id": (j.result or {}).get("task_id"),
                }
                for j in sorted(self._jobs.values(), key=lambda x: x.created_at, reverse=True)
            ][:30]
