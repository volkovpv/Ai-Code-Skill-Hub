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

    def _tiered_manifest(self, tiers: object) -> Path:
        manifest = self.tmp / "tiered.json"
        data = json.loads(self._echo_manifest().read_text(encoding="utf-8"))
        data["tiers"] = tiers
        manifest.write_text(json.dumps(data), encoding="utf-8")
        return manifest

    def _echo_argv_command(self, *placeholders: str) -> str:
        # Prints every argument, so the test can see what reached the harness.
        asked = " ".join("{%s}" % name for name in placeholders)
        return f'{sys.executable} -c "import sys; print(\'|\'.join(sys.argv[1:]))" {asked} {{prompt}}'

    def test_tier_selects_the_declared_environment_and_the_log_names_it(self):
        # A green run is green for one model at one effort; the log has to say which.
        manifest = self._tiered_manifest(
            {
                "gate": {"vendor": "anthropic", "model": "claude-opus-5", "effort": "medium"},
                "debug": {"vendor": "anthropic", "model": "claude-sonnet-5", "effort": "low"},
            }
        )
        for tier, model, effort in (
            ("gate", "claude-opus-5", "medium"),
            ("debug", "claude-sonnet-5", "low"),
        ):
            with self.subTest(tier=tier):
                outdir = self.tmp / f"answers-{tier}"
                result = self.run_eval(
                    "--platform", "universal",
                    "--tier", tier,
                    "--save-output", str(outdir),
                    "--command", self._echo_argv_command("model", "effort"),
                    str(manifest),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(
                    f"tier={tier} vendor=anthropic model={model} effort={effort}", result.stdout
                )
                # ...and the same pair actually reached the harness, not just the log.
                answer = (outdir / "example-skill--echoed--1.txt").read_text(encoding="utf-8")
                self.assertTrue(answer.startswith(f"{model}|{effort}|"), answer)

    def test_explicit_flags_override_the_declared_tier(self):
        manifest = self._tiered_manifest(
            {"gate": {"vendor": "anthropic", "model": "claude-sonnet-5", "effort": "medium"}}
        )
        result = self.run_eval(
            "--platform", "universal",
            "--model", "claude-opus-5",
            "--effort", "max",
            "--command", self._echo_argv_command("model", "effort"),
            str(manifest),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("model=claude-opus-5 effort=max", result.stdout)

    def test_declared_dial_without_a_placeholder_is_refused(self):
        # Otherwise the header names an environment the harness never received.
        manifest = self._tiered_manifest(
            {"gate": {"vendor": "anthropic", "model": "claude-sonnet-5", "effort": "medium"}}
        )
        for dial, given in (("model", "effort"), ("effort", "model")):
            with self.subTest(dial=dial):
                result = self.run_eval(
                    "--platform", "universal",
                    "--command", self._echo_argv_command(given),
                    str(manifest),
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(f"no {{{dial}}} placeholder", result.stderr)

    def test_placeholder_without_a_value_is_refused(self):
        for dial in ("model", "effort"):
            with self.subTest(dial=dial):
                manifest = self._echo_manifest()  # no tiers block
                result = self.run_eval(
                    "--platform", "universal",
                    "--command", self._echo_argv_command(dial),
                    str(manifest),
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(f"no {dial} is set", result.stderr)

    def test_manifest_without_tiers_still_runs_on_the_harness_default(self):
        manifest = self._echo_manifest()
        command = f'{sys.executable} -c "import sys; print(sys.argv[1])" {{prompt}}'
        result = self.run_eval("--platform", "universal", "--command", command, str(manifest))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("model=(harness default) effort=(harness default)", result.stdout)

    def test_the_shell_effort_does_not_leak_into_the_harness(self):
        # The operator's own CLAUDE_EFFORT must not decide what a run measures.
        manifest = self._echo_manifest()
        command = (
            f'{sys.executable} -c "import os; print(os.environ.get(\'CLAUDE_EFFORT\', \'unset\'))"'
            " {prompt}"
        )
        outdir = self.tmp / "leak"
        env = sandboxed_env()
        env["CLAUDE_EFFORT"] = "max"
        subprocess.run(
            [
                sys.executable, str(RUNNER), "--platform", "universal",
                "--save-output", str(outdir), "--command", command, str(manifest),
            ],
            cwd=ROOT, capture_output=True, text=True, timeout=30, env=env, check=False,
        )
        answer = (outdir / "example-skill--echoed--1.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(answer, "unset")

    def test_unknown_tier_and_unknown_dial_are_rejected(self):
        cheap = self._tiered_manifest({"gate": {"model": "m"}, "cheap": {"model": "m"}})
        result = self.run_eval("--validate-only", str(cheap))
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown tiers: cheap", result.stderr)

        dial = self._tiered_manifest({"gate": {"model": "m", "temperature": "0"}})
        result = self.run_eval("--validate-only", str(dial))
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown dials in tiers.gate: temperature", result.stderr)

    def test_dial_values_must_be_non_empty_strings(self):
        for tiers in ({"gate": {"model": ""}}, {"gate": {"model": 5}}, {"gate": {}}, {}, "sonnet"):
            with self.subTest(tiers=tiers):
                result = self.run_eval("--validate-only", str(self._tiered_manifest(tiers)))
                self.assertEqual(result.returncode, 2)
                self.assertIn("tiers", result.stderr)

    def test_effort_level_is_validated_here_because_the_harness_fails_open(self):
        # `claude --effort` warns and silently uses its default on a bad value.
        manifest = self._tiered_manifest(
            {"gate": {"vendor": "anthropic", "model": "claude-sonnet-5", "effort": "highest"}}
        )
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("effort 'highest' is not accepted by model", result.stderr)

    def test_a_tier_that_does_not_name_its_vendor_is_rejected(self):
        # Model and effort mean nothing without the vendor whose ladder they
        # belong to: 'high' is a different setting for a different supplier.
        manifest = self._tiered_manifest({"gate": {"model": "claude-sonnet-5", "effort": "medium"}})
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("tiers.gate is missing vendor", result.stderr)

    def test_an_unknown_vendor_or_model_is_a_manifest_defect(self):
        for tier, fragment in (
            (
                {"vendor": "acme", "model": "claude-sonnet-5", "effort": "medium"},
                "unknown vendor 'acme'",
            ),
            (
                {"vendor": "anthropic", "model": "claude-sonnet-9", "effort": "medium"},
                "is not registered in vendors.yaml",
            ),
            (
                {"vendor": "openai", "model": "claude-sonnet-5", "effort": "medium"},
                "belongs to vendor 'anthropic'",
            ),
        ):
            with self.subTest(tier=tier):
                result = self.run_eval(
                    "--validate-only", str(self._tiered_manifest({"gate": tier}))
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(fragment, result.stderr)

    def test_a_level_the_vendor_has_but_the_model_does_not_is_rejected(self):
        # The model's own ladder decides, not the vendor's superset — otherwise
        # a green run would name a level that model never accepted.
        manifest = self._tiered_manifest(
            {"gate": {"vendor": "google", "model": "gemini-3.1-pro-preview", "effort": "minimal"}}
        )
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not accepted by model 'gemini-3.1-pro-preview'", result.stderr)

    def test_a_model_that_takes_no_effort_at_all_cannot_be_declared(self):
        manifest = self._tiered_manifest(
            {"gate": {"vendor": "anthropic", "model": "claude-haiku-4-5", "effort": "low"}}
        )
        result = self.run_eval("--validate-only", str(manifest))
        self.assertEqual(result.returncode, 2)
        self.assertIn("takes no effort level at all", result.stderr)

    def test_an_override_cannot_route_around_the_registry(self):
        manifest = self._tiered_manifest(
            {"gate": {"vendor": "anthropic", "model": "claude-sonnet-5", "effort": "medium"}}
        )
        result = self.run_eval(
            "--platform", "universal",
            "--effort", "highest",
            "--command", self._echo_argv_command("model", "effort"),
            str(manifest),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not accepted by model", result.stderr)

    def test_every_catalog_manifest_declares_the_whole_environment_for_both_tiers(self):
        # The point of the tiers is that no live run is implicitly on whatever
        # the CLI and the operator's own settings happen to default to.
        for path in sorted((ROOT / "__test__" / "evals").glob("*/cases.json")):
            with self.subTest(manifest=path.name):
                tiers = json.loads(path.read_text(encoding="utf-8")).get("tiers", {})
                self.assertEqual(sorted(tiers), ["debug", "gate"], path)
                for tier, dials in tiers.items():
                    self.assertEqual(sorted(dials), ["effort", "model", "vendor"], (path, tier))


if __name__ == "__main__":
    import unittest

    unittest.main()
