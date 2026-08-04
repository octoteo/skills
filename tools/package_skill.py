#!/usr/bin/env python3
"""Package one validated skill folder as skill.zip."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import zipfile
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024


def load_validator() -> object:
    path = Path(__file__).with_name("validate_skill.py")
    spec = importlib.util.spec_from_file_location("validate_skill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package(skill: Path, output: Path) -> Path:
    validator = load_validator()
    errors = validator.validate(skill)
    if errors:
        raise ValueError("; ".join(errors))

    output.mkdir(parents=True, exist_ok=True)
    target = output / "skill.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(skill.rglob("*")):
            if not item.is_file() or "__pycache__" in item.parts or item.suffix in {".pyc", ".pyo"}:
                continue
            archive.write(item, item.relative_to(skill.parent))

    if target.stat().st_size > MAX_BYTES:
        target.unlink(missing_ok=True)
        raise ValueError("skill.zip exceeds 25 MiB")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        target = package(args.skill.resolve(), args.output.resolve())
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
