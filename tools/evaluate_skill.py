#!/usr/bin/env python3
"""Prepare, blind, validate, and score paired Agent Skill evaluations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
ROOT = TOOLS.parent

from eval_io import (  # noqa: E402
    DEFAULT_BOOTSTRAP_ITERATIONS, EvaluationError, create_run_template,
    load_spec, read_json, read_jsonl, write_jsonl,
)
from eval_judging import create_blind_materials  # noqa: E402
from eval_results import score_evaluation  # noqa: E402


def command_init(args: argparse.Namespace) -> int:
    run_path, responses_path = create_run_template(
        args.spec,
        args.output,
        args.run_id,
        args.baseline_model,
        args.skilled_model,
    )
    print(run_path)
    print(responses_path)
    return 0


def command_blind(args: argparse.Namespace) -> int:
    for path in create_blind_materials(args.spec, args.responses, args.output, args.seed):
        print(path)
    return 0


def command_score(args: argparse.Namespace) -> int:
    summary_path, report_path, summary = score_evaluation(
        spec_path=args.spec,
        responses_path=args.responses,
        key_path=args.key,
        judgments_path=args.judgments,
        manifest_path=args.manifest,
        output_dir=args.output,
        version=args.version,
        source_commit=args.source_commit,
        synthetic=args.synthetic,
        bootstrap_seed=args.bootstrap_seed,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    print(summary_path)
    print(report_path)
    if args.require_pass and not summary["release_gate"]["passed"]:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a paired response-capture template")
    init_parser.add_argument("--spec", type=Path, default=ROOT / "evals" / "wpf-development" / "eval.yaml")
    init_parser.add_argument("--output", type=Path, required=True)
    init_parser.add_argument("--run-id", required=True)
    init_parser.add_argument("--baseline-model", required=True)
    init_parser.add_argument("--skilled-model", required=True)
    init_parser.set_defaults(handler=command_init)

    blind_parser = subparsers.add_parser("blind", help="Create randomized A/B judging materials")
    blind_parser.add_argument("--spec", type=Path, default=ROOT / "evals" / "wpf-development" / "eval.yaml")
    blind_parser.add_argument("--responses", type=Path, required=True)
    blind_parser.add_argument("--output", type=Path, required=True)
    blind_parser.add_argument("--seed", type=int, default=0)
    blind_parser.set_defaults(handler=command_blind)

    score_parser = subparsers.add_parser("score", help="Score completed routing and blinded capability evidence")
    score_parser.add_argument("--spec", type=Path, default=ROOT / "evals" / "wpf-development" / "eval.yaml")
    score_parser.add_argument("--responses", type=Path, required=True)
    score_parser.add_argument("--key", type=Path, required=True)
    score_parser.add_argument("--judgments", type=Path, required=True)
    score_parser.add_argument("--manifest", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    score_parser.add_argument("--version", required=True)
    score_parser.add_argument("--source-commit", default="")
    score_parser.add_argument("--synthetic", action="store_true")
    score_parser.add_argument("--bootstrap-seed", type=int, default=0)
    score_parser.add_argument("--bootstrap-iterations", type=int, default=DEFAULT_BOOTSTRAP_ITERATIONS)
    score_parser.add_argument("--require-pass", action="store_true")
    score_parser.set_defaults(handler=command_score)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except EvaluationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
