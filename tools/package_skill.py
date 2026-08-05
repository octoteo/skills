#!/usr/bin/env python3
"""Create a deterministic, validated ChatGPT Agent Skill package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def load_validator():
    path = ROOT / "tools" / "validate_skill.py"
    spec = importlib.util.spec_from_file_location("validate_skill", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load validate_skill.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_files(skill_dir: Path) -> list[Path]:
    return [path for path in sorted(skill_dir.rglob("*"), key=lambda item: item.relative_to(skill_dir).as_posix()) if path.is_file() and not path.is_symlink()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_package(skill_dir: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    skill_dir = skill_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "skill.zip"
    checksum_path = output_dir / "skill.zip.sha256"
    manifest_path = output_dir / "manifest.json"
    validator = load_validator()
    errors = validator.validate(skill_dir)
    if errors:
        raise ValueError("skill validation failed:\n" + "\n".join(f"- {item}" for item in errors))
    entries: list[dict[str, object]] = []
    files = source_files(skill_dir)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True) as archive:
        for path in files:
            relative = path.relative_to(skill_dir).as_posix()
            archive_name = f"{skill_dir.name}/{relative}"
            data = path.read_bytes()
            info = zipfile.ZipInfo(archive_name, date_time=FIXED_TIME)
            info.create_system = 3
            executable = path.suffix.lower() in {".py", ".sh", ".ps1"}
            mode = 0o755 if executable else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            entries.append({"path": archive_name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    archive_hash = sha256_file(zip_path)
    checksum_path.write_text(f"{archive_hash}  skill.zip\n", encoding="ascii", newline="\n")
    manifest = {"schema_version": 1, "skill": skill_dir.name, "archive": "skill.zip", "archive_sha256": archive_hash, "file_count": len(entries), "files": entries}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return zip_path, checksum_path, manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="Root-level skill directory name or path")
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / ".artifacts")
    args = parser.parse_args(argv)
    skill_dir = Path(args.skill)
    if not skill_dir.is_absolute():
        candidate = ROOT / skill_dir
        skill_dir = candidate if candidate.exists() else skill_dir
    try:
        zip_path, checksum_path, manifest_path = create_package(skill_dir, args.output.resolve())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(zip_path)
    print(checksum_path)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
