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

from .helpers import FIXTURES, TempDirTestCase, sandboxed_env


class TestSkillNames(TempDirTestCase):
    def test_valid_names(self):
        for name in ("a", "example-skill", "skill2", "a-b-c-9", "x" * 64):
            validate_skill_name(name)

    def test_invalid_names(self):
        bad = ["", "UPPER", "under_score", "-lead", "trail-", "a b", "a/b", "../x", "x" * 65, "тест"]
        for name in bad:
            with self.assertRaises(SecurityError, msg=name):
                validate_skill_name(name)

    def test_non_string_or_empty_name_raises_security_error(self):
        # Non-strings must fail with SecurityError (never leak a TypeError),
        # and the empty string must hit the same dedicated message.
        for name in (None, 123, ["list"], ""):
            with self.assertRaisesRegex(
                SecurityError, r"^skill name must be a non-empty string$", msg=repr(name)
            ):
                validate_skill_name(name)


class TestPaths(TempDirTestCase):
    def test_relative_path_rejects_traversal_and_absolute(self):
        for rel in ("../x", "a/../b", "/etc/passwd", "a/./b", "", "a\\b", "a\x00b"):
            with self.assertRaises(SecurityError, msg=rel):
                validate_relative_path(rel)

    def test_non_string_or_empty_relative_path_raises_security_error(self):
        # Non-strings must fail with SecurityError (never leak a TypeError),
        # and the empty string must hit the same dedicated message.
        for rel in (None, 123, ""):
            with self.assertRaisesRegex(
                SecurityError, r"^relative path must be a non-empty string$", msg=repr(rel)
            ):
                validate_relative_path(rel)

    def test_relative_path_rejects_empty_segments(self):
        # "a//b" and trailing slashes hide empty segments — fail closed.
        for rel in ("a//b", "a/", "a/b/"):
            with self.assertRaisesRegex(
                SecurityError, "path traversal is not allowed", msg=rel
            ):
                validate_relative_path(rel)

    def test_error_messages_name_the_violation(self):
        # The message is part of the contract: users act on it, so tests pin
        # the discriminating words (also kills message-mutation survivors).
        with self.assertRaisesRegex(SecurityError, "longer than 64"):
            validate_skill_name("x" * 65)
        with self.assertRaisesRegex(SecurityError, "invalid skill name"):
            validate_skill_name("UPPER")
        with self.assertRaisesRegex(SecurityError, "path traversal is not allowed"):
            validate_relative_path("a/../b")
        with self.assertRaisesRegex(SecurityError, "absolute paths are not allowed"):
            validate_relative_path("/etc/passwd")
        with self.assertRaisesRegex(SecurityError, "unsupported characters"):
            validate_relative_path("a\\b")
        # "escapes base directory" is reachable only via symlink resolution:
        # any ".." segment is already rejected as traversal above.
        base = self.make_dir("base")
        (base / "sneaky").symlink_to(self.make_dir("outside"), target_is_directory=True)
        with self.assertRaisesRegex(SecurityError, "escapes base directory"):
            safe_join(base, "sneaky", "file.txt")

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

    def test_safe_join_validates_every_part(self):
        # Traversal segments are rejected per part, even when the joined
        # result would still resolve inside the base directory.
        base = self.make_dir("base")
        (base / "a").mkdir()
        (base / "a" / "b.txt").write_text("x", encoding="utf-8")
        for parts in (("a/../a",), (".",), ("a", "./b.txt")):
            with self.assertRaises(SecurityError, msg=parts):
                safe_join(base, *parts)

    def test_ensure_no_symlinks_message_names_the_offender(self):
        clean = self.make_dir("clean-target")
        (clean / "file.txt").write_text("ok", encoding="utf-8")
        dirty = self.make_dir("dirty-nested")
        (dirty / "inner").mkdir()
        (dirty / "inner" / "link").symlink_to(clean / "file.txt")
        with self.assertRaisesRegex(SecurityError, "symlink inside skill is not allowed"):
            ensure_no_symlinks(dirty)

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
        env = sandboxed_env()
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

    def test_python_network_access_is_denied_before_connect(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import socket; socket.create_connection(('127.0.0.1', 9))",
            ],
            cwd=self.tmp,
            env=sandboxed_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("network access is disabled in skill tests", result.stderr)

    def test_python_udp_sendto_is_denied_without_connect(self):
        # UDP datagrams need no connect(); sendto must be blocked separately.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
                "s.sendto(b'x', ('127.0.0.1', 9))",
            ],
            cwd=self.tmp,
            env=sandboxed_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("network access is disabled in skill tests", result.stderr)

    def test_python_udp_sendmsg_is_denied_without_connect(self):
        # L-16: sendmsg is a second connect-less egress path; the blocker denies
        # it explicitly, so it needs its own test (sendto's does not cover it).
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
                "s.sendmsg([b'x'], [], 0, ('127.0.0.1', 9))",
            ],
            cwd=self.tmp,
            env=sandboxed_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("network access is disabled in skill tests", result.stderr)
