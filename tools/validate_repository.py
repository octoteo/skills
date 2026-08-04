#!/usr/bin/env python3
"""Validate every root-level skill in the repository."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_validator(root: Path) -> object:
    path = root / "tools" / "validate_skill.py"
    spec = importlib.util.spec_from_file_location("validate_skill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tools/validate_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_skills(root: Path) -> list[Path]:
    excluded = {".git", ".github", ".artifacts", "tests", "tools"}
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and path.name not in excluded and (path / "SKILL.md").is_file()
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    validator = load_validator(root)
    skills = discover_skills(root)
    if not skills:
        print("ERROR: no root-level skills found", file=sys.stderr)
        return 1

    failed = False
    for skill in skills:
        errors = validator.validate(skill)
        if errors:
            failed = True
            for error in errors:
                print(f"ERROR [{skill.name}]: {error}")
        else:
            print(f"PASS [{skill.name}]")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
