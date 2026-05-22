"""API and agent integration tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from noesis.api.server import create_app
from noesis.agents.persistent_agent import PersistentAgent


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "api_test.db"))
    return TestClient(app)


class TestAPI:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_remember_and_list(self, client):
        r = client.post("/remember", json={"text": "FastAPI scaling with Redis cache"})
        assert r.status_code == 200
        memories = client.get("/memories").json()
        assert len(memories) >= 1

    def test_recall(self, client):
        client.post("/remember", json={"text": "User deployed Redis for API performance"})
        r = client.post("/recall", json={"query": "Redis API", "limit": 3})
        assert r.status_code == 200
        assert "results" in r.json()

    def test_graph(self, client):
        client.post("/remember", json={"text": "FastAPI connects to Redis"})
        r = client.get("/graph")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data

    def test_chat(self, client):
        r = client.post("/chat", json={"query": "backend scaling"})
        assert r.status_code == 200
        assert "memory_context" in r.json()

    def test_compare(self, client):
        r = client.post("/compare", json={
            "texts": ["User asked about Redis", "User asked about scaling"]
        })
        assert r.status_code == 200
        assert "compression_ratio" in r.json()


class TestPersistentAgent:
    def test_chat_returns_context(self, tmp_path):
        agent = PersistentAgent(db_path=str(tmp_path / "agent.db"))
        r = agent.chat("I am learning FastAPI with Redis")
        assert "memory_context" in r
        assert r["recalled_count"] >= 0

    def test_teach_and_recall(self, tmp_path):
        agent = PersistentAgent(db_path=str(tmp_path / "agent2.db"))
        agent.teach("Production uses Docker Redis Nginx Gunicorn")
        ctx = agent.get_context_for_llm("deployment stack")
        assert len(ctx) > 10
