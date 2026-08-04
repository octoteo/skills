#!/usr/bin/env python3
"""Discover and run test_*.py files recursively under tests/."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module(path: Path, index: int) -> object:
    module_name = f"skill_test_{index}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "tests").rglob("test_*.py"))
    if not files:
        print("ERROR: no tests found", file=sys.stderr)
        return 1

    suite = unittest.TestSuite()
    for index, path in enumerate(files):
        module = load_module(path, index)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
