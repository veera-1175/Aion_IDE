"""
Noesis Innovation Demo
Demonstrates all 5 innovations vs traditional AI memory approach.
"""

from __future__ import annotations

import json

from noesis import NoesisEngine


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def run() -> None:
    engine = NoesisEngine(db_path="data/innovation_demo.db")

    _safe_print("=" * 70)
    _safe_print("  NOESIS vs TRADITIONAL AI MEMORY")
    _safe_print("=" * 70)

    raw_inputs = [
        "User asked about Redis caching",
        "User asked about async workers",
        "User asked about FastAPI scaling",
        "User struggled with worker bottlenecks",
        "User deployed Redis for production APIs",
    ]

    # Innovation 1: Semantic Compression
    _safe_print("\n[1] SEMANTIC COMPRESSION")
    _safe_print("Traditional AI stores each conversation as raw text chunks.")
    comparison = engine.compare_with_traditional(raw_inputs)
    _safe_print(json.dumps(comparison, indent=2))

    # Innovation 2: Symbolic Portable Memory
    _safe_print("\n[2] SYMBOLIC PORTABLE MEMORY")
    memories = engine.list_memories(limit=1)
    if memories:
        pkt = engine.get_packet(memories[0].memory_id)
        if pkt:
            _safe_print(f"  Memory packet: {memories[0].memory_id}")
            _safe_print(f"  Semantic summary: {pkt.semantic_summary[:80]}...")
            _safe_print(f"  Bytecode size: {len(pkt.bytecode)} bytes (portable cognition)")
            _safe_print(f"  Token IDs: {len(pkt.token_ids)} symbolic tokens")
            export_path = engine.export_memory(memories[0].memory_id)
            _safe_print(f"  Exported for transfer: {export_path}")

    # Innovation 4: Knowledge Graph Recall
    _safe_print("\n[4] KNOWLEDGE GRAPH RECALL")
    explanation = engine.explain_recall("FastAPI Redis scaling")
    _safe_print(json.dumps(explanation, indent=2))
    contexts = engine.recall("backend scalability", mode="graph")
    for ctx in contexts[:2]:
        _safe_print(f"  Graph path: {' -> '.join(ctx.graph_path[:6])}")
        _safe_print(f"  Reconstructed: {ctx.summary[:80]}...")

    # Innovation 5: Adaptive Forgetting
    _safe_print("\n[5] ADAPTIVE FORGETTING")
    engine.remember("ok")
    engine.remember("thanks")
    result = engine.run_forgetting_cycle()
    _safe_print(f"  Forgotten low-value: {result['forgotten']}")
    _safe_print(f"  Redundancy merged: {result['redundancy_merged']}")

    _safe_print("\n[ENGINE STATS]")
    _safe_print(json.dumps(engine.stats(), indent=2))

    _safe_print("\n" + "=" * 70)
    _safe_print("  Innovation: HOW memory is represented, compressed, evolved, shared.")
    _safe_print("=" * 70)


if __name__ == "__main__":
    run()
