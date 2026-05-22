"""Phase 4 — Mesh client: push/pull memory packets to peer agents."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class MeshClient:
    """Connect to remote Noesis agents over HTTP (LAN / edge)."""

    def __init__(self, peer_url: str, timeout: float = 10.0):
        self.peer_url = peer_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            data = self._get("/health")
            return data.get("status") == "ok"
        except Exception:
            return False

    def list_packets(self) -> list[dict]:
        data = self._get("/packets")
        return data.get("packets", [])

    def get_packet(self, memory_id: str) -> dict:
        return self._get(f"/packets/{memory_id}")

    def push_packet(self, packet_dict: dict) -> dict:
        return self._post("/packets", packet_dict)

    def request_sync(self, agent_id: str) -> dict:
        return self._post("/sync", {"agent_id": agent_id})

    def pull_all(self) -> list[dict]:
        """Pull all available packets from peer."""
        return self.list_packets()

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(f"{self.peer_url}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.peer_url}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
