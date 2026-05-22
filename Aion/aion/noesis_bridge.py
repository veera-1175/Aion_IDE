"""Noesis integration — optional storage; recall disabled for fresh LLM runs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from noesis import NoesisEngine

from aion.models import AgentRole, MemoryContext

logger = logging.getLogger(__name__)


class NoesisBridge:
    """Bridge to Noesis — storage optional; recall can be disabled."""

    def __init__(self, db_path: str, agent_id: str = "AION-collective", recall_limit: int = 0):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.recall_limit = recall_limit
        self.engine = NoesisEngine(db_path=str(self.db_path))
        self.engine.agent_id = agent_id
        self._session_events: list[dict[str, Any]] = []

    def recall_for_task(self, task_description: str, limit: int | None = None) -> MemoryContext:
        """Return empty context when recall_limit is 0 (no prior data injected into agents)."""
        cap = self.recall_limit if limit is None else limit
        if cap <= 0:
            return MemoryContext(summaries=[], graph_paths=[], memory_ids=[], confidence=0.0)

        contexts = self.engine.recall(task_description, limit=cap, mode="hybrid")
        summaries = [c.summary for c in contexts]
        paths = [c.graph_path for c in contexts if c.graph_path]
        ids = [c.memory_id for c in contexts if c.memory_id != "graph-recall"]
        confidence = max((c.confidence for c in contexts), default=0.0)
        return MemoryContext(
            summaries=summaries,
            graph_paths=paths,
            memory_ids=ids,
            confidence=confidence,
        )

    def reset_all(self) -> dict[str, Any]:
        """Wipe all Noesis data — brand-new memory (clears tables in-place)."""
        agent_id = self.engine.agent_id
        with self.engine.store._connect() as conn:
            conn.executescript(
                "DELETE FROM memory_packets; DELETE FROM graph_edges; "
                "DELETE FROM memories; DELETE FROM raw_inputs;"
            )
        self.engine.graph.hydrate_from_store()
        cache = getattr(self.engine, "_embedding_cache", None)
        if isinstance(cache, dict):
            cache.clear()
        self._session_events = []
        return {"cleared": True, "db_path": str(self.db_path), "agent_id": agent_id}

    def remember_agent_work(
        self,
        role: AgentRole,
        content: str,
        input_type: str = "observation",
        **metadata: Any,
    ) -> dict[str, Any] | None:
        enriched = f"[{role.value.upper()} Agent] {content} | metadata: {metadata}"
        result = self.engine.remember(
            enriched,
            input_type=input_type,
            source=f"AION-{role.value}",
            agent_role=role.value,
            **{k: v for k, v in metadata.items() if k != "agent_role"},
        )
        if result:
            self._session_events.append({"role": role.value, "memory_id": result.get("memory_id")})
        return result

    def remember_bug_fix(self, error: str, fix: str, technology: str = "") -> dict | None:
        return self.remember_agent_work(
            AgentRole.DEBUG,
            f"Fixed error '{error[:80]}' with solution: {fix}. Technology: {technology}",
            input_type="log",
            category="bug_fix",
        )

    def remember_test_result(self, passed: int, failed: int, notes: str) -> dict | None:
        return self.remember_agent_work(
            AgentRole.TESTING,
            f"Tests: {passed} passed, {failed} failed. {notes}",
            input_type="event",
            category="test_run",
        )

    def stats(self) -> dict[str, Any]:
        s = self.engine.stats()
        s["session_events"] = len(self._session_events)
        s["recall_limit"] = self.recall_limit
        return s

    def explain_recall(self, query: str) -> dict:
        return self.engine.explain_recall(query)
