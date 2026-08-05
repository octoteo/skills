#!/usr/bin/env python3
"""Run all repository test_*.py files, including directories with hyphens."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def remove_caches() -> None:
    for path in ROOT.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    for path in ROOT.rglob("*.py[co]"):
        try:
            path.unlink()
        except OSError:
            pass


def load_test_module(path: Path, index: int):
    name = f"repo_test_{index}_{path.stem.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    remove_caches()
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    paths = sorted((ROOT / "tests").rglob("test_*.py"), key=lambda item: item.as_posix())
    if not paths:
        print("ERROR: no tests found", file=sys.stderr)
        return 1
    for index, path in enumerate(paths):
        suite.addTests(loader.loadTestsFromModule(load_test_module(path, index)))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    remove_caches()
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
