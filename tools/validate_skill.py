#!/usr/bin/env python3
"""Validate an installable Agent Skill using only the Python standard library."""

from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path

ALLOWED_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
LOCAL_PATH = re.compile(r"(?<![A-Za-z0-9_./-])(?:references|scripts|assets|agents)/[A-Za-z0-9_./-]+")
SECRET_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json", "secrets.json", "token.json"}
SECRET_SUFFIXES = {".pem", ".pfx", ".p12", ".key", ".kdbx", ".jks"}
SECRET_CONTENT = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:password|passwd|client_secret|api_key|access_token)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_SKILL_BYTES = 25 * 1024 * 1024
GENERATED_PARTS = {"__pycache__", ".pytest_cache"}
GENERATED_SUFFIXES = {".pyc", ".pyo"}
ALLOWED_FRONTMATTER = {"name", "description"}


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    result: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")):
            if current_key is None:
                raise ValueError(f"unsupported frontmatter indentation: {raw_line}")
            result[current_key] += " " + raw_line.strip()
            continue
        if ":" not in raw_line:
            raise ValueError(f"unsupported frontmatter line: {raw_line}")
        key, value = raw_line.split(":", 1)
        current_key = key.strip()
        if current_key in result:
            raise ValueError(f"duplicate frontmatter key: {current_key}")
        result[current_key] = value.strip().strip('"').strip("'")
    return result


def parse_openai_yaml(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.endswith(":") or stripped.startswith("-"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def is_text_file(path: Path) -> bool:
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" not in data


def iter_files(root: Path):
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            yield path
        elif path.is_file():
            yield path


def validate(skill_dir: Path) -> list[str]:
    skill_dir = skill_dir.resolve()
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not skill_md.is_file():
        return ["SKILL.md is missing"]
    if not openai_yaml.is_file():
        errors.append("agents/openai.yaml is missing")
    try:
        skill_text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ["SKILL.md must be UTF-8"]
    try:
        frontmatter = parse_frontmatter(skill_text)
    except ValueError as exc:
        errors.append(str(exc))
        frontmatter = {}
    if set(frontmatter) != ALLOWED_FRONTMATTER:
        errors.append("frontmatter must contain exactly name and description")
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not ALLOWED_NAME.fullmatch(name):
        errors.append("name must be lowercase kebab-case")
    if name and name != skill_dir.name:
        errors.append("frontmatter name must match the skill directory name")
    if len(name) > 64:
        errors.append("name exceeds 64 characters")
    if not description:
        errors.append("description is empty")
    if len(description) > 1024:
        errors.append("description exceeds 1024 characters")
    if "<" in description or ">" in description:
        errors.append("description cannot contain angle brackets")
    if len(skill_text.splitlines()) > 500:
        errors.append("SKILL.md exceeds 500 lines")
    if "TODO" in skill_text:
        errors.append("SKILL.md contains TODO")
    for reference in sorted(set(LOCAL_PATH.findall(skill_text))):
        target = (skill_dir / reference).resolve()
        try:
            target.relative_to(skill_dir)
        except ValueError:
            errors.append(f"reference escapes skill directory: {reference}")
            continue
        if not target.is_file():
            errors.append(f"referenced file is missing: {reference}")
    if openai_yaml.is_file():
        try:
            metadata_text = openai_yaml.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("agents/openai.yaml must be UTF-8")
        else:
            metadata = parse_openai_yaml(metadata_text)
            for required in ("display_name", "short_description"):
                if not metadata.get(required):
                    errors.append(f"agents/openai.yaml is missing {required}")
            for icon_key in ("icon_small", "icon_large"):
                icon_path = metadata.get(icon_key)
                if icon_path and not (skill_dir / icon_path).is_file():
                    errors.append(f"agents/openai.yaml references missing {icon_key}: {icon_path}")
            color = metadata.get("brand_color")
            if color and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                errors.append("brand_color must be a six-digit hex color")
    total_bytes = 0
    seen_casefold: dict[str, str] = {}
    for path in iter_files(skill_dir):
        rel = path.relative_to(skill_dir).as_posix()
        folded = rel.casefold()
        if folded in seen_casefold and seen_casefold[folded] != rel:
            errors.append(f"case-insensitive path collision: {seen_casefold[folded]} and {rel}")
        seen_casefold[folded] = rel
        if path.is_symlink():
            errors.append(f"symbolic links are not allowed: {rel}")
            continue
        try:
            mode = path.stat().st_mode
            size = path.stat().st_size
        except OSError as exc:
            errors.append(f"cannot stat {rel}: {exc}")
            continue
        if not stat.S_ISREG(mode):
            errors.append(f"non-regular file is not allowed: {rel}")
            continue
        total_bytes += size
        if size > MAX_FILE_BYTES:
            errors.append(f"file exceeds {MAX_FILE_BYTES} bytes: {rel}")
        lowered_name = path.name.lower()
        if any(part in GENERATED_PARTS for part in path.parts) or path.suffix.lower() in GENERATED_SUFFIXES:
            errors.append(f"generated cache file is not allowed: {rel}")
        if lowered_name.startswith("."):
            errors.append(f"hidden files are not allowed in a skill: {rel}")
        if lowered_name in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES:
            errors.append(f"credential-like file is not allowed: {rel}")
        if lowered_name in {"example.py", "api_reference.md", "example_asset.txt"}:
            errors.append(f"generated placeholder remains: {rel}")
        if is_text_file(path) and size <= MAX_FILE_BYTES:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for pattern in SECRET_CONTENT:
                if pattern.search(text):
                    errors.append(f"possible secret material detected in {rel}")
                    break
    if total_bytes > MAX_SKILL_BYTES:
        errors.append(f"skill exceeds {MAX_SKILL_BYTES} bytes before compression")
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path)
    args = parser.parse_args(argv)
    errors = validate(args.skill)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS [{args.skill.name}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
