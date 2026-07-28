"""Contract and execution tests for the opt-in skill eval runner."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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

    def _not_matches_manifest(self, pattern: object) -> Path:
        manifest = self.tmp / "not-matches.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skill": "example-skill",
                    "platforms": ["universal"],
                    "cases": [
                        {
                            "id": "unconditional",
                            "kind": "behavior",
                            "requirement": "the verdict must not be handed down flat",
                            "prompt": "The reviewer is right, move the test.",
                            "expect": {"exit_code": 0, "stdout_not_matches": pattern},
                        },
                        {
                            "id": "conditional",
                            "kind": "behavior",
                            "requirement": "the same words under a condition are allowed",
                            "prompt": "Under London the reviewer is right about the label.",
                            "expect": {"exit_code": 0, "stdout_not_matches": pattern},
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_forbidden_pattern_separates_a_flat_claim_from_a_conditional_one(self):
        # A plain stdout_not_contains ban cannot tell "the reviewer is right"
        # used as a verdict from the same words inside a school-conditional
        # clause; an anchored pattern can, which is why the field exists.
        manifest = self._not_matches_manifest(["(?i)^\\W*the reviewer is right"])
        command = f'{sys.executable} -c "import sys; print(sys.argv[1])" {{prompt}}'
        result = self.run_eval(
            "--platform",
            "universal",
            "--command",
            command,
            str(manifest),
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL example-skill:unconditional#1", result.stderr)
        self.assertIn("matches forbidden pattern", result.stderr)
        self.assertIn("PASS example-skill:conditional#1", result.stdout)

    def test_invalid_forbidden_pattern_is_rejected(self):
        manifest = self._not_matches_manifest(["(unbalanced"])
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid regex", result.stderr)

    def test_forbidden_patterns_must_be_a_list_of_strings(self):
        manifest = self._not_matches_manifest("not a list")
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("stdout_not_matches must be a list of strings", result.stderr)

    def _echo_manifest(self, case_id: str = "echoed") -> Path:
        manifest = self.tmp / "echo.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skill": "example-skill",
                    "platforms": ["universal"],
                    "cases": [
                        {
                            "id": case_id,
                            "kind": "behavior",
                            "requirement": "runner contract",
                            "prompt": "ANSWER",
                            "expect": {"exit_code": 0, "stdout_contains": ["ANSWER"]},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_save_output_keeps_one_harness_answer_per_attempt(self):
        # A verdict names the oracle that missed, not what the harness said,
        # and the temporary project is gone by then; without the saved answer
        # a failure can only be read by running the case again.
        manifest = self._echo_manifest()
        outdir = self.tmp / "answers"
        command = f'{sys.executable} -c "import sys; print(sys.argv[1])" {{prompt}}'
        result = self.run_eval(
            "--platform",
            "universal",
            "--command",
            command,
            "--repeat",
            "2",
            "--save-output",
            str(outdir),
            str(manifest),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = sorted(p.name for p in outdir.iterdir())
        self.assertEqual(saved, ["example-skill--echoed--1.txt", "example-skill--echoed--2.txt"])
        self.assertEqual(
            (outdir / "example-skill--echoed--1.txt").read_text(encoding="utf-8").strip(),
            "ANSWER",
        )

    def test_nothing_is_written_without_save_output(self):
        manifest = self._echo_manifest()
        command = f'{sys.executable} -c "import sys; print(sys.argv[1])" {{prompt}}'
        result = self.run_eval(
            "--platform",
            "universal",
            "--command",
            command,
            str(manifest),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["echo.json"])

    def test_case_id_that_would_escape_the_output_directory_is_rejected(self):
        manifest = self._echo_manifest("../escaped")
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn(".id must match", result.stderr)


if __name__ == "__main__":
    import unittest

    unittest.main()
