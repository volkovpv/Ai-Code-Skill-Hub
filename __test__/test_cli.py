"""End-to-end CLI checks: argument wiring, exit codes, `new` scaffolding."""

from __future__ import annotations

import contextlib
import io
import shutil
from unittest import mock

from skill_library.cli import main
from skill_library.validator import validate_library, validate_skill_dir

from .helpers import ROOT, TempDirTestCase, make_layered_library, make_library

SKILL = "alpha-skill"


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestCliOnRealLibrary(TempDirTestCase):
    def test_list(self):
        code, out, _ = run_cli("--library-root", str(ROOT), "list")
        self.assertEqual(code, 0)
        self.assertIn("example-skill", out)

    def test_validate(self):
        code, out, _ = run_cli("--library-root", str(ROOT), "validate")
        self.assertEqual(code, 0)
        self.assertIn("OK", out)


class TestCliLifecycle(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_library(self.tmp, names=(SKILL,))
        self.project = self.make_dir("project")

    def cli(self, *argv: str) -> tuple[int, str, str]:
        return run_cli("--library-root", str(self.library), *argv)

    def test_install_status_diff_remove(self):
        code, out, _ = self.cli("install", SKILL, "--target", str(self.project), "--copy")
        self.assertEqual(code, 0, out)
        self.assertIn("installed", out)

        code, out, _ = self.cli("status", "--target", str(self.project))
        self.assertEqual(code, 0)
        self.assertIn("state=ok", out)

        code, out, _ = self.cli("diff", SKILL, "--target", str(self.project))
        self.assertEqual(code, 0)
        self.assertIn("matches the library source", out)

        code, out, _ = self.cli("remove", SKILL, "--target", str(self.project))
        self.assertEqual(code, 0)
        self.assertIn("removed", out)

    def test_install_error_returns_nonzero(self):
        code, _, err = self.cli("install", "no-such-skill", "--target", str(self.project))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_validate_failure_returns_nonzero(self):
        (self.library / "skills" / SKILL / "ORIGIN.yaml").unlink()
        code, out, _ = self.cli("validate")
        self.assertEqual(code, 1)
        self.assertIn("missing ORIGIN.yaml", out)


class TestCliNew(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_library(self.tmp, names=(SKILL,))
        shutil.copytree(ROOT / "templates", self.library / "templates")

    def test_new_skill_from_template_passes_validation(self):
        code, out, _ = run_cli("--library-root", str(self.library), "new", "fresh-skill")
        self.assertEqual(code, 0, out)
        skill_dir = self.library / "skills" / "fresh-skill"
        self.assertTrue((skill_dir / "SKILL.md").is_file())
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: fresh-skill", content)
        self.assertNotIn("__SKILL_NAME__", content)
        # the generated skill and the whole library remain valid
        self.assertEqual(validate_skill_dir(skill_dir), [])
        self.assertEqual(validate_library(self.library), [])

    def test_new_refuses_existing_and_bad_names(self):
        code, _, err = run_cli("--library-root", str(self.library), "new", SKILL)
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        code, _, err = run_cli("--library-root", str(self.library), "new", "Bad_Name")
        self.assertEqual(code, 1)
        self.assertIn("invalid skill name", err)

    def test_new_with_layers_scaffolds_and_registers_capabilities(self):
        code, out, _ = run_cli(
            "--library-root", str(self.library),
            "new", "layered-skill", "--with", "knowledge,data,observations",
        )
        self.assertEqual(code, 0, out)
        skill_dir = self.library / "skills" / "layered-skill"
        self.assertTrue((skill_dir / "knowledge" / "INDEX.md").is_file())
        self.assertTrue((skill_dir / "data" / "README.md").is_file())
        self.assertTrue((skill_dir / "observations" / "INDEX.md").is_file())
        catalog = (self.library / "skills.yaml").read_text(encoding="utf-8")
        self.assertIn("knowledge: true", catalog)
        self.assertEqual(validate_skill_dir(skill_dir), [])
        self.assertEqual(validate_library(self.library), [])

    def test_new_without_layers_stays_minimal(self):
        code, out, _ = run_cli("--library-root", str(self.library), "new", "tiny-skill")
        self.assertEqual(code, 0, out)
        skill_dir = self.library / "skills" / "tiny-skill"
        self.assertFalse((skill_dir / "knowledge").exists())
        self.assertFalse((skill_dir / "data").exists())
        self.assertFalse((skill_dir / "observations").exists())
        self.assertEqual(validate_library(self.library), [])

    def test_new_rejects_unknown_layer(self):
        code, _, err = run_cli(
            "--library-root", str(self.library), "new", "x-skill", "--with", "history"
        )
        self.assertEqual(code, 1)
        self.assertIn("unknown layer", err)


    def test_new_rolls_back_files_and_catalog_on_registration_failure(self):
        catalog = self.library / "skills.yaml"
        before = catalog.read_bytes()
        with mock.patch(
            "skill_library.cli.load_catalog", side_effect=OSError("injected")
        ):
            code, _, err = run_cli("--library-root", str(self.library), "new", "rollback-skill")
        self.assertEqual(code, 1, err)
        self.assertFalse((self.library / "skills" / "rollback-skill").exists())
        self.assertEqual(catalog.read_bytes(), before)

class TestCliLayerCommands(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_layered_library(self.tmp, name=SKILL)

    def cli(self, *argv: str) -> tuple[int, str, str]:
        return run_cli("--library-root", str(self.library), *argv)

    def test_knowledge_list(self):
        code, out, _ = self.cli("knowledge", "list", SKILL)
        self.assertEqual(code, 0)
        self.assertIn("knowledge/patterns.md", out)
        self.assertIn("Patterns", out)

    def test_observation_cli_lifecycle(self):
        note = self.tmp / "note.md"
        note.write_text("# Observed thing\n\nDetails.\n", encoding="utf-8")
        code, out, _ = self.cli(
            "observation", "add", SKILL, "--from", str(note),
            "--evidence", "data/fixtures/sample.txt",
        )
        self.assertEqual(code, 0, out)
        self.assertIn("candidate", out)
        obs_id = next(w for w in out.split() if w.startswith("OBS-"))

        code, out, _ = self.cli("observation", "list", SKILL, "--status", "candidate")
        self.assertEqual(code, 0)
        self.assertIn(obs_id, out)

        code, out, _ = self.cli(
            "observation", "approve", SKILL, obs_id, "--reviewed-by", "reviewer"
        )
        self.assertEqual(code, 0, out)
        code, out, _ = self.cli("observation", "list", SKILL, "--status", "accepted")
        self.assertIn(obs_id, out)

    def test_observation_reject_via_cli(self):
        note = self.tmp / "note.md"
        note.write_text("# Weak observation\n\nNo proof.\n", encoding="utf-8")
        _, out, _ = self.cli("observation", "add", SKILL, "--from", str(note))
        obs_id = next(w for w in out.split() if w.startswith("OBS-"))
        code, out, _ = self.cli(
            "observation", "reject", SKILL, obs_id,
            "--reviewed-by", "reviewer", "--note", "no evidence",
        )
        self.assertEqual(code, 0, out)
        code, out, _ = self.cli("observation", "list", SKILL, "--status", "rejected")
        self.assertIn(obs_id, out)

    def test_data_validate_command(self):
        code, out, _ = self.cli("data", "validate", SKILL)
        self.assertEqual(code, 0)
        self.assertIn("data layer passed validation", out)
        (self.library / "skills" / SKILL / "data" / "README.md").unlink()
        code, out, _ = self.cli("data", "validate", SKILL)
        self.assertEqual(code, 1)
        self.assertIn("no data/README.md", out)

    def test_install_mode_flag(self):
        project = self.make_dir("project")
        code, out, _ = self.cli(
            "install", SKILL, "--target", str(project), "--mode", "full"
        )
        self.assertEqual(code, 0, out)
        self.assertIn("full mode", out)
        code, out, _ = self.cli("status", "--target", str(project))
        self.assertEqual(code, 0)
        self.assertIn("mode=full", out)


class TestCliStableTestGate(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_library(self.tmp, names=(SKILL,))
        (self.library / "__test__").mkdir()
        (self.library / "__test__" / "__init__.py").write_text("", encoding="utf-8")

    def cli(self, *argv: str) -> tuple[int, str, str]:
        return run_cli("--library-root", str(self.library), *argv)

    def test_targeted_stable_skill_requires_dedicated_tests(self):
        code, _, err = self.cli("test", SKILL)
        self.assertEqual(code, 1)
        self.assertIn("stable skill has no dedicated tests", err)

    def test_full_suite_rejects_stable_skill_without_tests(self):
        code, _, err = self.cli("test")
        self.assertEqual(code, 1)
        self.assertIn("stable skills without dedicated tests", err)

    def test_draft_skill_may_have_no_dedicated_tests(self):
        catalog = self.library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8").replace("status: stable", "status: draft"),
            encoding="utf-8",
        )
        code, out, err = self.cli("test", SKILL)
        self.assertEqual(code, 0, err)
        self.assertIn("no dedicated tests found", out)

    def test_stable_gate_requires_exact_module_name_not_prefix(self):
        # Skill "alpha" must not be considered covered by "test_alpha_skill.py"
        # (the dedicated tests of the longer-named skill "alpha-skill").
        self.library = make_library(self.tmp / "prefix", names=("alpha", SKILL))
        tests_dir = self.library / "__test__"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        (tests_dir / "test_alpha_skill.py").write_text("", encoding="utf-8")
        code, _, err = self.cli("test")
        self.assertEqual(code, 1)
        self.assertIn("alpha (test_alpha.py)", err)
        self.assertNotIn("alpha-skill (", err)

    def test_targeted_run_uses_exact_test_module_name(self):
        self.library = make_library(self.tmp / "exact", names=("alpha", SKILL))
        catalog = self.library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8").replace("status: stable", "status: draft"),
            encoding="utf-8",
        )
        tests_dir = self.library / "__test__"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        (tests_dir / "test_alpha_skill.py").write_text("", encoding="utf-8")
        code, out, err = self.cli("test", "alpha")
        self.assertEqual(code, 0, err)
        self.assertIn("(pattern test_alpha.py)", out)
