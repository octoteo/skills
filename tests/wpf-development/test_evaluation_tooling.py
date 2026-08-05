from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
SPEC = ROOT / "evals" / "wpf-development" / "eval.yaml"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


evaluator = load("evaluate_skill_tests", ROOT / "tools" / "evaluate_skill.py")
packager = load("package_skill_eval_tests", ROOT / "tools" / "package_skill.py")
release_checker = load("check_release_tests", ROOT / "tools" / "check_release.py")


class EvaluationToolingTests(unittest.TestCase):
    def create_completed_run(self, root: Path):
        run_dir = root / "run"
        evaluator.create_run_template(
            SPEC,
            run_dir,
            "test-run",
            "model-test",
            "model-test",
        )
        spec, cases = evaluator.load_spec(SPEC)
        responses_path = run_dir / "responses.jsonl"
        records = evaluator.read_jsonl(responses_path)
        case_map = {case.name: case for case in cases}
        for record in records:
            case = case_map[record["case"]]
            if record["variant"] == "skilled":
                record["activated"] = case.expect_activation
            else:
                record["activated"] = None
            if case.expect_activation:
                record["response"] = (
                    f"{record['variant']} response for {case.name} with concrete validation and recovery steps."
                )
            else:
                record["response"] = ""
        evaluator.write_jsonl(responses_path, records)

        judging_dir = run_dir / "judging"
        _, key_path, judgments_path = evaluator.create_blind_materials(
            SPEC,
            responses_path,
            judging_dir,
            seed=7,
        )
        key = evaluator.read_json(key_path)
        judgments = evaluator.read_jsonl(judgments_path)
        rubric_lengths = {case.name: len(case.rubric) for case in cases if case.expect_activation}
        for record in judgments:
            mapping = key["pairs"][record["case"]]
            for label, variant in mapping.items():
                score = 2 if variant == "skilled" else 1
                record["scores"][label] = [score] * rubric_lengths[record["case"]]
                record["critical_failure"][label] = False
            record["preferred"] = next(label for label, variant in mapping.items() if variant == "skilled")
        evaluator.write_jsonl(judgments_path, judgments)

        package_dir = root / "package"
        _, _, manifest_path = packager.create_package(ROOT / "wpf-development", package_dir)
        return responses_path, key_path, judgments_path, manifest_path

    def test_spec_has_production_sized_case_set(self) -> None:
        _, cases = evaluator.load_spec(SPEC)
        self.assertEqual(len(cases), 25)
        self.assertEqual(sum(case.expect_activation for case in cases), 18)
        self.assertEqual(sum(not case.expect_activation for case in cases), 7)

    def test_init_creates_two_records_per_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            _, responses = evaluator.create_run_template(SPEC, output, "run-1", "base", "skilled")
            _, cases = evaluator.load_spec(SPEC)
            records = evaluator.read_jsonl(responses)
            self.assertEqual(len(records), len(cases) * 2)
            self.assertEqual({record["variant"] for record in records}, {"baseline", "skilled"})

    def test_blinding_is_deterministic_and_hides_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            responses, _, _, _ = self.create_completed_run(root)
            first = root / "first"
            second = root / "second"
            evaluator.create_blind_materials(SPEC, responses, first, seed=11)
            evaluator.create_blind_materials(SPEC, responses, second, seed=11)
            self.assertEqual(
                (first / "blind-pairs.jsonl").read_bytes(),
                (second / "blind-pairs.jsonl").read_bytes(),
            )
            public_text = (first / "blind-pairs.jsonl").read_text(encoding="utf-8")
            self.assertNotIn('"variant"', public_text)
            self.assertNotIn('"skilled"', public_text)
            self.assertNotIn('"baseline"', public_text)

    def test_complete_real_like_run_passes_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            responses, key, judgments, manifest = self.create_completed_run(root)
            _, _, summary = evaluator.score_evaluation(
                SPEC,
                responses,
                key,
                judgments,
                manifest,
                root / "result",
                version="1.0.0",
                source_commit="abc123",
                synthetic=False,
                bootstrap_iterations=500,
                created_at="2026-08-05T00:00:00+00:00",
            )
            self.assertTrue(summary["release_gate"]["passed"])
            self.assertEqual(summary["evaluation"]["routing"]["false_positive"], 0)
            self.assertEqual(summary["evaluation"]["capability"]["losses"], 0)

    def test_synthetic_run_never_authorizes_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            responses, key, judgments, manifest = self.create_completed_run(root)
            _, _, summary = evaluator.score_evaluation(
                SPEC,
                responses,
                key,
                judgments,
                manifest,
                root / "result",
                version="1.0.0",
                source_commit="abc123",
                synthetic=True,
                bootstrap_iterations=500,
            )
            self.assertFalse(summary["release_gate"]["passed"])
            self.assertIn("synthetic_run", summary["release_gate"]["failed_gates"])

    def test_missing_positive_response_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir = root / "run"
            evaluator.create_run_template(SPEC, run_dir, "run-1", "base", "skilled")
            records = evaluator.read_jsonl(run_dir / "responses.jsonl")
            for record in records:
                if record["variant"] == "skilled":
                    record["activated"] = False
            evaluator.write_jsonl(run_dir / "responses.jsonl", records)
            with self.assertRaises(evaluator.EvaluationError):
                evaluator.create_blind_materials(SPEC, run_dir / "responses.jsonl", root / "blind", seed=0)

    def test_prerelease_does_not_require_model_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, manifest = packager.create_package(ROOT / "wpf-development", root / "package")
            result = release_checker.validate_release(
                "wpf-development-v0.9.0-beta.1",
                manifest,
                root / "results",
            )
            self.assertTrue(result["prerelease"])
            self.assertIsNone(result["evaluation_summary"])

    def test_stable_release_requires_matching_passing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            responses, key, judgments, manifest = self.create_completed_run(root)
            result_dir = root / "results" / "wpf-development" / "1.0.0"
            evaluator.score_evaluation(
                SPEC,
                responses,
                key,
                judgments,
                manifest,
                result_dir,
                version="1.0.0",
                source_commit="abc123",
                synthetic=False,
                bootstrap_iterations=500,
            )
            result = release_checker.validate_release(
                "wpf-development-v1.0.0",
                manifest,
                root / "results",
            )
            self.assertFalse(result["prerelease"])
            self.assertTrue(result["evaluation_summary"].endswith("summary.json"))

    def test_stable_release_rejects_package_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            responses, key, judgments, manifest = self.create_completed_run(root)
            result_dir = root / "results" / "wpf-development" / "1.0.0"
            evaluator.score_evaluation(
                SPEC,
                responses,
                key,
                judgments,
                manifest,
                result_dir,
                version="1.0.0",
                source_commit="abc123",
                synthetic=False,
                bootstrap_iterations=500,
            )
            summary_path = result_dir / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["package"]["archive_sha256"] = "0" * 64
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaises(release_checker.ReleaseError):
                release_checker.validate_release(
                    "wpf-development-v1.0.0",
                    manifest,
                    root / "results",
                )


if __name__ == "__main__":
    unittest.main()
