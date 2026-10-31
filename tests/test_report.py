"""Report tests: the three formats must agree on the same findings."""

import json

from fixmelist.report import render, render_json, render_markdown, render_text
from fixmelist.scanner import Finding


def sample() -> list[Finding]:
    return [
        Finding(path="a.py", line=3, tag="TODO", text="fix this"),
        Finding(path="a.py", line=9, tag="FIXME", text=""),
        Finding(path="b.js", line=1, tag="HACK", text="works for now"),
    ]


def test_text_groups_by_file() -> None:
    out = render_text(sample())
    assert out.startswith("a.py (2)\n  3: [TODO] fix this\n  9: [FIXME]\n")
    assert "b.js (1)\n  1: [HACK] works for now\n" in out


def test_text_empty() -> None:
    assert render_text([]) == "No markers found.\n"


def test_json_shape() -> None:
    data = json.loads(render_json(sample()))
    assert data["total"] == 3
    assert data["by_tag"] == {"TODO": 1, "FIXME": 1, "HACK": 1}
    assert data["findings"][0] == {
        "file": "a.py",
        "line": 3,
        "tag": "TODO",
        "text": "fix this",
    }


def test_markdown_table() -> None:
    out = render_markdown(sample())
    assert "| `a.py` | 3 | TODO | fix this |" in out
    assert out.startswith("# TODO report — 3 marker(s)")


def test_unknown_format_raises() -> None:
    try:
        render(sample(), "yaml")
    except ValueError as exc:
        assert "unknown format" in str(exc)
    else:  # pragma: no cover - the render must raise
        raise AssertionError("expected ValueError")
