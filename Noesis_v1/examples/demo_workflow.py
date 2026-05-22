"""
Noesis Full Workflow Demo
Demonstrates the complete 10-step memory pipeline from the architecture spec.
"""

from __future__ import annotations

import json
import textwrap

from noesis.core.engine import NoesisEngine


def _safe_print(text: str) -> None:
    """Print safely on Windows consoles that lack Unicode support."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def run_demo(engine: NoesisEngine | None = None) -> None:
    engine = engine or NoesisEngine(db_path="data/demo_noesis.db")

    print("=" * 60)
    print("  Noesis Memory Engine — Full Workflow Demo")
    print("=" * 60)

    # STEP 1 — Input Collection (FastAPI scaling scenario from spec)
    inputs = [
        {"content": "User asked about FastAPI scaling for production APIs.", "type": "conversation"},
        {"content": "User deployed Redis cache to improve API response times.", "type": "event"},
        {"content": "User struggled with async worker bottlenecks under load.", "type": "observation"},
        {"content": "Deployment sequence: Docker → Redis → Nginx → Gunicorn", "type": "log"},
        {"content": "User asked about FastAPI async patterns again.", "type": "conversation"},
        {"content": "ok", "type": "conversation"},  # low-value — should be skipped
        {"content": "User deployed Redis cluster on May 20 for production.", "type": "event"},
        {"content": "How do I scale FastAPI with Redis and async workers?", "type": "conversation"},
    ]

    _safe_print("\n[STEP 1] Input Collection")
    _safe_print(f"  Ingesting {len(inputs)} inputs...")

    _safe_print("\n[STEPS 2-5] Semantic Cognition Pipeline")
    results = engine.remember_batch(inputs)
    for r in results:
        _safe_print(f"  [+] {r['memory_id']} | {r['category']} | imp={r['importance']:.2f}")
        _safe_print(f"    {r['summary'][:70]}...")
        if r.get("merged"):
            _safe_print("    (merged with existing cluster)")

    _safe_print("\n[STEP 6] Knowledge Graph")
    subgraph = engine.get_graph("Fastapi")
    _safe_print(f"  Nodes: {subgraph.get('nodes', [])}")
    _safe_print(f"  Edges: {len(subgraph.get('edges', []))}")

    _safe_print("\n[STEP 7-8] Symbolic Compression -> Memory Packets")
    memories = engine.list_memories()
    if memories:
        mem = memories[0]
        packet_info = engine.store.get_packet(mem.memory_id)
        if packet_info:
            _safe_print(f"  Packet {mem.memory_id}:")
            _safe_print(f"    Summary: {packet_info.semantic_summary[:60]}...")
            _safe_print(f"    Bytecode size: {len(packet_info.bytecode)} bytes")
            decompressed = engine.symbolic.decompress(packet_info)
            _safe_print(f"    Reconstructed: {decompressed.get('reconstructed_text', '')[:60]}...")

    _safe_print("\n[STEP 9] Distributed Sync (local export)")
    if memories:
        export_path = engine.export_memory(memories[0].memory_id)
        _safe_print(f"  Exported to: {export_path}")

    _safe_print("\n[STEP 10] Context Reconstruction")
    contexts = engine.recall("backend scaling FastAPI Redis")
    for ctx in contexts:
        _safe_print(f"  Recall confidence: {ctx.confidence}")
        _safe_print(f"  Summary: {ctx.summary}")
        _safe_print(f"  Graph path: {' -> '.join(ctx.graph_path[:6])}")

    _safe_print("\n[Adaptive Forgetting]")
    forget_result = engine.run_forgetting_cycle()
    _safe_print(f"  Pruned: {len(forget_result['forgotten'])} low-retention memories")
    _safe_print(f"  Redundancy merged: {len(forget_result['redundancy_merged'])}")

    _safe_print("\n[Engine Stats]")
    _safe_print(json.dumps(engine.stats(), indent=2))

    _safe_print("\n" + "=" * 60)
    _safe_print("  Demo complete. Noesis pipeline operational.")
    _safe_print("=" * 60)


if __name__ == "__main__":
    run_demo()
