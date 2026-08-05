"""Blind-pair preparation and statistical helpers for skill evaluation."""

from __future__ import annotations

import math
import random
import statistics
from pathlib import Path
from typing import Any

from eval_io import (
    SCHEMA_VERSION, SCORE_MAX, SCORE_MIN, EvalCase, EvaluationError,
    index_responses, load_spec, read_jsonl, write_json, write_jsonl,
)


def create_blind_materials(
    spec_path: Path,
    responses_path: Path,
    output_dir: Path,
    seed: int,
) -> tuple[Path, Path, Path]:
    spec, cases = load_spec(spec_path)
    records = read_jsonl(responses_path)
    run_id, indexed = index_responses(records, spec["name"], cases, require_complete=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("blind-pairs.jsonl", "blind-key.json", "judgments.jsonl"):
        if (output_dir / filename).exists():
            raise EvaluationError(f"refusing to overwrite {output_dir / filename}")

    rng = random.Random(seed)
    pairs: list[dict[str, Any]] = []
    judgments: list[dict[str, Any]] = []
    key: dict[str, dict[str, str]] = {}
    for case in cases:
        if not case.expect_activation:
            continue
        first_is_skilled = bool(rng.getrandbits(1))
        mapping = {
            "A": "skilled" if first_is_skilled else "baseline",
            "B": "baseline" if first_is_skilled else "skilled",
        }
        key[case.name] = mapping
        pairs.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "skill": spec["name"],
                "case": case.name,
                "category": case.category,
                "prompt": case.prompt,
                "rubric": list(case.rubric),
                "critical": case.critical,
                "responses": {
                    label: indexed[(case.name, variant)]["response"]
                    for label, variant in mapping.items()
                },
            }
        )
        judgments.append(
            {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "skill": spec["name"],
                "case": case.name,
                "scores": {
                    "A": [None] * len(case.rubric),
                    "B": [None] * len(case.rubric),
                },
                "critical_failure": {"A": False, "B": False},
                "preferred": None,
                "notes": "",
            }
        )

    pairs_path = output_dir / "blind-pairs.jsonl"
    key_path = output_dir / "blind-key.json"
    judgments_path = output_dir / "judgments.jsonl"
    write_jsonl(pairs_path, pairs)
    write_json(
        key_path,
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "skill": spec["name"],
            "seed": seed,
            "pairs": key,
        },
    )
    write_jsonl(judgments_path, judgments)
    return pairs_path, key_path, judgments_path


def validate_score_list(value: Any, expected: int, case: str, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != expected:
        raise EvaluationError(f"judgment {case}/{label} must contain {expected} rubric scores")
    result: list[int] = []
    for index, score in enumerate(value, start=1):
        if not isinstance(score, int) or isinstance(score, bool) or not SCORE_MIN <= score <= SCORE_MAX:
            raise EvaluationError(f"judgment {case}/{label} score {index} must be an integer from 0 to 2")
        result.append(score)
    return result


def index_judgments(
    records: list[dict[str, Any]],
    run_id: str,
    skill: str,
    positive_cases: list[EvalCase],
) -> dict[str, dict[str, Any]]:
    expected = {case.name: case for case in positive_cases}
    indexed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        if record.get("schema_version") != SCHEMA_VERSION:
            raise EvaluationError(f"judgment record {index} has unsupported schema_version")
        if record.get("run_id") != run_id or record.get("skill") != skill:
            raise EvaluationError(f"judgment record {index} does not match the evaluation run")
        case_name = record.get("case")
        if case_name not in expected:
            raise EvaluationError(f"judgment record {index} has unknown case: {case_name}")
        if case_name in indexed:
            raise EvaluationError(f"duplicate judgment record: {case_name}")
        scores = record.get("scores")
        critical_failure = record.get("critical_failure")
        if not isinstance(scores, dict) or not isinstance(critical_failure, dict):
            raise EvaluationError(f"judgment {case_name} is missing scores or critical_failure")
        case = expected[case_name]
        for label in ("A", "B"):
            validate_score_list(scores.get(label), len(case.rubric), case_name, label)
            if not isinstance(critical_failure.get(label), bool):
                raise EvaluationError(f"judgment {case_name}/{label} critical_failure must be boolean")
        preferred = record.get("preferred")
        if preferred not in {"A", "B", "tie", None}:
            raise EvaluationError(f"judgment {case_name} preferred must be A, B, tie, or null")
        indexed[case_name] = record
    missing = sorted(set(expected) - set(indexed))
    if missing:
        raise EvaluationError("missing judgments: " + ", ".join(missing))
    return indexed


def exact_one_sided_sign_test(wins: int, losses: int) -> float:
    trials = wins + losses
    if trials == 0:
        return 1.0
    numerator = sum(math.comb(trials, count) for count in range(wins, trials + 1))
    return numerator / (2 ** trials)


def bootstrap_mean_delta(
    deltas: list[float],
    seed: int,
    iterations: int,
) -> tuple[float, float]:
    if not deltas:
        return 0.0, 0.0
    if iterations < 100:
        raise EvaluationError("bootstrap iterations must be at least 100")
    rng = random.Random(seed)
    size = len(deltas)
    samples = [statistics.fmean(rng.choice(deltas) for _ in range(size)) for _ in range(iterations)]
    samples.sort()
    lower_index = max(0, math.floor(0.025 * (iterations - 1)))
    upper_index = min(iterations - 1, math.ceil(0.975 * (iterations - 1)))
    return samples[lower_index], samples[upper_index]


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def threshold_result(name: str, actual: float | int, target: float | int, comparator: str) -> dict[str, Any]:
    if comparator == ">=":
        passed = actual >= target
    elif comparator == "<=":
        passed = actual <= target
    elif comparator == ">":
        passed = actual > target
    else:
        raise EvaluationError(f"unsupported comparator: {comparator}")
    return {
        "name": name,
        "actual": actual,
        "target": target,
        "comparator": comparator,
        "passed": passed,
    }
