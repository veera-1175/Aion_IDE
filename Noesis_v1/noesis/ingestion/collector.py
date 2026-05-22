"""Step 1 — Input Collection: conversations, logs, observations, documents."""

from __future__ import annotations

from noesis.core.models import InputType, RawInput
from noesis.storage.sqlite_store import SQLiteMemoryStore


class InputCollector:
    """Collects and normalizes diverse input streams into RawInput objects."""

    def __init__(self, store: SQLiteMemoryStore | None = None):
        self.store = store

    def from_conversation(self, text: str, source: str = "user", **metadata) -> RawInput:
        return self._create(text, InputType.CONVERSATION, source, metadata)

    def from_log(self, text: str, source: str = "system", **metadata) -> RawInput:
        return self._create(text, InputType.LOG, source, metadata)

    def from_observation(self, text: str, source: str = "agent", **metadata) -> RawInput:
        return self._create(text, InputType.OBSERVATION, source, metadata)

    def from_document(self, text: str, source: str = "document", **metadata) -> RawInput:
        return self._create(text, InputType.DOCUMENT, source, metadata)

    def from_event(self, text: str, source: str = "system", **metadata) -> RawInput:
        return self._create(text, InputType.EVENT, source, metadata)

    def from_sensor(self, text: str, source: str = "sensor", **metadata) -> RawInput:
        return self._create(text, InputType.SENSOR, source, metadata)

    def ingest_batch(self, items: list[dict]) -> list[RawInput]:
        """Ingest multiple items: [{"content": "...", "type": "conversation"}, ...]"""
        type_map = {t.value: t for t in InputType}
        results = []
        for item in items:
            input_type = type_map.get(item.get("type", "conversation"), InputType.CONVERSATION)
            raw = self._create(
                item["content"],
                input_type,
                item.get("source", "user"),
                item.get("metadata", {}),
            )
            results.append(raw)
        return results

    def _create(self, content: str, input_type: InputType, source: str, metadata: dict) -> RawInput:
        raw = RawInput(content=content.strip(), input_type=input_type, source=source, metadata=metadata)
        if self.store:
            self.store.log_raw_input(content, input_type.value, source, metadata)
        return raw
