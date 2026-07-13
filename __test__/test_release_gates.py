"""Release gates: version drift and the code-change ⇔ version-bump rule."""

from __future__ import annotations

from contextlib import redirect_stderr
import datetime
import importlib.util
from io import StringIO
import subprocess
import sys
from pathlib import Path
from unittest import mock

from .helpers import ROOT, TempDirTestCase

SCRIPTS = ROOT / "scripts"


def _load_script(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drift = _load_script("check_version_drift")
gate = _load_script("check_release_gate")
bump = _load_script("bump_version")
mutation_gate = _load_script("check_mutation_score")

PYPROJECT = """[project]
name = "skill-library"
version = "{version}"
"""

INIT = '"""Synthetic package."""\n\n__version__ = "{version}"\n'

CHANGELOG = """# Changelog

## [{version}] — 2026-07-12

Synthetic entry.
"""


class ReleaseRepoTestCase(TempDirTestCase):
    """Base: a synthetic git repo with the version-carrying files."""

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo),
             "-c", "user.name=test", "-c", "user.email=test@example.com",
             *args],
            capture_output=True, text=True, check=True,
        )
        return result.stdout

    def write_versions(self, version: str) -> None:
        (self.repo / "pyproject.toml").write_text(
            PYPROJECT.format(version=version), encoding="utf-8"
        )
        init = self.repo / "src" / "skill_library" / "__init__.py"
        init.parent.mkdir(parents=True, exist_ok=True)
        init.write_text(INIT.format(version=version), encoding="utf-8")
        (self.repo / "CHANGELOG.md").write_text(
            CHANGELOG.format(version=version), encoding="utf-8"
        )

    def commit_all(self, message: str = "change") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def make_repo(self, version: str = "0.0.0") -> None:
        self.repo = self.make_dir("repo")
        self.git("init", "-q")
        self.write_versions(version)
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        (self.repo / "README.md").write_text("# docs\n", encoding="utf-8")
        self.commit_all("initial")


class TestVersionDrift(ReleaseRepoTestCase):
    def test_real_repo_has_no_drift(self):
        self.assertEqual(drift.check(ROOT), [])

    def test_synced_versions_pass(self):
        self.make_repo("0.1.0")
        self.assertEqual(drift.check(self.repo), [])

    def test_init_mismatch_fails(self):
        self.make_repo("0.1.0")
        init = self.repo / "src" / "skill_library" / "__init__.py"
        init.write_text(INIT.format(version="0.2.0"), encoding="utf-8")
        problems = "\n".join(drift.check(self.repo))
        self.assertIn("__init__.py", problems)

    def test_changelog_mismatch_fails(self):
        self.make_repo("0.1.0")
        (self.repo / "CHANGELOG.md").write_text(
            CHANGELOG.format(version="0.0.9"), encoding="utf-8"
        )
        problems = "\n".join(drift.check(self.repo))
        self.assertIn("CHANGELOG.md", problems)


