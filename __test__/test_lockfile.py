"""Lock file round-trips and the YAML-subset parser/emitter behind them."""

from __future__ import annotations


from unittest import mock
from skill_library import yamlio
from skill_library.lockfile import (
    LOCKFILE_NAME,
    LockError,
    get_entry,
    load_lock,
    lock_path,
    remove_entry,
    save_lock,
    upsert_entry,
)

from .helpers import TempDirTestCase

SAMPLE_ENTRY = {
    "name": "alpha-skill",
    "source": "/some/library",
    "source_commit": None,
    "skill_version": "0.1.0",
    "agent": "universal",
    "mode": "copy",
    "target_path": ".agents/skills/alpha-skill",
    "checksum": "sha256:deadbeef",
    "installed_at": "2026-07-12T12:00:00+00:00",
    "updated_at": None,
    "files": [{"path": "SKILL.md", "sha256": "abc123"}],
}


class TestLockfile(TempDirTestCase):
    def test_missing_lock_is_empty(self):
        data = load_lock(self.tmp)
        self.assertEqual(data, {"version": 1, "skills": []})

    def test_roundtrip(self):
        data = load_lock(self.tmp)
        upsert_entry(data, dict(SAMPLE_ENTRY))
        save_lock(self.tmp, data)
        self.assertTrue(lock_path(self.tmp).is_file())
        loaded = load_lock(self.tmp)
        self.assertEqual(loaded["skills"][0], SAMPLE_ENTRY)

    def test_upsert_replaces_and_sorts(self):
        data = load_lock(self.tmp)
        upsert_entry(data, dict(SAMPLE_ENTRY, name="zeta-skill"))
        upsert_entry(data, dict(SAMPLE_ENTRY))
        upsert_entry(data, dict(SAMPLE_ENTRY, skill_version="0.2.0"))
        self.assertEqual([e["name"] for e in data["skills"]], ["alpha-skill", "zeta-skill"])
        self.assertEqual(get_entry(data, "alpha-skill")["skill_version"], "0.2.0")

    def test_remove_entry(self):
        data = load_lock(self.tmp)
        upsert_entry(data, dict(SAMPLE_ENTRY))
        self.assertTrue(remove_entry(data, "alpha-skill"))
        self.assertFalse(remove_entry(data, "alpha-skill"))
        self.assertEqual(data["skills"], [])

    def test_malformed_lock_raises(self):
        (self.tmp / LOCKFILE_NAME).write_text("version: 99\nskills: []\n", encoding="utf-8")
        with self.assertRaises(LockError):
            load_lock(self.tmp)
        (self.tmp / LOCKFILE_NAME).write_text("- just\n- a list\n", encoding="utf-8")
        with self.assertRaises(LockError):
            load_lock(self.tmp)

    def test_load_lock_defaults_missing_skills_key_to_empty_list(self):
        (self.tmp / LOCKFILE_NAME).write_text("version: 1\n", encoding="utf-8")
        self.assertEqual(load_lock(self.tmp), {"version": 1, "skills": []})

    def test_malformed_lock_message_names_the_problem(self):
        (self.tmp / LOCKFILE_NAME).write_text(
            "version: 1\nskills: not-a-list\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(LockError, "malformed lock file"):
            load_lock(self.tmp)

    def test_save_lock_creates_missing_target_directories(self):
        nested = self.tmp / "deep" / "project"
        save_lock(nested, {"skills": []})
        self.assertEqual(load_lock(nested), {"version": 1, "skills": []})

    def test_entry_helpers_tolerate_missing_skills_key(self):
        self.assertIsNone(get_entry({}, "alpha-skill"))
        self.assertFalse(remove_entry({}, "alpha-skill"))
        data: dict = {}
        upsert_entry(data, dict(SAMPLE_ENTRY))
        self.assertEqual(data["skills"], [SAMPLE_ENTRY])

    def test_upsert_sorts_nameless_entries_under_the_empty_string(self):
        # Entries without a 'name' sort under "" — before any named entry.
        data = {"version": 1, "skills": [{"name": "AAA"}]}
        upsert_entry(data, {"note": "no name"})
        self.assertEqual(data["skills"], [{"note": "no name"}, {"name": "AAA"}])

    def test_unsupported_version_message_names_both_versions(self):
        (self.tmp / LOCKFILE_NAME).write_text("version: 2\nskills: []\n", encoding="utf-8")
        with self.assertRaisesRegex(LockError, r"unsupported lock version 2 \(expected 1\)"):
            load_lock(self.tmp)

    def test_save_lock_normalizes_missing_sections(self):
        save_lock(self.tmp, {})
        self.assertEqual(load_lock(self.tmp), {"version": 1, "skills": []})
        text = lock_path(self.tmp).read_text(encoding="utf-8")
        self.assertIn("version: 1", text)

    def test_lookup_skips_entries_that_are_not_mappings(self):
        data = {"version": 1, "skills": ["junk", dict(SAMPLE_ENTRY)]}
        self.assertEqual(get_entry(data, "alpha-skill"), SAMPLE_ENTRY)
        self.assertIsNone(get_entry(data, "junk"))
        self.assertTrue(remove_entry(data, "alpha-skill"))
        self.assertEqual(data["skills"], ["junk"])


class TestYamlSubset(TempDirTestCase):
    def test_scalar_types(self):
        data = yamlio.loads(
            "a: 1\nb: true\nc: null\nd: 1.5\ne: plain text\nf: 'quoted: x'\n"
            'g: "with \\"escapes\\" and #hash"\nh: [x, y, 2]\ni: []\n'
        )
        self.assertEqual(
            data,
            {
                "a": 1,
                "b": True,
                "c": None,
                "d": 1.5,
                "e": "plain text",
                "f": "quoted: x",
                "g": 'with "escapes" and #hash',
                "h": ["x", "y", 2],
                "i": [],
            },
        )

    def test_comments_and_nesting(self):
        data = yamlio.loads(
            "# header\nroot:\n  child: value  # trailing\n  items:\n"
            "    - name: one\n      n: 1\n    - name: two\n      n: 2\n"
        )
        self.assertEqual(
            data,
            {"root": {"child": "value", "items": [{"name": "one", "n": 1}, {"name": "two", "n": 2}]}},
        )

    def test_roundtrip_awkward_strings(self):
        original = {
            "plain": "sha256:abcdef",
            "timestamp": "2026-07-12T12:00:00+00:00",
            "needs_quotes": "value: with colon",
            "hash": "contains # hash",
            "unicode": "русский текст",
            "list": ["a", 1, None, True],
            "nested": {"empty_list": [], "n": None},
        }
        self.assertEqual(yamlio.loads(yamlio.dumps(original)), original)

    def test_unsupported_features_rejected(self):
        for text in ("a: &anchor 1\n", "a: *ref\n", "a: |\n  block\n", "a: {flow: map}\n"):
            with self.assertRaises(yamlio.YamlError, msg=text):
                yamlio.loads(text)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(yamlio.YamlError):
            yamlio.loads("a: 1\na: 2\n")

    def test_tabs_rejected(self):
        with self.assertRaises(yamlio.YamlError):
            yamlio.loads("a:\n\tb: 1\n")

    def test_empty_flow_list_items_rejected(self):
        # Fail closed: "[a,,b]" and trailing commas are typos, not data.
        for text in ("x: [a,,b]\n", "x: [a,]\n", "x: [,]\n"):
            with self.assertRaisesRegex(yamlio.YamlError, "empty item in flow list", msg=text):
                yamlio.loads(text)


class TestAtomicLockWrite(TempDirTestCase):
    def test_replace_failure_preserves_previous_lock_and_cleans_temp_file(self):
        path = lock_path(self.tmp)
        path.write_text("original lock\n", encoding="utf-8")
        with mock.patch("skill_library.lockfile.os.replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                save_lock(self.tmp, {"version": 1, "skills": [dict(SAMPLE_ENTRY)]})
        self.assertEqual(path.read_text(encoding="utf-8"), "original lock\n")
        leftovers = [p for p in self.tmp.iterdir() if p != path]
        self.assertEqual(leftovers, [])
