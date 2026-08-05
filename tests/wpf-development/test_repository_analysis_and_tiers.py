from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[2] / "wpf-development" / "scripts"


def load(name: str):
    path = ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inspector = load("inspect_wpf_project")
scaffold = load("scaffold_wpf_solution")


class RepositoryModelTests(unittest.TestCase):
    def test_inherits_directory_build_props_and_central_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Directory.Build.props").write_text(
                '<Project><PropertyGroup><TargetFramework>net10.0-windows</TargetFramework><UseWPF>true</UseWPF><Nullable>enable</Nullable></PropertyGroup></Project>',
                encoding="utf-8",
            )
            (root / "Directory.Packages.props").write_text(
                '<Project><ItemGroup><PackageVersion Include="Microsoft.Extensions.Hosting" Version="10.0.1" /></ItemGroup></Project>',
                encoding="utf-8",
            )
            app = root / "src" / "App"
            app.mkdir(parents=True)
            (app / "App.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><PackageReference Include="Microsoft.Extensions.Hosting" /></ItemGroup></Project>',
                encoding="utf-8",
            )
            report = inspector.inspect_repository(root)
            project = report["projects"][0]
            self.assertEqual(report["summary"]["wpf_project_count"], 1)
            self.assertEqual(project["target_frameworks"], ["net10.0-windows"])
            self.assertEqual(project["package_references"][0]["version"], "10.0.1")
            self.assertEqual(project["package_references"][0]["source"], "central")
            self.assertFalse(any(item["code"] == "WPF_NO_TFM" for item in report["findings"]))

    def test_detects_missing_reference_and_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "A.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup><ItemGroup><ProjectReference Include="B.csproj" /><ProjectReference Include="Missing.csproj" /></ItemGroup></Project>',
                encoding="utf-8",
            )
            (root / "B.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup><ItemGroup><ProjectReference Include="A.csproj" /></ItemGroup></Project>',
                encoding="utf-8",
            )
            report = inspector.inspect_repository(root)
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("PROJECT_REFERENCE_MISSING", codes)
            self.assertIn("PROJECT_REFERENCE_CYCLE", codes)

    def test_secret_finding_never_discloses_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            secret = "super-secret-value"
            (root / "appsettings.json").write_text(
                '{"Authentication":{"ClientSecret":"' + secret + '"}}',
                encoding="utf-8",
            )
            report = inspector.inspect_repository(root)
            messages = [item["message"] for item in report["findings"] if item["code"] == "POTENTIAL_PLAINTEXT_SECRET"]
            self.assertEqual(len(messages), 1)
            self.assertIn("Authentication.ClientSecret", messages[0])
            self.assertNotIn(secret, messages[0])


class ArchitectureTierTests(unittest.TestCase):
    def rendered(self, tier: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temp:
            return [" ".join(command.args) for command in scaffold.build_commands(Path(temp), "Domec.DWF", "slnx", "10.0.1", "8.4.0", tier)]

    def test_compact_contains_only_app_and_tests(self) -> None:
        rendered = self.rendered("compact")
        self.assertTrue(any("dotnet new wpf" in item for item in rendered))
        self.assertFalse(any("Infrastructure" in item for item in rendered))
        self.assertFalse(any("Modules.Sample" in item for item in rendered))

    def test_product_preserves_layered_topology(self) -> None:
        rendered = self.rendered("product")
        self.assertTrue(any("Domec.DWF.Core" in item for item in rendered))
        self.assertTrue(any("Domec.DWF.Infrastructure" in item for item in rendered))
        self.assertTrue(any("dotnet test" in item and "--configuration Release" in item for item in rendered))

    def test_modular_adds_contracts_and_compile_time_module(self) -> None:
        rendered = self.rendered("modular")
        self.assertTrue(any("Modules.Abstractions" in item for item in rendered))
        self.assertTrue(any("Modules.Sample" in item for item in rendered))
        self.assertTrue(any("Modules.Sample" in item and "Modules.Abstractions" in item and " reference " in f" {item} " for item in rendered))

    def test_rejects_unsafe_names(self) -> None:
        for value in ("bad name", "Bad..Name", "Name.", "CON.Product"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scaffold.sanitize_name(value)

    def test_failure_preserves_preexisting_empty_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            root = destination / "Sample.Product"
            root.mkdir()

            def fail_first(command):
                (root / "partial.txt").write_text("partial", encoding="utf-8")
                raise scaffold.subprocess.CalledProcessError(7, command.args)

            with mock.patch.object(scaffold.platform, "system", return_value="Windows"), mock.patch.object(scaffold, "dotnet_major_version", return_value=10), mock.patch.object(scaffold, "run_command", side_effect=fail_first):
                code = scaffold.main([str(destination), "--name", "Sample.Product", "--execute"])
            self.assertEqual(code, 7)
            self.assertTrue((root / "partial.txt").is_file())


if __name__ == "__main__":
    unittest.main()
