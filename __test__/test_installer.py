"""Install / diff / update / remove against a temporary library and project."""

from __future__ import annotations

import os

from skill_library import installer, lockfile
from skill_library.installer import (
    InstallError,
    diff_skill,
    install_skill,
    remove_skill,
    status,
    update_skill,
)
from skill_library.security import SecurityError

from .helpers import (
    TempDirTestCase,
    bump_library_skill,
    make_layered_library,
    make_library,
)

SKILL = "alpha-skill"


class InstallerTestCase(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_library(self.tmp, names=(SKILL,))
        self.project = self.make_dir("project")

    def install(self, **kwargs):
        return install_skill(self.library, SKILL, self.project, **kwargs)

    def dest(self) -> "os.PathLike[str]":
        return self.project / ".agents" / "skills" / SKILL


class TestInstall(InstallerTestCase):
    def test_install_copies_files_and_writes_lock(self):
        message = self.install()
        self.assertIn("installed", message)
        self.assertTrue((self.dest() / "SKILL.md").is_file())
        self.assertTrue((self.dest() / "ORIGIN.yaml").is_file())
        lock = lockfile.load_lock(self.project)
        entry = lockfile.get_entry(lock, SKILL)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["skill_version"], "0.1.0")
        self.assertEqual(entry["agent"], "universal")
        self.assertEqual(entry["mode"], "copy")
        self.assertEqual(entry["target_path"], f".agents/skills/{SKILL}")
        self.assertTrue(entry["checksum"].startswith("sha256:"))
        self.assertTrue(entry["installed_at"])
        # per-file hashes recorded and correct
        recorded = {f["path"]: f["sha256"] for f in entry["files"]}
        self.assertIn("SKILL.md", recorded)
        self.assertEqual(
            recorded["SKILL.md"], installer.file_sha256(self.dest() / "SKILL.md")
        )

    def test_reinstall_is_idempotent(self):
        self.install()
        lock_before = (self.project / lockfile.LOCKFILE_NAME).read_bytes()
        message = self.install()
        self.assertIn("already installed and up to date", message)
        self.assertEqual(lock_before, (self.project / lockfile.LOCKFILE_NAME).read_bytes())

    def test_dry_run_changes_nothing(self):
        message = self.install(dry_run=True)
        self.assertIn("[dry-run]", message)
        self.assertFalse(self.dest().exists())
        self.assertFalse((self.project / lockfile.LOCKFILE_NAME).exists())

    def test_agent_claude_target_path(self):
        install_skill(self.library, SKILL, self.project, agent="claude")
        self.assertTrue((self.project / ".claude" / "skills" / SKILL / "SKILL.md").is_file())

    def test_agent_hermes_requires_explicit_dir(self):
        with self.assertRaises(InstallError):
            install_skill(self.library, SKILL, self.project, agent="hermes")
        custom = self.make_dir("hermes-config/skills")
        install_skill(
            self.library, SKILL, self.project, agent="hermes", skills_dir_override=custom
        )
        self.assertTrue((custom / SKILL / "SKILL.md").is_file())

    def test_unmanaged_destination_is_protected(self):
        stray_dir = self.dest()
        stray_dir.mkdir(parents=True)
        (stray_dir / "precious.txt").write_text("mine", encoding="utf-8")
        with self.assertRaises(InstallError):
            self.install()
        self.install(force=True)  # explicit override replaces the directory
        self.assertTrue((stray_dir / "SKILL.md").is_file())

    def test_skill_with_symlink_is_refused(self):
        evil = self.library / "skills" / SKILL / "references" / "evil.md"
        evil.symlink_to("/etc/hostname")
        with self.assertRaises((InstallError, SecurityError)):
            self.install()
        self.assertFalse(self.dest().exists())

    def test_unknown_skill_and_bad_name(self):
        with self.assertRaises(InstallError):
            install_skill(self.library, "no-such-skill", self.project)
        with self.assertRaises(SecurityError):
            install_skill(self.library, "../escape", self.project)

    def test_link_mode_creates_symlink(self):
        message = self.install(link=True)
        self.assertIn("link", message)
        self.assertTrue(self.dest().is_symlink())
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["mode"], "link")
        self.assertEqual(entry["files"], [])
        remove_skill(self.library, SKILL, self.project)
        self.assertFalse(self.dest().exists())
        # library source must be untouched
        self.assertTrue((self.library / "skills" / SKILL / "SKILL.md").is_file())


