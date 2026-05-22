"""JSON schemas for Groq Structured Outputs (strict mode requires additionalProperties: false everywhere)."""

from __future__ import annotations

# Fixed web project — strict mode OK
WEB_PROJECT_SCHEMA_STRICT = {
    "type": "object",
    "properties": {
        "files": {
            "type": "object",
            "properties": {
                "index.html": {"type": "string"},
                "styles.css": {"type": "string"},
                "script.js": {"type": "string"},
                "README.md": {"type": "string"},
            },
            "required": ["index.html", "styles.css", "script.js", "README.md"],
            "additionalProperties": False,
        },
        "summary": {"type": "string"},
    },
    "required": ["files", "summary"],
    "additionalProperties": False,
}

# Non-strict only (additionalProperties on files) — use with strict: false
GENERIC_PROJECT_SCHEMA_LOOSE = {
    "type": "object",
    "properties": {
        "files": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["files", "summary"],
    "additionalProperties": False,
    "x_groq_strict": False,
}

GROQ_STRICT_JSON_MODELS = frozenset({
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
})

MAX_STRICT_FILE_KEYS = 16


def build_edit_schema_strict(file_paths: list[str]) -> dict | None:
    """
    Build Groq strict schema from actual project files.
    Returns None if too many files (caller should use json_object mode).
    """
    paths = [p.replace("\\", "/") for p in file_paths if p and "." in p][:MAX_STRICT_FILE_KEYS]
    if not paths or len(file_paths) > MAX_STRICT_FILE_KEYS:
        return None

    file_props = {p: {"type": "string"} for p in paths}
    return {
        "type": "object",
        "properties": {
            "files": {
                "type": "object",
                "properties": file_props,
                "required": paths,
                "additionalProperties": False,
            },
            "summary": {"type": "string"},
        },
        "required": ["files", "summary"],
        "additionalProperties": False,
    }
