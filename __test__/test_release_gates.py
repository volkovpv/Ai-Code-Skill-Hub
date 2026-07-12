"""Release gates: version drift and the code-change ⇔ version-bump rule."""

from __future__ import annotations

import datetime
import importlib.util
import subprocess
import sys
from pathlib import Path

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
        # Строки версии в pyproject/__init__ и запись CHANGELOG не являются
        # «используемым кодом» — bump без изменений кода запрещён.
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
            pyproject.read_text(encoding="utf-8") + 'requires-python = ">=3.11"\n',
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
        # Полный сценарий: код изменён, версия поднята через bump_version —
        # оба гейта зелёные.
        self.make_repo("0.1.0")
        self.tag("v0.1.0")
        (self.repo / "src" / "skill_library" / "core.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )
        bump.bump(self.repo, "0.1.1", datetime.date(2026, 7, 12))
        self.commit_all()
        self.assertEqual(drift.check(self.repo), [])
        self.assertEqual(gate.check(self.repo), [])

    def test_picks_highest_semver_tag(self):
        # v0.9.0 и v0.10.0: по SemVer старше 0.10.0 (строковое сравнение дало
        # бы 0.9.0). Код изменён без bump относительно 0.10.0 — гейт падает
        # с упоминанием именно 0.10.0.
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
