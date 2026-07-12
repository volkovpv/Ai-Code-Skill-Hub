"""Observation lifecycle: add (candidate only) -> approve/reject with audit."""

from __future__ import annotations

from datetime import date

from skill_library import yamlio
from skill_library.discovery import split_frontmatter
from skill_library.observations import (
    ObservationError,
    add_observation,
    list_observations,
    review_observation,
)
from skill_library.validator import validate_skill_dir

from .helpers import TempDirTestCase, make_layered_library

SKILL = "alpha-skill"
TODAY = date(2026, 7, 12)


class ObservationTestCase(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = make_layered_library(self.tmp, name=SKILL)
        self.skill = self.library / "skills" / SKILL
        self.note = self.tmp / "note.md"
        self.note.write_text(
            "# Diff parsing fails on renames\n\nSeen while testing rename-only diffs.\n",
            encoding="utf-8",
        )


class TestAdd(ObservationTestCase):
    def test_add_creates_candidate_never_accepted(self):
        obs_id, path = add_observation(self.skill, self.note, today=TODAY)
        self.assertEqual(obs_id, "OBS-20260712-001")
        self.assertEqual(path.parent.name, "candidates")
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "candidate")
        self.assertIsNone(meta["reviewed_by"])
        self.assertIn("renames", body)
        # accepted/ still contains only the pre-existing fixture observation
        accepted = list_observations(self.skill, status="accepted")
        self.assertEqual([r["id"] for r in accepted], ["OBS-20260101-001"])
        # the skill remains valid with the new candidate
        self.assertEqual(validate_skill_dir(self.skill), [])

    def test_add_generates_sequential_ids(self):
        first, _ = add_observation(self.skill, self.note, today=TODAY)
        second, _ = add_observation(self.skill, self.note, today=TODAY)
        self.assertEqual((first, second), ("OBS-20260712-001", "OBS-20260712-002"))

    def test_add_dry_run_creates_nothing(self):
        obs_id, path = add_observation(self.skill, self.note, today=TODAY, dry_run=True)
        self.assertEqual(obs_id, "OBS-20260712-001")
        self.assertFalse(path.exists())

    def test_add_requires_body(self):
        empty = self.tmp / "empty.md"
        empty.write_text("---\nscope: x\n---\n\n", encoding="utf-8")
        with self.assertRaises(ObservationError):
            add_observation(self.skill, empty, today=TODAY)


class TestReview(ObservationTestCase):
    def test_approve_requires_evidence(self):
        obs_id, _ = add_observation(self.skill, self.note, today=TODAY)
        with self.assertRaises(ObservationError) as ctx:
            review_observation(self.skill, obs_id, "accepted", reviewed_by="reviewer", today=TODAY)
        self.assertIn("evidence", str(ctx.exception))

    def test_approve_moves_file_and_records_audit_metadata(self):
        obs_id, _ = add_observation(
            self.skill, self.note, evidence=["data/fixtures/sample.txt"], today=TODAY
        )
        dest = review_observation(
            self.skill, obs_id, "accepted", reviewed_by="reviewer", today=TODAY
        )
        self.assertEqual(dest.parent.name, "accepted")
        meta, _ = split_frontmatter(dest.read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "accepted")
        self.assertEqual(meta["reviewed_by"], "reviewer")
        self.assertEqual(meta["reviewed_at"], "2026-07-12")
        self.assertFalse(
            (self.skill / "observations" / "candidates" / f"{obs_id}.md").exists()
        )
        self.assertEqual(validate_skill_dir(self.skill), [])

    def test_reject_keeps_audit_trail(self):
        obs_id, _ = add_observation(self.skill, self.note, today=TODAY)
        dest = review_observation(
            self.skill, obs_id, "rejected", reviewed_by="reviewer",
            note="not reproducible", today=TODAY,
        )
        self.assertEqual(dest.parent.name, "rejected")
        meta, _ = split_frontmatter(dest.read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "rejected")
        self.assertEqual(meta["review_note"], "not reproducible")
        self.assertEqual(validate_skill_dir(self.skill), [])

    def test_review_requires_reviewer_and_candidate_status(self):
        obs_id, _ = add_observation(
            self.skill, self.note, evidence=["e"], today=TODAY
        )
        with self.assertRaises(ObservationError):
            review_observation(self.skill, obs_id, "accepted", reviewed_by=" ", today=TODAY)
        review_observation(self.skill, obs_id, "accepted", reviewed_by="reviewer", today=TODAY)
        with self.assertRaises(ObservationError):  # already reviewed
            review_observation(self.skill, obs_id, "rejected", reviewed_by="reviewer", today=TODAY)

    def test_review_dry_run_changes_nothing(self):
        obs_id, src = add_observation(self.skill, self.note, evidence=["e"], today=TODAY)
        dest = review_observation(
            self.skill, obs_id, "accepted", reviewed_by="r", today=TODAY, dry_run=True
        )
        self.assertTrue(src.exists())
        self.assertFalse(dest.exists())

    def test_unknown_observation(self):
        with self.assertRaises(ObservationError):
            review_observation(self.skill, "OBS-20990101-001", "accepted", reviewed_by="r")


class TestListing(ObservationTestCase):
    def test_list_filters_by_status(self):
        add_observation(self.skill, self.note, today=TODAY)
        all_ids = [r["id"] for r in list_observations(self.skill)]
        self.assertEqual(
            all_ids, ["OBS-20260101-001", "OBS-20260101-002", "OBS-20260712-001"]
        )
        candidates = [r["id"] for r in list_observations(self.skill, status="candidate")]
        self.assertEqual(candidates, ["OBS-20260101-002", "OBS-20260712-001"])
        with self.assertRaises(ObservationError):
            list_observations(self.skill, status="weird")

    def test_roundtrip_preserves_frontmatter_via_yamlio(self):
        obs_id, path = add_observation(
            self.skill, self.note, evidence=["a: colon value", "plain"], today=TODAY
        )
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["evidence"], ["a: colon value", "plain"])
        self.assertEqual(yamlio.loads(yamlio.dumps(meta)), meta)
