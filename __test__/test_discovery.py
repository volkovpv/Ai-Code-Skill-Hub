"""Discovery of skills in ``skills/`` (requirement: find valid, report broken)."""

from __future__ import annotations

from skill_library.discovery import DiscoveryError, discover_skills, load_catalog, load_skill

from .helpers import ROOT, TempDirTestCase, copy_fixture, make_library, write_skill


class TestDiscoverRealLibrary(TempDirTestCase):
    def test_example_skill_is_discovered(self):
        skills, problems = discover_skills(ROOT)
        self.assertEqual(problems, [])
        names = [s.name for s in skills]
        self.assertIn("example-skill", names)

    def test_catalog_matches_discovery(self):
        skills, _ = discover_skills(ROOT)
        catalog_names = {entry.name for entry in load_catalog(ROOT)}
        self.assertEqual({s.name for s in skills}, catalog_names)


class TestDiscoverSyntheticLibrary(TempDirTestCase):
    def test_discovers_valid_skills_sorted(self):
        library = make_library(self.tmp, names=("beta-skill", "alpha-skill"))
        skills, problems = discover_skills(library)
        self.assertEqual(problems, [])
        self.assertEqual([s.name for s in skills], ["alpha-skill", "beta-skill"])

    def test_discovers_valid_fixture(self):
        library = make_library(self.tmp, names=())
        copy_fixture("valid-skill", library / "skills")
        skills, problems = discover_skills(library)
        self.assertEqual(problems, [])
        self.assertEqual(skills[0].name, "valid-skill")
        self.assertTrue(skills[0].description)

    def test_missing_skill_md_is_reported(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        (library / "skills" / "broken-skill").mkdir()
        skills, problems = discover_skills(library)
        self.assertEqual([s.name for s in skills], ["alpha-skill"])
        self.assertTrue(any("broken-skill" in p and "SKILL.md" in p for p in problems))

    def test_missing_frontmatter_is_reported(self):
        library = make_library(self.tmp, names=())
        bad = library / "skills" / "bad-skill"
        bad.mkdir(parents=True)
        (bad / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
        skills, problems = discover_skills(library)
        self.assertEqual(skills, [])
        self.assertTrue(any("frontmatter" in p for p in problems))

    def test_load_skill_rejects_unterminated_frontmatter(self):
        library = make_library(self.tmp, names=())
        bad = library / "skills" / "bad-skill"
        bad.mkdir(parents=True)
        (bad / "SKILL.md").write_text("---\nname: bad-skill\n", encoding="utf-8")
        with self.assertRaises(DiscoveryError):
            load_skill(bad)

    def test_missing_skills_dir(self):
        skills, problems = discover_skills(self.tmp / "nowhere")
        self.assertEqual(skills, [])
        self.assertEqual(len(problems), 1)
