"""Dedicated tests for skills/example-skill (run via `skillctl test example-skill`).

Inputs come from the skill's own data layer (data/fixtures, data/examples),
so the tests double as evidence for the skill's accepted observations.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "example-skill"
SCRIPT = SKILL / "scripts" / "example.py"
FIXTURES = SKILL / "data" / "fixtures"
EXAMPLES = SKILL / "data" / "examples"

DOCS_DIFF = """\
diff --git a/docs/guide.md b/docs/guide.md
index 1111111..2222222 100644
--- a/docs/guide.md
+++ b/docs/guide.md
@@ -1 +1,2 @@
 # Guide
+More words.
"""


def run_script(stdin: str, cwd: Path) -> subprocess.CompletedProcess:
    # Sanitized environment: skill scripts must not need or see any secrets.
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestExampleSkillScript(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="example-skill-test-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_feature_example_matches_expected_output(self):
        diff = (EXAMPLES / "feature_change.diff").read_text(encoding="utf-8")
        expected = (EXAMPLES / "feature_change.expected").read_text(encoding="utf-8").strip()
        result = run_script(diff, self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected)

    def test_docs_diff_suggests_docs(self):
        result = run_script(DOCS_DIFF, self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("docs"), result.stdout)

    def test_deletion_heavy_fix_is_reported_as_refactor(self):
        # Evidence for observations/accepted/OBS-20260712-001.md and
        # knowledge/pitfalls.md: the classifier suggests `refactor` for a
        # deletion-heavy fix; agents must override the type manually.
        diff = (FIXTURES / "mixed_change.diff").read_text(encoding="utf-8")
        result = run_script(diff, self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("refactor"), result.stdout)

    def test_empty_input_fails_cleanly(self):
        result = run_script("", self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("empty diff", result.stderr)

    def test_script_writes_nothing_to_disk(self):
        diff = (EXAMPLES / "feature_change.diff").read_text(encoding="utf-8")
        run_script(diff, self.tmp)
        self.assertEqual(list(self.tmp.iterdir()), [])
