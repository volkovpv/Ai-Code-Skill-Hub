"""Discovery of skills in ``skills/`` (requirement: find valid, report broken)."""

from __future__ import annotations

from skill_library.discovery import DiscoveryError, discover_skills, load_catalog, load_skill
from skill_library.models import CatalogEntry
from skill_library.validator import validate_library

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

    def test_non_utf8_skill_md_is_reported_not_raised(self):
        # H-3: a non-UTF-8 SKILL.md becomes a discovery problem, not a bare
        # UnicodeDecodeError that would crash `skillctl list`/`validate`.
        library = make_library(self.tmp, names=("alpha-skill",))
        bad = library / "skills" / "bad-skill"
        bad.mkdir(parents=True)
        (bad / "SKILL.md").write_bytes(b"---\nname: \xff\xfe\n---\n")
        skills, problems = discover_skills(library)
        self.assertEqual([s.name for s in skills], ["alpha-skill"])
        self.assertTrue(any("bad-skill" in p and "UTF-8" in p for p in problems))

    def test_load_skill_raises_discoveryerror_on_non_utf8(self):
        library = make_library(self.tmp, names=())
        bad = library / "skills" / "bad-skill"
        bad.mkdir(parents=True)
        (bad / "SKILL.md").write_bytes(b"\xff\xfe binary")
        with self.assertRaises(DiscoveryError):
            load_skill(bad)

    def test_missing_skills_dir(self):
        skills, problems = discover_skills(self.tmp / "nowhere")
        self.assertEqual(skills, [])
        self.assertEqual(len(problems), 1)

    def test_load_catalog_rejects_duplicate_entries(self):
        # M-7: a duplicated catalog name is a data error, not silently tolerated.
        library = make_library(self.tmp, names=("alpha-skill",))
        catalog = library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8")
            + "  - name: alpha-skill\n    path: skills/alpha-skill\n"
            "    version: 0.1.0\n    status: stable\n    summary: dup\n"
            "    platforms: [universal]\n    license: MIT\n",
            encoding="utf-8",
        )
        with self.assertRaises(DiscoveryError) as ctx:
            load_catalog(library)
        self.assertIn("duplicate", str(ctx.exception))


class TestCatalogEntryTypeRobustness(TempDirTestCase):
    """H-6/M-2: a wrong-typed structural field must become a diagnosable
    problem, never a bare ``ValueError`` traceback out of the fail-closed
    validator."""

    def test_from_dict_rejects_list_capabilities(self):
        # dict(['knowledge', 'data']) would otherwise raise an opaque ValueError.
        with self.assertRaises(ValueError) as ctx:
            CatalogEntry.from_dict({"name": "x", "capabilities": ["knowledge", "data"]})
        self.assertIn("'capabilities' must be a mapping", str(ctx.exception))

    def test_from_dict_rejects_scalar_content_policy(self):
        with self.assertRaises(ValueError) as ctx:
            CatalogEntry.from_dict({"name": "x", "content_policy": "nope"})
        self.assertIn("'content_policy' must be a mapping", str(ctx.exception))

    def test_from_dict_rejects_scalar_platforms(self):
        # list("linux") would silently yield ['l','i','n','u','x'] — reject it.
        with self.assertRaises(ValueError) as ctx:
            CatalogEntry.from_dict({"name": "x", "platforms": "linux"})
        self.assertIn("'platforms' must be a list", str(ctx.exception))

    def test_from_dict_accepts_absent_and_well_typed_fields(self):
        # negative control: missing fields default; correct types round-trip.
        empty = CatalogEntry.from_dict({"name": "x"})
        self.assertEqual((empty.platforms, empty.capabilities, empty.content_policy), ([], {}, {}))
        typed = CatalogEntry.from_dict(
            {"name": "x", "platforms": ["linux"], "capabilities": {"data": True}}
        )
        self.assertEqual(typed.platforms, ["linux"])
        self.assertEqual(typed.capabilities, {"data": True})

    def test_load_catalog_reports_bad_type_as_discovery_error(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        catalog = library / "skills.yaml"
        catalog.write_text(
            "version: 1\nskills:\n"
            "  - name: alpha-skill\n    path: skills/alpha-skill\n"
            "    capabilities:\n      - knowledge\n      - data\n",
            encoding="utf-8",
        )
        with self.assertRaises(DiscoveryError) as ctx:
            load_catalog(library)
        self.assertIn("'capabilities' must be a mapping", str(ctx.exception))

    def test_validate_library_stays_fail_closed_on_bad_type(self):
        # end-to-end: no traceback escapes; the defect surfaces as a problem.
        library = make_library(self.tmp, names=("alpha-skill",))
        catalog = library / "skills.yaml"
        catalog.write_text(
            "version: 1\nskills:\n"
            "  - name: alpha-skill\n    path: skills/alpha-skill\n"
            "    platforms: universal\n",
            encoding="utf-8",
        )
        problems = validate_library(library)
        self.assertTrue(
            any("'platforms' must be a list" in p for p in problems),
            problems,
        )
