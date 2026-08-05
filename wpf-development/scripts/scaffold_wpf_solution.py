#!/usr/bin/env python3
"""Plan or execute a conservative .NET 10 WPF solution scaffold.

Execution is intentionally opt-in. The default behavior prints commands only.
"""

from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class Command:
    args: tuple[str, ...]
    cwd: Path


def sanitize_name(value: str) -> str:
    segments = value.split(".")
    if not segments or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", segment) for segment in segments):
        raise ValueError("name must be dot-separated C# identifiers using letters, digits, and underscores")
    if any(segment.upper() in RESERVED_WINDOWS_NAMES for segment in segments):
        raise ValueError("name contains a Windows-reserved path segment")
    return value


def quote(arg: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:\\*-]+", arg):
        return arg
    return '"' + arg.replace('"', '\\"') + '"'


def project_layout(name: str, tier: str) -> dict[str, str]:
    app = f"{name}.App"
    tests = f"{name}.Tests"
    if tier == "compact":
        return {"app": app, "tests": tests}
    if tier == "product":
        return {
            "app": app,
            "core": f"{name}.Core",
            "infrastructure": f"{name}.Infrastructure",
            "tests": tests,
        }
    if tier == "modular":
        return {
            "app": app,
            "core": f"{name}.Core",
            "infrastructure": f"{name}.Infrastructure",
            "module_contracts": f"{name}.Modules.Abstractions",
            "sample_module": f"{name}.Modules.Sample",
            "tests": tests,
        }
    raise ValueError(f"unsupported architecture tier: {tier}")


def build_commands(
    destination: Path,
    name: str,
    solution_format: str,
    host_version: str | None,
    mvvm_version: str | None,
    tier: str = "product",
) -> list[Command]:
    name = sanitize_name(name)
    root = destination.resolve() / name
    layout = project_layout(name, tier)
    extension = "slnx" if solution_format == "slnx" else "sln"
    solution = root / f"{name}.{extension}"

    commands: list[Command] = [Command(("dotnet", "new", "sln", "-n", name, "--format", solution_format), root)]
    commands.append(Command(("dotnet", "new", "wpf", "-n", layout["app"], "-o", f"src/{layout['app']}", "--framework", "net10.0"), root))

    class_library_keys = [key for key in ("core", "infrastructure", "module_contracts", "sample_module") if key in layout]
    for key in class_library_keys:
        project = layout[key]
        commands.append(Command(("dotnet", "new", "classlib", "-n", project, "-o", f"src/{project}", "--framework", "net10.0"), root))

    commands.append(Command(("dotnet", "new", "mstest", "-n", layout["tests"], "-o", f"tests/{layout['tests']}", "--framework", "net10.0"), root))

    project_paths = [f"src/{layout['app']}/{layout['app']}.csproj"]
    project_paths.extend(f"src/{layout[key]}/{layout[key]}.csproj" for key in class_library_keys)
    project_paths.append(f"tests/{layout['tests']}/{layout['tests']}.csproj")
    commands.append(Command(("dotnet", "sln", str(solution), "add", *project_paths), root))

    app_references: list[str] = []
    if tier in {"product", "modular"}:
        app_references.extend(
            [
                f"src/{layout['core']}/{layout['core']}.csproj",
                f"src/{layout['infrastructure']}/{layout['infrastructure']}.csproj",
            ]
        )
    if tier == "modular":
        app_references.extend(
            [
                f"src/{layout['module_contracts']}/{layout['module_contracts']}.csproj",
                f"src/{layout['sample_module']}/{layout['sample_module']}.csproj",
            ]
        )
    if app_references:
        commands.append(Command(("dotnet", "add", f"src/{layout['app']}/{layout['app']}.csproj", "reference", *app_references), root))

    if tier in {"product", "modular"}:
        commands.append(
            Command(
                (
                    "dotnet",
                    "add",
                    f"src/{layout['infrastructure']}/{layout['infrastructure']}.csproj",
                    "reference",
                    f"src/{layout['core']}/{layout['core']}.csproj",
                ),
                root,
            )
        )

    if tier == "modular":
        commands.append(
            Command(
                (
                    "dotnet",
                    "add",
                    f"src/{layout['sample_module']}/{layout['sample_module']}.csproj",
                    "reference",
                    f"src/{layout['core']}/{layout['core']}.csproj",
                    f"src/{layout['module_contracts']}/{layout['module_contracts']}.csproj",
                ),
                root,
            )
        )

    test_references = [f"src/{layout['app']}/{layout['app']}.csproj"] if tier == "compact" else [f"src/{layout['core']}/{layout['core']}.csproj", f"src/{layout['infrastructure']}/{layout['infrastructure']}.csproj"]
    if tier == "modular":
        test_references.append(f"src/{layout['sample_module']}/{layout['sample_module']}.csproj")
    commands.append(Command(("dotnet", "add", f"tests/{layout['tests']}/{layout['tests']}.csproj", "reference", *test_references), root))

    if host_version:
        commands.append(Command(("dotnet", "add", f"src/{layout['app']}/{layout['app']}.csproj", "package", "Microsoft.Extensions.Hosting", "--version", host_version), root))
    if mvvm_version:
        commands.append(Command(("dotnet", "add", f"src/{layout['app']}/{layout['app']}.csproj", "package", "CommunityToolkit.Mvvm", "--version", mvvm_version), root))

    commands.extend(
        [
            Command(("dotnet", "restore", str(solution)), root),
            Command(("dotnet", "build", str(solution), "--no-restore", "--configuration", "Release"), root),
            Command(("dotnet", "test", str(solution), "--no-build", "--configuration", "Release"), root),
        ]
    )
    return commands


