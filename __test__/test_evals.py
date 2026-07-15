"""Contract and execution tests for the opt-in skill eval runner."""

from __future__ import annotations

import json
import subprocess
import sys

from .helpers import ROOT, TempDirTestCase, sandboxed_env

RUNNER = ROOT / "scripts" / "run_skill_evals.py"
EVALS_DIR = ROOT / "__test__" / "evals"
EXAMPLE_CASES = EVALS_DIR / "example-skill" / "cases.json"


class TestEvalRunner(TempDirTestCase):
    def run_eval(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            env=sandboxed_env(),
            check=False,
        )

    def test_repository_manifest_is_valid(self):
        result = self.run_eval("--validate-only", str(EXAMPLE_CASES))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 case(s)", result.stdout)

    def test_every_catalog_eval_manifest_is_valid(self):
        manifests = sorted(EVALS_DIR.glob("*/cases.json"))
        self.assertGreaterEqual(len(manifests), 4, manifests)
        result = self.run_eval("--validate-only", *(str(m) for m in manifests))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_eval_manifests_exist_for_every_draft_skill_awaiting_the_gate(self):
        # The three split skills stay draft until the eval-gate passes; the
        # gate needs a manifest, so its absence would make "draft until evals
        # pass" unfalsifiable.
        for skill in ("typescript-coding", "hexagonal-service", "typescript-nestjs"):
            manifest = EVALS_DIR / skill / "cases.json"
            self.assertTrue(manifest.is_file(), manifest)
            kinds = {
                case["kind"]
                for case in json.loads(manifest.read_text(encoding="utf-8"))["cases"]
            }
            # positive/boundary cases are 'trigger'/'behavior'; conflicts are
            # behavior cases; 'negative' pins non-activation.
            self.assertEqual(kinds, {"trigger", "behavior", "negative"}, skill)

    def test_duplicate_case_ids_are_rejected(self):
        manifest = self.tmp / "duplicate.json"
        case = {
            "id": "same",
            "kind": "behavior",
            "requirement": "demo",
            "prompt": "demo",
            "expect": {"exit_code": 0},
        }
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skill": "example-skill",
                    "platforms": ["universal"],
                    "cases": [case, case],
                }
            ),
            encoding="utf-8",
        )
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate case id", result.stderr)

    def test_local_fake_harness_exercises_install_and_expectations(self):
        manifest = self.tmp / "local.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skill": "example-skill",
                    "platforms": ["universal"],
                    "cases": [
                        {
                            "id": "local",
                            "kind": "behavior",
                            "requirement": "runner contract",
                            "prompt": "SAFE",
                            "expect": {
                                "exit_code": 0,
                                "stdout_contains": ["SAFE"],
                                "stdout_not_contains": ["network"],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        command = f'{sys.executable} -c "import sys; print(sys.argv[1])" {{prompt}}'
        result = self.run_eval(
            "--platform",
            "universal",
            "--command",
            command,
            str(manifest),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS example-skill:local#1", result.stdout)


if __name__ == "__main__":
    import unittest

    unittest.main()
