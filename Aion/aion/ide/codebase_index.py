"""Semantic-ish codebase index (TF-IDF + optional Noesis recall)."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

_SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
_TEXT_EXT = {
    ".py", ".js", ".ts", ".tsx", ".html", ".css", ".json", ".md", ".yaml", ".yml", ".txt", ".rs", ".go", ".java",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())


class CodebaseIndex:
    def __init__(self) -> None:
        self._docs: dict[str, str] = {}
        self._df: Counter[str] = Counter()
        self._root: Path | None = None

    def rebuild(self, project_root: Path) -> dict:
        project_root = project_root.resolve()
        self._root = project_root
        self._docs.clear()
        self._df.clear()
        for path in project_root.rglob("*"):
            if not path.is_file():
                continue
            if any(p in _SKIP for p in path.parts):
                continue
            if path.suffix.lower() not in _TEXT_EXT:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:50000]
            except OSError:
                continue
            rel = str(path.relative_to(project_root)).replace("\\", "/")
            self._docs[rel] = text
            for tok in set(_tokenize(text)):
                self._df[tok] += 1
        return {"indexed": len(self._docs), "root": str(project_root)}

    def search(self, query: str, limit: int = 20) -> list[dict]:
        if not self._docs or not query.strip():
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        n = len(self._docs)
        scores: list[tuple[float, str, int, str]] = []
        for rel, text in self._docs.items():
            tokens = _tokenize(text)
            tf = Counter(tokens)
            score = 0.0
            for qt in q_tokens:
                if qt not in tf:
                    continue
                idf = math.log((1 + n) / (1 + self._df.get(qt, 0))) + 1
                score += (tf[qt] / max(len(tokens), 1)) * idf
            if rel.lower().find(query.lower()) >= 0:
                score += 2.0
            if score > 0:
                line = 1
                snippet = ""
                for i, line_text in enumerate(text.splitlines(), 1):
                    if query.lower() in line_text.lower():
                        line = i
                        snippet = line_text.strip()[:120]
                        break
                scores.append((score, rel, line, snippet))
        scores.sort(reverse=True, key=lambda x: x[0])
        return [
            {"path": rel, "line": line, "snippet": snippet, "score": round(sc, 3)}
            for sc, rel, line, snippet in scores[:limit]
        ]
