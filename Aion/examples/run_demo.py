"""AION demo — build FastAPI auth API with multi-agent pipeline."""

from __future__ import annotations

import json
import sys


def run(coordinator=None):
    from aion.coordinator import AionCoordinator

    coord = coordinator or AionCoordinator()

    print("=" * 60)
    print("  AION — Multi-Agent Software Engineering Demo")
    print("  Powered by Noesis Persistent Memory")
    print("=" * 60)

    task_desc = "Build authentication API using FastAPI with JWT login"
    print(f"\n[Task] {task_desc}\n")

    task = coord.run_task(task_desc, project_name="fastapi_auth_demo")

    for r in task.results:
        status = "OK" if r.success else "FAIL"
        print(f"  [{status}] {r.role.value.upper()} Agent: {r.summary}")
        if r.artifacts:
            print(f"         Files: {', '.join(r.artifacts[:5])}")

    print(f"\n[Workspace] {task.workspace_path}")
    print(f"[Status] {task.status.value}")

    # Second run — demonstrate memory reuse
    print("\n" + "-" * 60)
    print("[Memory Demo] Running similar task — agents should recall prior work...")
    task2 = coord.run_task(
        "Build another FastAPI authentication service with JWT",
        project_name="fastapi_auth_demo_2",
    )
    ctx = coord.memory.recall_for_task("FastAPI JWT authentication", limit=3)
    print(f"  Recalled {len(ctx.summaries)} memories from Noesis:")
    for s in ctx.summaries[:3]:
        print(f"    - {s[:80]}...")

    print("\n[Noesis Stats]")
    print(json.dumps(coord.memory_stats(), indent=2))
    print("\n" + "=" * 60)
    print("  Demo complete. Run: aion serve  →  http://localhost:8090")
    print("=" * 60)

    return task.status.value == "success"


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
