"""Configuration loader for Noesis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return _default_config()
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or _default_config()


def _default_config() -> dict[str, Any]:
    return {
        "engine": {"name": "Noesis", "version": "0.1.0", "agent_id": "agent-default"},
        "storage": {"type": "sqlite", "path": "data/noesis.db"},
        "semantic": {
            "embedding_model": "all-MiniLM-L6-v2",
            "similarity_threshold": 0.75,
            "min_importance": 0.15,
            "abstraction_min_events": 2,
        },
        "symbolic": {"vocab_size": 512, "sp_model_path": "data/symbolic_vocab.model", "compression": "msgpack"},
        "graph": {"backend": "networkx", "max_traversal_depth": 4},
        "forgetting": {"enabled": True, "decay_rate": 0.02, "min_retention_score": 0.1, "review_boost": 0.15},
        "sync": {"enabled": False, "transport": "local", "mesh_port": 8765},
    }
