"""Render scan findings as text, JSON, or Markdown.

Each renderer takes the same sorted list of findings, so the three formats
never disagree about what was found.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Iterable

from .scanner import Finding

_FORMATS: tuple[str, ...] = ("text", "json", "markdown")


def group_by_file(findings: Iterable[Finding]) -> OrderedDict[str, list[Finding]]:
    """Group findings by file, preserving the scan's sorted order."""
    grouped: OrderedDict[str, list[Finding]] = OrderedDict()
    for finding in findings:
        grouped.setdefault(finding.path, []).append(finding)
    return grouped


def render_text(findings: list[Finding]) -> str:
    """Human-readable report, grouped by file."""
    if not findings:
        return "No markers found.\n"
    lines: list[str] = []
    for path, items in group_by_file(findings).items():
        lines.append(f"{path} ({len(items)})")
        for item in items:
            detail = f"  {item.line}: [{item.tag}]"
            if item.text:
                detail += f" {item.text}"
            lines.append(detail)
    return "\n".join(lines) + "\n"


def render_json(findings: list[Finding]) -> str:
    """Machine-readable report: one object per finding, plus a summary."""
    payload = {
        "total": len(findings),
        "by_tag": _count_by_tag(findings),
        "findings": [
            {
                "file": f.path,
                "line": f.line,
                "tag": f.tag,
                "text": f.text,
            }
            for f in findings
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_markdown(findings: list[Finding]) -> str:
    """Markdown report, handy for pasting into an issue or a PR."""
    if not findings:
        return "No markers found.\n"
    lines = [
        f"# TODO report — {len(findings)} marker(s)",
        "",
        "| File | Line | Tag | Note |",
        "| ---- | ---: | --- | ---- |",
    ]
    for item in findings:
        note = item.text.replace("|", "\\|")
        lines.append(f"| `{item.path}` | {item.line} | {item.tag} | {note} |")
    return "\n".join(lines) + "\n"


def render(findings: list[Finding], fmt: str) -> str:
    """Render in ``fmt``; raises ValueError for unknown formats."""
    if fmt == "text":
        return render_text(findings)
    if fmt == "json":
        return render_json(findings)
    if fmt == "markdown":
        return render_markdown(findings)
    raise ValueError(f"unknown format: {fmt!r} (choose from: {', '.join(_FORMATS)})")


def _count_by_tag(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.tag] = counts.get(finding.tag, 0) + 1
    return counts
