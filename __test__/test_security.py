"""Fail-closed path handling and sandboxed execution of skill scripts."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from skill_library.security import (
    SecurityError,
    ensure_no_symlinks,
    safe_join,
    validate_relative_path,
    validate_skill_name,
)

from .helpers import FIXTURES, TempDirTestCase


class TestSkillNames(TempDirTestCase):
    def test_valid_names(self):
        for name in ("a", "example-skill", "skill2", "a-b-c-9", "x" * 64):
            validate_skill_name(name)

    def test_invalid_names(self):
        bad = ["", "UPPER", "under_score", "-lead", "trail-", "a b", "a/b", "../x", "x" * 65, "тест"]
        for name in bad:
            with self.assertRaises(SecurityError, msg=name):
                validate_skill_name(name)


class TestPaths(TempDirTestCase):
    def test_relative_path_rejects_traversal_and_absolute(self):
        for rel in ("../x", "a/../b", "/etc/passwd", "a/./b", "", "a\\b"):
            with self.assertRaises(SecurityError, msg=rel):
                validate_relative_path(rel)

    def test_safe_join_stays_inside(self):
        base = self.make_dir("base")
        path = safe_join(base, "a", "b/c.txt")
        self.assertTrue(str(path).startswith(str(base)))

    def test_safe_join_rejects_escape(self):
        base = self.make_dir("base")
        for parts in (("../outside",), ("a/../../outside",), ("/abs",)):
            with self.assertRaises(SecurityError, msg=parts):
                safe_join(base, *parts)

    def test_safe_join_rejects_symlink_escape(self):
        base = self.make_dir("base")
        outside = self.make_dir("outside")
        (base / "sneaky").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(SecurityError):
            safe_join(base, "sneaky", "file.txt")

    def test_ensure_no_symlinks(self):
        clean = self.make_dir("clean")
        (clean / "file.txt").write_text("ok", encoding="utf-8")
        ensure_no_symlinks(clean)  # must not raise
        dirty = self.make_dir("dirty")
        (dirty / "link").symlink_to(clean / "file.txt")
        with self.assertRaises(SecurityError):
            ensure_no_symlinks(dirty)


class TestSandboxedScriptExecution(TempDirTestCase):
    """Skill scripts are executed only against test fixtures, in a temp cwd,
    with a sanitized environment that carries no secrets."""

    def test_fixture_probe_runs_without_secrets(self):
        probe = FIXTURES / "valid-skill" / "scripts" / "probe.py"
        sandbox = self.make_dir("sandbox")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        parent_env = dict(os.environ, SECRET_TOKEN="do-not-leak")  # noqa: S106 - fake value
        self.assertIn("SECRET_TOKEN", parent_env)  # the leak we guard against
        result = subprocess.run(
            [sys.executable, str(probe)],
            cwd=sandbox,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(os.path.realpath(payload["cwd"]), os.path.realpath(str(sandbox)))
        self.assertNotIn("SECRET_TOKEN", payload["env_keys"])
