"""LangChain integration — Noesis as external persistent memory."""

from __future__ import annotations

from typing import Any

from noesis.core.engine import NoesisEngine


class NoesisMemory:
    """
    LangChain-compatible memory backend.
    Install: pip install langchain langchain-community

    Usage:
        memory = NoesisMemory()
        chain = LLMChain(llm=llm, memory=memory)
    """

    def __init__(self, db_path: str | None = None, return_messages: bool = True):
        self.engine = NoesisEngine(db_path=db_path)
        self.return_messages = return_messages
        self._lc_memory = None
        self._init_langchain()

    def _init_langchain(self) -> None:
        try:
            from langchain_core.memory import BaseMemory
            from langchain_core.messages import AIMessage, HumanMessage
        except ImportError:
            return

        engine = self.engine
        return_messages = self.return_messages

        class _NoesisLCBase(BaseMemory):
            @property
            def memory_variables(self) -> list[str]:
                return ["history", "noesis_context"]

            def load_memory_variables(self, inputs: dict) -> dict[str, str]:
                query = inputs.get("input") or inputs.get("question") or ""
                if query:
                    engine.remember(str(query), source="user")
                contexts = engine.recall(str(query), limit=5) if query else []
                ctx_text = "\n".join(c.summary for c in contexts) or "No memory."
                if return_messages:
                    history = []
                    for c in contexts[:3]:
                        history.append(HumanMessage(content=f"[Memory] {c.summary}"))
                    return {"history": history, "noesis_context": ctx_text}
                return {"history": ctx_text, "noesis_context": ctx_text}

            def save_context(self, inputs: dict, outputs: dict) -> None:
                user = inputs.get("input") or inputs.get("question") or ""
                ai = outputs.get("output") or outputs.get("text") or ""
                if user:
                    engine.remember(str(user), source="user")
                if ai:
                    engine.remember(str(ai)[:500], source="assistant", input_type="observation")

            def clear(self) -> None:
                pass

        self._lc_memory = _NoesisLCBase()

    @property
    def langchain_memory(self) -> Any:
        if self._lc_memory is None:
            raise ImportError("Install langchain: pip install langchain langchain-core")
        return self._lc_memory

    def remember(self, text: str, **kwargs) -> dict | None:
        return self.engine.remember(text, **kwargs)

    def recall(self, query: str, limit: int = 5) -> list:
        return self.engine.recall(query, limit=limit)
