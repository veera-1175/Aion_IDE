"""FastAPI REST API for Noesis — agents, dashboards, integrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from noesis.core.engine import NoesisEngine
from noesis.core.models import ReconstructedContext

# FastAPI is optional — graceful import
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    BaseModel = object  # type: ignore


STATIC_DIR = Path(__file__).parent / "static"


class RememberRequest(BaseModel):
    text: str
    input_type: str = "conversation"
    source: str = "user"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecallRequest(BaseModel):
    query: str
    limit: int = 5
    mode: str = "hybrid"


class CompareRequest(BaseModel):
    texts: list[str]


class SyncPushRequest(BaseModel):
    peer_url: str
    memory_id: str | None = None


class ImportRequest(BaseModel):
    path: str
    source_agent: str = "remote"


_engine: NoesisEngine | None = None


def get_engine() -> NoesisEngine:
    global _engine
    if _engine is None:
        _engine = NoesisEngine()
    return _engine


def create_app(db_path: str | None = None) -> "FastAPI":
    if not HAS_FASTAPI:
        raise ImportError("FastAPI required: pip install fastapi uvicorn")

    global _engine
    _engine = NoesisEngine(db_path=db_path) if db_path else NoesisEngine()

    app = FastAPI(
        title="Noesis Memory Engine",
        description="Semantic + Symbolic Distributed AI Memory API",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        index = STATIC_DIR / "index.html"
        if index.exists():
            return HTMLResponse(index.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Noesis API</h1><p>See <a href='/docs'>/docs</a></p>")

    @app.get("/health")
    def health():
        e = get_engine()
        return {"status": "ok", "agent_id": e.agent_id, "memories": e.stats()["total_memories"]}

    @app.get("/stats")
    def stats():
        return get_engine().stats()

    @app.post("/remember")
    def remember(req: RememberRequest):
        result = get_engine().remember(
            req.text, input_type=req.input_type, source=req.source, **req.metadata
        )
        if not result:
            raise HTTPException(400, "Input skipped (low importance)")
        return result

    @app.post("/recall")
    def recall(req: RecallRequest):
        contexts = get_engine().recall(req.query, limit=req.limit, mode=req.mode)
        return {
            "query": req.query,
            "results": [
                {
                    "memory_id": c.memory_id,
                    "summary": c.summary,
                    "concepts": c.concepts,
                    "graph_path": c.graph_path,
                    "confidence": c.confidence,
                    "related": c.related_memories,
                }
                for c in contexts
            ],
        }

    @app.post("/explain")
    def explain(req: RecallRequest):
        return get_engine().explain_recall(req.query)

    @app.post("/compare")
    def compare(req: CompareRequest):
        return get_engine().compare_with_traditional(req.texts)

    @app.get("/memories")
    def list_memories(cluster: str | None = None, limit: int = 50):
        records = get_engine().list_memories(cluster=cluster, limit=limit)
        return [
            {
                "memory_id": m.memory_id,
                "summary": m.abstracted_content,
                "category": m.category.value,
                "importance": m.importance,
                "cluster": m.cluster_id,
                "tags": m.tags,
                "concepts": [c.label for c in m.concepts],
            }
            for m in records
        ]

    @app.get("/memories/{memory_id}")
    def get_memory(memory_id: str):
        m = get_engine().get_memory(memory_id)
        if not m:
            raise HTTPException(404, "Memory not found")
        return {
            "memory_id": m.memory_id,
            "content": m.content,
            "summary": m.abstracted_content,
            "category": m.category.value,
            "importance": m.importance,
            "cluster": m.cluster_id,
            "metadata": m.metadata,
        }

    @app.get("/graph")
    def full_graph():
        e = get_engine()
        nodes = [
            {"id": n, "label": n, "type": e.graph.graph.nodes[n].get("type", "concept")}
            for n in e.graph.graph.nodes
        ]
        edges = [
            {"from": u, "to": v, "relation": d.get("relation", "relates_to")}
            for u, v, d in e.graph.graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    @app.get("/graph/{concept}")
    def subgraph(concept: str):
        return get_engine().get_graph(concept)

    @app.post("/forget")
    def forget_cycle():
        return get_engine().run_forgetting_cycle()

    @app.post("/sync/push")
    def sync_push(req: SyncPushRequest):
        return get_engine().sync_to_peer(req.peer_url, req.memory_id)

    @app.post("/sync/pull")
    def sync_pull(peer_url: str):
        return get_engine().sync_from_peer(peer_url)

    @app.get("/export/{memory_id}")
    def export_memory(memory_id: str):
        path = get_engine().export_memory(memory_id)
        if not path:
            raise HTTPException(404, "Memory not found")
        return FileResponse(path, filename=path.name)

    @app.post("/chat")
    def chat(req: RecallRequest):
        """Chat endpoint: remember then recall related context."""
        e = get_engine()
        stored = e.remember(req.query, source="user")
        contexts = e.recall(req.query, limit=req.limit, mode="hybrid")

        # Include memory just stored if recall missed it (e.g. same-turn name)
        if stored and not any(c.memory_id == stored.get("memory_id") for c in contexts):
            contexts.insert(
                0,
                ReconstructedContext(
                    memory_id=stored["memory_id"],
                    summary=stored["summary"],
                    related_memories=[],
                    concepts=stored.get("concepts", []),
                    graph_path=[],
                    confidence=0.9,
                ),
            )

        memory_context = "\n".join(f"- {c.summary}" for c in contexts) if contexts else "No prior memory."
        return {
            "query": req.query,
            "stored": stored,
            "memory_context": memory_context,
            "recalled": len(contexts),
            "graph_paths": [c.graph_path for c in contexts],
        }

    return app
