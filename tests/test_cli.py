"""CLI tests: end-to-end behaviour, safety flags, and exit codes."""

from pathlib import Path

import pytest

from fixmelist.cli import main


def write(tmp: Path, name: str, content: str) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_stdout_report(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    write(tmp_path, "a.py", "# TODO: ship it\n")
    assert main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "a.py (1)" in out
    assert "1: [TODO] ship it" in out


def test_missing_path_exit_1(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope")]) == 1
    assert "no such directory" in capsys.readouterr().err


def test_output_file_and_no_silent_overwrite(tmp_path: Path) -> None:
    write(tmp_path, "a.py", "# TODO: ship it\n")
    report = tmp_path / "report.md"
    assert main([str(tmp_path), "--format", "markdown", "-o", str(report)]) == 0
    assert report.read_text().startswith("# TODO report")
    # Second run without --force must refuse, not clobber.
    assert main([str(tmp_path), "-o", str(report)]) == 1
    assert report.read_text().startswith("# TODO report")
    assert main([str(tmp_path), "-o", str(report), "--force"]) == 0


def test_dry_run_writes_nothing(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    write(tmp_path, "a.py", "# TODO: ship it\n")
    report = tmp_path / "report.txt"
    assert main([str(tmp_path), "-o", str(report), "--dry-run"]) == 0
    assert not report.exists()
    assert "would write 1 finding(s)" in capsys.readouterr().out


def test_bad_flag_exits_2(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([str(tmp_path), "--format", "yaml"])
    assert excinfo.value.code == 2


def test_tag_filter_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "a.py", "# TODO: one\n# FIXME: two\n")
    assert main([str(tmp_path), "--tag", "FIXME"]) == 0
    out = capsys.readouterr().out
    assert "FIXME" in out
    assert "TODO" not in out
