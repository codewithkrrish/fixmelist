"""Command-line front end for fixmelist.

Thin by design: argument parsing and output live here, scanning lives in
``scanner`` and rendering in ``report``. ``main`` returns an exit code
instead of calling ``sys.exit`` so tests can drive it directly.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .report import render
from .scanner import DEFAULT_TAGS, ScanError, ScanOptions, scan_tree

EXIT_OK = 0
EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fixmelist",
        description=(
            "List TODO, FIXME, HACK and XXX comments across a codebase, "
            "grouped by file."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        metavar="TAG",
        help="only report this tag (repeatable; default: TODO FIXME HACK XXX)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="report format (default: text)",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="write the report to FILE instead of stdout",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite --output if it already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="scan and say what would be written, without writing anything",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="also scan hidden files and directories",
    )
    parser.add_argument(
        "--include-vendor",
        action="store_true",
        help="also scan vendor, node_modules and Pods directories",
    )
    return parser


def _write_atomic(destination: Path, content: str) -> None:
    """Write ``content`` to ``destination`` without risking a torn file."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(destination.parent),
        delete=False,
        prefix=destination.name + ".",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(destination)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = ScanOptions(
        tags=tuple(args.tags) if args.tags else DEFAULT_TAGS,
        include_hidden=args.include_hidden,
        include_vendor=args.include_vendor,
    )
    try:
        findings = scan_tree(Path(args.path), options)
    except ScanError as exc:
        print(f"fixmelist: {exc}", file=sys.stderr)
        return EXIT_ERROR

    content = render(findings, args.format)

    if args.dry_run:
        target = args.output or "stdout"
        print(
            f"fixmelist: would write {len(findings)} finding(s) "
            f"({args.format} format) to {target}"
        )
        return EXIT_OK

    if args.output:
        destination = Path(args.output)
        if destination.exists() and not args.force:
            print(
                f"fixmelist: {destination} already exists "
                "(use --force to overwrite)",
                file=sys.stderr,
            )
            return EXIT_ERROR
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(destination, content)
        except OSError as exc:
            print(f"fixmelist: cannot write {destination}: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(f"fixmelist: wrote {len(findings)} finding(s) to {destination}")
        return EXIT_OK

    print(content, end="")
    return EXIT_OK


def entry() -> None:
    """Console-script entry point."""
    raise SystemExit(main())
