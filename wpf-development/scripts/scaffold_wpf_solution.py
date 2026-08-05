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


@dataclass(frozen=True)
class Command:
    args: tuple[str, ...]
    cwd: Path


def sanitize_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", value):
        raise ValueError("name must use letters, digits, underscores, and dots, and cannot start with a digit")
    return value


def quote(arg: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:\\*-]+", arg):
        return arg
    return '"' + arg.replace('"', '\\"') + '"'


def build_commands(destination: Path, name: str, solution_format: str, host_version: str | None, mvvm_version: str | None) -> list[Command]:
    root = destination.resolve() / name
    app = f"{name}.App"
    core = f"{name}.Core"
    infrastructure = f"{name}.Infrastructure"
    tests = f"{name}.Tests"
    extension = "slnx" if solution_format == "slnx" else "sln"
    solution = root / f"{name}.{extension}"
    commands = [
        Command(("dotnet", "new", "sln", "-n", name, "--format", solution_format), root),
        Command(("dotnet", "new", "wpf", "-n", app, "-o", f"src/{app}", "--framework", "net10.0"), root),
        Command(("dotnet", "new", "classlib", "-n", core, "-o", f"src/{core}", "--framework", "net10.0"), root),
        Command(("dotnet", "new", "classlib", "-n", infrastructure, "-o", f"src/{infrastructure}", "--framework", "net10.0"),
        Command(("dotnet", "new", "mstest", "-n", tests, "-o", f"tests/{tests}", "--framework", "net10.0"),
        Command(("dotnet", "sln", str(solution), "add", f"src/{app}/{app}.csproj", f"src/{core}/{core}.csproj", f"src/{infrastructure}/{infrastructure}.csproj", f"tests/{tests}/{tests}.csproj"), root),
        Command(("dotnet", "add", f"src/{app}/{app}.csproj", "reference", f"src/{core}/{core}.csproj", f"src/{infrastructure}/{infrastructure}.csproj"), root),
        Command(("dotnet", "add", f"src/{infrastructure}/{infrastructure}.csproj", "reference", f"src/{core}/{core}.csproj"), root),
        Command(("dotnet", "add", f"tests/{tests}/{tests}.csproj", "reference", f"src/{core}/{core}.csproj", f"src/{infrastructure}/{infrastructure}.csproj"), root),
    ]
    if host_version:
        commands.append(Command(("dotnet", "add", f"src/{app}/{app}.csproj", "package", "Microsoft.Extensions.Hosting", "--version", host_version), root))
    if mvvm_version:
        commands.append(Command(("dotnet", "add", f"src/{app}/{app}.csproj", "package", "CommunityToolkit.Mvvm", "--version", mvvm_version), root))
    commands.extend([Command(("dotnet", "restore", str(solution)), root), Command(("dotnet", "build", str(solution), "--no-restore"), root), Command(("dotnet", "test", str(solution), "--no-build"), root)])
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
    parser = argparse.ArgumentParser(description="Plan or create a layered .NET 10 WPF solution.")
    parser.add_argument("destination", type=Path, help="Parent directory for the new solution directory.")
    parser.add_argument("--name", required=True, help="Product or solution name, for example Domec.DWF.")
    parser.add_argument("--solution-format", choices=("slnx", "sln"), default="slnx")
    parser.add_argument("--host-version", help="Verified Microsoft.Extensions.Hosting 10.0.x version to add.")
    parser.add_argument("--mvvm-version", help="Verified CommunityToolkit.Mvvm version to add.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print commands only. This is the default.")
    mode.add_argument("--execute", action="store_true", help="Execute commands. Requires Windows and .NET 10 SDK.")
    parser.add_argument("--keep-on-failure", action="store_true", help="Keep a partially created solution when execution fails. The default removes only the new empty destination root.")
    return parser.parse_args(argv)


def cleanup_partial_root(root: Path, destination: Path, name: str) -> bool:
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
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    root = args.destination.resolve() / name
    if root.exists() and any(root.iterdir()):
        print(f"error: destination already exists and is not empty: {root}", file=sys.stderr)
        return 1
    commands = build_commands(args.destination, name, args.solution_format, args.host_version, args.mvvm_version)
    print(f"Solution root: {root}")
    print("Mode: execute" if args.execute else "Mode: dry-run")
    print()
    if not args.execute:
        for command in commands:
            print(f"[{command.cwd}] {' '.join(quote(arg) for arg in command.args)}")
        if not args.host_version:
            print("\nNote: Generic Host package was not added. Verify and pass --host-version for a current stable 10.0.x version.")
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
        if not args.keep_on_failure:
            try:
                removed = cleanup_partial_root(root, args.destination, name)
            except OSError as cleanup_error:
                print(f"warning: partial scaffold cleanup failed: {cleanup_error}", file=sys.stderr)
            else:
                if removed:
                    print(f"Removed partial scaffold: {root}", file=sys.stderr)
        return exc.returncode or 1
    print("\nScaffold completed. Integrate Generic Host, configuration, logging, navigation, and product-specific reliability requirements before production use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
