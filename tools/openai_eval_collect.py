#!/usr/bin/env python3
"""Upload a Skill and collect paired Responses API evaluation evidence safely."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
ROOT = TOOLS.parent

from eval_io import (  # noqa: E402
    EvaluationError,
    create_run_template,
    load_spec,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)
from openai_eval_api import (  # noqa: E402
    DEFAULT_API_BASE,
    DEFAULT_MODEL,
    ApiError,
    OpenAIHttpClient,
    activation_evidence,
    build_response_payload,
    encode_multipart,
    extract_output_text,
    extract_shell_commands,
    require_api_key,
    sha256_file,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_version(value: Any) -> int | str | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value:
        return int(value) if value.isdigit() else value
    return None


def create_receipt(
    response: dict[str, Any], package: Path, manifest: Path | None, api_base: str, existing_skill_id: str | None
) -> dict[str, Any]:
    skill_id = existing_skill_id or response.get("skill_id") or response.get("id")
    if not isinstance(skill_id, str) or not skill_id:
        raise ApiError("skill upload response did not include a skill id")
    version = parse_version(response.get("version"))
    if version is None:
        version = parse_version(response.get("latest_version")) or parse_version(response.get("default_version"))
    if version is None:
        raise ApiError("skill upload response did not include a version")
    package_hash = sha256_file(package)
    manifest_data = read_json(manifest) if manifest else None
    if manifest_data and manifest_data.get("archive_sha256") != package_hash:
        raise EvaluationError("manifest archive_sha256 does not match the uploaded package")
    return {
        "schema_version": 1,
        "created_at": utc_now(),
        "api_base": api_base.rstrip("/"),
        "skill_id": skill_id,
        "skill_version": version,
        "package": package.name,
        "package_sha256": package_hash,
        "skill_content_sha256": manifest_data.get("skill_content_sha256") if manifest_data else None,
        "api_object": response.get("object"),
    }


def upload_skill(
    client: OpenAIHttpClient,
    package: Path,
    manifest: Path | None,
    output: Path,
    existing_skill_id: str | None,
) -> dict[str, Any]:
    endpoint = f"/skills/{existing_skill_id}/versions" if existing_skill_id else "/skills"
    response = client.post_zip(endpoint, package)
    receipt = create_receipt(response, package, manifest, client.api_base, existing_skill_id)
    write_json(output, receipt)
    return receipt


def load_or_create_run(
    spec_path: Path,
    output_dir: Path,
    run_id: str,
    model: str,
    resume: bool,
) -> tuple[list[dict[str, Any]], Path]:
    responses_path = output_dir / "responses.jsonl"
    if responses_path.exists():
        if not resume:
            raise EvaluationError(f"response capture already exists; pass --resume: {responses_path}")
        return read_jsonl(responses_path), responses_path
    if output_dir.exists() and any(output_dir.iterdir()):
        raise EvaluationError(f"output directory contains files but no responses.jsonl: {output_dir}")
    _, responses_path = create_run_template(spec_path, output_dir, run_id, model, model)
    return read_jsonl(responses_path), responses_path


def selected_case_names(cases: list[Any], names: list[str], max_cases: int) -> list[str]:
    available = [case.name for case in cases]
    if names:
        unknown = sorted(set(names) - set(available))
        if unknown:
            raise EvaluationError("unknown case names: " + ", ".join(unknown))
        selected = [name for name in available if name in set(names)]
    else:
        selected = available
    if max_cases > 0:
        selected = selected[:max_cases]
    if not selected:
        raise EvaluationError("no evaluation cases selected")
    return selected


def collect_responses(
    client: OpenAIHttpClient,
    spec_path: Path,
    receipt_path: Path,
    manifest_path: Path,
    output_dir: Path,
    run_id: str,
    model: str,
    reasoning_effort: str,
    max_output_tokens: int,
    resume: bool,
    case_names: list[str],
    max_cases: int,
) -> tuple[Path, int]:
    spec, cases = load_spec(spec_path)
    receipt = read_json(receipt_path)
    manifest = read_json(manifest_path)
    if receipt.get("package_sha256") != manifest.get("archive_sha256"):
        raise EvaluationError("skill receipt package_sha256 does not match the evaluation manifest")
    receipt_content = receipt.get("skill_content_sha256")
    manifest_content = manifest.get("skill_content_sha256")
    if receipt_content and manifest_content and receipt_content != manifest_content:
        raise EvaluationError("skill receipt content hash does not match the evaluation manifest")
    skill_id = receipt.get("skill_id")
    skill_version = receipt.get("skill_version")
    if not isinstance(skill_id, str) or not skill_id:
        raise EvaluationError("skill receipt has no skill_id")
    if parse_version(skill_version) is None:
        raise EvaluationError("skill receipt has no valid skill_version")
    selected = set(selected_case_names(cases, case_names, max_cases))
    records, responses_path = load_or_create_run(spec_path, output_dir, run_id, model, resume)
    run_path = output_dir / "run.json"
    run_data = read_json(run_path)
    run_data["runtime"] = {
        "type": "openai_responses_hosted_shell",
        "model": model,
        "skill_id": skill_id,
        "skill_version": skill_version,
        "package_sha256": receipt.get("package_sha256"),
        "skill_content_sha256": manifest.get("skill_content_sha256"),
    }
    run_data["collection"] = {
        "reasoning_effort": reasoning_effort,
        "max_output_tokens": max_output_tokens,
        "activation_detection": "visible shell reads of SKILL.md or named skill resources",
    }
    write_json(run_path, run_data)
    case_map = {case.name: case for case in cases}
    raw_dir = output_dir / "raw"
    completed = 0
    for record in records:
        case_name = record.get("case")
        variant = record.get("variant")
        if case_name not in selected or variant not in {"baseline", "skilled"}:
            continue
        if isinstance(record.get("response"), str) and record["response"].strip():
            continue
        case = case_map[case_name]
        use_skill = variant == "skilled"
        payload = build_response_payload(
            model=model,
            prompt=case.prompt,
            skill_id=skill_id if use_skill else None,
            skill_version=skill_version if use_skill else None,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
        )
        response = client.post_json("/responses", payload)
        status = response.get("status")
        if isinstance(status, str) and status != "completed":
            raise ApiError(f"response did not complete for {case_name}/{variant}: status={status}")
        if response.get("error"):
            raise ApiError(f"response failed for {case_name}/{variant}: {response.get('error')}")
        text = extract_output_text(response)
        if not text:
            raise ApiError(f"response contained no output text for {case_name}/{variant}")
        commands = extract_shell_commands(response)
        evidence = activation_evidence(commands, str(spec["name"])) if use_skill else []
        raw_dir.mkdir(parents=True, exist_ok=True)
        write_json(raw_dir / f"{case_name}-{variant}.json", response)
        record.update(
            {
                "model": model,
                "activated": bool(evidence) if use_skill else None,
                "response": text,
                "notes": "Activation inferred from visible shell reads of the mounted skill." if evidence else "",
                "response_id": response.get("id"),
                "api_model": response.get("model"),
                "completed_at": utc_now(),
                "shell_commands": commands,
                "activation_evidence": evidence,
                "usage": response.get("usage"),
                "skill_id": skill_id if use_skill else None,
                "skill_version": skill_version if use_skill else None,
                "package_sha256": receipt.get("package_sha256") if use_skill else None,
            }
        )
        write_jsonl(responses_path, records)
        completed += 1
    return responses_path, completed


def plan_upload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "action": "upload-skill-version" if args.skill_id else "create-skill",
        "endpoint": f"/skills/{args.skill_id}/versions" if args.skill_id else "/skills",
        "package": str(args.package),
        "package_sha256": sha256_file(args.package),
        "receipt": str(args.output),
        "execute": args.execute,
    }


def command_upload(args: argparse.Namespace) -> int:
    if not args.package.is_file():
        raise EvaluationError(f"package not found: {args.package}")
    if args.manifest and not args.manifest.is_file():
        raise EvaluationError(f"manifest not found: {args.manifest}")
    plan = plan_upload(args)
    if not args.execute:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    client = OpenAIHttpClient(require_api_key(), args.api_base, args.timeout, args.max_retries)
    receipt = upload_skill(client, args.package, args.manifest, args.output, args.skill_id)
    print(args.output)
    print(f"skill_id={receipt['skill_id']} version={receipt['skill_version']}")
    return 0


def command_collect(args: argparse.Namespace) -> int:
    _, cases = load_spec(args.spec)
    selected = selected_case_names(cases, args.case, args.max_cases)
    plan = {
        "action": "collect-paired-responses",
        "model": args.model,
        "case_count": len(selected),
        "request_count": len(selected) * 2,
        "output": str(args.output),
        "resume": args.resume,
        "execute": args.execute,
    }
    if not args.execute:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    client = OpenAIHttpClient(require_api_key(), args.api_base, args.timeout, args.max_retries)
    responses, completed = collect_responses(
        client=client,
        spec_path=args.spec,
        receipt_path=args.receipt,
        manifest_path=args.manifest,
        output_dir=args.output,
        run_id=args.run_id,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        max_output_tokens=args.max_output_tokens,
        resume=args.resume,
        case_names=args.case,
        max_cases=args.max_cases,
    )
    print(responses)
    print(f"completed_requests={completed}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload = subparsers.add_parser("upload", help="Create a hosted Skill or upload a new version")
    upload.add_argument("--package", type=Path, default=ROOT / ".artifacts" / "wpf-development" / "skill.zip")
    upload.add_argument("--manifest", type=Path, default=ROOT / ".artifacts" / "wpf-development" / "manifest.json")
    upload.add_argument("--output", type=Path, required=True)
    upload.add_argument("--skill-id", help="Upload a new version of this existing hosted Skill id")
    upload.add_argument("--api-base", default=DEFAULT_API_BASE)
    upload.add_argument("--timeout", type=float, default=300.0)
    upload.add_argument("--max-retries", type=int, default=4)
    upload.add_argument("--execute", action="store_true", help="Perform paid/network API operations")
    upload.set_defaults(handler=command_upload)

    collect = subparsers.add_parser("collect", help="Collect baseline and mounted-Skill Responses API evidence")
    collect.add_argument("--spec", type=Path, default=ROOT / "evals" / "wpf-development" / "eval.yaml")
    collect.add_argument("--receipt", type=Path, required=True)
    collect.add_argument("--manifest", type=Path, default=ROOT / ".artifacts" / "wpf-development" / "manifest.json")
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--run-id", required=True)
    collect.add_argument("--model", default=DEFAULT_MODEL)
    collect.add_argument("--reasoning-effort", choices=("none", "low", "medium", "high", "xhigh", "max"), default="medium")
    collect.add_argument("--max-output-tokens", type=int, default=8000)
    collect.add_argument("--case", action="append", default=[], help="Collect only a named case; repeatable")
    collect.add_argument("--max-cases", type=int, default=0, help="Limit cases for a smoke run; 0 means all")
    collect.add_argument("--resume", action="store_true")
    collect.add_argument("--api-base", default=DEFAULT_API_BASE)
    collect.add_argument("--timeout", type=float, default=600.0)
    collect.add_argument("--max-retries", type=int, default=4)
    collect.add_argument("--execute", action="store_true", help="Perform paid/network API operations")
    collect.set_defaults(handler=command_collect)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (EvaluationError, ApiError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
