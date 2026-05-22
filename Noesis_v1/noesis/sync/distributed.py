"""Phase 4 — Distributed Synchronization Layer (MVP: local file export/import)."""

from __future__ import annotations

import json
from pathlib import Path

from noesis.core.models import MemoryPacket


class DistributedSyncLayer:
    """
    Distributed sync for memory packets across agents/devices.
    MVP: JSON file export/import for LAN/offline transfer.
    Phase 4: WebRTC, libp2p, MQTT integrations.
    """

    def __init__(self, config: dict):
        sync_cfg = config.get("sync", {})
        self.enabled = sync_cfg.get("enabled", False)
        self.transport = sync_cfg.get("transport", "local")
        self.export_dir = Path("data/sync_exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_packet(self, packet: MemoryPacket, agent_id: str = "default") -> Path:
        """Export portable memory packet to sync directory."""
        filename = f"{agent_id}_{packet.memory_id}_{packet.timestamp[:10]}.json"
        path = self.export_dir / filename
        path.write_text(json.dumps(packet.to_dict(), indent=2), encoding="utf-8")
        return path

    def import_packet(self, path: str | Path) -> MemoryPacket:
        """Import memory packet from file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return self.import_packet_from_dict(data)

    def import_packet_from_dict(self, data: dict) -> MemoryPacket:
        """Import memory packet from JSON dict (file or HTTP)."""
        return MemoryPacket(
            memory_id=data["memory_id"],
            importance=data["importance"],
            semantic_cluster=data["semantic_cluster"],
            category=data["category"],
            semantic_summary=data["semantic_summary"],
            bytecode=bytes.fromhex(data["bytecode"]),
            token_ids=data.get("token_ids", []),
            graph_edges=[tuple(e) for e in data.get("graph_edges", [])],
            tags=data.get("tags", []),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )

    def list_pending_exports(self) -> list[Path]:
        return sorted(self.export_dir.glob("*.json"))

    # Phase 4 stubs
    async def sync_via_webrtc(self, peer_id: str, packet: MemoryPacket) -> bool:
        raise NotImplementedError("WebRTC sync — Phase 4. Enable with: pip install noesis[sync]")

    async def sync_via_libp2p(self, peer_id: str, packet: MemoryPacket) -> bool:
        raise NotImplementedError("libp2p sync — Phase 4")
