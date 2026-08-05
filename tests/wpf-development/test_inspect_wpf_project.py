from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "wpf-development" / "scripts" / "inspect_wpf_project.py"
spec = importlib.util.spec_from_file_location("inspect_wpf_project", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class InspectWpfProjectTests(unittest.TestCase):
    def test_detects_wpf_and_net10_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net9.0-windows</TargetFramework><UseWPF>true</UseWPF><UseWindowsForms>true</UseWindowsForms></PropertyGroup></Project>', encoding="utf-8")
            (root / "App.xaml").write_text('<Application StartupUri="MainWindow.xaml"><Application.Resources /></Application>', encoding="utf-8")
            (root / "MainWindow.xaml").write_text('<Grid><Grid.ColumnDefinitions /><TextBlock Foreground="{DynamicResource MissingBrush}" /></Grid>', encoding="utf-8")
            (root / "Worker.cs").write_text("class Worker { void Run() { Task.Delay(1).Wait(); } }", encoding="utf-8")
            report = module.inspect_repository(root)
            codes = {item["code"] for item in report["findings"]}
            self.assertEqual(report["summary"]["wpf_project_count"], 1)
            self.assertIn("WPF_NOT_NET10", codes)
            self.assertIn("WPF_WINFORMS_INTEROP", codes)
            self.assertIn("EMPTY_GRID_DEFINITIONS", codes)
            self.assertIn("DYNAMIC_RESOURCE_REVIEW", codes)
            self.assertIn("STARTUP_URI", codes)
            self.assertIn("SYNC_OVER_ASYNC", codes)

    def test_markdown_report_contains_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = module.inspect_repository(Path(temp))
            text = module.render_markdown(report)
            self.assertIn("# WPF Project Inspection", text)
            self.assertIn("NO_PROJECTS", text)

    def test_strict_mode_returns_two_for_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "App.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net10.0-windows</TargetFramework><UseWPF>true</UseWPF></PropertyGroup></Project>', encoding="utf-8")
            (root / "MainWindow.xaml").write_text("<Grid><Grid.RowDefinitions /></Grid>", encoding="utf-8")
            code = module.main([str(root), "--format", "json", "--strict"])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
