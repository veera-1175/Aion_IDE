"""Workspace checkpoints before agent edits (Cursor-style rollback)."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

_TEXT_EXT = {
    ".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".yaml", ".yml", ".txt",
}


class CheckpointManager:
    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def create(self, project_root: Path, label: str = "") -> dict:
        project_root = project_root.resolve()
        cid = f"CP-{uuid.uuid4().hex[:10]}"
        dest = self.store_dir / cid
        dest.mkdir(parents=True)
        files: list[str] = []
        for path in project_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _TEXT_EXT:
                continue
            if any(p in {".git", ".venv", "node_modules", "__pycache__"} for p in path.parts):
                continue
            rel = str(path.relative_to(project_root)).replace("\\", "/")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            files.append(rel)
        meta = {
            "id": cid,
            "label": label or "Agent checkpoint",
            "root": str(project_root),
            "created_at": time.time(),
            "files": files,
        }
        (dest / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta

    def list_all(self) -> list[dict]:
        out: list[dict] = []
        for d in sorted(self.store_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not d.is_dir():
                continue
            meta = d / "_meta.json"
            if meta.is_file():
                try:
                    out.append(json.loads(meta.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    pass
        return out[:50]

    def restore(self, checkpoint_id: str) -> dict:
        dest = self.store_dir / checkpoint_id
        meta_path = dest / "_meta.json"
        if not meta_path.is_file():
            raise FileNotFoundError(checkpoint_id)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        root = Path(meta["root"])
        restored = 0
        for rel in meta.get("files", []):
            src = dest / rel
            if not src.is_file():
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            restored += 1
        return {"checkpoint_id": checkpoint_id, "restored": restored, "root": str(root)}
