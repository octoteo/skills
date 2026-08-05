from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "openai_eval_collect.py"
spec = importlib.util.spec_from_file_location("openai_eval_collect_tests", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeClient:
    api_base = "https://api.openai.test/v1"

    def __init__(self) -> None:
        self.payloads = []

    def post_json(self, path, payload):
        self.payloads.append((path, payload))
        skilled = bool(payload["tools"][0]["environment"].get("skills"))
        prompt = payload["input"]
        output = []
        if skilled:
            output.append(
                {
                    "type": "shell_call",
                    "action": {
                        "commands": [
                            "cat /mnt/data/skills/wpf-development/SKILL.md && sed -n '1,80p' /mnt/data/skills/wpf-development/references/security.md"
                        ]
                    },
                }
            )
        output.append(
            {
                "type": "message",
                "content": [{"type": "output_text", "text": f"answer:{prompt}:{'skilled' if skilled else 'baseline'}"}],
            }
        )
        return {
            "id": f"resp-{len(self.payloads)}",
            "model": payload["model"],
            "output": output,
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }


class OpenAIEvalCollectorTests(unittest.TestCase):
    def create_fixture(self, root: Path):
        eval_dir = root / "evals" / "wpf-development"
        cases = eval_dir / "cases"
        cases.mkdir(parents=True)
        (eval_dir / "eval.yaml").write_text(
            json.dumps({"schema_version": 1, "name": "wpf-development", "stimuli_path": "cases"}),
            encoding="utf-8",
        )
        (cases / "positive.json").write_text(
            json.dumps(
                {
                    "name": "positive",
                    "category": "create",
                    "prompt": "Create a production WPF app.",
                    "expect_activation": True,
                    "critical": True,
                    "rubric": ["A", "B", "C"],
                }
            ),
            encoding="utf-8",
        )
        (cases / "negative.json").write_text(
            json.dumps(
                {
                    "name": "negative",
                    "category": "negative-routing",
                    "prompt": "Create an Avalonia app.",
                    "expect_activation": False,
                    "critical": False,
                    "rubric": [],
                }
            ),
            encoding="utf-8",
        )
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps({"archive_sha256": "a" * 64, "skill_content_sha256": "b" * 64}), encoding="utf-8"
        )
        receipt = root / "receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skill_id": "skill_test",
                    "skill_version": 3,
                    "package_sha256": "a" * 64,
                    "skill_content_sha256": "b" * 64,
                }
            ),
            encoding="utf-8",
        )
        return eval_dir / "eval.yaml", receipt, manifest

    def test_payload_controls_only_skill_attachment(self):
        baseline = module.build_response_payload("model", "prompt", None, None, "medium", 1000)
        skilled = module.build_response_payload("model", "prompt", "skill_1", 2, "medium", 1000)
        self.assertNotIn("skills", baseline["tools"][0]["environment"])
        self.assertEqual(
            skilled["tools"][0]["environment"]["skills"],
            [{"type": "skill_reference", "skill_id": "skill_1", "version": 2}],
        )
        baseline_environment = baseline["tools"][0]["environment"].copy()
        skilled_environment = skilled["tools"][0]["environment"].copy()
        skilled_environment.pop("skills")
        self.assertEqual(baseline_environment, skilled_environment)

    def test_extracts_text_and_shell_commands(self):
        response = {
            "output": [
                {"type": "shell_call", "action": {"commands": ["cat /x/SKILL.md", "ls"]}},
                {"type": "message", "content": [{"type": "output_text", "text": "hello"}]},
            ]
        }
        self.assertEqual(module.extract_output_text(response), "hello")
        self.assertEqual(module.extract_shell_commands(response), ["cat /x/SKILL.md", "ls"])

    def test_activation_requires_manifest_or_named_resource_read(self):
        self.assertEqual(module.activation_evidence(["ls /tmp"], "wpf-development"), [])
        self.assertTrue(module.activation_evidence(["cat /mnt/skills/x/SKILL.md"], "wpf-development"))
        self.assertTrue(
            module.activation_evidence(
                ["Get-Content C:/skills/wpf-development/references/security.md"],
                "wpf-development",
            )
        )

    def test_receipt_binds_manifest_and_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "skill.zip"
            package.write_bytes(b"zip")
            package_hash = module.sha256_file(package)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"archive_sha256": package_hash, "skill_content_sha256": "b" * 64}),
                encoding="utf-8",
            )
            receipt = module.create_receipt(
                {"id": "skill_abc", "latest_version": 4, "object": "skill"},
                package,
                manifest,
                module.DEFAULT_API_BASE,
                None,
            )
            self.assertEqual(receipt["skill_id"], "skill_abc")
            self.assertEqual(receipt["skill_version"], 4)
            self.assertEqual(receipt["package_sha256"], package_hash)

    def test_collects_and_resumes_without_duplicate_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_spec, receipt, manifest = self.create_fixture(root)
            output = root / "run"
            client = FakeClient()
            responses, completed = module.collect_responses(
                client,
                eval_spec,
                receipt,
                manifest,
                output,
                "run-1",
                "model-snapshot",
                "medium",
                1000,
                False,
                [],
                0,
            )
            self.assertEqual(completed, 4)
            records = module.read_jsonl(responses)
            skilled = [r for r in records if r["variant"] == "skilled"]
            self.assertTrue(all(r["activated"] for r in skilled))
            self.assertTrue(all(r["package_sha256"] == "a" * 64 for r in skilled))
            self.assertEqual(len(list((output / "raw").glob("*.json"))), 4)
            _, second_completed = module.collect_responses(
                client,
                eval_spec,
                receipt,
                manifest,
                output,
                "run-1",
                "model-snapshot",
                "medium",
                1000,
                True,
                [],
                0,
            )
            self.assertEqual(second_completed, 0)
            self.assertEqual(len(client.payloads), 4)

    def test_dry_run_does_not_require_api_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_spec, receipt, manifest = self.create_fixture(root)
            with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                code = module.main(
                    [
                        "collect",
                        "--spec",
                        str(eval_spec),
                        "--receipt",
                        str(receipt),
                        "--manifest",
                        str(manifest),
                        "--output",
                        str(root / "run"),
                        "--run-id",
                        "run-1",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertFalse((root / "run").exists())

    def test_execute_requires_environment_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_spec, receipt, manifest = self.create_fixture(root)
            with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()):
                code = module.main(
                    [
                        "collect",
                        "--spec",
                        str(eval_spec),
                        "--receipt",
                        str(receipt),
                        "--manifest",
                        str(manifest),
                        "--output",
                        str(root / "run"),
                        "--run-id",
                        "run-1",
                        "--execute",
                    ]
                )
            self.assertEqual(code, 1)

    def test_api_key_is_not_written_to_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_spec, receipt, manifest = self.create_fixture(root)
            output = root / "run"
            secret = "unit-test-secret-value"
            client = FakeClient()
            module.collect_responses(
                client, eval_spec, receipt, manifest, output, "run-1", "model", "medium", 1000, False, [], 1
            )
            combined = "".join(path.read_text(encoding="utf-8") for path in output.rglob("*.json*"))
            self.assertNotIn(secret, combined)

    def test_http_client_retries_rate_limit(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"id":"ok"}'

        calls = []

        def opener(request, timeout):
            calls.append(request)
            if len(calls) == 1:
                raise urllib.error.HTTPError(
                    request.full_url, 429, "rate", {"Retry-After": "0"}, io.BytesIO(b'{"error":"rate"}')
                )
            return Response()

        client = module.OpenAIHttpClient("test-key", opener=opener, sleeper=lambda _: None, max_retries=1)
        result = client.post_json("/responses", {"model": "m"})
        self.assertEqual(result, {"id": "ok"})
        self.assertEqual(len(calls), 2)

    def test_multipart_uses_files_field_without_key_material(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "skill.zip"
            package.write_bytes(b"archive-bytes")
            body, content_type = module.encode_multipart("files", package)
            self.assertIn(b'name="files"', body)
            self.assertIn(b'filename="skill.zip"', body)
            self.assertIn(b"archive-bytes", body)
            self.assertNotIn(b"OPENAI_API_KEY", body)
            self.assertTrue(content_type.startswith("multipart/form-data; boundary="))

    def test_new_version_receipt_preserves_existing_skill_id(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "skill.zip"
            package.write_bytes(b"archive")
            receipt = module.create_receipt(
                {"id": "skill_version_object", "version": 7},
                package,
                None,
                module.DEFAULT_API_BASE,
                "skill_existing",
            )
            self.assertEqual(receipt["skill_id"], "skill_existing")
            self.assertEqual(receipt["skill_version"], 7)

    def test_manifest_mismatch_blocks_collection_before_api_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            eval_spec, receipt, manifest = self.create_fixture(root)
            manifest.write_text(json.dumps({"archive_sha256": "c" * 64}), encoding="utf-8")
            client = FakeClient()
            with self.assertRaises(module.EvaluationError):
                module.collect_responses(
                    client,
                    eval_spec,
                    receipt,
                    manifest,
                    root / "run",
                    "run-1",
                    "model",
                    "medium",
                    1000,
                    False,
                    [],
                    0,
                )
            self.assertEqual(client.payloads, [])

    def test_manual_workflow_encrypts_private_evidence(self):
        workflow = (ROOT / ".github" / "workflows" / "model-eval.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertIn("EVAL_ARTIFACT_PASSPHRASE", workflow)
        self.assertIn("openssl enc -aes-256-cbc", workflow)
        self.assertIn("Upload encrypted evidence only", workflow)
        self.assertNotIn("--api-key", workflow)


if __name__ == "__main__":
    unittest.main()
