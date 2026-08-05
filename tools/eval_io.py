"""Evaluation specification and evidence I/O primitives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
SCORE_MIN = 0
SCORE_MAX = 2
DEFAULT_BOOTSTRAP_ITERATIONS = 10_000


class EvaluationError(ValueError):
    """Raised when evaluation evidence is incomplete or inconsistent."""


@dataclass(frozen=True)
class EvalCase:
    name: str
    category: str
    prompt: str
    expect_activation: bool
    rubric: tuple[str, ...]
    critical: bool


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvaluationError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvaluationError(f"expected a JSON object in {path}")
    return data


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvaluationError(f"cannot read {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"invalid JSONL in {path} line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise EvaluationError(f"expected an object in {path} line {line_number}")
        records.append(record)
    return records


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records)
    path.write_text(content, encoding="utf-8", newline="\n")


def load_spec(path: Path) -> tuple[dict[str, Any], list[EvalCase]]:
    data = read_json(path)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise EvaluationError(f"unsupported eval schema_version in {path}")
    skill = data.get("name")
    if not isinstance(skill, str) or not skill:
        raise EvaluationError("eval specification has no skill name")
    stimuli = data.get("stimuli")
    stimuli_path = data.get("stimuli_path")
    source_files = [path]
    if stimuli is not None and stimuli_path is not None:
        raise EvaluationError("eval specification cannot define both stimuli and stimuli_path")
    if stimuli_path is not None:
        if not isinstance(stimuli_path, str) or not stimuli_path.strip():
            raise EvaluationError("eval stimuli_path must be a non-empty string")
        case_dir = (path.parent / stimuli_path).resolve()
        try:
            case_dir.relative_to(path.parent.resolve())
        except ValueError as exc:
            raise EvaluationError("eval stimuli_path escapes its specification directory") from exc
        if not case_dir.is_dir():
            raise EvaluationError(f"eval stimuli_path is not a directory: {case_dir}")
        case_files = sorted(case_dir.glob("*.json"), key=lambda item: item.name)
        if not case_files:
            raise EvaluationError(f"eval stimuli_path contains no JSON cases: {case_dir}")
        stimuli = []
        for case_file in case_files:
            case_data = read_json(case_file)
            stimuli.append(case_data)
            source_files.append(case_file)
    if not isinstance(stimuli, list) or not stimuli:
        raise EvaluationError("eval specification has no stimuli")
    data["stimuli"] = stimuli
    data["source_files"] = [item.as_posix() for item in source_files]

    cases: list[EvalCase] = []
    seen: set[str] = set()
    for index, item in enumerate(stimuli, start=1):
        if not isinstance(item, dict):
            raise EvaluationError(f"stimulus {index} must be an object")
        name = item.get("name")
        category = item.get("category")
        prompt = item.get("prompt")
        expect_activation = item.get("expect_activation")
        rubric_value = item.get("rubric", [])
        critical = item.get("critical", False)
        if not isinstance(name, str) or not name:
            raise EvaluationError(f"stimulus {index} has no name")
        if name in seen:
            raise EvaluationError(f"duplicate stimulus name: {name}")
        seen.add(name)
        if not isinstance(category, str) or not category:
            raise EvaluationError(f"stimulus {name} has no category")
        if not isinstance(prompt, str) or not prompt.strip():
            raise EvaluationError(f"stimulus {name} has no prompt")
        if not isinstance(expect_activation, bool):
            raise EvaluationError(f"stimulus {name} must define expect_activation as boolean")
        if not isinstance(critical, bool):
            raise EvaluationError(f"stimulus {name} critical must be boolean")
        if expect_activation:
            if not isinstance(rubric_value, list) or len(rubric_value) < 2:
                raise EvaluationError(f"positive stimulus {name} needs rubric items")
            if not all(isinstance(value, str) and value.strip() for value in rubric_value):
                raise EvaluationError(f"stimulus {name} has an invalid rubric")
        elif rubric_value not in ([], None):
            raise EvaluationError(f"negative stimulus {name} must not define a capability rubric")
        cases.append(
            EvalCase(
                name=name,
                category=category,
                prompt=prompt,
                expect_activation=expect_activation,
                rubric=tuple(rubric_value or []),
                critical=critical,
            )
        )
    return data, cases


def evaluation_spec_digest(spec: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    source_files = spec.get("source_files", [])
    if not isinstance(source_files, list) or not source_files:
        raise EvaluationError("eval specification source_files are unavailable")
    for value in source_files:
        path = Path(value)
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def safe_run_id(value: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if not value or any(character not in allowed for character in value):
        raise EvaluationError("run id may contain only letters, digits, hyphen, underscore, and dot")
    return value


def create_run_template(
    spec_path: Path,
    output_dir: Path,
    run_id: str,
    baseline_model: str,
    skilled_model: str,
) -> tuple[Path, Path]:
    spec, cases = load_spec(spec_path)
    safe_run_id(run_id)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in output_dir.iterdir() if path.name not in {".gitkeep"}]
    if existing:
        raise EvaluationError(f"output directory is not empty: {output_dir}")

    run = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "skill": spec["name"],
        "spec": spec_path.as_posix(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "model": baseline_model,
            "configuration": "Skill unavailable or disabled",
        },
        "skilled": {
            "model": skilled_model,
            "configuration": "wpf-development installed and available",
        },
        "instructions": "Fill activated and response fields. Do not alter case or variant identifiers.",
    }
    records: list[dict[str, Any]] = []
    for case in cases:
        for variant, model, configuration in (
            ("baseline", baseline_model, "Skill unavailable or disabled"),
            ("skilled", skilled_model, "wpf-development installed and available"),
        ):
            records.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "run_id": run_id,
                    "skill": spec["name"],
                    "case": case.name,
                    "variant": variant,
                    "model": model,
                    "configuration": configuration,
                    "activated": None,
                    "response": "",
                    "notes": "",
                }
            )
    run_path = output_dir / "run.json"
    responses_path = output_dir / "responses.jsonl"
    write_json(run_path, run)
    write_jsonl(responses_path, records)
    return run_path, responses_path


def index_responses(
    records: list[dict[str, Any]],
    skill: str,
    cases: list[EvalCase],
    require_complete: bool,
) -> tuple[str, dict[tuple[str, str], dict[str, Any]]]:
    expected_cases = {case.name: case for case in cases}
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    run_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        if record.get("schema_version") != SCHEMA_VERSION:
            raise EvaluationError(f"response record {index} has unsupported schema_version")
        if record.get("skill") != skill:
            raise EvaluationError(f"response record {index} has the wrong skill")
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise EvaluationError(f"response record {index} has no run_id")
        run_ids.add(run_id)
        case_name = record.get("case")
        variant = record.get("variant")
        if case_name not in expected_cases:
            raise EvaluationError(f"response record {index} has unknown case: {case_name}")
        if variant not in {"baseline", "skilled"}:
            raise EvaluationError(f"response record {index} has invalid variant: {variant}")
        key = (case_name, variant)
        if key in indexed:
            raise EvaluationError(f"duplicate response record: {case_name}/{variant}")
        activated = record.get("activated")
        if require_complete and variant == "skilled" and not isinstance(activated, bool):
            raise EvaluationError(f"skilled response {case_name} must record activated as true or false")
        if activated is not None and not isinstance(activated, bool):
            raise EvaluationError(f"response {case_name}/{variant} has invalid activated value")
        response = record.get("response")
        if not isinstance(response, str):
            raise EvaluationError(f"response {case_name}/{variant} must be a string")
        case = expected_cases[case_name]
        if require_complete and case.expect_activation and not response.strip():
            raise EvaluationError(f"positive response is empty: {case_name}/{variant}")
        indexed[key] = record

    if len(run_ids) != 1:
        raise EvaluationError("response records must have exactly one run_id")
    missing = [
        f"{case.name}/{variant}"
        for case in cases
        for variant in ("baseline", "skilled")
        if (case.name, variant) not in indexed
    ]
    if missing:
        raise EvaluationError("missing response records: " + ", ".join(missing))
    return next(iter(run_ids)), indexed