class TestReleaseGate(ReleaseRepoTestCase):
    def tag(self, name: str) -> None:
        self.git("tag", name)

    def test_no_tags_baseline_passes(self):
        self.make_repo("0.0.0")
        self.assertEqual(gate.check(self.repo), [])

    def test_no_changes_since_tag_passes(self):
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        self.assertEqual(gate.check(self.repo), [])

    def test_code_change_without_bump_fails(self):
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("version is still 0.1.0", problems)

    def test_code_change_with_bump_passes(self):
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        self.write_versions("0.1.1")
        self.commit_all()
        self.assertEqual(gate.check(self.repo), [])

    def test_infra_only_change_without_bump_passes(self):
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "README.md").write_text("# docs v2\n", encoding="utf-8")
        self.commit_all()
        self.assertEqual(gate.check(self.repo), [])

    def test_infra_only_change_with_bump_fails(self):
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "README.md").write_text("# docs v2\n", encoding="utf-8")
        self.write_versions("0.1.1")
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("only infrastructure changed", problems)

    def test_version_bump_alone_counts_as_infra_only(self):
        # Version lines in pyproject/__init__ and the CHANGELOG entry are not
        # "used code" — a bump without code changes is forbidden.
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        self.write_versions("0.2.0")
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("only infrastructure changed", problems)

    def test_non_version_pyproject_change_is_code_change(self):
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        pyproject = self.repo / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8") + 'requires-python = ">=3.12"\n',
            encoding="utf-8",
        )
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("version is still 0.1.0", problems)

    def test_version_downgrade_fails(self):
        self.make_repo("0.2.0")
        self.tag("v0.2.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 3\n", encoding="utf-8"
        )
        self.write_versions("0.1.0")
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("went backwards", problems)

    def test_bumped_repo_passes_gate_with_code_change(self):
        # Full scenario: code changed, version bumped via bump_version —
        # both gates are green.
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        bump.bump(self.repo, "0.1.1", datetime.date(2026, 7, 12))
        self.commit_all()
        self.assertEqual(drift.check(self.repo), [])
        self.assertEqual(gate.check(self.repo), [])

    def test_rename_out_of_release_paths_without_bump_fails(self):
        # H-1: moving used code out of a released location must still count as a
        # used-code change. `git diff --name-only` collapses the rename to the
        # new (infra) path only, hiding the removal from src/ — the gate would
        # wave it through as infra-only. `--name-status -M` sees both endpoints.
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "_attic").mkdir()
        self.git("mv", "src/skill_library/core.py", "_attic/core.py")
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("version is still 0.1.0", problems)
        self.assertIn("src/skill_library/core.py", problems)

    def test_rename_into_release_paths_without_bump_fails(self):
        # Symmetric direction: moving a file into a released location adds new
        # used code — relevant by the new endpoint of the rename.
        self.make_repo("0.1.0")
        (self.repo / "extra.py").write_text("VALUE = 9\n", encoding="utf-8")
        self.commit_all("add extra at repo root")
        self.tag("v0.1.0")
        self.git("mv", "extra.py", "src/skill_library/extra.py")
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("version is still 0.1.0", problems)
        self.assertIn("src/skill_library/extra.py", problems)

    def test_delete_used_code_without_bump_fails(self):
        # Deleting used code is a used-code change (relevant by the old path).
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        self.git("rm", "-q", "src/skill_library/core.py")
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("version is still 0.1.0", problems)

    def test_rename_within_infra_without_bump_passes(self):
        # Guard against over-firing: a rename with both endpoints in infra is
        # not release-relevant.
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "docs").mkdir()
        self.git("mv", "README.md", "docs/README.md")
        self.commit_all()
        self.assertEqual(gate.check(self.repo), [])

    def test_rename_used_code_to_infra_with_bump_passes(self):
        # The H-1 scenario, handled correctly: relevant change + a bump = green.
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "_attic").mkdir()
        self.git("mv", "src/skill_library/core.py", "_attic/core.py")
        self.write_versions("0.1.1")
        self.commit_all()
        self.assertEqual(gate.check(self.repo), [])

    def test_picks_highest_semver_tag(self):
        # v0.9.0 and v0.10.0: by SemVer 0.10.0 is higher (string comparison
        # would pick 0.9.0). Code changed without a bump relative to 0.10.0 —
        # the gate fails mentioning exactly 0.10.0.
        self.make_repo("0.9.0")
        self.tag("v0.9.0")
        self.write_versions("0.10.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        self.commit_all()
        self.tag("v0.10.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 3\n", encoding="utf-8"
        )
        self.commit_all()
        problems = "\n".join(gate.check(self.repo))
        self.assertIn("version is still 0.10.0", problems)


UV_LOCK = """version = 1
revision = 3
requires-python = ">=3.12"

[[package]]
name = "skill-library"
version = "{version}"
source = {{ editable = "." }}
"""


class TestBumpVersion(ReleaseRepoTestCase):
    DATE = datetime.date(2026, 7, 12)

    def test_explicit_bump_updates_all_three_files(self):
        self.make_repo("0.0.0")
        bump.bump(self.repo, "0.0.1", self.DATE)
        self.assertEqual(drift.read_pyproject_version(self.repo), "0.0.1")
        self.assertEqual(drift.read_init_version(self.repo), "0.0.1")
        self.assertEqual(drift.read_changelog_version(self.repo), "0.0.1")
        self.assertEqual(drift.check(self.repo), [])

    def test_changelog_stub_inserted_before_previous_entry(self):
        self.make_repo("0.1.0")
        bump.bump(self.repo, "0.2.0", self.DATE)
        text = (self.repo / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertLess(text.index("## [0.2.0] — 2026-07-12"), text.index("## [0.1.0]"))
        self.assertIn("TODO", text)

    def test_next_version_parts(self):
        self.assertEqual(bump.next_version("0.1.2", "patch"), "0.1.3")
        self.assertEqual(bump.next_version("0.1.2", "minor"), "0.2.0")
        self.assertEqual(bump.next_version("0.1.2", "major"), "1.0.0")

    def test_downgrade_and_same_version_rejected(self):
        self.make_repo("0.2.0")
        with self.assertRaises(SystemExit):
            bump.bump(self.repo, "0.1.0", self.DATE)
        with self.assertRaises(SystemExit):
            bump.bump(self.repo, "0.2.0", self.DATE)

    def test_invalid_version_rejected(self):
        self.make_repo("0.1.0")
        with self.assertRaises(SystemExit):
            bump.bump(self.repo, "0.1.x", self.DATE)

    def test_bump_updates_uv_lock_when_present(self):
        self.make_repo("0.1.0")
        (self.repo / "uv.lock").write_text(
            UV_LOCK.format(version="0.1.0"), encoding="utf-8"
        )
        bump.bump(self.repo, "0.2.0", self.DATE)
        text = (self.repo / "uv.lock").read_text(encoding="utf-8")
        self.assertIn('name = "skill-library"\nversion = "0.2.0"', text)
        self.assertNotIn('"0.1.0"', text)

    def test_bump_without_uv_lock_succeeds(self):
        # Zero-tooling fallback: a missing uv.lock is not an error.
        self.make_repo("0.1.0")
        bump.bump(self.repo, "0.2.0", self.DATE)
        self.assertEqual(drift.check(self.repo), [])

    def test_bump_fails_on_uv_lock_without_project_entry(self):
        # Fail-closed: the lock exists but has no entry for the project package.
        self.make_repo("0.1.0")
        (self.repo / "uv.lock").write_text(
            'version = 1\nrevision = 3\nrequires-python = ">=3.12"\n',
            encoding="utf-8",
        )
        with self.assertRaises(SystemExit):
            bump.bump(self.repo, "0.2.0", self.DATE)

    def _read_all_versions(self, repo: Path) -> dict[str, str]:
        return {
            "pyproject": (repo / "pyproject.toml").read_text(encoding="utf-8"),
            "init": (repo / "src" / "skill_library" / "__init__.py").read_text(encoding="utf-8"),
            "changelog": (repo / "CHANGELOG.md").read_text(encoding="utf-8"),
        }

    def test_bump_aborting_on_uv_lock_leaves_no_partial_write(self):
        # H-4: a bump that fails on uv.lock (regenerated / missing the project
        # entry) used to abort AFTER pyproject.toml and __init__.py were already
        # stamped, leaving a half-bumped tree with no rollback. The pre-flight
        # now computes every substitution before touching disk, so a failing
        # bump changes nothing.
        self.make_repo("0.1.0")
        (self.repo / "uv.lock").write_text(
            'version = 1\nrevision = 3\nrequires-python = ">=3.12"\n',
            encoding="utf-8",
        )
        before = self._read_all_versions(self.repo)
        with self.assertRaises(SystemExit):
            bump.bump(self.repo, "0.2.0", self.DATE)
        self.assertEqual(self._read_all_versions(self.repo), before)
        self.assertEqual(drift.read_pyproject_version(self.repo), "0.1.0")
        self.assertEqual(drift.check(self.repo), [])  # still internally consistent

    def test_bump_rolls_back_files_written_before_a_mid_commit_failure(self):
        # H-4 residual: even past the pre-flight, an IO error part-way through the
        # write set must not leave a half-stamped tree. Fail the third atomic
        # write and assert the two already-written files are restored byte-for-byte.
        self.make_repo("0.1.0")
        (self.repo / "uv.lock").write_text(
            UV_LOCK.format(version="0.1.0"), encoding="utf-8"
        )
        before = self._read_all_versions(self.repo)
        real_write = bump._atomic_write
        calls = {"n": 0}

        def flaky_write(path: Path, text: str) -> None:
            calls["n"] += 1
            if calls["n"] == 3:  # blow up mid-commit, after two files landed
                raise OSError("disk full")
            real_write(path, text)

        with mock.patch.object(bump, "_atomic_write", flaky_write):
            with self.assertRaises(OSError):
                bump.bump(self.repo, "0.2.0", self.DATE)
        self.assertEqual(self._read_all_versions(self.repo), before)
        self.assertEqual(drift.check(self.repo), [])

    def test_bump_rejects_non_semver_current_version(self):
        # L-9: a non-standard current version (e.g. a pre-release tag) must give a
        # diagnosable SystemExit, not a bare ValueError from parse_version's int().
        self.make_repo("0.1.0rc1")
        with self.assertRaises(SystemExit) as ctx:
            bump.bump(self.repo, "0.2.0", self.DATE)
        self.assertIn("not a valid X.Y.Z", str(ctx.exception))

    def test_main_rejects_non_semver_current_before_computing_next(self):
        # L-9: the --patch/--minor/--major path parses `current` via next_version;
        # main() must reject a malformed current up front rather than let int() throw.
        self.make_repo("0.1.0rc1")
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            bump.main(["--patch", "--root", str(self.repo)])

    def _write_versions_crlf(self, repo: Path, version: str) -> None:
        def crlf(text: str) -> bytes:
            return text.replace("\n", "\r\n").encode("utf-8")

        (repo / "pyproject.toml").write_bytes(crlf(PYPROJECT.format(version=version)))
        init = repo / "src" / "skill_library" / "__init__.py"
        init.parent.mkdir(parents=True, exist_ok=True)
        init.write_bytes(crlf(INIT.format(version=version)))
        (repo / "CHANGELOG.md").write_bytes(crlf(CHANGELOG.format(version=version)))
        (repo / "uv.lock").write_bytes(crlf(UV_LOCK.format(version=version)))

    def test_bump_preserves_crlf_line_endings(self):
        # M-1: bumping must not silently rewrite CRLF files to LF (which under
        # core.autocrlf=true produced a hundreds-of-lines noise diff and broke
        # the "byte-identical to uv lock" contract).
        repo = self.make_dir("crlf")
        self._write_versions_crlf(repo, "0.1.0")
        bump.bump(repo, "0.2.0", self.DATE)

        for name in ("pyproject.toml", "src/skill_library/__init__.py",
                     "CHANGELOG.md", "uv.lock"):
            data = (repo / name).read_bytes()
            self.assertIn(b"\r\n", data, f"{name} lost its CRLF endings")
            self.assertEqual(
                data.count(b"\n"), data.count(b"\r\n"),
                f"{name} gained a bare LF (mixed line endings)",
            )
        # The change actually landed, and the inserted CHANGELOG stub is CRLF too.
        self.assertEqual(drift.read_pyproject_version(repo), "0.2.0")
        self.assertIn(b"## [0.2.0] \xe2\x80\x94 2026-07-12\r\n",
                      (repo / "CHANGELOG.md").read_bytes())
        self.assertIn('version = "0.2.0"',
                      (repo / "uv.lock").read_text(encoding="utf-8"))

    def test_bump_preserves_lf_line_endings(self):
        # Guard the other direction: an LF repo must never gain a stray CR.
        self.make_repo("0.1.0")
        (self.repo / "uv.lock").write_text(
            UV_LOCK.format(version="0.1.0"), encoding="utf-8"
        )
        bump.bump(self.repo, "0.2.0", self.DATE)
        for name in ("pyproject.toml", "src/skill_library/__init__.py",
                     "CHANGELOG.md", "uv.lock"):
            self.assertNotIn(b"\r", (self.repo / name).read_bytes(),
                             f"{name} gained a CR on an LF repo")

class TestMutationScoreGate(TempDirTestCase):
    def test_score_counts_survivors_and_timeouts_as_not_killed(self):
        actual = mutation_gate.score(
            {"killed": 75, "survived": 20, "timeout": 5, "no_tests": 0}
        )
        self.assertEqual(actual, 75.0)

    def test_empty_mutation_set_is_not_a_failure(self):
        self.assertEqual(mutation_gate.score({}), 100.0)

    def test_main_enforces_threshold_and_rejects_malformed_stats(self):
        stats = self.tmp / "stats.json"
        stats.write_text(
            '{"killed": 74, "survived": 26, "timeout": 0}',
            encoding="utf-8",
        )
        errors = StringIO()
        with redirect_stderr(errors):
            self.assertEqual(mutation_gate.main([str(stats), "--minimum", "75"]), 1)
            stats.write_text("{broken", encoding="utf-8")
            self.assertEqual(mutation_gate.main([str(stats)]), 2)
        self.assertIn("required >= 75.00%", errors.getvalue())
        self.assertIn("cannot read", errors.getvalue())
