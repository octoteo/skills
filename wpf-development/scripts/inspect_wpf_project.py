#!/usr/bin/env python3
"""Inspect a repository for .NET and WPF project characteristics.

The script uses only the Python standard library. It performs static inspection and
never edits the target repository.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {
    ".git",
    ".idea",
    ".vs",
    ".vscode",
    "bin",
    "obj",
    "node_modules",
    "packages",
    "TestResults",
}


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None


@dataclass
class ProjectInfo:
    path: str
    sdk: str | None = None
    target_frameworks: list[str] = field(default_factory=list)
    output_type: str | None = None
    use_wpf: bool = False
    use_winforms: bool = False
    nullable: str | None = None
    implicit_usings: str | None = None
    runtime_identifiers: list[str] = field(default_factory=list)
    package_references: list[dict[str, str | None]] = field(default_factory=list)
    project_references: list[str] = field(default_factory=list)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def iter_files(root: Path, suffixes: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in suffixes:
            yield path


def text_values(root: ET.Element, name: str) -> list[str]:
    values: list[str] = []
    for element in root.iter():
        if local_name(element.tag) == name and element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def bool_value(values: list[str]) -> bool:
    return any(value.lower() == "true" for value in values)


def split_values(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in value.split(";"):
            item = item.strip()
            if item and item not in result:
                result.append(item)
    return result


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def parse_project(path: Path, root_path: Path, findings: list[Finding]) -> ProjectInfo | None:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        findings.append(Finding("error", "XML_PARSE", f"Cannot parse project XML: {exc}", relative(path, root_path)))
        return None

    project_root = tree.getroot()
    info = ProjectInfo(path=relative(path, root_path), sdk=project_root.attrib.get("Sdk"))

    tfms = text_values(project_root, "TargetFramework") + text_values(project_root, "TargetFrameworks")
    info.target_frameworks = split_values(tfms)
    info.output_type = next(iter(text_values(project_root, "OutputType")), None)
    info.use_wpf = bool_value(text_values(project_root, "UseWPF"))
    info.use_winforms = bool_value(text_values(project_root, "UseWindowsForms"))
    info.nullable = next(iter(text_values(project_root, "Nullable")), None)
    info.implicit_usings = next(iter(text_values(project_root, "ImplicitUsings")), None)
    rids = text_values(project_root, "RuntimeIdentifier") + text_values(project_root, "RuntimeIdentifiers")
    info.runtime_identifiers = split_values(rids)

    for element in project_root.iter():
        name = local_name(element.tag)
        if name == "PackageReference":
            include = element.attrib.get("Include") or element.attrib.get("Update")
            version = element.attrib.get("Version")
            if version is None:
                version_element = next((child for child in element if local_name(child.tag) == "Version"), None)
                version = version_element.text.strip() if version_element is not None and version_element.text else None
            if include:
                info.package_references.append({"name": include, "version": version})
        elif name == "ProjectReference":
            include = element.attrib.get("Include")
            if include:
                info.project_references.append(include.replace("\\", "/"))

    if info.use_wpf:
        if not info.target_frameworks:
            findings.append(Finding("warning", "WPF_NO_TFM", "WPF project has no directly visible target framework.", info.path))
        for tfm in info.target_frameworks:
            if not tfm.startswith("net10.0-windows"):
                findings.append(Finding("warning", "WPF_NOT_NET10", f"WPF target framework is '{tfm}', not net10.0-windows.", info.path))
        if info.output_type and info.output_type.lower() not in {"winexe", "library"}:
            findings.append(Finding("info", "WPF_OUTPUT_TYPE", f"WPF project output type is '{info.output_type}'.", info.path))
        if info.use_winforms:
            findings.append(Finding("info", "WPF_WINFORMS_INTEROP", "Project enables both WPF and Windows Forms; inspect type ambiguity, DPI, focus, and disposal boundaries.", info.path))

    return info


def inspect_xaml(path: Path, root: Path, findings: list[Finding]) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        findings.append(Finding("warning", "XAML_READ", f"Cannot read XAML: {exc}", relative(path, root)))
        return

    rel = relative(path, root)
    if re.search(r"<\s*Grid\.(ColumnDefinitions|RowDefinitions)\s*/\s*>", text, flags=re.IGNORECASE):
        findings.append(Finding("error", "EMPTY_GRID_DEFINITIONS", "Empty Grid definition collections are incompatible with .NET 10 WPF.", rel))

    dynamic_keys = re.findall(r"\{\s*DynamicResource\s+([^}\s,]+)", text)
    if dynamic_keys:
        unique_keys = sorted(set(dynamic_keys))
        findings.append(Finding("info", "DYNAMIC_RESOURCE_REVIEW", f"Review DynamicResource keys and target dependency properties: {', '.join(unique_keys[:12])}", rel))

    if path.name.lower() == "app.xaml" and re.search(r"\bStartupUri\s*=", text):
        findings.append(Finding("info", "STARTUP_URI", "App.xaml uses StartupUri. Remove it if Generic Host resolves the main window.", rel))

    if "WindowsFormsHost" in text or "ElementHost" in text:
        findings.append(Finding("info", "INTEROP_HOST", "WPF/WinForms interop host detected; verify DPI, focus, airspace, and disposal behavior.", rel))


def inspect_code(path: Path, root: Path, findings: list[Finding]) -> None:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return
    rel = relative(path, root)

    sync_wait_patterns = [r"\.Result\b", r"\.Wait\s*\(", r"GetAwaiter\s*\(\s*\)\s*\.GetResult\s*\("]
    if any(re.search(pattern, text) for pattern in sync_wait_patterns):
        findings.append(Finding("warning", "SYNC_OVER_ASYNC", "Potential synchronous wait may block or deadlock the UI thread; inspect call context.", rel))

    if "BinaryFormatter" in text:
        findings.append(Finding("error", "BINARY_FORMATTER", "BinaryFormatter usage is unsafe and incompatible with modern .NET guidance.", rel))

    if re.search(r"async\s+void\s+(?!On|Application_|Button_|Window_|.*_Click)", text):
        findings.append(Finding("warning", "ASYNC_VOID", "Potential async void method outside an obvious event-handler pattern.", rel))


def inspect_repository(root: Path) -> dict:
    root = root.resolve()
    findings: list[Finding] = []
    projects: list[ProjectInfo] = []

    for project_file in iter_files(root, {".csproj"}):
        info = parse_project(project_file, root, findings)
        if info:
            projects.append(info)

    for xaml_file in iter_files(root, {".xaml"}):
        inspect_xaml(xaml_file, root, findings)

    for code_file in iter_files(root, {".cs"}):
        inspect_code(code_file, root, findings)

    wpf_projects = [project for project in projects if project.use_wpf]
    if not projects:
        findings.append(Finding("warning", "NO_PROJECTS", "No .csproj files were found below the target path."))
    elif not wpf_projects:
        findings.append(Finding("warning", "NO_WPF_PROJECTS", "No project with <UseWPF>true</UseWPF> was found."))

    metadata = {
        "root": root.as_posix(),
        "solutions": sorted(relative(path, root) for path in iter_files(root, {".sln", ".slnx"})),
        "global_json": (root / "global.json").exists(),
        "directory_build_props": sorted(relative(path, root) for path in root.rglob("Directory.Build.props") if not any(part in IGNORED_DIRS for part in path.parts)),
        "directory_packages_props": sorted(relative(path, root) for path in root.rglob("Directory.Packages.props") if not any(part in IGNORED_DIRS for part in path.parts)),
        "appsettings": sorted(relative(path, root) for path in root.rglob("appsettings*.json") if not any(part in IGNORED_DIRS for part in path.parts)),
    }

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda item: (severity_order.get(item.severity, 9), item.path or "", item.code))

    return {
        "metadata": metadata,
        "summary": {
            "project_count": len(projects),
            "wpf_project_count": len(wpf_projects),
            "finding_count": len(findings),
            "errors": sum(1 for item in findings if item.severity == "error"),
            "warnings": sum(1 for item in findings if item.severity == "warning"),
            "info": sum(1 for item in findings if item.severity == "info"),
        },
        "projects": [asdict(project) for project in sorted(projects, key=lambda item: item.path)],
        "findings": [asdict(item) for item in findings],
    }


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    metadata = report["metadata"]
    lines = [
        "# WPF Project Inspection",
        "",
        f"- Root: `{metadata['root']}`",
        f"- Projects: {summary['project_count']}",
        f"- WPF projects: {summary['wpf_project_count']}",
        f"- Findings: {summary['finding_count']} ({summary['errors']} errors, {summary['warnings']} warnings, {summary['info']} info)",
        "",
        "## Repository metadata",
        "",
        f"- Solutions: {', '.join(f'`{item}`' for item in metadata['solutions']) or 'none'}",
        f"- global.json: {'yes' if metadata['global_json'] else 'no'}",
        f"- Directory.Build.props: {', '.join(f'`{item}`' for item in metadata['directory_build_props']) or 'none'}",
        f"- Directory.Packages.props: {', '.join(f'`{item}`' for item in metadata['directory_packages_props']) or 'none'}",
        "",
        "## Projects",
        "",
    ]

    if not report["projects"]:
        lines.append("No projects found.")
    else:
        for project in report["projects"]:
            lines.extend(
                [
                    f"### `{project['path']}`",
                    "",
                    f"- SDK: `{project['sdk'] or 'unspecified'}`",
                    f"- Target frameworks: {', '.join(f'`{item}`' for item in project['target_frameworks']) or 'unspecified'}",
                    f"- WPF: {'yes' if project['use_wpf'] else 'no'}",
                    f"- Windows Forms: {'yes' if project['use_winforms'] else 'no'}",
                    f"- Output type: `{project['output_type'] or 'unspecified'}`",
                    f"- Runtime identifiers: {', '.join(f'`{item}`' for item in project['runtime_identifiers']) or 'none'}",
                    f"- Package references: {len(project['package_references'])}",
                    f"- Project references: {len(project['project_references'])}",
                    "",
                ]
            )

    lines.extend(["## Findings", ""])
    if not report["findings"]:
        lines.append("No heuristic findings.")
    else:
        for item in report["findings"]:
            location = f" (`{item['path']}`)" if item.get("path") else ""
            lines.append(f"- **{item['severity'].upper()} {item['code']}**{location}: {item['message']}")

    lines.extend(
        [
            "",
            "> This is a static heuristic report. Confirm findings through source review, build output, tests, and Windows runtime validation.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a repository for .NET 10 WPF readiness.")
    parser.add_argument("path", type=Path, help="Repository or project directory to inspect.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, help="Optional output file. Defaults to stdout.")
    parser.add_argument("--strict", action="store_true", help="Return exit code 2 when errors are found.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.path.exists() or not args.path.is_dir():
        print(f"error: directory not found: {args.path}", file=sys.stderr)
        return 1

    report = inspect_repository(args.path)
    output = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    if args.strict and report["summary"]["errors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
