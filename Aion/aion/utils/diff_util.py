"""Line diff stats for Composer UI."""

from __future__ import annotations

import difflib


def line_diff(before: str, after: str) -> dict[str, int | list[str]]:
    """Return addition/deletion counts and unified diff lines for display."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    additions = 0
    deletions = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before_lines, after_lines).get_opcodes():
        if tag == "insert":
            additions += j2 - j1
        elif tag == "delete":
            deletions += i2 - i1
        elif tag == "replace":
            deletions += i2 - i1
            additions += j2 - j1

    display = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            lineterm="",
            n=2,
        )
    )[:200]

    return {
        "additions": additions,
        "deletions": deletions,
        "lines": display,
    }


def trim_text(text: str, max_chars: int = 16000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n/* … truncated … */"
