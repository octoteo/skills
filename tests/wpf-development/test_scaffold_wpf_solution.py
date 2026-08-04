from __future__ import annotations

import importlib.util
import tempfile
import unittest
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "wpf-development" / "scripts" / "scaffold_wpf_solution.py"
spec = importlib.util.spec_from_file_location("scaffold_wpf_solution", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ScaffoldWpfSolutionTests(unittest.TestCase):
    def test_builds_expected_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            commands = module.build_commands(Path(temp), "Domec.DWF", "slnx", "10.0.8", "8.4.0")
            flattened = [command.args for command in commands]
            self.assertIn(("dotnet", "new", "wpf", "-n", "Domec.DWF.App", "-o", "src/Domec.DWF.App", "--framework", "net10.0"), flattened)
            self.assertTrue(any("Microsoft.Extensions.Hosting" in command for command in flattened))
            self.assertTrue(any("CommunityToolkit.Mvvm" in command for command in flattened))

    def test_rejects_invalid_name(self) -> None:
        with self.assertRaises(ValueError):
            module.sanitize_name("bad name")


if __name__ == "__main__":
    unittest.main()