class TestDiffAndUpdate(InstallerTestCase):
    def test_diff_empty_when_in_sync(self):
        self.install()
        self.assertEqual(diff_skill(self.library, SKILL, self.project), "")

    def test_diff_shows_upstream_changes(self):
        self.install()
        bump_library_skill(self.library, SKILL)
        diff = diff_skill(self.library, SKILL, self.project)
        self.assertIn("+## Changelog", diff)
        self.assertIn(f"installed/{SKILL}/SKILL.md", diff)
        self.assertIn(f"library/{SKILL}/SKILL.md", diff)

    def test_update_applies_new_version(self):
        self.install()
        bump_library_skill(self.library, SKILL, new_version="0.2.0")
        message = update_skill(self.library, SKILL, self.project)
        self.assertIn("updated to version 0.2.0", message)
        self.assertIn("## Changelog", (self.dest() / "SKILL.md").read_text(encoding="utf-8"))
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["skill_version"], "0.2.0")
        self.assertTrue(entry["updated_at"])
        self.assertEqual(diff_skill(self.library, SKILL, self.project), "")

    def test_update_when_up_to_date(self):
        self.install()
        self.assertIn("already up to date", update_skill(self.library, SKILL, self.project))

    def test_update_dry_run(self):
        self.install()
        bump_library_skill(self.library, SKILL)
        before = (self.dest() / "SKILL.md").read_bytes()
        message = update_skill(self.library, SKILL, self.project, dry_run=True)
        self.assertIn("[dry-run]", message)
        self.assertEqual(before, (self.dest() / "SKILL.md").read_bytes())

    def test_update_refuses_local_modifications(self):
        self.install()
        bump_library_skill(self.library, SKILL)
        installed_md = self.dest() / "SKILL.md"
        installed_md.write_text("locally changed\n", encoding="utf-8")
        with self.assertRaises(InstallError):
            update_skill(self.library, SKILL, self.project)
        # explicit --force overwrites
        message = update_skill(self.library, SKILL, self.project, force=True)
        self.assertIn("updated", message)
        self.assertIn("## Changelog", installed_md.read_text(encoding="utf-8"))

    def test_update_requires_install(self):
        with self.assertRaises(InstallError):
            update_skill(self.library, SKILL, self.project)


