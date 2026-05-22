"""Phase 4 — HTTP mesh server for LAN/edge memory synchronization."""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MeshRequestHandler(BaseHTTPRequestHandler):
    """REST API for memory packet exchange between agents."""

    registry: dict = {}  # class-level: path -> handler callbacks

    def log_message(self, format, *args):
        logger.debug(format % args)

    def _json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json_response({"status": "ok", "service": "noesis-mesh"})
        elif path == "/packets":
            list_fn = self.registry.get("list_packets")
            packets = list_fn() if list_fn else []
            self._json_response({"packets": packets, "count": len(packets)})
        elif path.startswith("/packets/"):
            mem_id = path.split("/")[-1]
            get_fn = self.registry.get("get_packet")
            if get_fn:
                pkt = get_fn(mem_id)
                if pkt:
                    self._json_response(pkt)
                    return
            self._json_response({"error": "not found"}, 404)
        else:
            self._json_response({"error": "unknown path"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/packets":
            data = self._read_body()
            push_fn = self.registry.get("push_packet")
            if push_fn:
                result = push_fn(data)
                self._json_response(result, 201)
            else:
                self._json_response({"error": "no handler"}, 500)
        elif path == "/sync":
            data = self._read_body()
            sync_fn = self.registry.get("sync_all")
            if sync_fn:
                result = sync_fn(data.get("agent_id", "unknown"))
                self._json_response(result)
            else:
                self._json_response({"error": "no handler"}, 500)
        else:
            self._json_response({"error": "unknown path"}, 404)


class MeshServer:
    """LAN-accessible memory mesh node."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def register_handlers(
        self,
        list_packets: Callable,
        get_packet: Callable,
        push_packet: Callable,
        sync_all: Callable | None = None,
    ) -> None:
        MeshRequestHandler.registry = {
            "list_packets": list_packets,
            "get_packet": get_packet,
            "push_packet": push_packet,
            "sync_all": sync_all,
        }

    def start(self, background: bool = True) -> None:
        self._server = HTTPServer((self.host, self.port), MeshRequestHandler)
        if background:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            logger.info("Noesis mesh server on http://%s:%d", self.host, self.port)
        else:
            self._server.serve_forever()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
