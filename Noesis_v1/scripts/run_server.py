#!/usr/bin/env python3
"""Start Noesis API + Web Dashboard."""

from __future__ import annotations

import argparse


def main():
    parser = argparse.ArgumentParser(description="Noesis API Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("--reload", action="store_true", help="Dev auto-reload")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        raise SystemExit("Install server deps: pip install fastapi uvicorn") from None

    from noesis.api.server import create_app

    app = create_app(db_path=args.db)
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
