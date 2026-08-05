#!/usr/bin/env python3
"""Validate every root-level Agent Skill and its evaluation specification."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESERVED = {".git", ".github", ".artifacts", "eval-results", "eval-runs", "evals", "tests", "tools"}
REQUIRED_CATEGORIES = {"create", "modernize", "implement", "review", "troubleshoot", "negative"}
REQUIRED_THRESHOLD_KEYS = {
    "positive_recall_min",
    "negative_specificity_min",
    "routing_accuracy_min",
    "skilled_mean_min",
    "mean_delta_min",
    "win_rate_non_ties_min",
    "sign_test_p_max",
    "bootstrap_delta_ci_low_min",
    "skilled_critical_failures_max",
}
MIN_STIMULI = 20
MIN_POSITIVE = 12
MIN_NEGATIVE = 5


def load_validator():
    path = ROOT / "tools" / "validate_skill.py"
    spec = importlib.util.spec_from_file_location("validate_skill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load validate_skill.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_thresholds(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["eval release_thresholds must be an object"]
    errors: list[str] = []
    missing = REQUIRED_THRESHOLD_KEYS - set(value)
    extra = set(value) - REQUIRED_THRESHOLD_KEYS
    if missing:
        errors.append("eval release_thresholds are missing: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("eval release_thresholds contain unsupported keys: " + ", ".join(sorted(extra)))
    for key in sorted(REQUIRED_THRESHOLD_KEYS - {"skilled_critical_failures_max"}):
        if key not in value:
            continue
        number = value[key]
        if not is_number(number):
            errors.append(f"eval threshold {key} must be numeric")
            continue
        if key == "mean_delta_min" or key == "bootstrap_delta_ci_low_min":
            if not -1.0 <= float(number) <= 1.0:
                errors.append(f"eval threshold {key} must be between -1 and 1")
        elif not 0.0 <= float(number) <= 1.0:
            errors.append(f"eval threshold {key} must be between 0 and 1")
    critical = value.get("skilled_critical_failures_max")
    if critical is not None and (
        not isinstance(critical, int) or isinstance(critical, bool) or critical < 0
    ):
        errors.append("eval threshold skilled_critical_failures_max must be a non-negative integer")
    return errors


def validate_score_scale(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["eval score_scale must be an object"]
    errors: list[str] = []
    if value.get("minimum") != 0 or value.get("maximum") != 2:
        errors.append("eval score_scale must use the repository 0 to 2 scale")
    labels = value.get("labels")
    if not isinstance(labels, dict) or set(labels) != {"0", "1", "2"}:
        errors.append("eval score_scale labels must define 0, 1, and 2")
    elif not all(isinstance(item, str) and item.strip() for item in labels.values()):
        errors.append("eval score_scale labels must be non-empty strings")
    return errors


def validate_eval(skill_name: str) -> list[str]:
    path = ROOT / "evals" / skill_name / "eval.yaml"
    if not path.is_file():
        return [f"missing evaluation specification: {path.relative_to(ROOT)}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid evaluation specification: {exc}"]

    errors: list[str] = []
    if not isinstance(data, dict):
        return ["evaluation specification must be a JSON object"]
    if data.get("schema_version") != 1:
        errors.append("eval schema_version must be 1")
    if data.get("name") != skill_name:
        errors.append("eval name must match skill name")
    if data.get("type") != "paired-capability":
        errors.append("eval type must be paired-capability")
    description = data.get("description")
    if not isinstance(description, str) or len(description.strip()) < 20:
        errors.append("eval description is missing or too short")
    errors.extend(validate_score_scale(data.get("score_scale")))
    errors.extend(validate_thresholds(data.get("release_thresholds")))

    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        errors.append("eval defaults must be an object")
    else:
        runs = defaults.get("runs")
        if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
            errors.append("eval defaults.runs must be a positive integer")
        iterations = defaults.get("bootstrap_iterations")
        if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 100:
            errors.append("eval defaults.bootstrap_iterations must be at least 100")
        for seed_name in ("bootstrap_seed", "blind_seed"):
            seed = defaults.get(seed_name)
            if not isinstance(seed, int) or isinstance(seed, bool):
                errors.append(f"eval defaults.{seed_name} must be an integer")

    stimuli = data.get("stimuli")
    stimuli_path = data.get("stimuli_path")
    if stimuli is not None and stimuli_path is not None:
        return errors + ["eval cannot define both stimuli and stimuli_path"]
    if stimuli_path is not None:
        if not isinstance(stimuli_path, str) or not stimuli_path.strip():
            return errors + ["eval stimuli_path must be a non-empty string"]
        case_dir = (path.parent / stimuli_path).resolve()
        try:
            case_dir.relative_to(path.parent.resolve())
        except ValueError:
            return errors + ["eval stimuli_path escapes its specification directory"]
        if not case_dir.is_dir():
            return errors + [f"eval stimuli_path is not a directory: {stimuli_path}"]
        case_files = sorted(case_dir.glob("*.json"), key=lambda item: item.name)
        if not case_files:
            return errors + ["eval stimuli_path contains no JSON cases"]
        stimuli = []
        for case_file in case_files:
            try:
                case_data = json.loads(case_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid evaluation case {case_file.name}: {exc}")
                continue
            stimuli.append(case_data)
    if not isinstance(stimuli, list):
        return errors + ["eval stimuli must be a list or provided through stimuli_path"]
    if len(stimuli) < MIN_STIMULI:
        errors.append(f"eval must contain at least {MIN_STIMULI} stimuli")

    names: set[str] = set()
    prompts: set[str] = set()
    positive = 0
    negative = 0
    categories: set[str] = set()
    critical_positive = 0
    for index, stimulus in enumerate(stimuli, start=1):
        if not isinstance(stimulus, dict):
            errors.append(f"stimulus {index} must be an object")
            continue
        name = stimulus.get("name")
        prompt = stimulus.get("prompt")
        category = stimulus.get("category")
        activation = stimulus.get("expect_activation")
        critical = stimulus.get("critical")
        graders = stimulus.get("graders")
        rubric = stimulus.get("rubric")

        if not isinstance(name, str) or not name.strip():
            errors.append(f"stimulus {index} has no name")
        elif name in names:
            errors.append(f"duplicate stimulus name: {name}")
        else:
            names.add(name)
        if not isinstance(prompt, str) or len(prompt.strip()) < 20:
            errors.append(f"stimulus {index} prompt is too short")
        elif prompt.strip() in prompts:
            errors.append(f"duplicate stimulus prompt at index {index}")
        else:
            prompts.add(prompt.strip())
        if not isinstance(category, str) or not category:
            errors.append(f"stimulus {index} has no category")
        else:
            categories.add(category)
        if not isinstance(activation, bool):
            errors.append(f"stimulus {index} must explicitly define expect_activation")
            continue
        if not isinstance(critical, bool):
            errors.append(f"stimulus {index} critical must be boolean")
        if not isinstance(graders, list):
            errors.append(f"stimulus {index} graders must be a list")

        if activation:
            positive += 1
            if critical is True:
                critical_positive += 1
            if category == "negative":
                errors.append(f"positive stimulus {index} cannot use category negative")
            if not isinstance(rubric, list) or len(rubric) < 3:
                errors.append(f"positive stimulus {index} needs at least three rubric items")
            elif not all(isinstance(item, str) and len(item.strip()) >= 20 for item in rubric):
                errors.append(f"positive stimulus {index} has an invalid rubric item")
            elif len(set(rubric)) != len(rubric):
                errors.append(f"positive stimulus {index} has duplicate rubric items")
            if graders != [{"type": "prompt"}]:
                errors.append(f"positive stimulus {index} must use the prompt grader declaration")
        else:
            negative += 1
            if category != "negative":
                errors.append(f"negative stimulus {index} must use category negative")
            if rubric not in ([], None):
                errors.append(f"negative stimulus {index} must not define a capability rubric")
            if graders not in ([], None):
                errors.append(f"negative stimulus {index} must not define capability graders")

    if positive < MIN_POSITIVE:
        errors.append(f"eval needs at least {MIN_POSITIVE} positive activation scenarios")
    if negative < MIN_NEGATIVE:
        errors.append(f"eval needs at least {MIN_NEGATIVE} negative activation scenarios")
    if critical_positive < 4:
        errors.append("eval needs at least four critical positive scenarios")
    missing = REQUIRED_CATEGORIES - categories
    if missing:
        errors.append("eval is missing categories: " + ", ".join(sorted(missing)))
    return errors


def main() -> int:
    validator = load_validator()
    skill_dirs = [
        path
        for path in sorted(ROOT.iterdir(), key=lambda item: item.name)
        if path.is_dir() and path.name not in RESERVED and (path / "SKILL.md").is_file()
    ]
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
