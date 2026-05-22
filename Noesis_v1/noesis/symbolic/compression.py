"""Layer 2 — Symbolic Compression Engine."""

from __future__ import annotations

from noesis.core.models import MemoryPacket, MemoryRecord
from noesis.symbolic.bytecode import BytecodeEncoder
from noesis.symbolic.packets import PacketBuilder
from noesis.symbolic.tokenizer import SymbolicTokenizer


class SymbolicCompressionEngine:
    """
    Layer 2 — Symbolic Compression Engine
    Handles: tokenization, bytecode conversion, deterministic reconstruction
    """

    def __init__(self, config: dict):
        sym_cfg = config.get("symbolic", {})
        self.tokenizer = SymbolicTokenizer(
            model_path=sym_cfg.get("sp_model_path", "data/symbolic_vocab.model"),
            vocab_size=sym_cfg.get("vocab_size", 8000),
        )
        self.encoder = BytecodeEncoder()
        self.packet_builder = PacketBuilder()
        self.use_zlib = sym_cfg.get("compression") == "zlib"

    def compress(self, record: MemoryRecord, graph_edges: list[tuple[str, str, str]] | None = None) -> MemoryPacket:
        token_ids = self.tokenizer.encode(record.abstracted_content)
        payload = {
            "memory_id": record.memory_id,
            "summary": record.abstracted_content,
            "raw_excerpt": record.content[:200],
            "token_ids": token_ids,
            "category": record.category.value,
            "importance": record.importance,
            "cluster": record.cluster_id,
            "tags": record.tags,
            "concepts": [
                {"label": c.label, "type": c.concept_type}
                for c in record.concepts[:20]
            ],
        }
        bytecode = self.encoder.encode(payload, use_zlib=self.use_zlib)
        return self.packet_builder.build(record, token_ids, bytecode, graph_edges)

    def decompress(self, packet: MemoryPacket) -> dict:
        """Reconstruct semantic payload from bytecode."""
        payload = self.encoder.decode(packet.bytecode, use_zlib=self.use_zlib)
        if "token_ids" in payload:
            payload["reconstructed_text"] = self.tokenizer.decode(payload["token_ids"])
        return payload
