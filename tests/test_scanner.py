"""Scanner tests: markers, comment styles, ignored dirs, odd inputs."""

from pathlib import Path

import pytest

from fixmelist.scanner import (
    DEFAULT_TAGS,
    ScanError,
    ScanOptions,
    scan_file,
    scan_tree,
)


def write(tmp: Path, name: str, content: str) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_python_and_js_markers(tmp_path: Path) -> None:
    write(tmp_path, "a.py", "# TODO: fix the retry logic\nx = 1  # FIXME later\n")
    write(tmp_path, "b.js", "// HACK: this only works on Tuesdays\nconst x = 1;\n")
    findings = scan_tree(tmp_path)
    assert [(f.path, f.line, f.tag) for f in findings] == [
        ("a.py", 1, "TODO"),
        ("a.py", 2, "FIXME"),
        ("b.js", 1, "HACK"),
    ]
    assert findings[0].text == "fix the retry logic"


def test_tag_without_text_and_tag_in_code_ignored(tmp_path: Path) -> None:
    # A bare TODO with nothing after it still counts; a TODO in code
    # (not inside a comment) does not.
    write(tmp_path, "a.py", "# TODO\nTODO = 5\n")
    findings = scan_tree(tmp_path)
    assert len(findings) == 1
    assert findings[0].tag == "TODO"
    assert findings[0].text == ""


def test_block_comments(tmp_path: Path) -> None:
    write(tmp_path, "a.c", "/* FIXME: leak on error path\n   still broken */\nint main() {}\n")
    write(tmp_path, "b.html", "<!-- XXX: remove before launch -->\n")
    findings = scan_tree(tmp_path)
    assert [(f.path, f.tag) for f in findings] == [
        ("a.c", "FIXME"),
        ("b.html", "XXX"),
    ]


def test_hidden_and_vendor_dirs_ignored_by_default(tmp_path: Path) -> None:
    write(tmp_path, ".hidden/secret.py", "# TODO: hidden\n")
    write(tmp_path, "vendor/dep.py", "# TODO: not mine\n")
    write(tmp_path, "node_modules/dep.js", "// TODO: not mine either\n")
    write(tmp_path, "mine.py", "# TODO: mine\n")
    assert [f.path for f in scan_tree(tmp_path)] == ["mine.py"]
    assert [f.path for f in scan_tree(tmp_path, ScanOptions(include_hidden=True))] == [
        ".hidden/secret.py",
        "mine.py",
    ]
    vendor = scan_tree(tmp_path, ScanOptions(include_vendor=True))
    assert {f.path for f in vendor} == {
        "mine.py",
        "node_modules/dep.js",
        "vendor/dep.py",
    }


def test_binary_files_skipped(tmp_path: Path) -> None:
    blob = tmp_path / "logo.png"
    blob.write_bytes(b"\x89PNG\r\n\x00\x1a\n# TODO: not a comment\n")
    assert scan_tree(tmp_path) == []


def test_empty_directory(tmp_path: Path) -> None:
    assert scan_tree(tmp_path) == []


def test_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ScanError):
        scan_tree(tmp_path / "nope")


def test_file_as_root_raises(tmp_path: Path) -> None:
    target = write(tmp_path, "a.py", "# TODO: x\n")
    with pytest.raises(ScanError):
        scan_tree(target)


def test_tag_filter(tmp_path: Path) -> None:
    write(tmp_path, "a.py", "# TODO: one\n# FIXME: two\n")
    findings = scan_tree(tmp_path, ScanOptions(tags=("FIXME",)))
    assert [f.tag for f in findings] == ["FIXME"]


def test_scan_file_uses_relative_paths(tmp_path: Path) -> None:
    target = write(tmp_path, "deep/nested/a.py", "# TODO: x\n")
    findings = scan_file(target, tmp_path, DEFAULT_TAGS)
    assert findings[0].path == "deep/nested/a.py"
    assert findings[0].line == 1
