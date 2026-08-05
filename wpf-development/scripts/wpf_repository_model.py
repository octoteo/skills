#!/usr/bin/env python3
"""Repository and MSBuild model used by the WPF inspector."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
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

EFFECTIVE_PROPERTIES = {
    "TargetFramework",
    "TargetFrameworks",
    "OutputType",
    "UseWPF",
    "UseWindowsForms",
    "Nullable",
    "ImplicitUsings",
    "RuntimeIdentifier",
    "RuntimeIdentifiers",
    "PublishTrimmed",
    "PublishSingleFile",
    "SelfContained",
    "AllowUnsafeBlocks",
}

SECRET_KEY_PATTERN = re.compile(
    r"(^|[_.:-])(password|passwd|pwd|secret|token|api[-_]?key|connectionstrings?|clientsecret|privatekey)($|[_.:-])",
    re.IGNORECASE,
)

PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change-me",
    "placeholder",
    "redacted",
    "not-set",
    "none",
    "null",
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
    publish_trimmed: bool = False
    publish_single_file: bool = False
    self_contained: bool = False
    allow_unsafe_blocks: bool = False
    package_references: list[dict[str, str | None]] = field(default_factory=list)
    project_references: list[str] = field(default_factory=list)
    resolved_project_references: list[str] = field(default_factory=list)
    property_sources: list[str] = field(default_factory=list)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_ignored(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in IGNORED_DIRS for part in parts)


def iter_files(root: Path, suffixes: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or is_ignored(path, root):
            continue
        if path.suffix.lower() in suffixes:
            yield path


def parse_xml(path: Path, root_path: Path, findings: list[Finding], code: str = "XML_PARSE") -> ET.Element | None:
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        findings.append(Finding("error", code, f"Cannot parse XML: {exc}", relative(path, root_path)))
        return None


def collect_unconditional_properties(root: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for group in root.iter():
        if local_name(group.tag) != "PropertyGroup" or group.attrib.get("Condition"):
            continue
        for child in group:
            if child.attrib.get("Condition") or child.text is None:
                continue
            name = local_name(child.tag)
            text = child.text.strip()
            if name in EFFECTIVE_PROPERTIES and text:
                values[name] = text
    return values


def split_values(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        for item in value.split(";"):
            item = item.strip()
            if item and item not in result:
                result.append(item)
    return result


def bool_property(properties: dict[str, str], name: str) -> bool:
    return properties.get(name, "").strip().lower() == "true"


def find_upward(start: Path, stop: Path, filename: str) -> Path | None:
    start = start.resolve()
    stop = stop.resolve()
    current = start
    while True:
        candidate = current / filename
        if candidate.is_file():
            return candidate
        if current == stop or current.parent == current:
            return None
        try:
            current.relative_to(stop)
        except ValueError:
            return None
        current = current.parent


def load_effective_properties(
    project_path: Path,
    root_path: Path,
    project_root: ET.Element,
    findings: list[Finding],
) -> tuple[dict[str, str], list[str]]:
    properties: dict[str, str] = {}
    sources: list[str] = []
    props_path = find_upward(project_path.parent, root_path, "Directory.Build.props")
    if props_path:
        props_root = parse_xml(props_path, root_path, findings, "DIRECTORY_BUILD_PROPS_PARSE")
        if props_root is not None:
            properties.update(collect_unconditional_properties(props_root))
            sources.append(relative(props_path, root_path))
    properties.update(collect_unconditional_properties(project_root))
    sources.append(relative(project_path, root_path))
    return properties, sources


def central_package_versions(project_path: Path, root_path: Path, findings: list[Finding]) -> tuple[dict[str, str], str | None]:
    props_path = find_upward(project_path.parent, root_path, "Directory.Packages.props")
    if not props_path:
        return {}, None
    props_root = parse_xml(props_path, root_path, findings, "DIRECTORY_PACKAGES_PROPS_PARSE")
    if props_root is None:
        return {}, relative(props_path, root_path)

    versions: dict[str, str] = {}
    for group in props_root.iter():
        if local_name(group.tag) != "ItemGroup" or group.attrib.get("Condition"):
            continue
        for element in group:
            if local_name(element.tag) != "PackageVersion" or element.attrib.get("Condition"):
                continue
            include = element.attrib.get("Include") or element.attrib.get("Update")
            version = element.attrib.get("Version") or element.attrib.get("VersionOverride")
            if version is None:
                version_element = next((child for child in element if local_name(child.tag) in {"Version", "VersionOverride"}), None)
                version = version_element.text.strip() if version_element is not None and version_element.text else None
            if include and version:
                versions[include.lower()] = version
    return versions, relative(props_path, root_path)


def parse_project(path: Path, root_path: Path, findings: list[Finding]) -> ProjectInfo | None:
    project_root = parse_xml(path, root_path, findings)
    if project_root is None:
        return None

    properties, property_sources = load_effective_properties(path, root_path, project_root, findings)
    central_versions, central_source = central_package_versions(path, root_path, findings)
    info = ProjectInfo(
        path=relative(path, root_path),
        sdk=project_root.attrib.get("Sdk"),
        property_sources=property_sources,
    )

    info.target_frameworks = split_values(
        value for key in ("TargetFramework", "TargetFrameworks") if (value := properties.get(key))
    )
    info.output_type = properties.get("OutputType")
    info.use_wpf = bool_property(properties, "UseWPF")
    info.use_winforms = bool_property(properties, "UseWindowsForms")
    info.nullable = properties.get("Nullable")
    info.implicit_usings = properties.get("ImplicitUsings")
    info.runtime_identifiers = split_values(
        value for key in ("RuntimeIdentifier", "RuntimeIdentifiers") if (value := properties.get(key))
    )
    info.publish_trimmed = bool_property(properties, "PublishTrimmed")
    info.publish_single_file = bool_property(properties, "PublishSingleFile")
    info.self_contained = bool_property(properties, "SelfContained")
    info.allow_unsafe_blocks = bool_property(properties, "AllowUnsafeBlocks")

    for element in project_root.iter():
        name = local_name(element.tag)
        if name == "PackageReference":
            include = element.attrib.get("Include") or element.attrib.get("Update")
            version = element.attrib.get("Version") or element.attrib.get("VersionOverride")
            if version is None:
                version_element = next((child for child in element if local_name(child.tag) in {"Version", "VersionOverride"}), None)
                version = version_element.text.strip() if version_element is not None and version_element.text else None
            source = "project" if version else None
            if include and version is None:
                version = central_versions.get(include.lower())
                source = "central" if version else None
            if include:
                info.package_references.append({"name": include, "version": version, "source": source})
                if version is None:
                    findings.append(
                        Finding(
                            "warning",
                            "PACKAGE_VERSION_UNRESOLVED",
                            f"PackageReference '{include}' has no project or central version visible to static inspection.",
                            info.path,
                        )
                    )
        elif name == "ProjectReference":
            include = element.attrib.get("Include")
            if include:
                info.project_references.append(include.replace("\\", "/"))

    if central_source and central_source not in info.property_sources:
        info.property_sources.append(central_source)

    if info.use_wpf:
        if not info.target_frameworks:
            findings.append(Finding("warning", "WPF_NO_TFM", "WPF project has no unconditionally visible target framework.", info.path))
        for tfm in info.target_frameworks:
            if not tfm.startswith("net10.0-windows"):
                findings.append(Finding("warning", "WPF_NOT_NET10", f"WPF target framework is '{tfm}', not net10.0-windows.", info.path))
        if info.output_type and info.output_type.lower() not in {"winexe", "library"}:
            findings.append(Finding("info", "WPF_OUTPUT_TYPE", f"WPF project output type is '{info.output_type}'.", info.path))
        if info.use_winforms:
            findings.append(Finding("info", "WPF_WINFORMS_INTEROP", "Project enables both WPF and Windows Forms; inspect type ambiguity, DPI, focus, and disposal boundaries.", info.path))
        if info.publish_trimmed:
            findings.append(Finding("warning", "WPF_TRIMMING_ENABLED", "WPF project enables trimming. Validate XAML, reflection, serializers, and third-party libraries on published output.", info.path))

    if info.allow_unsafe_blocks:
        findings.append(Finding("info", "UNSAFE_CODE_ENABLED", "Project enables unsafe code; confirm the native or performance requirement and review trust boundaries.", info.path))

    return info


def inspect_project_graph(root: Path, projects: list[ProjectInfo], findings: list[Finding]) -> None:
    project_by_path = {project.path: project for project in projects}
    graph: dict[str, list[str]] = {project.path: [] for project in projects}

    for project in projects:
        project_file = root / project.path
        for reference in project.project_references:
            if "$(" in reference or "@(" in reference:
                findings.append(Finding("info", "PROJECT_REFERENCE_DYNAMIC", f"ProjectReference uses an MSBuild expression and was not resolved statically: {reference}", project.path))
                continue
            target = (project_file.parent / reference).resolve()
            try:
                target_rel = target.relative_to(root).as_posix()
            except ValueError:
                findings.append(Finding("error", "PROJECT_REFERENCE_OUTSIDE_ROOT", f"ProjectReference leaves the inspected repository: {reference}", project.path))
                continue
            if not target.is_file():
                findings.append(Finding("error", "PROJECT_REFERENCE_MISSING", f"ProjectReference target does not exist: {target_rel}", project.path))
                continue
            project.resolved_project_references.append(target_rel)
            if target_rel in project_by_path:
                graph[project.path].append(target_rel)

    state: dict[str, int] = {node: 0 for node in graph}
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
        body = nodes[:-1]
        rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
        return min(rotations)

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for target in sorted(graph[node]):
            if state[target] == 0:
                visit(target)
            elif state[target] == 1:
                index = stack.index(target)
                cycle = stack[index:] + [target]
                key = canonical_cycle(cycle)
                if key not in cycles:
                    cycles.add(key)
                    findings.append(Finding("error", "PROJECT_REFERENCE_CYCLE", "Project reference cycle: " + " -> ".join(cycle), node))
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if state[node] == 0:
            visit(node)
