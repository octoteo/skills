#!/usr/bin/env python3
"""Inspect a repository for .NET and WPF project characteristics.

The script uses only the Python standard library. It performs static inspection,
never edits the target repository, and intentionally does not attempt to evaluate
arbitrary MSBuild conditions or imports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from wpf_repository_checks import inspect_repository, render_markdown  # noqa: E402


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a repository for .NET 10 WPF readiness.")
    parser.add_argument("path", type=Path, help="Repository or project directory to inspect.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, help="Optional output file. Defaults to stdout.")
    parser.add_argument("--strict", action="store_true", help="Return exit code 2 when errors are found.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.path.exists() or not args.path.is_dir():
        print(f"error: directory not found: {args.path}", file=sys.stderr)
        return 1

    report = inspect_repository(args.path)
    output = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    if args.strict and report["summary"]["errors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
