"""Score paired evaluations and render release evidence."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval_io import (
    DEFAULT_BOOTSTRAP_ITERATIONS, SCHEMA_VERSION, SCORE_MAX, EvaluationError,
    evaluation_spec_digest, index_responses, load_spec, read_json, read_jsonl,
    write_json,
)
from eval_judging import (
    bootstrap_mean_delta, exact_one_sided_sign_test, index_judgments, ratio,
    threshold_result, validate_score_list,
)


def score_evaluation(
    spec_path: Path,
    responses_path: Path,
    key_path: Path,
    judgments_path: Path,
    manifest_path: Path,
    output_dir: Path,
    version: str,
    source_commit: str,
    synthetic: bool,
    bootstrap_seed: int = 0,
    bootstrap_iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    created_at: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    spec, cases = load_spec(spec_path)
    responses = read_jsonl(responses_path)
    run_id, indexed_responses = index_responses(responses, spec["name"], cases, require_complete=True)
    key_data = read_json(key_path)
    if key_data.get("schema_version") != SCHEMA_VERSION:
        raise EvaluationError("blind key has unsupported schema_version")
    if key_data.get("run_id") != run_id or key_data.get("skill") != spec["name"]:
        raise EvaluationError("blind key does not match the evaluation run")
    pair_key = key_data.get("pairs")
    if not isinstance(pair_key, dict):
        raise EvaluationError("blind key has no pair mapping")

    positive_cases = [case for case in cases if case.expect_activation]
    negative_cases = [case for case in cases if not case.expect_activation]
    judgments = index_judgments(read_jsonl(judgments_path), run_id, spec["name"], positive_cases)
    manifest = read_json(manifest_path)
    if manifest.get("skill") != spec["name"]:
        raise EvaluationError("package manifest skill does not match evaluation skill")
    archive_hash = manifest.get("archive_sha256")
    if not isinstance(archive_hash, str) or len(archive_hash) != 64:
        raise EvaluationError("package manifest has no valid archive_sha256")

    true_positive = false_negative = true_negative = false_positive = 0
    for case in cases:
        activated = indexed_responses[(case.name, "skilled")].get("activated")
        if case.expect_activation and activated:
            true_positive += 1
        elif case.expect_activation:
            false_negative += 1
        elif activated:
            false_positive += 1
        else:
            true_negative += 1

    routing = {
        "true_positive": true_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "positive_recall": ratio(true_positive, true_positive + false_negative),
        "negative_specificity": ratio(true_negative, true_negative + false_positive),
        "accuracy": ratio(true_positive + true_negative, len(cases)),
        "precision": ratio(true_positive, true_positive + false_positive),
    }

    case_scores: list[dict[str, Any]] = []
    baseline_scores: list[float] = []
    skilled_scores: list[float] = []
    deltas: list[float] = []
    wins = ties = losses = 0
    skilled_critical_failures = 0
    baseline_critical_failures = 0

    for case in positive_cases:
        mapping = pair_key.get(case.name)
        if not isinstance(mapping, dict) or set(mapping) != {"A", "B"} or set(mapping.values()) != {"baseline", "skilled"}:
            raise EvaluationError(f"blind key has invalid mapping for {case.name}")
        judgment = judgments[case.name]
        scores_by_variant: dict[str, list[int]] = {}
        critical_by_variant: dict[str, bool] = {}
        for label in ("A", "B"):
            variant = mapping[label]
            scores_by_variant[variant] = validate_score_list(
                judgment["scores"][label], len(case.rubric), case.name, label
            )
            critical_by_variant[variant] = judgment["critical_failure"][label]
        max_points = SCORE_MAX * len(case.rubric)
        baseline_normalized = sum(scores_by_variant["baseline"]) / max_points
        skilled_normalized = sum(scores_by_variant["skilled"]) / max_points
        delta = skilled_normalized - baseline_normalized
        baseline_scores.append(baseline_normalized)
        skilled_scores.append(skilled_normalized)
        deltas.append(delta)
        baseline_critical_failures += int(critical_by_variant["baseline"])
        skilled_critical_failures += int(critical_by_variant["skilled"])
        if delta > 1e-12:
            outcome = "win"
            wins += 1
        elif delta < -1e-12:
            outcome = "loss"
            losses += 1
        else:
            outcome = "tie"
            ties += 1
        case_scores.append(
            {
                "case": case.name,
                "category": case.category,
                "critical": case.critical,
                "baseline": baseline_normalized,
                "skilled": skilled_normalized,
                "delta": delta,
                "outcome": outcome,
                "baseline_critical_failure": critical_by_variant["baseline"],
                "skilled_critical_failure": critical_by_variant["skilled"],
            }
        )

    ci_low, ci_high = bootstrap_mean_delta(deltas, bootstrap_seed, bootstrap_iterations)
    mean_baseline = statistics.fmean(baseline_scores)
    mean_skilled = statistics.fmean(skilled_scores)
    mean_delta = statistics.fmean(deltas)
    sign_test_p = exact_one_sided_sign_test(wins, losses)
    win_rate = ratio(wins, wins + losses)
    capability = {
        "baseline_mean": mean_baseline,
        "skilled_mean": mean_skilled,
        "mean_delta": mean_delta,
        "bootstrap_delta_ci_95": [ci_low, ci_high],
        "bootstrap_iterations": bootstrap_iterations,
        "bootstrap_seed": bootstrap_seed,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "win_rate_non_ties": win_rate,
        "one_sided_sign_test_p": sign_test_p,
        "baseline_critical_failures": baseline_critical_failures,
        "skilled_critical_failures": skilled_critical_failures,
        "cases": case_scores,
    }

    thresholds = spec.get("release_thresholds")
    if not isinstance(thresholds, dict):
        raise EvaluationError("eval specification has no release_thresholds")
    checks = [
        threshold_result("positive_recall", routing["positive_recall"], thresholds["positive_recall_min"], ">="),
        threshold_result("negative_specificity", routing["negative_specificity"], thresholds["negative_specificity_min"], ">="),
        threshold_result("routing_accuracy", routing["accuracy"], thresholds["routing_accuracy_min"], ">="),
        threshold_result("skilled_mean", mean_skilled, thresholds["skilled_mean_min"], ">="),
        threshold_result("mean_delta", mean_delta, thresholds["mean_delta_min"], ">="),
        threshold_result("win_rate_non_ties", win_rate, thresholds["win_rate_non_ties_min"], ">="),
        threshold_result("one_sided_sign_test_p", sign_test_p, thresholds["sign_test_p_max"], "<="),
        threshold_result("bootstrap_delta_ci_low", ci_low, thresholds["bootstrap_delta_ci_low_min"], ">"),
        threshold_result(
            "skilled_critical_failures",
            skilled_critical_failures,
            thresholds["skilled_critical_failures_max"],
            "<=",
        ),
    ]
    failed_gates = [check["name"] for check in checks if not check["passed"]]
    if synthetic:
        failed_gates.append("synthetic_run")
    passed = not failed_gates

    model_metadata = {
        variant: sorted(
            {
                str(record.get("model", "")).strip()
                for (case_name, record_variant), record in indexed_responses.items()
                if record_variant == variant and str(record.get("model", "")).strip()
            }
        )
        for variant in ("baseline", "skilled")
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "skill": spec["name"],
        "version": version,
        "run_id": run_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "source": {
            "commit": source_commit,
            "spec_sha256": evaluation_spec_digest(spec),
            "spec_files": spec.get("source_files", [spec_path.as_posix()]),
        },
        "package": {
            "archive": manifest.get("archive", "skill.zip"),
            "archive_sha256": archive_hash,
            "skill_content_sha256": manifest.get("skill_content_sha256"),
            "file_count": manifest.get("file_count"),
        },
        "evaluation": {
            "synthetic": synthetic,
            "case_count": len(cases),
            "positive_count": len(positive_cases),
            "negative_count": len(negative_cases),
            "models": model_metadata,
            "routing": routing,
            "capability": capability,
        },
        "release_gate": {
            "passed": passed,
            "failed_gates": failed_gates,
            "checks": checks,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"
    write_json(summary_path, summary)
    report_path.write_text(render_report(summary), encoding="utf-8", newline="\n")
    return summary_path, report_path, summary


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(summary: dict[str, Any]) -> str:
    evaluation = summary["evaluation"]
    routing = evaluation["routing"]
    capability = evaluation["capability"]
    release_gate = summary["release_gate"]
    status = "PASS" if release_gate["passed"] else "FAIL"
    lines = [
        f"# {summary['skill']} evaluation report",
        "",
        f"- Version: `{summary['version']}`",
        f"- Run: `{summary['run_id']}`",
        f"- Package SHA-256: `{summary['package']['archive_sha256']}`",
        f"- Evidence type: {'synthetic test fixture' if evaluation['synthetic'] else 'recorded model evaluation'}",
        f"- Release gate: **{status}**",
        "",
    ]
    if evaluation["synthetic"]:
        lines.extend(
            [
                "> Synthetic results validate the evaluator only. They are never acceptable evidence for a stable release.",
                "",
            ]
        )
    lines.extend(
        [
            "## Routing",
            "",
            f"- Positive recall: {percent(routing['positive_recall'])}",
            f"- Negative specificity: {percent(routing['negative_specificity'])}",
            f"- Overall accuracy: {percent(routing['accuracy'])}",
            f"- False positives: {routing['false_positive']}",
            f"- False negatives: {routing['false_negative']}",
            "",
            "## Capability",
            "",
            f"- Baseline mean: {percent(capability['baseline_mean'])}",
            f"- Skilled mean: {percent(capability['skilled_mean'])}",
            f"- Mean delta: {percent(capability['mean_delta'])}",
            f"- 95% bootstrap delta CI: {percent(capability['bootstrap_delta_ci_95'][0])} to {percent(capability['bootstrap_delta_ci_95'][1])}",
            f"- Win / tie / loss: {capability['wins']} / {capability['ties']} / {capability['losses']}",
            f"- Non-tie win rate: {percent(capability['win_rate_non_ties'])}",
            f"- One-sided exact sign-test p: {capability['one_sided_sign_test_p']:.6f}",
            f"- Skilled critical failures: {capability['skilled_critical_failures']}",
            "",
            "## Release checks",
            "",
            "| Check | Actual | Requirement | Result |",
            "|---|---:|---:|---|",
        ]
    )
    for check in release_gate["checks"]:
        actual = check["actual"]
        target = check["target"]
        actual_text = f"{actual:.6f}" if isinstance(actual, float) else str(actual)
        target_text = f"{target:.6f}" if isinstance(target, float) else str(target)
        lines.append(
            f"| `{check['name']}` | {actual_text} | {check['comparator']} {target_text} | {'PASS' if check['passed'] else 'FAIL'} |"
        )
    lines.extend(["", "## Case results", "", "| Case | Category | Baseline | Skilled | Delta | Outcome |", "|---|---|---:|---:|---:|---|"])
    for case in capability["cases"]:
        lines.append(
            f"| `{case['case']}` | {case['category']} | {percent(case['baseline'])} | {percent(case['skilled'])} | {percent(case['delta'])} | {case['outcome']} |"
        )
    if release_gate["failed_gates"]:
        lines.extend(["", "## Failed gates", ""])
        lines.extend(f"- `{name}`" for name in release_gate["failed_gates"])
    lines.append("")
    return "\n".join(lines)
