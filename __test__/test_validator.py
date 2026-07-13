"""Validation rules: frontmatter, naming, duplicates, ORIGIN.yaml, local links."""

from __future__ import annotations

import os

from skill_library.validator import (
    HARD_MAX_FILE_BYTES,
    MAX_DESCRIPTION_LENGTH,
    layer_has_content,
    validate_data_layer,
    validate_library,
    validate_skill_dir,
)

from .helpers import (
    ORIGIN_TEMPLATE,
    ROOT,
    TempDirTestCase,
    add_layers,
    copy_fixture,
    make_library,
    make_layered_library,
    write_skill,
)


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


class TestLayerHasContent(TempDirTestCase):
    def test_gitkeep_and_bare_directories_do_not_count(self):
        layer = self.make_dir("knowledge")
        self.assertFalse(layer_has_content(layer))
        (layer / ".gitkeep").write_text("", encoding="utf-8")
        self.assertFalse(layer_has_content(layer))
        (layer / "sub").mkdir()
        self.assertFalse(layer_has_content(layer))
        (layer / "sub" / "note.md").write_text("x\n", encoding="utf-8")
        self.assertTrue(layer_has_content(layer))


class TestLocalLinks(TempDirTestCase):
    def test_external_and_anchor_links_are_ignored(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(
            skills_dir,
            "linked-skill",
            body_extra=(
                "\nSee [site](https://example.com/docs), "
                "[mail](mailto:dev@example.com) and [top](#workflow).\n"
            ),
        )
        self.assertEqual(validate_skill_dir(skill), [])

    def test_anchor_suffix_is_stripped_before_resolution(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(
            skills_dir,
            "anchored-skill",
            body_extra=(
                "\nDetails in [notes](references/notes.md#usage) and "
                "[deep](references/notes.md#a#b).\n"
            ),
        )
        self.assertEqual(validate_skill_dir(skill), [])

    def test_inline_code_reference_to_missing_file_fails(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(
            skills_dir,
            "codey-skill",
            body_extra="\nRun `scripts/run.py` after reading `references/gone.md`.\n",
        )
        (skill / "scripts").mkdir()
        (skill / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
        problems = validate_skill_dir(skill)
        self.assertIn(
            "SKILL.md links to a missing local resource: references/gone.md", problems
        )
        self.assertNotIn(
            "SKILL.md links to a missing local resource: scripts/run.py", problems
        )

    def test_checking_continues_after_an_outside_link(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(
            skills_dir,
            "multi-problem-skill",
            body_extra="\nBad: [out](../other/file.md) and [gone](references/zzz.md).\n",
        )
        problems = validate_skill_dir(skill)
        self.assertIn(
            "SKILL.md links outside the skill directory: ../other/file.md", problems
        )
        self.assertIn(
            "SKILL.md links to a missing local resource: references/zzz.md", problems
        )


class TestOriginProvenance(TempDirTestCase):
    def test_vendored_origin_requires_provenance_fields(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "vendored-skill")
        (skill / "ORIGIN.yaml").write_text(
            "type: vendored\nsource: null\nlicense: null\nimported_at: null\n",
            encoding="utf-8",
        )
        problems = validate_skill_dir(skill)
        for required in ("source", "license", "imported_at"):
            self.assertIn(f"ORIGIN.yaml: vendored skill must set '{required}'", problems)


class TestContentPolicyLimits(TempDirTestCase):
    def _layered_skill(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "layered-skill")
        add_layers(skill)
        return skill

    def test_out_of_range_max_bytes_is_flagged_unprefixed(self):
        skill = self._layered_skill()
        expected = (
            f"content_policy: max_tracked_file_bytes must be within 1..{HARD_MAX_FILE_BYTES}"
        )
        for bad in (0, HARD_MAX_FILE_BYTES + 1):
            problems = validate_data_layer(skill, {"max_tracked_file_bytes": bad})
            self.assertIn(expected, problems)

    def test_boundary_max_bytes_values_are_accepted(self):
        skill = self._layered_skill()
        out_of_range = (
            f"content_policy: max_tracked_file_bytes must be within 1..{HARD_MAX_FILE_BYTES}"
        )
        # The hard ceiling itself is a legal policy value.
        problems = validate_data_layer(skill, {"max_tracked_file_bytes": HARD_MAX_FILE_BYTES})
        self.assertEqual(problems, [])
        # max=1 is legal too and must be honoured, naming the oversized file.
        problems = validate_data_layer(skill, {"max_tracked_file_bytes": 1})
        self.assertNotIn(out_of_range, problems)
        self.assertTrue(
            any(p.startswith("data/fixtures/sample.txt: 14 bytes exceeds") for p in problems),
            problems,
        )

    def test_file_exactly_at_limit_passes(self):
        skill = self._layered_skill()
        blob = skill / "data" / "fixtures" / "blob.bin"
        blob.write_bytes(b"a" * 64)
        problems = validate_data_layer(skill, {"max_tracked_file_bytes": 64})
        self.assertFalse(any("blob.bin" in p for p in problems), problems)
        blob.write_bytes(b"a" * 65)
        problems = validate_data_layer(skill, {"max_tracked_file_bytes": 64})
        self.assertTrue(
            any(p.startswith("data/fixtures/blob.bin: 65 bytes exceeds") for p in problems),
            problems,
        )


class TestLayoutRules(TempDirTestCase):
    def test_forbidden_document_deep_in_the_tree_fails(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "doc-skill")
        (skill / "references" / "README.md").write_text("# nope\n", encoding="utf-8")
        problems = "\n".join(validate_skill_dir(skill))
        self.assertIn("references/README.md: auxiliary documents are not allowed", problems)

    def test_executable_suffixes_belong_in_scripts_only(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "exec-skill")
        (skill / "assets").mkdir()
        (skill / "scripts").mkdir()
        (skill / "scripts" / "run.sh").write_text("echo ok\n", encoding="utf-8")
        suffixes = ("sh", "bash", "exe", "bat", "cmd")
        for suffix in suffixes:
            (skill / "assets" / f"tool.{suffix}").write_text("echo no\n", encoding="utf-8")
        problems = validate_skill_dir(skill)
        for suffix in suffixes:
            self.assertIn(
                f"assets/tool.{suffix}: executable files belong in scripts/ only", problems
            )
        self.assertNotIn("scripts/run.sh: executable files belong in scripts/ only", problems)

    def test_executable_bit_outside_scripts_flagged_except_gitkeep(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "bitty-skill")
        helper = skill / "references" / "helper.py"
        helper.write_text("print('hi')\n", encoding="utf-8")
        os.chmod(helper, 0o755)
        (skill / "assets").mkdir()
        gitkeep = skill / "assets" / ".gitkeep"
        gitkeep.write_text("", encoding="utf-8")
        os.chmod(gitkeep, 0o755)
        problems = validate_skill_dir(skill)
        self.assertIn(
            "references/helper.py: unexpected executable bit outside scripts/", problems
        )
        self.assertFalse(any(".gitkeep" in p for p in problems), problems)


class TestKnowledgeLayer(TempDirTestCase):
    def _layered_skill(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "know-skill")
        add_layers(skill)
        return skill

    def test_toc_required_only_above_100_lines(self):
        skill = self._layered_skill()
        long_md = skill / "knowledge" / "long.md"
        long_md.write_text("line\n" * 100, encoding="utf-8")
        problems = validate_skill_dir(skill)
        self.assertFalse(any("table of contents" in p for p in problems), problems)
        long_md.write_text("line\n" * 101, encoding="utf-8")
        problems = validate_skill_dir(skill)
        self.assertIn(
            "knowledge/long.md: files longer than 100 lines must start with a short "
            "table of contents ('## Contents' / '## Оглавление')",
            problems,
        )

    def test_index_broken_link_names_the_index(self):
        skill = self._layered_skill()
        index = skill / "knowledge" / "INDEX.md"
        index.write_text(
            index.read_text(encoding="utf-8") + "\n[gone](missing.md)\n", encoding="utf-8"
        )
        problems = validate_skill_dir(skill)
        self.assertIn(
            "knowledge/INDEX.md links to a missing local resource: missing.md", problems
        )


class TestFrontmatterFields(TempDirTestCase):
    def _bare_skill(self, name: str, frontmatter: str):
        skill = self.make_dir(f"skills/{name}")
        (skill / "SKILL.md").write_text(
            f"---\n{frontmatter}---\n\n# body\n\ntext\n", encoding="utf-8"
        )
        (skill / "ORIGIN.yaml").write_text(ORIGIN_TEMPLATE, encoding="utf-8")
        return skill

    def test_missing_name_is_reported_not_crashed(self):
        skill = self._bare_skill("nameless-skill", "description: something useful\n")
        problems = validate_skill_dir(skill)
        self.assertIn("frontmatter: 'name' is missing or empty", problems)

    def test_missing_description_is_reported_verbatim(self):
        skill = self._bare_skill("desc-less-skill", "name: desc-less-skill\n")
        problems = validate_skill_dir(skill)
        self.assertIn("frontmatter: 'description' is missing or empty", problems)

    def test_description_length_boundary(self):
        skills_dir = self.make_dir("skills")
        ok = write_skill(skills_dir, "brief-skill", description="d" * MAX_DESCRIPTION_LENGTH)
        self.assertEqual(validate_skill_dir(ok), [])
        wordy = write_skill(
            skills_dir, "wordy-skill", description="d" * (MAX_DESCRIPTION_LENGTH + 1)
        )
        problems = validate_skill_dir(wordy)
        self.assertIn(
            f"frontmatter: 'description' is longer than {MAX_DESCRIPTION_LENGTH} characters",
            problems,
        )

    def test_invalid_directory_name_is_reported_verbatim(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "Bad_Dir", frontmatter_name="good-name")
        problems = validate_skill_dir(skill)
        self.assertTrue(
            any(p.startswith("invalid skill name 'Bad_Dir'") for p in problems), problems
        )


class TestContentPolicyFlags(TempDirTestCase):
    def test_pii_and_review_flags_are_pinned(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "flaggy-skill")
        problems = validate_skill_dir(skill, {"pii_allowed": True})
        self.assertIn(
            "content_policy: pii_allowed/secrets_allowed must stay false — this library "
            "never publishes PII or secrets",
            problems,
        )
        problems = validate_skill_dir(skill, {"observation_review_required": False})
        self.assertIn("content_policy: observation_review_required must stay true", problems)

    def test_data_layer_is_not_scanned_twice(self):
        skills_dir = self.make_dir("skills")
        skill = write_skill(skills_dir, "layered-skill")
        add_layers(skill)
        expected = (
            f"content_policy: max_tracked_file_bytes must be within 1..{HARD_MAX_FILE_BYTES}"
        )
        problems = validate_skill_dir(skill, {"max_tracked_file_bytes": 0})
        self.assertEqual(problems.count(expected), 1, problems)


class TestCapabilities(TempDirTestCase):
    def test_undeclared_layers_default_to_not_declared(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        skill = library / "skills" / "alpha-skill"
        knowledge = skill / "knowledge"
        knowledge.mkdir()
        (knowledge / "INDEX.md").write_text(
            "# Knowledge index\n\n[patterns.md](patterns.md)\n", encoding="utf-8"
        )
        (knowledge / "patterns.md").write_text("# Patterns\n", encoding="utf-8")
        catalog = library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8")
            + "    capabilities:\n      knowledge: true\n",
            encoding="utf-8",
        )
        self.assertEqual(validate_library(library), [])


class TestLibraryScanning(TempDirTestCase):
    def test_stray_files_and_hidden_dirs_are_skipped(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        (library / "skills" / "notes.txt").write_text("scratch\n", encoding="utf-8")
        hidden = library / "skills" / ".cache"
        hidden.mkdir()
        (hidden / "junk.bin").write_text("junk\n", encoding="utf-8")
        self.assertEqual(validate_library(library), [])

    def test_catalog_content_policy_reaches_skill_validation(self):
        library = make_layered_library(self.tmp)
        catalog = library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8").replace(
                "pii_allowed: false", "pii_allowed: true"
            ),
            encoding="utf-8",
        )
        problems = validate_library(library)
        self.assertIn(
            "alpha-skill: content_policy: pii_allowed/secrets_allowed must stay false — "
            "this library never publishes PII or secrets",
            problems,
        )

    def test_zero_version_entry_fails(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        catalog = library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8").replace("version: 0.1.0", "version: 0.0.0"),
            encoding="utf-8",
        )
        problems = validate_library(library)
        self.assertIn("skills.yaml: entry 'alpha-skill' must declare a version", problems)

    def test_duplicate_message_names_both_directories(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        write_skill(library / "skills", "alpha-copy", frontmatter_name="alpha-skill")
        problems = "\n".join(validate_library(library))
        self.assertIn("directories 'alpha-copy' and 'alpha-skill'", problems)


class TestStablePlaceholders(TempDirTestCase):
    def test_stable_skill_rejects_placeholders(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        skill_md = library / "skills" / "alpha-skill" / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8") + "\nTODO: finish this workflow.\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_library(library))
        self.assertIn("stable skill must not contain TODO/TBD/FIXME", problems)

    def test_draft_skill_allows_scaffold_placeholders(self):
        library = make_library(self.tmp, names=("alpha-skill",))
        catalog = library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8").replace("status: stable", "status: draft"),
            encoding="utf-8",
        )
        skill_md = library / "skills" / "alpha-skill" / "SKILL.md"
        skill_md.write_text(
            skill_md.read_text(encoding="utf-8") + "\nTODO: finish this workflow.\n",
            encoding="utf-8",
        )
        self.assertEqual(validate_library(library), [])
