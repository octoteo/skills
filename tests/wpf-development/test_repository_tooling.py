from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load("validate_skill_tests", ROOT / "tools" / "validate_skill.py")
packager = load("package_skill_tests", ROOT / "tools" / "package_skill.py")


class RepositoryToolingTests(unittest.TestCase):
    def copy_skill(self, root: Path) -> Path:
        destination = root / "wpf-development"
        shutil.copytree(ROOT / "wpf-development", destination)
        return destination

    def test_current_skill_validates(self) -> None:
        self.assertEqual(validator.validate(ROOT / "wpf-development"), [])

    def test_missing_reference_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = self.copy_skill(Path(temp))
            (skill / "references" / "dotnet10.md").unlink()
            errors = validator.validate(skill)
            self.assertTrue(any("referenced file is missing" in item for item in errors))

    def test_secret_file_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = self.copy_skill(Path(temp))
            (skill / ".env").write_text("API_KEY=not-a-real-secret-value", encoding="utf-8")
            errors = validator.validate(skill)
            self.assertTrue(any("hidden files" in item or "credential-like" in item for item in errors))

    def test_symlink_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = self.copy_skill(Path(temp))
            target = skill / "SKILL.md"
            link = skill / "references" / "linked.md"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")
            errors = validator.validate(skill)
            self.assertTrue(any("symbolic links" in item for item in errors))

    def test_package_is_deterministic_and_has_single_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            zip_one, checksum_one, manifest_one = packager.create_package(ROOT / "wpf-development", first)
            for path in (ROOT / "wpf-development").rglob("*"):
                if path.is_file():
                    path.touch()
            zip_two, checksum_two, manifest_two = packager.create_package(ROOT / "wpf-development", second)
            self.assertEqual(hashlib.sha256(zip_one.read_bytes()).hexdigest(), hashlib.sha256(zip_two.read_bytes()).hexdigest())
            self.assertEqual(checksum_one.read_text(encoding="ascii"), checksum_two.read_text(encoding="ascii"))
            self.assertEqual(json.loads(manifest_one.read_text(encoding="utf-8")), json.loads(manifest_two.read_text(encoding="utf-8")))
            with zipfile.ZipFile(zip_one) as archive:
                names = archive.namelist()
                self.assertTrue(names)
                self.assertTrue(all(name.startswith("wpf-development/") for name in names))
                self.assertFalse(any("tests/" in name or "tools/" in name for name in names))


if __name__ == "__main__":
    unittest.main()
