"""AION tests."""

from __future__ import annotations

import pytest

from aion.coordinator import AionCoordinator
from aion.codegen.llm_coder import LLMCoder


@pytest.fixture
def coord(tmp_path, monkeypatch):
    import yaml

    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(f"""
noesis:
  db_path: "{(tmp_path / 'mem.db').as_posix()}"
  agent_id: test-forge
workspace:
  root: "{(tmp_path / 'ws').as_posix()}"
coordinator:
  recall_limit: 0
llm:
  enabled: true
  provider: groq
  model: llama-3.1-8b-instant
agents:
  coding: {{enabled: true}}
  debug: {{enabled: true}}
  testing: {{enabled: true}}
  memory: {{enabled: true}}
""")

    def _mock_llm(self, plan, task, memory_context=""):
        return (
            {
                "main.py": '"""LLM generated"""\nprint("ok")\n',
                "tests/test_main.py": "def test_ok():\n    assert True\n",
                "README.md": "# mock project\n",
            },
            "Mock LLM project for tests",
        )

    monkeypatch.setattr(LLMCoder, "create_project", _mock_llm, raising=False)
    return AionCoordinator(config_path=cfg)


def test_full_pipeline_llm_only(coord):
    task = coord.run_task("Build a simple calculator in Python", project_name="test_calc")
    assert task.status.value == "success"
    coding = next(r for r in task.results if r.role.value == "coding")
    assert coding.metadata.get("creation_source") == "llm"
    proj = coord.workspace.project_path("test_calc")
    assert proj.is_dir()
    py_files = list(proj.rglob("*.py"))
    assert py_files, f"expected .py files under {proj}"


def test_fresh_memory_no_recall(coord):
    coord.run_task("Build FastAPI JWT auth API", project_name="p1")
    ctx = coord.memory.recall_for_task("FastAPI authentication JWT")
    assert len(ctx.summaries) == 0


def test_reset_memory(coord):
    coord.run_task("test task", project_name="x")
    assert coord.memory_stats()["total_memories"] >= 1
    coord.memory.reset_all()
    assert coord.memory_stats()["total_memories"] == 0


def test_infer_project_name_create_uses_task_not_open_folder(tmp_path):
    from aion.utils.names import infer_project_name
    from aion.tools.workspace import WorkspaceManager

    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    (ws_root / "MAIN").mkdir()
    (ws_root / "MAIN" / "main.py").write_text("x", encoding="utf-8")
    ws = WorkspaceManager(ws_root)

    name = infer_project_name(
        "Build a portfolio website with HTML and CSS",
        prefer_existing=False,
        output_dir=str(ws_root),
        workspace=ws,
    )
    assert name == "portfolio"


def test_llm_coder_coerces_flat_filename_json():
    from aion.codegen.planner import TaskPlan
    from aion.llm import LLMClient

    coder = LLMCoder(LLMClient(enabled=False))
    plan = TaskPlan(app_type="python_app", description="calc")
    raw = '{"main.py": "print(1)", "README.md": "# hi", "summary": "done"}'
    result = coder._parse_and_fix(raw, plan, is_web=False)
    assert result is not None
    files, summary = result
    assert "main.py" in files
    assert summary == "done"
