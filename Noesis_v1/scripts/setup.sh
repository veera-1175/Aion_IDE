#!/usr/bin/env bash
# Noesis Setup Script (Linux/macOS)
set -e
cd "$(dirname "$0")/.."

echo "=== Noesis Setup ==="

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -e ".[api,dev]" -q

mkdir -p data
[ -f .env ] || cp .env.example .env

echo ""
echo "Setup complete!"
echo "  Dashboard: python scripts/run_server.py"
echo "  Demo:      python examples/innovation_demo.py"