def dotnet_major_version() -> int | None:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return None
    completed = subprocess.run([dotnet, "--version"], check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        return None
    match = re.match(r"(\d+)", completed.stdout.strip())
    return int(match.group(1)) if match else None


def run_command(command: Command) -> None:
    command.cwd.mkdir(parents=True, exist_ok=True)
    print(f"[{command.cwd}] {' '.join(quote(arg) for arg in command.args)}")
    subprocess.run(command.args, cwd=command.cwd, check=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or create a .NET 10 WPF solution at a selected architecture tier.")
    parser.add_argument("destination", type=Path, help="Parent directory for the new solution directory.")
    parser.add_argument("--name", required=True, help="Product or solution name, for example Domec.DWF.")
    parser.add_argument("--tier", choices=("compact", "product", "modular"), default="product")
    parser.add_argument("--solution-format", choices=("slnx", "sln"), default="slnx")
    parser.add_argument("--host-version", help="Verified Microsoft.Extensions.Hosting 10.0.x version to add to the App project.")
    parser.add_argument("--mvvm-version", help="Verified CommunityToolkit.Mvvm version to add to the App project.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print commands only. This is the default.")
    mode.add_argument("--execute", action="store_true", help="Execute commands. Requires Windows and a .NET 10 SDK.")
    parser.add_argument("--keep-on-failure", action="store_true", help="Keep a partially created solution when execution fails. The default removes only a newly owned scaffold root.")
    return parser.parse_args(argv)


def cleanup_partial_root(root: Path, destination: Path, name: str) -> bool:
    """Remove only the scaffold root that this invocation is allowed to own."""
    destination = destination.resolve()
    root = root.resolve()
    if root.name != name or root.parent != destination or root == destination:
        return False
    if root.exists():
        shutil.rmtree(root)
    return True


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        name = sanitize_name(args.name)
        project_layout(name, args.tier)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    root = args.destination.resolve() / name
    root_preexisted = root.exists()
    if root.is_symlink():
        print(f"error: destination root must not be a symbolic link: {root}", file=sys.stderr)
        return 1
    if root_preexisted and any(root.iterdir()):
        print(f"error: destination already exists and is not empty: {root}", file=sys.stderr)
        return 1

    commands = build_commands(args.destination, name, args.solution_format, args.host_version, args.mvvm_version, args.tier)
    print(f"Solution root: {root}")
    print(f"Architecture tier: {args.tier}")
    print("Mode: execute" if args.execute else "Mode: dry-run")
    print()

    if not args.execute:
        for command in commands:
            print(f"[{command.cwd}] {' '.join(quote(arg) for arg in command.args)}")
        if not args.host_version:
            print("\nNote: Generic Host package was not added. Verify and pass --host-version when application lifetime, configuration, logging, or hosted services require it.")
        if not args.mvvm_version:
            print("Note: MVVM toolkit package was not added. Verify and pass --mvvm-version only if the project will use it.")
        return 0

    if platform.system() != "Windows":
        print("error: execution is supported only on Windows. Use --dry-run on other operating systems.", file=sys.stderr)
        return 1

    major = dotnet_major_version()
    if major is None:
        print("error: dotnet SDK was not found or could not be queried.", file=sys.stderr)
        return 1
    if major < 10:
        print(f"error: .NET 10 SDK is required; detected major version {major}.", file=sys.stderr)
        return 1

    try:
        for command in commands:
            run_command(command)
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed with exit code {exc.returncode}", file=sys.stderr)
        if not args.keep_on_failure and not root_preexisted:
            try:
                removed = cleanup_partial_root(root, args.destination, name)
            except OSError as cleanup_error:
                print(f"warning: partial scaffold cleanup failed: {cleanup_error}", file=sys.stderr)
            else:
                if removed:
                    print(f"Removed partial scaffold: {root}", file=sys.stderr)
        elif root_preexisted:
            print(f"Preserved pre-existing empty scaffold root: {root}", file=sys.stderr)
        return exc.returncode or 1

    print("\nScaffold completed and validated in Release configuration. Integrate application lifetime, configuration, logging, navigation, security, and product-specific reliability requirements before production use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
