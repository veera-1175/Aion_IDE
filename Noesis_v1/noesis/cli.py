"""Noesis CLI — full command-line interface."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from noesis import __version__
from noesis.core.engine import NoesisEngine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Noesis Memory Engine — Semantic + Symbolic Distributed AI Memory",
    )
    parser.add_argument("--version", action="version", version=f"Noesis {__version__}")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_remember = sub.add_parser("remember", help="Store compressed semantic memory")
    p_remember.add_argument("text")
    p_remember.add_argument("--type", default="conversation")
    p_remember.add_argument("--source", default="user")

    p_recall = sub.add_parser("recall", help="Recall via graph + semantic search")
    p_recall.add_argument("query")
    p_recall.add_argument("--limit", type=int, default=5)
    p_recall.add_argument("--mode", default="hybrid", choices=["hybrid", "graph", "semantic"])

    sub.add_parser("list", help="List memories")
    sub.add_parser("stats", help="Engine statistics")

    p_export = sub.add_parser("export", help="Export portable memory packet")
    p_export.add_argument("memory_id")

    p_import = sub.add_parser("import", help="Import memory from packet file")
    p_import.add_argument("path")
    p_import.add_argument("--agent", default="remote")

    sub.add_parser("forget-cycle", help="Run adaptive forgetting + redundancy merge")
    sub.add_parser("explain", help="Explain graph-based recall for a query")
    p_explain = sub.add_parser("explain-query", help="Explain recall for query")
    p_explain.add_argument("query")

    p_graph = sub.add_parser("graph", help="Knowledge subgraph")
    p_graph.add_argument("concept")

    p_sync = sub.add_parser("sync-push", help="Push packets to peer agent")
    p_sync.add_argument("peer_url")
    p_sync.add_argument("--memory-id", default=None)

    p_pull = sub.add_parser("sync-pull", help="Pull packets from peer agent")
    p_pull.add_argument("peer_url")

    p_mesh = sub.add_parser("mesh-serve", help="Start LAN mesh server")
    p_mesh.add_argument("--port", type=int, default=8765)

    sub.add_parser("demo", help="Full workflow demo")
    sub.add_parser("innovation", help="Innovation vs traditional AI demo")
    sub.add_parser("multi-agent", help="Multi-agent collective memory demo")
    sub.add_parser("chat", help="Interactive persistent agent")

    p_serve = sub.add_parser("serve", help="Start API + web dashboard")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.add_argument("--reload", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    engine = NoesisEngine(db_path=args.db)

    if args.command == "remember":
        result = engine.remember(args.text, input_type=args.type, source=args.source)
        print(json.dumps(result, indent=2) if result else "Skipped (low importance).")
        sys.exit(0 if result else 1)

    elif args.command == "recall":
        for ctx in engine.recall(args.query, limit=args.limit, mode=args.mode):
            print(json.dumps({
                "memory_id": ctx.memory_id,
                "summary": ctx.summary,
                "graph_path": ctx.graph_path,
                "confidence": ctx.confidence,
            }, indent=2))

    elif args.command == "list":
        for mem in engine.list_memories():
            print(f"[{mem.memory_id}] ({mem.category.value}) imp={mem.importance:.2f}")
            print(f"  {mem.abstracted_content[:100]}")

    elif args.command == "stats":
        print(json.dumps(engine.stats(), indent=2))

    elif args.command == "export":
        path = engine.export_memory(args.memory_id)
        print(f"Exported: {path}" if path else "Not found.")
        sys.exit(0 if path else 1)

    elif args.command == "import":
        print(json.dumps(engine.import_memory(args.path, args.agent), indent=2))

    elif args.command == "forget-cycle":
        print(json.dumps(engine.run_forgetting_cycle(), indent=2))

    elif args.command == "explain-query":
        print(json.dumps(engine.explain_recall(args.query), indent=2))

    elif args.command == "graph":
        print(json.dumps(engine.get_graph(args.concept), indent=2))

    elif args.command == "sync-push":
        print(json.dumps(engine.sync_to_peer(args.peer_url, args.memory_id), indent=2))

    elif args.command == "sync-pull":
        print(json.dumps(engine.sync_from_peer(args.peer_url), indent=2))

    elif args.command == "mesh-serve":
        engine.start_mesh_server(args.port)
        print(f"Mesh server on http://0.0.0.0:{args.port}  (Ctrl+C to stop)")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopped.")

    elif args.command == "demo":
        from examples.demo_workflow import run_demo
        run_demo(engine)

    elif args.command == "innovation":
        from examples.innovation_demo import run
        run()

    elif args.command == "multi-agent":
        from examples.multi_agent_demo import run
        run()

    elif args.command == "chat":
        from examples.chat_agent_demo import main as chat_main
        chat_main()

    elif args.command == "serve":
        try:
            import uvicorn
            from noesis.api.server import create_app
        except ImportError:
            print("Install API: pip install fastapi uvicorn", file=sys.stderr)
            sys.exit(1)
        app = create_app(db_path=args.db)
        print(f"Dashboard: http://localhost:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
