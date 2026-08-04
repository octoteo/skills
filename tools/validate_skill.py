#!/usr/bin/env python3
"""Validate the standalone skill structure without third-party dependencies."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    result: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith((" ", "\t")) and current_key:
            result[current_key] += " " + raw_line.strip()
            continue
        if ":" not in raw_line:
            raise ValueError(f"unsupported frontmatter line: {raw_line}")
        key, value = raw_line.split(":", 1)
        current_key = key.strip()
        result[current_key] = value.strip().strip('"').strip("'")
    return result


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    skill_md = path / "SKILL.md"
    agent_yaml = path / "agents" / "openai.yaml"
    if not skill_md.is_file():
        return ["SKILL.md is missing"]
    if not agent_yaml.is_file():
        errors.append("agents/openai.yaml is missing")

    text = skill_md.read_text(encoding="utf-8")
    try:
        frontmatter = parse_frontmatter(text)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    if set(frontmatter) != {"name", "description"}:
        errors.append("frontmatter must contain exactly name and description")
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not ALLOWED_NAME.fullmatch(name):
        errors.append("name must be lowercase kebab-case")
    if name != path.name:
        errors.append("frontmatter name must match the skill directory name")
    if len(name) > 64:
        errors.append("name exceeds 64 characters")
    if not description:
        errors.append("description is empty")
    if len(description) > 1024:
        errors.append("description exceeds 1024 characters")
    if "<" in description or ">" in description:
        errors.append("description cannot contain angle brackets")
    if text.count("\n") > 500:
        errors.append("SKILL.md exceeds the recommended 500 lines")
    if "TODO" in text:
        errors.append("SKILL.md contains TODO")

    for placeholder in path.rglob("*"):
        if placeholder.name in {"example.py", "api_reference.md", "example_asset.txt"}:
            errors.append(f"generated placeholder remains: {placeholder.relative_to(path)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill", type=Path)
    args = parser.parse_args(argv)
    errors = validate(args.skill)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
