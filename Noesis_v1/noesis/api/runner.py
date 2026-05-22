"""Entry point for noesis-serve command."""

from __future__ import annotations

import argparse


def main():
    parser = argparse.ArgumentParser(description="Noesis API Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", default=None)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        raise SystemExit("Install: pip install fastapi uvicorn") from None

    from noesis.api.server import create_app

    app = create_app(db_path=args.db)
    print(f"Noesis Dashboard: http://localhost:{args.port}")
    print(f"API Docs: http://localhost:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
