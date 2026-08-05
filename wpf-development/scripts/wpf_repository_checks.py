#!/usr/bin/env python3
"""Static WPF, configuration, and report checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from wpf_repository_model import (
    PLACEHOLDER_VALUES,
    SECRET_KEY_PATTERN,
    Finding,
    ProjectInfo,
    inspect_project_graph,
    is_ignored,
    iter_files,
    parse_project,
    relative,
)

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


def is_placeholder_secret(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    lowered = text.lower()
    return (
        lowered in PLACEHOLDER_VALUES
        or text.startswith("${")
        or text.startswith("%")
        or text.startswith("@Microsoft.KeyVault")
        or text.startswith("<") and text.endswith(">")
    )


def inspect_json_configuration(path: Path, root: Path, findings: list[Finding]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(Finding("warning", "JSON_CONFIG_PARSE", f"Cannot parse JSON configuration: {exc}", relative(path, root)))
        return

    def walk(value: object, key_path: list[str]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, key_path + [str(key)])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, key_path + [str(index)])
        elif key_path:
            joined = ".".join(key_path)
            if SECRET_KEY_PATTERN.search(joined) and not is_placeholder_secret(value):
                findings.append(
                    Finding(
                        "warning",
                        "POTENTIAL_PLAINTEXT_SECRET",
                        f"Configuration key '{joined}' appears to contain a non-placeholder secret. Move it to protected configuration and redact support output.",
                        relative(path, root),
                    )
                )

    walk(payload, [])


def inspect_global_json(root: Path, findings: list[Finding]) -> dict[str, object]:
    path = root / "global.json"
    if not path.is_file():
        return {"present": False, "sdk_version": None, "roll_forward": None, "allow_prerelease": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(Finding("error", "GLOBAL_JSON_PARSE", f"Cannot parse global.json: {exc}", "global.json"))
        return {"present": True, "sdk_version": None, "roll_forward": None, "allow_prerelease": None}
    sdk = payload.get("sdk") if isinstance(payload, dict) else None
    sdk = sdk if isinstance(sdk, dict) else {}
    return {
        "present": True,
        "sdk_version": sdk.get("version"),
        "roll_forward": sdk.get("rollForward"),
        "allow_prerelease": sdk.get("allowPrerelease"),
    }


def inspect_repository(root: Path) -> dict:
    root = root.resolve()
    findings: list[Finding] = []
    projects: list[ProjectInfo] = []

    for project_file in iter_files(root, {".csproj"}):
        info = parse_project(project_file, root, findings)
        if info:
            projects.append(info)

    inspect_project_graph(root, projects, findings)

    for xaml_file in iter_files(root, {".xaml"}):
        inspect_xaml(xaml_file, root, findings)

    for code_file in iter_files(root, {".cs"}):
        inspect_code(code_file, root, findings)

    appsettings_files = sorted(
        path for path in root.rglob("appsettings*.json") if path.is_file() and not is_ignored(path, root)
    )
    for config_file in appsettings_files:
        inspect_json_configuration(config_file, root, findings)

    wpf_projects = [project for project in projects if project.use_wpf]
    if not projects:
        findings.append(Finding("warning", "NO_PROJECTS", "No .csproj files were found below the target path."))
    elif not wpf_projects:
        findings.append(Finding("warning", "NO_WPF_PROJECTS", "No project with an effective <UseWPF>true</UseWPF> was found."))

    global_json = inspect_global_json(root, findings)
    metadata = {
        "root": root.as_posix(),
        "solutions": sorted(relative(path, root) for path in iter_files(root, {".sln", ".slnx"})),
        "global_json": global_json["present"],
        "global_json_sdk_version": global_json["sdk_version"],
        "global_json_roll_forward": global_json["roll_forward"],
        "global_json_allow_prerelease": global_json["allow_prerelease"],
        "directory_build_props": sorted(relative(path, root) for path in root.rglob("Directory.Build.props") if path.is_file() and not is_ignored(path, root)),
        "directory_packages_props": sorted(relative(path, root) for path in root.rglob("Directory.Packages.props") if path.is_file() and not is_ignored(path, root)),
        "appsettings": [relative(path, root) for path in appsettings_files],
    }

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda item: (severity_order.get(item.severity, 9), item.path or "", item.code, item.message))

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
    global_json_text = "no"
    if metadata["global_json"]:
        details = [metadata.get("global_json_sdk_version"), metadata.get("global_json_roll_forward")]
        global_json_text = ", ".join(str(item) for item in details if item) or "yes"

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
        f"- global.json: {global_json_text}",
        f"- Directory.Build.props: {', '.join(f'`{item}`' for item in metadata['directory_build_props']) or 'none'}",
        f"- Directory.Packages.props: {', '.join(f'`{item}`' for item in metadata['directory_packages_props']) or 'none'}",
        f"- appsettings files: {', '.join(f'`{item}`' for item in metadata['appsettings']) or 'none'}",
        "",
        "## Projects",
        "",
    ]

    if not report["projects"]:
        lines.append("No projects found.")
    else:
        for project in report["projects"]:
            unresolved_packages = sum(1 for package in project["package_references"] if not package.get("version"))
            lines.extend(
                [
                    f"### `{project['path']}`",
                    "",
                    f"- SDK: `{project['sdk'] or 'unspecified'}`",
                    f"- Effective property sources: {', '.join(f'`{item}`' for item in project['property_sources'])}",
                    f"- Target frameworks: {', '.join(f'`{item}`' for item in project['target_frameworks']) or 'unspecified'}",
                    f"- WPF: {'yes' if project['use_wpf'] else 'no'}",
                    f"- Windows Forms: {'yes' if project['use_winforms'] else 'no'}",
                    f"- Output type: `{project['output_type'] or 'unspecified'}`",
                    f"- Runtime identifiers: {', '.join(f'`{item}`' for item in project['runtime_identifiers']) or 'none'}",
                    f"- Package references: {len(project['package_references'])} ({unresolved_packages} unresolved versions)",
                    f"- Project references: {len(project['resolved_project_references'])} resolved / {len(project['project_references'])} declared",
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
            "> This is a static heuristic report. It evaluates only unconditioned MSBuild properties and visible files. Confirm findings through restore/build output, tests, and Windows runtime validation.",
        ]
    )
    return "\n".join(lines)
