"""Persistent AI agent powered by Noesis — remembers across sessions."""

from __future__ import annotations

from typing import Any

from noesis.core.engine import NoesisEngine


class PersistentAgent:
    """
    Drop-in assistant wrapper that uses Noesis instead of raw chat history.
    Suitable for Noesis demos, edge devices, and multi-session assistants.
    """

    def __init__(self, agent_id: str | None = None, db_path: str | None = None):
        self.engine = NoesisEngine(db_path=db_path)
        if agent_id:
            self.engine.agent_id = agent_id
            self.engine.config.setdefault("engine", {})["agent_id"] = agent_id
        self.session_turns = 0

    def chat(self, user_message: str) -> dict[str, Any]:
        """
        Process user message:
        1. Store as compressed semantic memory
        2. Recall relevant context via graph + embeddings
        3. Return augmented response context
        """
        self.session_turns += 1
        stored = self.engine.remember(user_message, source="user")

        contexts = self.engine.recall(user_message, limit=5, mode="hybrid")
        memory_block = self._format_context(contexts)

        return {
            "user_message": user_message,
            "stored": stored,
            "memory_context": memory_block,
            "recalled_count": len(contexts),
            "session_turns": self.session_turns,
            "suggested_system_prompt": self._build_system_prompt(memory_block),
            "graph_paths": [c.graph_path for c in contexts if c.graph_path],
        }

    def get_context_for_llm(self, query: str) -> str:
        """Format memory for injection into any LLM system prompt."""
        contexts = self.engine.recall(query, limit=5, mode="hybrid")
        return self._build_system_prompt(self._format_context(contexts))

    def teach(self, fact: str, category: str = "conversation") -> dict:
        """Explicitly teach the agent a fact."""
        return self.engine.remember(fact, input_type=category) or {}

    def share_with_agent(self, peer_url: str) -> dict:
        """Sync all memories to another Noesis agent."""
        return self.engine.sync_to_peer(peer_url)

    def learn_from_agent(self, peer_url: str) -> dict:
        """Import collective memory from peer."""
        return self.engine.sync_from_peer(peer_url)

    def summary(self) -> dict:
        return self.engine.stats()

    @staticmethod
    def _format_context(contexts) -> str:
        if not contexts:
            return "No relevant long-term memory."
        lines = []
        for i, ctx in enumerate(contexts, 1):
            path = " -> ".join(ctx.graph_path[:5]) if ctx.graph_path else ""
            lines.append(f"{i}. {ctx.summary}")
            if path:
                lines.append(f"   (via: {path})")
        return "\n".join(lines)

    @staticmethod
    def _build_system_prompt(memory_block: str) -> str:
        return f"""You are an AI assistant with persistent Noesis memory.
Use this compressed long-term knowledge (NOT raw chat logs):

{memory_block}

Respond using this context when relevant. Do not claim you lack memory."""
