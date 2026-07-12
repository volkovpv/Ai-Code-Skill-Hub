"""Validation rules: frontmatter, naming, duplicates, ORIGIN.yaml, local links."""

from __future__ import annotations

from skill_library.validator import validate_library, validate_skill_dir

from .helpers import ROOT, TempDirTestCase, copy_fixture, make_library, write_skill


class TestValidateSkillDir(TempDirTestCase):
    def test_valid_fixture_passes(self):
        library = make_library(self.tmp, names=())
        skill = copy_fixture("valid-skill", library / "skills")
        self.assertEqual(validate_skill_dir(skill), [])

    def test_real_example_skill_passes(self):
        self.assertEqual(validate_skill_dir(ROOT / "skills" / "example-skill"), [])

    def test_invalid_fixture_fails_with_expected_problems(self):
        library = make_library(self.tmp, names=())
        skill = copy_fixture("invalid-skill", library / "skills")
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("does not match directory name", problems)
        self.assertIn("missing ORIGIN.yaml", problems)
        self.assertIn("references/missing.md", problems)

    def test_missing_frontmatter_fails(self):
        skill = self.make_dir("skills/plain-skill")
        (skill / "SKILL.md").write_text("# body only\n", encoding="utf-8")
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("frontmatter", problems)

    def test_empty_description_fails(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "quiet-skill", description="")
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("'description' is missing or empty", problems)

    def test_bad_directory_name_fails(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "Bad_Name", frontmatter_name="Bad_Name")
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("invalid skill name", problems)

    def test_link_escaping_skill_dir_fails(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(
            skills_dir,
            "escapist-skill",
            body_extra="\nSee [secret](../../etc/passwd).\n",
        )
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("links outside the skill directory", problems)

    def test_symlink_inside_skill_fails(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "linky-skill")
        (skill / "references" / "evil.md").symlink_to("/etc/hostname")
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("symlink is not allowed", problems)


class TestValidateLibrary(TempDirTestCase):
    def test_synthetic_library_passes(self):
        library = make_library(self.tmp, names=("alpha-skill", "beta-skill"))
        self.assertEqual(validate_library(library), [])

    def test_real_library_passes(self):
        self.assertEqual(validate_library(ROOT), [])

    def test_duplicate_names_fail(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        # second directory with the same frontmatter name
        write_skill(library / "skills", "alpha-copy", frontmatter_name="alpha-skill")
        problems = "\n".join(validate_library(library))
        self.assertIn("duplicate skill name 'alpha-skill'", problems)

    def test_uncatalogued_skill_fails(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        write_skill(library / "skills", "stray-skill")
        problems = "\n".join(validate_library(library))
        self.assertIn("'stray-skill' is not listed in the catalog", problems)

    def test_catalog_entry_without_directory_fails(self):
        library = make_library(self.tmp, names=("alpha-skill", "ghost-skill"))
        import shutil

        shutil.rmtree(library / "skills" / "ghost-skill")
        problems = "\n".join(validate_library(library))
        self.assertIn("'ghost-skill' has no directory", problems)
