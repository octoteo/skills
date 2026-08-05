from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[2] / "wpf-development" / "scripts" / "scaffold_wpf_solution.py"
spec = importlib.util.spec_from_file_location("scaffold_wpf_solution", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ScaffoldWpfSolutionTests(unittest.TestCase):
    def test_dry_run_builds_layered_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            commands = module.build_commands(Path(temp), "Domec.DWF", "slnx", "10.0.0", "8.4.0")
            rendered = [" ".join(command.args) for command in commands]
            self.assertTrue(any("dotnet new wpf" in item for item in rendered))
            self.assertTrue(any("Microsoft.Extensions.Hosting" in item for item in rendered))
            self.assertTrue(any("CommunityToolkit.Mvvm" in item for item in rendered))
            self.assertTrue(any("dotnet test" in item for item in rendered))

    def test_rejects_invalid_product_name(self) -> None:
        with self.assertRaises(ValueError):
            module.sanitize_name("bad name")

    def test_default_mode_does_not_execute_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(module, "run_command") as run:
            code = module.main([temp, "--name", "Sample.Product"])
            self.assertEqual(code, 0)
            run.assert_not_called()

    def test_execute_rejects_non_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(module.platform, "system", return_value="Linux"):
            code = module.main([temp, "--name", "Sample.Product", "--execute"])
            self.assertEqual(code, 1)

    def test_execute_cleans_partial_root_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            root = destination / "Sample.Product"
            def fail_first(command):
                root.mkdir(parents=True, exist_ok=True)
                (root / "partial.txt").write_text("partial", encoding="utf-8")
                raise module.subprocess.CalledProcessError(7, command.args)
            with mock.patch.object(module.platform, "system", return_value="Windows"), mock.patch.object(module, "dotnet_major_version", return_value=10), mock.patch.object(module, "run_command", side_effect=fail_first):
                code = module.main([str(destination), "--name", "Sample.Product", "--execute"])
            self.assertEqual(code, 7)
            self.assertFalse(root.exists())

    def test_keep_on_failure_preserves_partial_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            root = destination / "Sample.Product"
            def fail_first(command):
                root.mkdir(parents=True, exist_ok=True)
                (root / "partial.txt").write_text("partial", encoding="utf-8")
                raise module.subprocess.CalledProcessError(9, command.args)
            with mock.patch.object(module.platform, "system", return_value="Windows"), mock.patch.object(module, "dotnet_major_version", return_value=10), mock.patch.object(module, "run_command", side_effect=fail_first):
                code = module.main([str(destination), "--name", "Sample.Product", "--execute", "--keep-on-failure"])
            self.assertEqual(code, 9)
            self.assertTrue((root / "partial.txt").is_file())


if __name__ == "__main__":
    unittest.main()
