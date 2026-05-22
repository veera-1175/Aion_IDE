"""LSP-style helpers — hover, diagnostics, symbols (validator-backed)."""

from __future__ import annotations

import re
from pathlib import Path

from aion.tools.validators import detect_languages, validate_all


def get_diagnostics(project_root: Path) -> list[dict]:
    errors, by_lang = validate_all(project_root)
    issues: list[dict] = []
    for err in errors:
        m = re.match(r"^(\w+)\s+([^:]+):\s*(.+)$", err)
        if m:
            lang, rel, msg = m.group(1), m.group(2), m.group(3)
            line = 1
            lm = re.search(r"line (\d+)", msg)
            if lm:
                line = int(lm.group(1))
            issues.append({
                "path": rel,
                "line": line,
                "column": 1,
                "message": msg,
                "severity": "error",
                "source": lang,
            })
        else:
            issues.append({
                "path": "",
                "line": 1,
                "column": 1,
                "message": err,
                "severity": "error",
                "source": "aion",
            })
    return issues


def hover_info(project_root: Path, rel_path: str, line: int) -> dict:
    path = (project_root / rel_path.replace("\\", "/")).resolve()
    if not path.is_file() or not str(path).startswith(str(project_root.resolve())):
        return {"contents": ""}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line < 1 or line > len(lines):
        return {"contents": ""}
    text = lines[line - 1]
    langs = detect_languages(project_root)
    return {
        "contents": f"**{rel_path}** :{line}\n\n```\n{text[:200]}\n```\n\nLanguages: {', '.join(sorted(langs))}",
    }


def document_symbols(project_root: Path, rel_path: str) -> list[dict]:
    path = (project_root / rel_path.replace("\\", "/")).resolve()
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    symbols: list[dict] = []
    if path.suffix == ".py":
        for i, line in enumerate(text.splitlines(), 1):
            m = re.match(r"^(def|class)\s+(\w+)", line)
            if m:
                symbols.append({
                    "name": m.group(2),
                    "kind": "class" if m.group(1) == "class" else "function",
                    "line": i,
                })
    elif path.suffix in (".js", ".ts"):
        for i, line in enumerate(text.splitlines(), 1):
            m = re.match(r"^(export\s+)?(function|class)\s+(\w+)", line)
            if m:
                symbols.append({"name": m.group(3), "kind": m.group(2), "line": i})
    return symbols


_KEYWORDS: dict[str, list[str]] = {
    "python": [
        "def", "class", "import", "from", "return", "if", "elif", "else", "for", "while",
        "try", "except", "finally", "with", "as", "pass", "break", "continue", "raise",
        "True", "False", "None", "and", "or", "not", "in", "is", "lambda", "yield", "async", "await",
        "print", "self", "super",
    ],
    "javascript": [
        "function", "const", "let", "var", "return", "if", "else", "for", "while", "class",
        "import", "export", "from", "default", "async", "await", "try", "catch", "throw", "new",
        "true", "false", "null", "undefined", "typeof", "this",
    ],
    "typescript": [
        "function", "const", "let", "interface", "type", "enum", "implements", "extends",
        "import", "export", "from", "return", "async", "await", "public", "private", "readonly",
    ],
    "html": ["div", "span", "script", "style", "link", "meta", "head", "body", "html", "button", "input"],
    "css": ["display", "flex", "color", "background", "margin", "padding", "border", "width", "height"],
}


def _word_at(line: str, column: int) -> str:
    if column < 1:
        column = 1
    col = min(column, len(line)) if line else 0
    before = line[:col]
    m = re.search(r"[\w.$]+$", before)
    return m.group(0) if m else ""


def get_completions(
    project_root: Path,
    rel_path: str,
    line: int,
    column: int,
    prefix_text: str = "",
) -> list[dict]:
    """Symbol + keyword completions for Monaco IntelliSense."""
    path = (project_root / rel_path.replace("\\", "/")).resolve()
    if not path.is_file() or not str(path).startswith(str(project_root.resolve())):
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    cur_line = lines[line - 1] if 1 <= line <= len(lines) else ""
    word = _word_at(cur_line, column)
    if not word and prefix_text:
        tail = prefix_text.splitlines()[-1] if prefix_text else ""
        word = _word_at(tail, len(tail) + 1)

    lang = path.suffix.lstrip(".")
    lang_map = {"py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript"}
    lang_key = lang_map.get(lang, lang)

    seen: set[str] = set()
    out: list[dict] = []

    def add(label: str, insert: str | None = None, kind: str = "keyword", detail: str = "") -> None:
        if not label or label in seen:
            return
        seen.add(label)
        out.append({
            "label": label,
            "insertText": insert if insert is not None else label,
            "kind": kind,
            "detail": detail,
        })

    for sym in document_symbols(project_root, rel_path):
        add(sym["name"], kind="function" if sym.get("kind") == "function" else "class", detail=sym.get("kind", ""))

    for kw in _KEYWORDS.get(lang_key, []):
        if not word or kw.startswith(word) or word in kw:
            add(kw, kind="keyword")

    if word.startswith("@"):
        for py in project_root.rglob("*"):
            if py.is_file() and any(x in py.parts for x in (".git", ".venv", "node_modules", "__pycache__")):
                continue
            rel = str(py.relative_to(project_root)).replace("\\", "/")
            if rel.endswith((".py", ".js", ".ts", ".html", ".css", ".md", ".json")):
                tag = "@" + rel.split("/")[-1]
                if tag.startswith(word) or not word[1:]:
                    add(tag, insert=f"@{rel} ", kind="file", detail=rel)

    return out[:80]
