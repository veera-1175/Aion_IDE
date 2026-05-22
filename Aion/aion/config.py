"""Configuration loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"


def _load_dotenv() -> None:
    """Load Aion/.env into os.environ (does not override existing vars)."""
    for candidate in (ROOT / ".env", Path.cwd() / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    _load_dotenv()
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.exists():
        return _defaults()
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or _defaults()
    llm = cfg.setdefault("llm", {})
    if os.getenv("LLM_PROVIDER"):
        llm["provider"] = os.getenv("LLM_PROVIDER")
    if os.getenv("OLLAMA_MODEL"):
        llm["model"] = os.getenv("OLLAMA_MODEL")
    if os.getenv("GROQ_MODEL"):
        llm["model"] = os.getenv("GROQ_MODEL")
    # Auto-enable when any supported backend is configured
    if os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or llm.get("provider") == "ollama":
        llm["enabled"] = True
    return cfg


def _defaults() -> dict[str, Any]:
    return {
        "project": {"name": "AION", "version": "1.0.0"},
        "noesis": {"db_path": "data/AION_memory.db", "agent_id": "AION-collective"},
        "workspace": {"root": "workspace", "default_project": "generated_app"},
        "coordinator": {"max_iterations": 3, "recall_limit": 5},
        "llm": {"enabled": False, "provider": "openai", "model": "gpt-4o-mini"},
        "agents": {
            "coding": {"enabled": True},
            "debug": {"enabled": True},
            "testing": {"enabled": True},
            "memory": {"enabled": True},
        },
        "api": {"host": "127.0.0.1", "port": 8090},
    }
