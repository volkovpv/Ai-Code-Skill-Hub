"""Validation of the optional layers: knowledge/, data/, observations/,
content policy (sizes, secret scan) and capability consistency."""

from __future__ import annotations

from skill_library import validator
from skill_library.validator import (
    DEFAULT_CONTENT_POLICY,
    _check_content_policy,
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

    def test_non_integer_max_bytes_is_reported_not_raised(self):
        # M-2: a non-numeric max_tracked_file_bytes must degrade to a problem,
        # not a bare ValueError traceback out of the fail-closed validator.
        problems = validate_skill_dir(self.skill, {"max_tracked_file_bytes": "abc"})
        self.assertTrue(
            any("max_tracked_file_bytes must be within" in p for p in problems), problems
        )

    def test_valid_integer_max_bytes_reports_no_policy_problem(self):
        # negative control: a legitimate integer limit raises no size problem.
        problems = validate_skill_dir(self.skill, {"max_tracked_file_bytes": 262144})
        self.assertFalse(
            any("max_tracked_file_bytes" in p for p in problems), problems
        )

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

    def test_accepted_with_only_blank_evidence_fails(self):
        obs = self.accepted / "OBS-20260101-003.md"
        obs.write_text(
            "---\nid: OBS-20260101-003\nstatus: accepted\nobserved_at: 2026-01-01\n"
            "scope: x\nevidence:\n  - \"\"\n  - \"  \"\nreviewed_by: r\n"
            "reviewed_at: 2026-01-02\n---\n\nBody.\n",
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


# H-5: one obviously-fake positive marker (must be caught) and one non-secret
# look-alike (must NOT be flagged) per secret-scan heuristic. Sample lengths are
# crafted to sit just above / below each pattern's threshold. Every marker is an
# obvious placeholder ("FAKE"/canonical AWS doc key), never a real credential.
SECRET_SCAN_CASES = [
    (
        "private key block",
        "-----BEGIN PRIVATE KEY-----\nFAKE-NOT-A-REAL-KEY\n-----END PRIVATE KEY-----\n",
        "-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n",
    ),
    ("AWS access key id", "AKIAIOSFODNN7EXAMPLE\n", "AKIA1234\n"),
    ("GitHub token", "ghp_FAKE" + "0" * 32 + "\n", "ghp_tooshort\n"),
    ("GitHub fine-grained token", "github_pat_FAKE" + "0" * 20 + "\n", "github_pat_tooshort\n"),
    ("Slack token", "xoxb-FAKE" + "0" * 8 + "\n", "xoxb-short\n"),
    ("API secret key", "sk-FAKE" + "0" * 30 + "\n", "sk-shortkey\n"),
    ("hardcoded credential", 'api_key = "FAKE' + "0" * 16 + '"\n', 'password = "hunter2"\n'),
]


class TestSecretScanCoverage(TempDirTestCase):
    """H-5: every one of the 7 secret-scan heuristics is guarded by a positive
    (fake marker is caught) and a negative (look-alike is not flagged) case, so
    a mutation/typo in any single regex fails at least one test."""

    def _scan(self, name: str, content: str) -> str:
        skill = self.make_dir(name)
        (skill / "sample.txt").write_text(content, encoding="utf-8")
        problems: list[str] = []
        _check_content_policy(skill, dict(DEFAULT_CONTENT_POLICY), problems)
        return "\n".join(problems)

    def test_every_scanner_pattern_has_a_paired_case(self):
        # Structural guard: adding a pattern without a paired case fails here,
        # closing the exact gap H-5 describes (untested regex mutates silently).
        kinds_under_test = {kind for kind, _, _ in SECRET_SCAN_CASES}
        kinds_in_scanner = {kind for _, kind in validator._SECRET_PATTERNS}
        self.assertEqual(kinds_under_test, kinds_in_scanner)

    def test_positive_markers_are_flagged(self):
        for i, (kind, positive, _negative) in enumerate(SECRET_SCAN_CASES):
            with self.subTest(kind=kind):
                self.assertIn(f"possible {kind} detected", self._scan(f"pos-{i}", positive))

    def test_negative_lookalikes_are_not_flagged(self):
        for i, (kind, _positive, negative) in enumerate(SECRET_SCAN_CASES):
            with self.subTest(kind=kind):
                self.assertNotIn("secrets are forbidden", self._scan(f"neg-{i}", negative))
