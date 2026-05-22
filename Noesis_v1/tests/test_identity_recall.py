"""Tests for personal identity memory and recall."""

from __future__ import annotations

import pytest

from noesis import NoesisEngine


@pytest.fixture
def engine(tmp_path):
    return NoesisEngine(db_path=str(tmp_path / "identity.db"))


def test_name_remember_and_recall(engine):
    engine.remember("my name is veera")
    contexts = engine.recall("what is my name", mode="hybrid")
    assert len(contexts) >= 1
    combined = " ".join(c.summary.lower() for c in contexts)
    assert "veera" in combined


def test_text_search_fallback(engine):
    engine.remember("my name is veera")
    results = engine.store.search_by_text("what is my name")
    assert len(results) >= 1
    assert "veera" in results[0].abstracted_content.lower() or "veera" in results[0].content.lower()
