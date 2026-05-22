"""AION CLI."""

from __future__ import annotations

import argparse
import json
import sys

from aion.coordinator import AionCoordinator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AION — Multi-Agent Software Engineering with Noesis Memory",
    )
    parser.add_argument("--version", action="version", version="AION 1.0.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run multi-agent pipeline on a task")
    p_run.add_argument("task", help='e.g. "Build authentication API using FastAPI"')
    p_run.add_argument("--project", default=None, help="Project folder name")
    p_run.add_argument(
        "--output",
        default=None,
        help="Parent directory to create the project in (e.g. D:\\Projects)",
    )
    p_run.add_argument("--mode", choices=["create", "edit"], default="create")

    sub.add_parser("stats", help="Noesis + task statistics")
    sub.add_parser("reset-memory", help="Wipe Noesis database (brand new memory)")
    sub.add_parser("demo", help="Run FastAPI auth demo")
    p_serve = sub.add_parser("serve", help="Start web UI")
    p_serve.add_argument("--port", type=int, default=8090)

    args = parser.parse_args()
    coord = AionCoordinator()

    if args.command == "run":
        task = coord.run_task(args.task, project_name=args.project, output_dir=args.output, mode=args.mode)
        print(json.dumps(task.to_dict(), indent=2))
        sys.exit(0 if task.status.value == "success" else 1)

    elif args.command == "stats":
        print(json.dumps(coord.memory_stats(), indent=2))

    elif args.command == "reset-memory":
        result = coord.memory.reset_all()
        print(json.dumps(result, indent=2))
        print("Noesis memory cleared. Stats:", json.dumps(coord.memory_stats(), indent=2))

    elif args.command == "demo":
        from examples.run_demo import run
        run(coord)

    elif args.command == "serve":
        try:
            import uvicorn
            from aion.api.server import create_app
        except ImportError:
            print("Install: pip install fastapi uvicorn", file=sys.stderr)
            sys.exit(1)
        app = create_app(coord)
        print(f"AION UI: http://127.0.0.1:{args.port}")
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
