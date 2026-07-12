"""Validation of the optional layers: knowledge/, data/, observations/,
content policy (sizes, secret scan) and capability consistency."""

from __future__ import annotations

from skill_library.validator import (
    DEFAULT_CONTENT_POLICY,
    validate_data_layer,
    validate_library,
    validate_skill_dir,
)

from .helpers import (
    ROOT,
    TempDirTestCase,
    add_layers,
    make_layered_library,
    make_library,
    write_skill,
)

SKILL = "alpha-skill"


class TestLayeredSkillValidation(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_layered_library(self.tmp, name=SKILL)
        self.skill = self.library / "skills" / SKILL

    def test_layered_skill_and_library_pass(self):
        self.assertEqual(validate_skill_dir(self.skill), [])
        self.assertEqual(validate_library(self.library), [])

    def test_plain_skill_without_layers_stays_valid(self):
        # backward compatibility: layers are optional capabilities
        library = make_library(self.tmp / "plain", names=("plain-skill",))
        self.assertEqual(validate_skill_dir(library / "skills" / "plain-skill"), [])
        self.assertEqual(validate_library(library), [])

    def test_real_example_skill_passes_with_layers(self):
        self.assertEqual(validate_library(ROOT), [])

    def test_knowledge_requires_index(self):
        (self.skill / "knowledge" / "INDEX.md").unlink()
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("no knowledge/INDEX.md", problems)

    def test_knowledge_index_links_are_checked(self):
        (self.skill / "knowledge" / "INDEX.md").write_text(
            "# Index\n\nSee [missing](missing.md).\n", encoding="utf-8"
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("missing local resource: missing.md", problems)

    def test_long_knowledge_file_requires_toc(self):
        long_text = "# Long\n\n" + "line\n" * 120
        (self.skill / "knowledge" / "long.md").write_text(long_text, encoding="utf-8")
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("table of contents", problems)
        with_toc = "# Long\n\n## Contents\n\n- one\n\n" + "line\n" * 120
        (self.skill / "knowledge" / "long.md").write_text(with_toc, encoding="utf-8")
        self.assertEqual(validate_skill_dir(self.skill), [])

    def test_data_requires_readme(self):
        (self.skill / "data" / "README.md").unlink()
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("no data/README.md", problems)
        self.assertIn("no data/README.md", "\n".join(validate_data_layer(self.skill)))

    def test_unknown_directory_is_flagged(self):
        (self.skill / "history").mkdir()
        (self.skill / "history" / "log.md").write_text("x\n", encoding="utf-8")
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("unknown directory 'history/'", problems)

    def test_forbidden_docs_except_data_readme(self):
        (self.skill / "CHANGELOG.md").write_text("x\n", encoding="utf-8")
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("CHANGELOG.md: auxiliary documents are not allowed", problems)
        # data/README.md itself is the allowed exception
        self.assertNotIn("data/README.md: auxiliary", problems)


class TestContentPolicy(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_layered_library(self.tmp, name=SKILL)
        self.skill = self.library / "skills" / SKILL

    def test_private_key_marker_blocks_validation(self):
        (self.skill / "data" / "fixtures" / "bad.pem").write_text(
            "-----BEGIN PRIVATE KEY-----\nTESTMARKER-NOT-A-REAL-KEY\n-----END PRIVATE KEY-----\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("possible private key block", problems)

    def test_aws_style_marker_blocks_validation(self):
        # canonical AWS documentation example key — an obvious test marker
        (self.skill / "data" / "fixtures" / "creds.txt").write_text(
            "key id: AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8"
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("possible AWS access key id", problems)

    def test_data_validate_scans_data_layer(self):
        (self.skill / "data" / "fixtures" / "creds.txt").write_text(
            "key id: AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8"
        )
        problems = "\n".join(validate_data_layer(self.skill))
        self.assertIn("AWS access key id", problems)

    def test_oversized_file_blocks_validation(self):
        big = self.skill / "data" / "fixtures" / "big.txt"
        big.write_bytes(b"x" * (DEFAULT_CONTENT_POLICY["max_tracked_file_bytes"] + 1))
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("exceeds max_tracked_file_bytes", problems)

    def test_policy_can_raise_limit_deliberately(self):
        big = self.skill / "data" / "fixtures" / "big.txt"
        big.write_bytes(b"x" * (DEFAULT_CONTENT_POLICY["max_tracked_file_bytes"] + 1))
        policy = {"max_tracked_file_bytes": 1024 * 1024}
        self.assertEqual(validate_skill_dir(self.skill, policy), [])

    def test_pii_and_secret_flags_must_stay_false(self):
        problems = "\n".join(validate_skill_dir(self.skill, {"secrets_allowed": True}))
        self.assertIn("must stay false", problems)
        problems = "\n".join(
            validate_skill_dir(self.skill, {"observation_review_required": False})
        )
        self.assertIn("observation_review_required must stay true", problems)


class TestObservationValidation(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_layered_library(self.tmp, name=SKILL)
        self.skill = self.library / "skills" / SKILL
        self.accepted = self.skill / "observations" / "accepted"

    def test_accepted_without_review_metadata_fails(self):
        obs = self.accepted / "OBS-20260101-003.md"
        obs.write_text(
            "---\nid: OBS-20260101-003\nstatus: accepted\nobserved_at: 2026-01-01\n"
            "scope: x\nevidence:\n  - e1\nreviewed_by: null\nreviewed_at: null\n---\n\nBody.\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("must set 'reviewed_by'", problems)

    def test_accepted_without_evidence_fails(self):
        obs = self.accepted / "OBS-20260101-003.md"
        obs.write_text(
            "---\nid: OBS-20260101-003\nstatus: accepted\nobserved_at: 2026-01-01\n"
            "scope: x\nevidence: []\nreviewed_by: r\nreviewed_at: 2026-01-02\n---\n\nBody.\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("non-empty 'evidence'", problems)

    def test_status_must_match_directory(self):
        obs = self.accepted / "OBS-20260101-003.md"
        obs.write_text(
            "---\nid: OBS-20260101-003\nstatus: candidate\nobserved_at: 2026-01-01\n"
            "scope: x\nevidence: []\n---\n\nBody.\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("does not match directory", problems)

    def test_duplicate_ids_fail(self):
        src = self.accepted / "OBS-20260101-001.md"
        dup_dir = self.skill / "observations" / "candidates"
        dup = dup_dir / "OBS-20260101-001.md"
        dup.write_text(
            src.read_text(encoding="utf-8").replace("status: accepted", "status: candidate"),
            encoding="utf-8",
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("duplicate observation id", problems)

    def test_bad_id_format_fails(self):
        obs = self.accepted / "weird.md"
        obs.write_text(
            "---\nid: not-an-id\nstatus: accepted\nobserved_at: 2026-01-01\nscope: x\n"
            "evidence:\n  - e\nreviewed_by: r\nreviewed_at: 2026-01-02\n---\n\nBody.\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_skill_dir(self.skill))
        self.assertIn("must match OBS-YYYYMMDD-NNN", problems)


class TestCapabilityConsistency(TempDirTestCase):
    def test_declared_capability_requires_content(self):
        library = make_layered_library(self.tmp, name=SKILL)
        import shutil

        shutil.rmtree(library / "skills" / SKILL / "knowledge")
        problems = "\n".join(validate_library(library))
        self.assertIn("capability 'knowledge: true' but", problems)

    def test_undeclared_layer_with_content_is_flagged(self):
        library = make_library(self.tmp, names=(SKILL,))
        add_layers(library / "skills" / SKILL, SKILL)
        # catalog has no capabilities block at all -> stays valid (compat)
        self.assertEqual(
            [p for p in validate_library(library) if "capability" in p], []
        )
        # ...but an explicit block must match reality
        catalog = library / "skills.yaml"
        catalog.write_text(
            catalog.read_text(encoding="utf-8")
            + "    capabilities:\n      knowledge: false\n      data: true\n      observations: true\n",
            encoding="utf-8",
        )
        problems = "\n".join(validate_library(library))
        self.assertIn("knowledge/ has content but the capability flag", problems)
