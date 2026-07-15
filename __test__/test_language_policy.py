"""Tests for scripts/check_language.py — the English-only policy gate.

Policy (AGENTS.md): Russian is allowed only in the root README.md,
__test__/README.md and audit reports under _audit/; everywhere else the text
must be English, with explicit per-line waivers for Unicode test data.
"""

from __future__ import annotations

import subprocess
import sys

from .helpers import ROOT, TempDirTestCase, sandboxed_env

SCRIPT = ROOT / "scripts" / "check_language.py"

RU_LINE = "Это русский текст.\n"  # non-english-ok: the scanner's own test sample


class TestLanguagePolicy(TempDirTestCase):
    def run_scan(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            env=sandboxed_env(),
            check=False,
        )

    def write(self, rel: str, content: str) -> None:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_clean_tree_passes(self):
        self.write("skills/demo/SKILL.md", "# demo\n\nAll English here.\n")
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cyrillic_text_is_flagged_with_path_and_line(self):
        self.write("skills/demo/ORIGIN.yaml", "# comment\n# " + RU_LINE)
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 1)
        self.assertIn("skills/demo/ORIGIN.yaml:2:", result.stdout)

    def test_allowlisted_locations_pass(self):
        self.write("README.md", RU_LINE)
        self.write("__test__/README.md", RU_LINE)
        self.write("_audit/2026-01-01-report.md", RU_LINE)
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_readme_outside_root_is_not_allowlisted(self):
        self.write("skills/demo/data/README.md", RU_LINE)
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 1)

    def test_waiver_with_reason_passes_without_reason_fails(self):
        self.write(
            "with_reason.py",
            'x = "тест"  # non-english-ok: unicode fixture\n',  # non-english-ok: sample under test
        )
        self.assertEqual(self.run_scan(str(self.tmp)).returncode, 0)
        self.write(
            "without_reason.py",
            'y = "тест"  # non-english-ok:\n',  # non-english-ok: sample under test
        )
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 1)
        self.assertIn("without_reason.py:1:", result.stdout)

    def test_binary_files_are_skipped(self):
        (self.tmp / "blob.bin").write_bytes("бинарь".encode("utf-16") + b"\xff\xfe\x00")  # non-english-ok: binary sample
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_skip_dirs_are_not_scanned(self):
        self.write("mutants/generated.py", RU_LINE)
        self.write("pkg.egg-info/PKG-INFO", RU_LINE)
        result = self.run_scan(str(self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_root_is_a_usage_error(self):
        result = self.run_scan(str(self.tmp / "nope"))
        self.assertEqual(result.returncode, 2)

    def test_too_many_arguments_is_a_usage_error(self):
        result = self.run_scan(str(self.tmp), str(self.tmp))
        self.assertEqual(result.returncode, 2)

    def test_the_repository_itself_is_clean(self):
        # The gate that enforces the policy on this very repo.
        result = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    import unittest

    unittest.main()
