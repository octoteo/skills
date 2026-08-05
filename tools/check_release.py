#!/usr/bin/env python3
"""Validate per-skill release tags and stable evaluation evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TAG = re.compile(
    r"^(?P<skill>[a-z0-9]+(?:-[a-z0-9]+)*)-v"
    r"(?P<version>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)"
    r"(?P<prerelease>-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$"
)


class ReleaseError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReleaseError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError(f"expected a JSON object in {path}")
    return data


def validate_release(tag: str, manifest_path: Path, results_root: Path) -> dict[str, Any]:
    match = TAG.fullmatch(tag)
    if not match:
        raise ReleaseError(
            "tag must use <skill>-v<major>.<minor>.<patch> with an optional prerelease suffix"
        )
    skill = match.group("skill")
    version = f"{match.group('version')}.{match.group('minor')}.{match.group('patch')}"
    prerelease = match.group("prerelease") is not None
    manifest = read_json(manifest_path)
    if manifest.get("skill") != skill:
        raise ReleaseError("release tag skill does not match package manifest skill")
    archive_hash = manifest.get("archive_sha256")
    if not isinstance(archive_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", archive_hash):
        raise ReleaseError("package manifest has no valid archive_sha256")

    result: dict[str, Any] = {
        "skill": skill,
        "version": version,
        "tag": tag,
        "prerelease": prerelease,
        "archive_sha256": archive_hash,
        "evaluation_summary": None,
    }
    if prerelease:
        return result

    summary_path = results_root / skill / version / "summary.json"
    if not summary_path.is_file():
        raise ReleaseError(f"stable release requires evaluation evidence: {summary_path}")
    summary = read_json(summary_path)
    if summary.get("schema_version") != 1:
        raise ReleaseError("evaluation summary has an unsupported schema_version")
    if summary.get("skill") != skill or summary.get("version") != version:
        raise ReleaseError("evaluation summary skill or version does not match the release tag")
    evaluation = summary.get("evaluation")
    release_gate = summary.get("release_gate")
    package = summary.get("package")
    if not isinstance(evaluation, dict) or not isinstance(release_gate, dict) or not isinstance(package, dict):
        raise ReleaseError("evaluation summary is missing required sections")
    if evaluation.get("synthetic") is not False:
        raise ReleaseError("synthetic evaluation results cannot authorize a stable release")
    if release_gate.get("passed") is not True:
        failed = release_gate.get("failed_gates", [])
        raise ReleaseError(f"evaluation release gate did not pass: {failed}")
    if package.get("archive_sha256") != archive_hash:
        raise ReleaseError("evaluation evidence package hash does not match the release package")
    manifest_content_hash = manifest.get("skill_content_sha256")
    if manifest_content_hash and package.get("skill_content_sha256") != manifest_content_hash:
        raise ReleaseError("evaluation evidence skill content hash does not match the release package")
    if not isinstance(summary.get("created_at"), str) or not summary["created_at"]:
        raise ReleaseError("evaluation summary has no created_at timestamp")
    if not isinstance(summary.get("run_id"), str) or not summary["run_id"]:
        raise ReleaseError("evaluation summary has no run_id")
    result["evaluation_summary"] = summary_path.as_posix()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, default=Path("eval-results"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_release(args.tag, args.manifest, args.results_root)
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        kind = "prerelease" if result["prerelease"] else "stable release"
        print(f"PASS [{result['tag']}] {kind}")
        if result["evaluation_summary"]:
            print(result["evaluation_summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
