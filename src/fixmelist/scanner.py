"""Find TODO-style markers hiding in a codebase's comments.

The scanner walks a directory tree, reads each text file, and records every
line where a marker (TODO, FIXME, HACK, XXX by default) shows up inside a
comment. It deliberately ignores hidden directories and common vendored
folders, because nobody wants a report full of somebody else's TODOs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TAGS: tuple[str, ...] = ("TODO", "FIXME", "HACK", "XXX")

#: Directories skipped unless the caller opts back in.
DEFAULT_IGNORED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".tox",
        ".eggs",
        "node_modules",
        "vendor",
        "venv",
        ".venv",
        "dist",
        "build",
        "target",
        "Pods",
    }
)

#: How many bytes to peek at when deciding whether a file is binary.
_BINARY_PROBE_BYTES = 8192

#: Line-comment markers per file extension.
_LINE_MARKERS: dict[str, tuple[str, ...]] = {
    ".py": ("#",),
    ".pyi": ("#",),
    ".sh": ("#",),
    ".bash": ("#",),
    ".zsh": ("#",),
    ".rb": ("#",),
    ".yaml": ("#",),
    ".yml": ("#",),
    ".toml": ("#",),
    ".ini": ("#", ";"),
    ".cfg": ("#", ";"),
    ".js": ("//",),
    ".jsx": ("//",),
    ".ts": ("//",),
    ".tsx": ("//",),
    ".c": ("//",),
    ".h": ("//",),
    ".cpp": ("//",),
    ".hpp": ("//",),
    ".java": ("//",),
    ".go": ("//",),
    ".rs": ("//",),
    ".swift": ("//",),
    ".kt": ("//",),
    ".kts": ("//",),
    ".php": ("//", "#"),
    ".dart": ("//",),
    ".scala": ("//",),
    ".sql": ("--",),
    ".lua": ("--",),
    ".hs": ("--",),
}

#: Block-comment delimiters per file extension.
_BLOCK_MARKERS: dict[str, tuple[str, str]] = {
    ".js": ("/*", "*/"),
    ".jsx": ("/*", "*/"),
    ".ts": ("/*", "*/"),
    ".tsx": ("/*", "*/"),
    ".c": ("/*", "*/"),
    ".h": ("/*", "*/"),
    ".cpp": ("/*", "*/"),
    ".hpp": ("/*", "*/"),
    ".java": ("/*", "*/"),
    ".go": ("/*", "*/"),
    ".rs": ("/*", "*/"),
    ".swift": ("/*", "*/"),
    ".kt": ("/*", "*/"),
    ".kts": ("/*", "*/"),
    ".php": ("/*", "*/"),
    ".css": ("/*", "*/"),
    ".scss": ("/*", "*/"),
    ".html": ("<!--", "-->"),
    ".xml": ("<!--", "-->"),
    ".md": ("<!--", "-->"),
}

#: Fallback markers for file types we don't know about.
_GENERIC_LINE_MARKERS: tuple[str, ...] = ("#", "//", "--")
_GENERIC_BLOCK_MARKERS: tuple[str, str] = ("/*", "*/")


class ScanError(Exception):
    """Raised when a scan cannot start (bad path, unreadable root)."""


@dataclass(frozen=True)
class Finding:
    """One marker found in one file."""

    path: str  # path relative to the scanned root
    line: int  # 1-based line number
    tag: str
    text: str  # whatever followed the tag, stripped


@dataclass
class ScanOptions:
    """Toggles for a scan. Defaults mirror what most people want."""

    tags: tuple[str, ...] = DEFAULT_TAGS
    include_hidden: bool = False
    include_vendor: bool = False
    extra_ignored_dirs: frozenset[str] = field(default_factory=frozenset)


def _markers_for(path: Path) -> tuple[tuple[str, ...], tuple[str, str] | None]:
    """Return (line markers, block markers) for a file's extension."""
    ext = path.suffix.lower()
    line = _LINE_MARKERS.get(ext, _GENERIC_LINE_MARKERS)
    block = _BLOCK_MARKERS.get(ext, _GENERIC_BLOCK_MARKERS)
    # Extensions with no line-comment syntax at all (css, html, ...) get
    # block comments only; the generic fallback would invent markers.
    if ext in {".css", ".scss", ".html", ".xml", ".md"}:
        line = ()
    return line, block


