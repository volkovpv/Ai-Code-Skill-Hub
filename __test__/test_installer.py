"""Install / diff / update / remove against a temporary library and project."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from unittest import mock

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
    write_skill,
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
        self.assertFalse((stray_dir / "precious.txt").exists())

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
        self.assertIn("symlink to the library", message)  # no bogus file count
        self.assertTrue(self.dest().is_symlink())
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["mode"], "link")
        self.assertEqual(entry["files"], [])
        remove_skill(self.library, SKILL, self.project)
        self.assertFalse(self.dest().exists())
        # library source must be untouched
        self.assertTrue((self.library / "skills" / SKILL / "SKILL.md").is_file())

    def test_relative_skills_dir_override_resolves_inside_project(self):
        install_skill(
            self.library,
            SKILL,
            self.project,
            agent="hermes",
            skills_dir_override=Path("custom/skills"),
        )
        self.assertTrue(
            (self.project / "custom" / "skills" / SKILL / "SKILL.md").is_file()
        )
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["target_path"], f"custom/skills/{SKILL}")

    def test_install_records_source_metadata_in_lock(self):
        def fake_commit(root):
            # the library root itself must be asked for its commit
            self.assertEqual(Path(root).resolve(), self.library)
            return "deadbeef1234"

        with mock.patch.object(installer, "library_commit", side_effect=fake_commit):
            self.install()
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["source"], str(self.library))
        self.assertEqual(entry["source_commit"], "deadbeef1234")
        # copy installs never carry a link target
        self.assertNotIn("link_target", entry)
        # timestamps are UTC-aware ISO strings
        self.assertTrue(entry["installed_at"].endswith("+00:00"))

    def test_dry_run_reinstall_still_refuses_modified_copy(self):
        self.install()
        (self.dest() / "SKILL.md").write_text("locally changed\n", encoding="utf-8")
        with self.assertRaises(InstallError):
            self.install(dry_run=True)

    def test_force_reinstall_overwrites_modified_copy(self):
        self.install()
        (self.dest() / "SKILL.md").write_text("locally changed\n", encoding="utf-8")
        message = self.install(force=True)
        self.assertIn("installed", message)
        library_md = (self.library / "skills" / SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual((self.dest() / "SKILL.md").read_text(encoding="utf-8"), library_md)

    def test_mode_switch_requires_force_even_with_equal_checksums(self):
        # a plain skill ships the same files in both modes -> equal checksums
        skill_dir = self.library / "skills" / SKILL
        self.assertEqual(
            installer.aggregate_checksum(installer.snapshot(skill_dir, "runtime")),
            installer.aggregate_checksum(installer.snapshot(skill_dir, "full")),
        )
        self.install()  # runtime
        with self.assertRaises(InstallError):
            self.install(install_mode="full")

    def test_link_install_over_copy_requires_force(self):
        self.install(install_mode="full")  # same checksum as the link (full) install
        with self.assertRaises(InstallError):
            self.install(link=True)
        self.install(link=True, force=True)
        self.assertTrue(self.dest().is_symlink())

    def test_force_link_reinstall_replaces_stray_directory(self):
        self.install(link=True)
        self.dest().unlink()
        self.dest().mkdir()  # someone replaced the managed symlink with a directory
        self.install(link=True, force=True)
        self.assertTrue(self.dest().is_symlink())

    def test_force_link_agent_switch_never_prunes_library_source(self):
        assets = self.library / "skills" / SKILL / "assets"
        assets.mkdir()  # empty directory in the source must survive reinstalls
        self.install(link=True)
        # moving the link to another agent unlinks the old symlink; it must
        # never be treated as a managed directory (that would prune the library)
        self.install(link=True, agent="claude", force=True)
        self.assertTrue((self.project / ".claude" / "skills" / SKILL).is_symlink())
        self.assertFalse(self.dest().exists())
        self.assertTrue(assets.is_dir())


class TestInstallerHelpers(InstallerTestCase):
    """Unit-level checks of installer helpers on real inputs (mutation kill-set)."""

    def test_file_sha256_matches_hashlib(self):
        import hashlib

        payload = b"skill payload\n" * 1000
        target = self.tmp / "blob.bin"
        target.write_bytes(payload)
        self.assertEqual(
            installer.file_sha256(target), hashlib.sha256(payload).hexdigest()
        )

    def test_snapshot_records_per_file_hashes_sorted(self):
        skill_dir = self.library / "skills" / SKILL
        records = installer.snapshot(skill_dir)
        paths = [record["path"] for record in records]
        self.assertEqual(paths, sorted(paths))
        self.assertIn("SKILL.md", paths)
        for record in records:
            self.assertEqual(
                record["sha256"], installer.file_sha256(skill_dir / record["path"])
            )

    def test_iter_skill_files_filters_junk_and_rejects_unknown_mode(self):
        skill_dir = self.library / "skills" / SKILL
        (skill_dir / "__pycache__").mkdir()
        (skill_dir / "__pycache__" / "x.pyc").write_bytes(b"\x00")
        (skill_dir / "references" / "notes.pyc").write_bytes(b"\x00")
        (skill_dir / ".DS_Store").write_bytes(b"\x00")
        files = installer.iter_skill_files(skill_dir)
        self.assertEqual(files, ["ORIGIN.yaml", "SKILL.md", "references/notes.md"])
        with self.assertRaises(InstallError):
            installer.iter_skill_files(skill_dir, "partial")

    def test_library_commit_returns_head_in_git_repo_and_none_outside(self):
        import subprocess

        repo = self.make_dir("repo")
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "-q"], check=True)
        (repo / "f.txt").write_text("x", encoding="utf-8")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
        head = subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(installer.library_commit(repo), head)
        self.assertIsNone(installer.library_commit(self.make_dir("plain-dir")))

    def test_library_commit_requires_zero_exit_and_nonempty_output(self):
        import subprocess

        # git echoes the rev name on an unborn HEAD but exits non-zero
        unborn = subprocess.CompletedProcess(["git"], returncode=128, stdout="HEAD\n", stderr="fatal")
        with mock.patch.object(installer.subprocess, "run", return_value=unborn):
            self.assertIsNone(installer.library_commit(self.library))
        silent = subprocess.CompletedProcess(["git"], returncode=0, stdout="\n", stderr="")
        with mock.patch.object(installer.subprocess, "run", return_value=silent):
            self.assertIsNone(installer.library_commit(self.library))

    def test_installed_state_missing_for_broken_link(self):
        self.install(link=True)
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        shutil.rmtree(self.library / "skills" / SKILL)  # symlink target gone
        self.assertEqual(installer.installed_state(self.project, entry), "missing")

    def test_installed_state_resolves_lock_entry_paths_fail_closed(self):
        entry = {"name": SKILL, "mode": "copy"}
        # no target_path recorded -> refuse rather than guess
        with self.assertRaises(InstallError):
            installer.installed_state(self.project, dict(entry))
        # single-segment and nested relative paths resolve against the project
        (self.project / "flat").mkdir()
        self.assertEqual(
            installer.installed_state(self.project, {**entry, "target_path": "flat"}), "ok"
        )
        (self.project / "sub" / "nested").mkdir(parents=True)
        self.assertEqual(
            installer.installed_state(self.project, {**entry, "target_path": "sub/nested"}),
            "ok",
        )
        # traversal in the recorded path is refused
        with self.assertRaises(SecurityError):
            installer.installed_state(self.project, {**entry, "target_path": "sub/.."})

    def test_copy_files_creates_nested_parent_directories(self):
        skill_dir = self.library / "skills" / SKILL
        deep = skill_dir / "references" / "deep"
        deep.mkdir()
        (deep / "nested.md").write_text("# deep\n", encoding="utf-8")
        dest = self.tmp / "copy-dest"
        installer._copy_files(skill_dir, dest, installer.snapshot(skill_dir))
        self.assertTrue((dest / "references" / "deep" / "nested.md").is_file())

    def test_remove_destination_unlinks_symlinks_and_files(self):
        target = self.make_dir("link-target")
        (target / "keep.txt").write_text("keep\n", encoding="utf-8")
        link = self.tmp / "link"
        link.symlink_to(target, target_is_directory=True)
        installer._remove_destination(link)
        self.assertFalse(link.is_symlink())
        self.assertTrue((target / "keep.txt").is_file())  # target untouched

        plain = self.tmp / "plain.txt"
        plain.write_text("x", encoding="utf-8")
        installer._remove_destination(plain)
        self.assertFalse(plain.exists())

    def test_delete_managed_files_tolerates_entry_without_files(self):
        self.make_dir("victim/nested/deep")
        victim_root = self.tmp / "victim"
        installer._delete_managed_files(victim_root, {}, verify=True, force=False)
        self.assertFalse(victim_root.exists())  # empty tree pruned bottom-up

    def test_installed_state_tracks_link_installs(self):
        self.install(link=True)
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(installer.installed_state(self.project, entry), "ok")

        # symlink retargeted to another directory -> modified
        elsewhere = self.make_dir("elsewhere")
        self.dest().unlink()
        self.dest().symlink_to(elsewhere, target_is_directory=True)
        self.assertEqual(installer.installed_state(self.project, entry), "modified")

        # symlink replaced by a plain directory -> modified, gone -> missing
        self.dest().unlink()
        self.dest().mkdir()
        self.assertEqual(installer.installed_state(self.project, entry), "modified")
        self.dest().rmdir()
        self.assertEqual(installer.installed_state(self.project, entry), "missing")

    def test_target_path_outside_project_is_recorded_absolute(self):
        outside = self.make_dir("outside-skills")
        install_skill(
            self.library, SKILL, self.project, agent="hermes", skills_dir_override=outside
        )
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["target_path"], str((outside / SKILL).resolve()))
        self.assertEqual(installer.installed_state(self.project, entry), "ok")


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
        message = update_skill(self.library, SKILL, self.project)
        self.assertIn("already up to date", message)
        self.assertIn("(0.1.0)", message)  # reports the installed skill version

    def test_diff_link_install_is_empty_even_when_symlink_diverges(self):
        self.install(link=True)
        self.dest().unlink()
        self.dest().mkdir()  # divergence is status's job to report, not diff's
        self.assertEqual(diff_skill(self.library, SKILL, self.project), "")

    def test_diff_covers_deleted_extra_and_modified_files(self):
        self.install()
        (self.dest() / "references" / "notes.md").unlink()
        (self.dest() / "SKILL.md").write_text("locally changed\n", encoding="utf-8")
        (self.dest() / "extra.md").write_text("local only\n", encoding="utf-8")
        diff = diff_skill(self.library, SKILL, self.project)
        # modified file: local content shows up as removed lines
        self.assertIn("-locally changed\n", diff)
        # deleted file: restored from the library as a pure addition
        self.assertIn("@@ -0,0 +1 @@\n+# notes\n", diff)
        # extra unmanaged file: shown as a pure deletion relative to the library
        self.assertIn("@@ -1 +0,0 @@\n-local only\n", diff)
        # output stays a well-formed unified diff, line by line
        for line in diff.splitlines():
            self.assertTrue(line.startswith(("---", "+++", "@@", "+", "-", " ")), line)

    def test_update_refreshes_link_install_metadata(self):
        self.install(link=True)
        bump_library_skill(self.library, SKILL, new_version="0.2.0")
        message = update_skill(self.library, SKILL, self.project)
        self.assertIn("symlink install refreshed", message)
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["skill_version"], "0.2.0")
        self.assertTrue(entry["updated_at"])
        self.assertEqual(
            entry["checksum"],
            installer.aggregate_checksum(
                installer.snapshot(self.library / "skills" / SKILL, "full")
            ),
        )
        self.assertTrue(self.dest().is_symlink())

    def test_update_dry_run_still_refuses_modified_copy(self):
        self.install()
        (self.dest() / "SKILL.md").write_text("locally changed\n", encoding="utf-8")
        with self.assertRaises(InstallError):
            update_skill(self.library, SKILL, self.project, dry_run=True)

    def test_update_reinstalls_when_files_are_missing(self):
        self.install()
        (self.dest() / "references" / "notes.md").unlink()
        (self.dest() / "SKILL.md").write_text("locally changed\n", encoding="utf-8")
        # a broken install is repaired without --force, local edits included
        message = update_skill(self.library, SKILL, self.project)
        self.assertIn("updated to version", message)
        self.assertTrue((self.dest() / "references" / "notes.md").is_file())
        self.assertNotIn(
            "locally changed", (self.dest() / "SKILL.md").read_text(encoding="utf-8")
        )

    def test_update_preserves_lock_entry_identity_fields(self):
        install_skill(self.library, SKILL, self.project, agent="claude")
        lock = lockfile.load_lock(self.project)
        lockfile.get_entry(lock, SKILL)["installed_at"] = "2020-01-01T00:00:00+00:00"
        lockfile.save_lock(self.project, lock)
        bump_library_skill(self.library, SKILL, new_version="0.2.0")

        update_skill(self.library, SKILL, self.project)

        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["agent"], "claude")
        self.assertEqual(entry["mode"], "copy")
        self.assertEqual(entry["installed_at"], "2020-01-01T00:00:00+00:00")
        self.assertTrue(entry["updated_at"])
        self.assertEqual(
            entry["checksum"],
            installer.aggregate_checksum(
                installer.snapshot(self.library / "skills" / SKILL, "runtime")
            ),
        )
        self.assertTrue(entry["files"])
        self.assertEqual(installer.installed_state(self.project, entry), "ok")

    def test_update_defaults_agent_for_legacy_lock_entries(self):
        self.install()
        lock = lockfile.load_lock(self.project)
        del lockfile.get_entry(lock, SKILL)["agent"]  # lock written before agents existed
        lockfile.save_lock(self.project, lock)
        bump_library_skill(self.library, SKILL, new_version="0.2.0")
        update_skill(self.library, SKILL, self.project)
        entry = lockfile.get_entry(lockfile.load_lock(self.project), SKILL)
        self.assertEqual(entry["agent"], "universal")

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
        message = remove_skill(self.library, SKILL, self.project)
        # exact count, no leftover note when nothing unmanaged was kept
        self.assertEqual(message, f"{SKILL}: removed 3 managed file(s)")
        self.assertFalse(self.dest().exists())

    def test_remove_link_refuses_retargeted_symlink_without_force(self):
        self.install(link=True)
        elsewhere = self.make_dir("elsewhere")
        self.dest().unlink()
        self.dest().symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(InstallError):
            remove_skill(self.library, SKILL, self.project)
        self.assertTrue(self.dest().is_symlink())  # rollback kept the symlink
        self.assertIsNotNone(lockfile.get_entry(lockfile.load_lock(self.project), SKILL))

        remove_skill(self.library, SKILL, self.project, force=True)
        self.assertFalse(self.dest().exists())
        self.assertIsNone(lockfile.get_entry(lockfile.load_lock(self.project), SKILL))

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


class TestTransactionalRollback(InstallerTestCase):
    def assert_no_backups(self):
        skills_root = self.dest().parent
        backups = list(skills_root.glob(f".{SKILL}.skillctl-backup-*"))
        self.assertEqual(backups, [])

    def test_force_install_restores_unmanaged_destination_when_lock_write_fails(self):
        self.dest().mkdir(parents=True)
        precious = self.dest() / "precious.txt"
        precious.write_text("mine", encoding="utf-8")

        with mock.patch.object(installer.lockfile, "save_lock", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.install(force=True)

        self.assertEqual(precious.read_text(encoding="utf-8"), "mine")
        self.assertFalse((self.dest() / "SKILL.md").exists())
        self.assertFalse((self.project / lockfile.LOCKFILE_NAME).exists())
        self.assert_no_backups()

    def test_update_restores_files_and_lock_when_lock_write_fails(self):
        self.install()
        installed_before = (self.dest() / "SKILL.md").read_bytes()
        lock_before = (self.project / lockfile.LOCKFILE_NAME).read_bytes()
        bump_library_skill(self.library, SKILL, new_version="0.2.0")

        with mock.patch.object(installer.lockfile, "save_lock", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                update_skill(self.library, SKILL, self.project)

        self.assertEqual((self.dest() / "SKILL.md").read_bytes(), installed_before)
        self.assertEqual((self.project / lockfile.LOCKFILE_NAME).read_bytes(), lock_before)
        self.assert_no_backups()

    def test_remove_restores_files_and_lock_when_lock_write_fails(self):
        self.install()
        installed_before = (self.dest() / "SKILL.md").read_bytes()
        lock_before = (self.project / lockfile.LOCKFILE_NAME).read_bytes()

        with mock.patch.object(installer.lockfile, "save_lock", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                remove_skill(self.library, SKILL, self.project)

        self.assertEqual((self.dest() / "SKILL.md").read_bytes(), installed_before)
        self.assertEqual((self.project / lockfile.LOCKFILE_NAME).read_bytes(), lock_before)
        self.assert_no_backups()

    def test_force_agent_switch_restores_previous_install_when_lock_write_fails(self):
        self.install()
        old_md = self.dest() / "SKILL.md"

        with mock.patch.object(installer.lockfile, "save_lock", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                install_skill(self.library, SKILL, self.project, agent="claude", force=True)

        # both the old and the new destination take part in the rollback
        self.assertTrue(old_md.is_file())
        self.assertFalse((self.project / ".claude" / "skills" / SKILL).exists())
        self.assert_no_backups()

    def test_remove_link_restores_symlink_when_lock_write_fails(self):
        self.install(link=True)
        source = (self.library / "skills" / SKILL).resolve()

        with mock.patch.object(installer.lockfile, "save_lock", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                remove_skill(self.library, SKILL, self.project)

        self.assertTrue(self.dest().is_symlink())
        self.assertEqual(self.dest().resolve(), source)
        self.assertIsNotNone(lockfile.get_entry(lockfile.load_lock(self.project), SKILL))
        self.assert_no_backups()


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

    def test_status_rows_expose_name_and_lock_entry(self):
        self.install()
        row = status(self.library, self.project)[0]
        self.assertEqual(row["name"], SKILL)
        self.assertEqual(row["entry"]["name"], SKILL)

    def test_status_names_corrupt_entries_with_question_mark(self):
        self.install()
        lock = lockfile.load_lock(self.project)
        del lockfile.get_entry(lock, SKILL)["name"]
        lockfile.save_lock(self.project, lock)
        rows = status(self.library, self.project)
        self.assertEqual(rows[0]["name"], "?")
        self.assertEqual(rows[0]["update"], "missing in library")


class TestSourceValidationGate(InstallerTestCase):
    """install must re-validate the source skill against its catalog entry."""

    def test_install_refuses_stable_skill_with_placeholders(self):
        skill_md = self.library / "skills" / SKILL / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8") + "\nTODO: tighten wording\n",
            encoding="utf-8",
        )
        with self.assertRaises(InstallError):
            self.install()
        self.assertFalse(self.dest().exists())

    def test_install_enforces_catalog_content_policy(self):
        catalog = self.library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8")
            + "    content_policy:\n      max_tracked_file_bytes: 64\n",
            encoding="utf-8",
        )
        with self.assertRaises(InstallError):
            self.install()  # SKILL.md alone exceeds the tightened limit
        self.assertFalse(self.dest().exists())

    def test_uncataloged_skill_installs_with_placeholder_version(self):
        write_skill(self.library / "skills", "ghost-skill")
        install_skill(self.library, "ghost-skill", self.project)
        entry = lockfile.get_entry(lockfile.load_lock(self.project), "ghost-skill")
        self.assertEqual(entry["skill_version"], "0.0.0")
        # a content change is advertised even without a catalog version
        notes = self.library / "skills" / "ghost-skill" / "references" / "notes.md"
        notes.write_text("# notes\n\nchanged upstream\n", encoding="utf-8")
        row = status(self.library, self.project)[0]
        self.assertEqual(row["update"], "available (0.0.0 -> ?)")
