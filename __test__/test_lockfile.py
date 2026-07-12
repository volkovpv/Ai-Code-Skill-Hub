"""Lock file round-trips and the YAML-subset parser/emitter behind them."""

from __future__ import annotations

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