def _comment_text(
    line: str,
    line_markers: tuple[str, ...],
    block: tuple[str, str] | None,
    in_block: bool,
) -> tuple[str | None, bool]:
    """Extract the comment portion of one line.

    Returns (comment_text, still_in_block). ``comment_text`` is None when
    the line contains no comment at all. This is a simple scanner, not a
    parser: a marker inside a string literal will look like a comment.
    That's an accepted trade-off, documented in the README.
    """
    if in_block:
        assert block is not None
        end = line.find(block[1])
        if end == -1:
            return line, True
        return line[: end + len(block[1])], False

    candidates: list[tuple[int, str, str]] = []
    for marker in line_markers:
        idx = line.find(marker)
        if idx != -1:
            candidates.append((idx, marker, "line"))
    if block is not None:
        idx = line.find(block[0])
        if idx != -1:
            candidates.append((idx, block[0], "block"))
    if not candidates:
        return None, False

    idx, marker, kind = min(candidates, key=lambda c: c[0])
    if kind == "line":
        return line[idx:], False
    rest = line[idx + len(marker) :]
    assert block is not None
    end = rest.find(block[1])
    if end == -1:
        return rest, True
    return rest[:end], False


def _is_binary(path: Path) -> bool:
    """True when the file looks binary (a NUL byte near the start)."""
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(_BINARY_PROBE_BYTES)
    except OSError:
        return True  # unreadable files are skipped, not crashed on


def _tag_pattern(tags: tuple[str, ...]) -> re.Pattern[str]:
    alternation = "|".join(re.escape(tag) for tag in tags)
    # A tag may be followed by ":" or "-" and then free text.
    return re.compile(r"\b(" + alternation + r")\b\s*[:\-]?\s*(.*)")


def scan_file(path: Path, root: Path, tags: tuple[str, ...]) -> list[Finding]:
    """Scan one file and return its findings (empty when none)."""
    if _is_binary(path):
        return []
    pattern = _tag_pattern(tags)
    line_markers, block = _markers_for(path)
    findings: list[Finding] = []
    in_block = False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    relative = str(path.relative_to(root))
    for lineno, line in enumerate(text.splitlines(), start=1):
        comment, in_block = _comment_text(line, line_markers, block, in_block)
        if comment is None:
            continue
        match = pattern.search(comment)
        if match:
            findings.append(
                Finding(
                    path=relative,
                    line=lineno,
                    tag=match.group(1),
                    text=match.group(2).strip(),
                )
            )
    return findings


def scan_tree(root: Path, options: ScanOptions | None = None) -> list[Finding]:
    """Walk ``root`` and return every finding, sorted by path then line.

    Raises ScanError when ``root`` does not exist or is not a directory.
    Files that can't be read are skipped silently; a scan of a whole tree
    shouldn't die because of one locked file.
    """
    opts = options or ScanOptions()
    if not root.exists():
        raise ScanError(f"no such directory: {root}")
    if not root.is_dir():
        raise ScanError(f"not a directory: {root}")

    ignored = set(DEFAULT_IGNORED_DIRS) | set(opts.extra_ignored_dirs)
    if opts.include_vendor:
        ignored.discard("vendor")
        ignored.discard("node_modules")
        ignored.discard("Pods")

    findings: list[Finding] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in place so os.walk doesn't descend into ignored dirs.
        kept: list[str] = []
        for dirname in dirnames:
            if dirname in ignored:
                continue
            if not opts.include_hidden and dirname.startswith("."):
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for filename in filenames:
            if not opts.include_hidden and filename.startswith("."):
                continue
            findings.extend(
                scan_file(Path(dirpath) / filename, root, opts.tags)
            )
    findings.sort(key=lambda f: (f.path, f.line))
    return findings
