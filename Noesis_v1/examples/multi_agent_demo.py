"""
Multi-Agent Demo — Innovation #3: Distributed Shared AI Memory
Two agents share learned knowledge via portable memory packets.
"""

from __future__ import annotations

import json
from pathlib import Path

from noesis import NoesisEngine


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def run() -> None:
    demo_dir = Path("data/multi_agent_demo")
    demo_dir.mkdir(parents=True, exist_ok=True)
    agent_a_db = demo_dir / "agent_a.db"
    agent_b_db = demo_dir / "agent_b.db"

    agent_a = NoesisEngine(db_path=str(agent_a_db))
    agent_b = NoesisEngine(db_path=str(agent_b_db))
    agent_a.config["engine"]["agent_id"] = "agent-alpha"
    agent_b.config["engine"]["agent_id"] = "agent-beta"

    _safe_print("=" * 60)
    _safe_print("  MULTI-AGENT COLLECTIVE MEMORY DEMO")
    _safe_print("=" * 60)

    _safe_print("\n[Agent Alpha] Learning from user...")
    r = agent_a.remember("User deployed Redis cluster for FastAPI scaling")
    _safe_print(f"  Stored: {r['summary'][:70]}...")

    export_path = agent_a.export_memory(r["memory_id"])
    _safe_print(f"\n[Export] Portable memory packet: {export_path}")

    _safe_print("\n[Agent Beta] Importing collective memory...")
    imported = agent_b.import_memory(export_path, source_agent="agent-alpha")
    _safe_print(json.dumps(imported, indent=2))

    _safe_print("\n[Agent Beta] Recalling imported knowledge...")
    contexts = agent_b.recall("Redis FastAPI scaling", mode="hybrid")
    for ctx in contexts:
        _safe_print(f"  {ctx.summary[:80]}...")
        _safe_print(f"  Confidence: {ctx.confidence}")

    _safe_print("\n[Result] Agent Alpha's experience became Agent Beta's memory.")
    _safe_print("  Traditional AI: isolated agents, no portable cognition.")
    _safe_print("  Noesis: symbolic packets enable collective intelligence.")
    _safe_print(f"\n  Agent A memories: {agent_a.stats()['total_memories']}")
    _safe_print(f"  Agent B memories: {agent_b.stats()['total_memories']}")


if __name__ == "__main__":
    run()