class TestRemove(InstallerTestCase):
    def test_remove_deletes_only_managed_files(self):
        self.install()
        stray = self.dest() / "references" / "user-note.md"
        stray.write_text("keep me\n", encoding="utf-8")
        message = remove_skill(self.library, SKILL, self.project)
        self.assertIn("unmanaged files were kept", message)
        self.assertTrue(stray.is_file())
        self.assertFalse((self.dest() / "SKILL.md").exists())
        self.assertIsNone(lockfile.get_entry(lockfile.load_lock(self.project), SKILL))

    def test_remove_cleans_empty_directories(self):
        self.install()
        remove_skill(self.library, SKILL, self.project)
        self.assertFalse(self.dest().exists())

    def test_remove_refuses_modified_files_without_force(self):
        self.install()
        (self.dest() / "SKILL.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(InstallError):
            remove_skill(self.library, SKILL, self.project)
        remove_skill(self.library, SKILL, self.project, force=True)
        self.assertFalse(self.dest().exists())

    def test_remove_dry_run(self):
        self.install()
        message = remove_skill(self.library, SKILL, self.project, dry_run=True)
        self.assertIn("[dry-run]", message)
        self.assertTrue((self.dest() / "SKILL.md").is_file())

    def test_remove_requires_lock_entry(self):
        with self.assertRaises(InstallError):
            remove_skill(self.library, SKILL, self.project)


class LayeredInstallerTestCase(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_layered_library(self.tmp, name=SKILL)
        self.project = self.make_dir("project")
        self.dest = self.project / ".agents" / "skills" / SKILL

    def install(self, **kwargs):
        return install_skill(self.library, SKILL, self.project, **kwargs)


class TestInstallModes(LayeredInstallerTestCase):
    def test_runtime_is_default_and_excludes_dev_content(self):
        message = self.install()
        self.assertIn("runtime mode", message)
        # shipped: knowledge, data/examples + README, accepted observations
        self.assertTrue((self.dest / "knowledge" / "patterns.md").is_file())
        self.assertTrue((self.dest / "data" / "README.md").is_file())
        self.assertTrue((self.dest / "data" / "examples" / "sample.txt").is_file())
        self.assertTrue(
            (self.dest / "observations" / "accepted" / "OBS-20260101-001.md").is_file()
        )
        # excluded: candidates, rejected, test-only fixtures
        self.assertFalse((self.dest / "observations" / "candidates").exists())
        self.assertFalse((self.dest / "data" / "fixtures").exists())
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["install_mode"], "runtime")
        recorded = {f["path"] for f in entry["files"]}
        self.assertNotIn("observations/candidates/OBS-20260101-002.md", recorded)

    def test_full_mode_ships_everything(self):
        message = self.install(install_mode="full")
        self.assertIn("full mode", message)
        self.assertTrue(
            (self.dest / "observations" / "candidates" / "OBS-20260101-002.md").is_file()
        )
        self.assertTrue((self.dest / "data" / "fixtures" / "sample.txt").is_file())
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["install_mode"], "full")

    def test_mode_checksums_differ_and_mode_switch_needs_force(self):
        runtime_files = installer.snapshot(self.library / "skills" / SKILL, "runtime")
        full_files = installer.snapshot(self.library / "skills" / SKILL, "full")
        self.assertNotEqual(
            installer.aggregate_checksum(runtime_files),
            installer.aggregate_checksum(full_files),
        )
        self.install()
        with self.assertRaises(InstallError):
            self.install(install_mode="full")
        self.install(install_mode="full", force=True)
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["install_mode"], "full")

    def test_runtime_reinstall_is_idempotent(self):
        self.install()
        self.assertIn("already installed and up to date", self.install())

    def test_diff_and_update_track_knowledge_changes(self):
        self.install()
        knowledge = self.library / "skills" / SKILL / "knowledge" / "patterns.md"
        knowledge.write_text("# Patterns\n\nA refined pattern.\n", encoding="utf-8")
        diff = diff_skill(self.library, SKILL, self.project)
        self.assertIn("+A refined pattern.", diff)
        update_skill(self.library, SKILL, self.project)
        self.assertIn(
            "refined", (self.dest / "knowledge" / "patterns.md").read_text(encoding="utf-8")
        )
        self.assertEqual(diff_skill(self.library, SKILL, self.project), "")

    def test_diff_ignores_changes_in_runtime_excluded_files(self):
        self.install()
        candidate = (
            self.library / "skills" / SKILL / "observations" / "candidates" / "OBS-20260101-002.md"
        )
        candidate.write_text(
            candidate.read_text(encoding="utf-8") + "\nMore notes.\n", encoding="utf-8"
        )
        self.assertEqual(diff_skill(self.library, SKILL, self.project), "")
        rows = status(self.library, self.project)
        self.assertEqual(rows[0]["update"], "none")

    def test_update_protects_locally_modified_knowledge(self):
        self.install()
        installed = self.dest / "knowledge" / "patterns.md"
        installed.write_text("locally tuned\n", encoding="utf-8")
        knowledge = self.library / "skills" / SKILL / "knowledge" / "patterns.md"
        knowledge.write_text("# Patterns\n\nUpstream change.\n", encoding="utf-8")
        with self.assertRaises(InstallError):
            update_skill(self.library, SKILL, self.project)
        update_skill(self.library, SKILL, self.project, force=True)
        self.assertIn("Upstream change", installed.read_text(encoding="utf-8"))

    def test_remove_deletes_all_managed_layer_files(self):
        self.install(install_mode="full")
        remove_skill(self.library, SKILL, self.project)
        self.assertFalse(self.dest.exists())

    def test_legacy_lock_entry_without_install_mode_is_treated_as_full(self):
        self.install(install_mode="full")
        lock = lockfile.load_lock(self.project)
        entry = lockfile.get_entry(lock, SKILL)
        del entry["install_mode"]  # simulate a lock written by the previous version
        lockfile.save_lock(self.project, lock)
        rows = status(self.library, self.project)
        self.assertEqual(rows[0]["state"], "ok")
        self.assertEqual(rows[0]["update"], "none")
        self.assertEqual(diff_skill(self.library, SKILL, self.project), "")


class TestStatus(InstallerTestCase):
    def test_status_reports_states_and_updates(self):
        self.install()
        rows = status(self.library, self.project)
        self.assertEqual(rows[0]["state"], "ok")
        self.assertEqual(rows[0]["update"], "none")

        bump_library_skill(self.library, SKILL, new_version="0.2.0")
        rows = status(self.library, self.project)
        self.assertIn("available (0.1.0 -> 0.2.0)", rows[0]["update"])

        (self.dest() / "SKILL.md").write_text("changed\n", encoding="utf-8")
        rows = status(self.library, self.project)
        self.assertEqual(rows[0]["state"], "modified")

    def test_status_empty_project(self):
        self.assertEqual(status(self.library, self.project), [])
