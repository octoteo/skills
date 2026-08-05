#!/usr/bin/env python3
"""Validate every root-level Agent Skill and its evaluation specification."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESERVED = {".git", ".github", ".artifacts", "evals", "tests", "tools"}


def load_validator():
    path = ROOT / "tools" / "validate_skill.py"
    spec = importlib.util.spec_from_file_location("validate_skill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load validate_skill.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_eval(skill_name: str) -> list[str]:
    path = ROOT / "evals" / skill_name / "eval.yaml"
    if not path.is_file():
        return [f"missing evaluation specification: {path.relative_to(ROOT)}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid evaluation specification: {exc}"]
    errors: list[str] = []
    if data.get("name") != skill_name:
        errors.append("eval name must match skill name")
    stimuli = data.get("stimuli")
    if not isinstance(stimuli, list):
        return errors + ["eval stimuli must be a list"]
    if len(stimuli) < 15:
        errors.append("eval must contain at least 15 stimuli")
    names: set[str] = set()
    positive = 0
    negative = 0
    categories: set[str] = set()
    for index, stimulus in enumerate(stimuli, start=1):
        if not isinstance(stimulus, dict):
            errors.append(f"stimulus {index} must be an object")
            continue
        name = stimulus.get("name")
        prompt = stimulus.get("prompt")
        category = stimulus.get("category")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"stimulus {index} has no name")
        elif name in names:
            errors.append(f"duplicate stimulus name: {name}")
        else:
            names.add(name)
        if not isinstance(prompt, str) or len(prompt.strip()) < 20:
            errors.append(f"stimulus {index} prompt is too short")
        if not isinstance(category, str) or not category:
            errors.append(f"stimulus {index} has no category")
        else:
            categories.add(category)
        if stimulus.get("expect_activation", True) is False:
            negative += 1
        else:
            positive += 1
            rubric = stimulus.get("rubric")
            if not isinstance(rubric, list) or len(rubric) < 2:
                errors.append(f"positive stimulus {index} needs at least two rubric items")
    if positive < 10:
        errors.append("eval needs at least 10 positive activation scenarios")
    if negative < 5:
        errors.append("eval needs at least 5 negative activation scenarios")
    required_categories = {"create", "modernize", "implement", "review", "troubleshoot", "negative"}
    missing = required_categories - categories
    if missing:
        errors.append("eval is missing categories: " + ", ".join(sorted(missing)))
    return errors


def main() -> int:
    validator = load_validator()
    skill_dirs = [path for path in sorted(ROOT.iterdir(), key=lambda item: item.name) if path.is_dir() and path.name not in RESERVED and (path / "SKILL.md").is_file()]
    if not skill_dirs:
        print("ERROR: no root-level skills found")
        return 1
    failed = False
    for skill_dir in skill_dirs:
        errors = validator.validate(skill_dir)
        errors.extend(validate_eval(skill_dir.name))
        if errors:
            failed = True
            print(f"FAIL [{skill_dir.name}]")
            for error in sorted(set(errors)):
                print(f"  - {error}")
        else:
            print(f"PASS [{skill_dir.name}]")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
