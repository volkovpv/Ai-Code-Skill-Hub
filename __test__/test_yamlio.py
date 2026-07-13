"""Targeted tests for the YAML-subset parser/emitter (`skill_library.yamlio`).

These tests were written from a mutation-testing triage: each test pins an
observable behaviour whose mutants survived the existing suite. They cover
comment stripping around quotes, escape handling, quoted keys, flow lists,
block structure edge cases, error diagnostics (message + line number), and
the exact canonical output of the emitter.
"""

from __future__ import annotations

from skill_library.yamlio import YamlError, dump_file, dumps, load_file, loads

from .helpers import TempDirTestCase

import unittest


class CommentStrippingTests(unittest.TestCase):
    """Trailing ``#`` comments are stripped only outside of quotes."""

    def test_comment_after_single_quoted_value(self):
        self.assertEqual(loads("key: 'ab' # comment"), {"key": "ab"})

    def test_comment_after_double_quoted_value(self):
        self.assertEqual(loads('key: "ab" # comment'), {"key": "ab"})

    def test_comment_after_double_quoted_value_with_escaped_quote(self):
        self.assertEqual(loads('key: "a\\"b" # comment'), {"key": 'a"b'})

    def test_comment_with_single_space_before_hash(self):
        self.assertEqual(loads("key: value # comment"), {"key": "value"})

    def test_hash_not_preceded_by_space_is_data(self):
        self.assertEqual(loads("key: aX# tail"), {"key": "aX# tail"})

    def test_plain_value_before_comment_is_kept_verbatim(self):
        # A plain (unquoted) scalar must not accidentally enter "quote mode".
        self.assertEqual(loads("key: Xab # c"), {"key": "Xab"})

    def test_trailing_tab_outside_indentation_is_allowed(self):
        # Only tabs in *indentation* are rejected; elsewhere they are data
        # (and a trailing tab is stripped like any trailing whitespace).
        self.assertEqual(loads("key: value\t"), {"key": "value"})


class DoubleQuoteEscapeTests(unittest.TestCase):
    """Escape sequences inside double-quoted scalars."""

    def test_newline_and_tab_escapes(self):
        self.assertEqual(loads('k: "a\\nb\\tc"'), {"k": "a\nb\tc"})

    def test_backslash_and_quote_escapes(self):
        self.assertEqual(loads('k: "a\\\\b\\"c"'), {"k": 'a\\b"c'})

    def test_escape_at_end_of_string(self):
        self.assertEqual(loads('k: "ab\\n"'), {"k": "ab\n"})

    def test_dangling_backslash_raises_yaml_error(self):
        # ``"ab\`` + closing quote: the backslash consumes the terminator.
        with self.assertRaises(YamlError):
            loads('k: "ab\\"')

    def test_unknown_escape_raises_yaml_error(self):
        with self.assertRaises(YamlError):
            loads('k: "a\\qb"')


class ScalarTests(unittest.TestCase):
    """Plain / quoted scalars and the reserved words."""

    def test_empty_flow_mapping(self):
        self.assertEqual(loads("k: {}"), {"k": {}})

    def test_closing_bracket_without_opening_is_plain_string(self):
        self.assertEqual(loads("k: a]"), {"k": "a]"})

    def test_empty_quoted_strings(self):
        self.assertEqual(loads('k: ""'), {"k": ""})
        self.assertEqual(loads("k: ''"), {"k": ""})

    def test_lone_quote_raises(self):
        with self.assertRaises(YamlError):
            loads('k: "')
        with self.assertRaises(YamlError):
            loads("k: '")

    def test_doubled_single_quote_escape(self):
        self.assertEqual(loads("k: 'a''b'"), {"k": "a'b"})

    def test_plain_scalar_is_not_rejected_as_special(self):
        # Only ``&*!|>`` are rejected as the first character.
        self.assertEqual(loads("k: Xvalue"), {"k": "Xvalue"})

    def test_null_spellings(self):
        self.assertEqual(
            loads("a: Null\nb: NULL\nc: ~"), {"a": None, "b": None, "c": None}
        )

    def test_true_spellings(self):
        self.assertEqual(loads("a: True\nb: TRUE"), {"a": True, "b": True})

    def test_false_spellings(self):
        self.assertEqual(loads("a: False\nb: FALSE"), {"a": False, "b": False})

    def test_zero_padded_int_stays_string(self):
        # M-17: a leading-zero token (id/index/code) is a string in YAML 1.2;
        # coercing to int would drop the padding irreversibly.
        self.assertEqual(loads("a: 007\nb: 00\nc: -042"),
                         {"a": "007", "b": "00", "c": "-042"})

    def test_bare_zero_and_plain_ints_still_coerce(self):
        self.assertEqual(loads("a: 0\nb: -0\nc: 42\nd: -7"),
                         {"a": 0, "b": 0, "c": 42, "d": -7})

    def test_zero_padded_int_round_trips_as_string(self):
        self.assertEqual(loads(dumps({"pin": "007"})), {"pin": "007"})


class FlowListTests(unittest.TestCase):
    def test_plain_items_never_enter_quote_mode(self):
        self.assertEqual(loads("k: [Xa, b]"), {"k": ["Xa", "b"]})


class QuotedKeyTests(unittest.TestCase):
    """``"key": value`` lines take the quoted-key path in ``_split_key``."""

    def test_basic_double_quoted_key(self):
        self.assertEqual(loads('"a": 1'), {"a": 1})

    def test_single_quoted_key_with_space(self):
        self.assertEqual(loads("'a b': 1"), {"a b": 1})

    def test_empty_quoted_key(self):
        # Pins current behaviour: an explicitly quoted empty key is accepted.
        self.assertEqual(loads('"": 1'), {"": 1})

    def test_escaped_quote_inside_key(self):
        self.assertEqual(loads('"a\\"b": 1'), {'a"b': 1})

    def test_escaped_quote_as_first_key_character(self):
        self.assertEqual(loads('"\\"x": 1'), {'"x': 1})

    def test_space_between_quoted_key_and_colon(self):
        self.assertEqual(loads('"a" : 1'), {"a": 1})

    def test_unquoted_key_starting_with_letter_is_not_quoted_path(self):
        self.assertEqual(loads("Xkey: 1"), {"Xkey": 1})

    def test_unterminated_quoted_key_raises_yaml_error(self):
        with self.assertRaisesRegex(YamlError, "unterminated quoted key"):
            loads('"abc: 1')


class BlockStructureTests(unittest.TestCase):
    def test_bare_dash_is_list_with_null_item(self):
        self.assertEqual(loads("-"), [None])

    def test_key_without_value_followed_by_sibling(self):
        # A sibling at the *same* indent must not be swallowed as the value.
        self.assertEqual(loads("a:\nb: 1"), {"a": None, "b": 1})

    def test_list_item_with_nested_mapping_block(self):
        self.assertEqual(loads("- a:\n    x: 1"), [{"a": {"x": 1}}])

    def test_list_item_line_inside_mapping_raises(self):
        with self.assertRaises(YamlError):
            loads("k: 1\n- a: 1")


class ErrorDiagnosticsTests(unittest.TestCase):
    """Errors must carry the offending line number and a stable message.

    These assertions pin the parser's diagnostics contract; they also kill
    the mutation-testing survivors that corrupt line numbers or messages.
    """

    def check(self, text: str, *fragments: str):
        with self.assertRaises(YamlError) as cm:
            loads(text)
        message = str(cm.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)

    def test_tab_in_indentation_reports_physical_line(self):
        self.check("a: 1\nb: 2\n\tc: 3", "line 3", "tabs are not allowed")

    def test_flow_mapping_reports_line(self):
        self.check("a: 1\nb: {x: 1}", "line 2", "flow mappings are not supported")

    def test_flow_mapping_in_list_item_mapping_reports_line(self):
        self.check("- k: {a: 1}", "line 1", "flow mappings are not supported")

    def test_empty_flow_list_item_reports_line(self):
        self.check("a: [x,,y]", "line 1", "empty item in flow list")

    def test_bad_scalar_inside_flow_list_reports_line(self):
        self.check("a: [&x]", "line 1", "unsupported YAML feature")

    def test_bad_escape_reports_line(self):
        self.check('k: "a\\qb"', "line 1", "unsupported escape sequence")

    def test_bad_escape_in_quoted_key_reports_line(self):
        self.check('"a\\qb": 1', "line 1", "unsupported escape sequence")

    def test_missing_colon_after_quoted_key(self):
        self.check('"a" 1', "line 1", "expected ':' after quoted key")

    def test_empty_mapping_key(self):
        self.check(": 1", "line 1", "empty mapping key")

    def test_line_without_colon(self):
        self.check("plainscalar", "line 1", "expected 'key: value'")

    def test_duplicate_key_reports_second_line(self):
        self.check("a: 1\na: 2", "line 2", "duplicate key")

    def test_bare_dash_inside_mapping(self):
        self.check("a: 1\n-", "line 2", "unexpected list item inside mapping")

    def test_bad_scalar_as_list_item_reports_line(self):
        self.check("- &a", "line 1", "unsupported YAML feature")


class DumpTests(unittest.TestCase):
    """Canonical emitter output, pinned exactly."""

    def test_scalar_keywords_are_lowercase(self):
        self.assertEqual(
            dumps({"a": None, "b": True, "c": False}),
            "a: null\nb: true\nc: false\n",
        )

    def test_string_escapes_are_emitted(self):
        self.assertEqual(
            dumps({"k": 'a\\b"c\nd\te'}),
            'k: "a\\\\b\\"c\\nd\\te"\n',
        )

    def test_nested_map_and_list_use_two_space_indent(self):
        self.assertEqual(
            dumps({"a": {"b": 1}, "c": [1, 2]}),
            "a:\n  b: 1\nc:\n  - 1\n  - 2\n",
        )

    def test_list_of_mappings_inlines_first_key(self):
        self.assertEqual(dumps([{"k": 1, "m": 2}]), "- k: 1\n  m: 2\n")

    def test_carriage_return_is_rejected(self):
        with self.assertRaises(YamlError):
            dumps({"a": "x\ry"})

    def test_nested_list_item_is_rejected(self):
        with self.assertRaises(YamlError):
            dumps({"a": [[1, 2]]})

    def test_empty_dict_list_item_is_rejected(self):
        with self.assertRaises(YamlError):
            dumps({"a": [{}]})

    def test_roundtrip_of_tricky_strings(self):
        for value in ("ab\n", "ab ", "a\\b", 'a"b', "a\nb", "a\tb", 'a\\b"c\nd\te'):
            with self.subTest(value=value):
                self.assertEqual(loads(dumps({"k": value})), {"k": value})

    def test_roundtrip_of_unicode_keys_and_values(self):
        data = {"ключ": "значение"}
        self.assertEqual(loads(dumps(data)), data)


class FileIoTests(TempDirTestCase):
    def test_file_roundtrip_uses_utf8(self):
        # dump_file/load_file must be locale-independent (explicit UTF-8).
        path = self.tmp / "data.yaml"
        data = {"название": "проверка", "items": ["a", "б"]}
        dump_file(path, data)
        self.assertIn("проверка", path.read_text(encoding="utf-8"))
        self.assertEqual(load_file(path), data)

    def test_load_file_reports_non_utf8_as_yamlerror(self):
        # A binary/mis-encoded file must surface as YamlError (which callers
        # already handle), not a bare UnicodeDecodeError (audit H-3).
        path = self.tmp / "broken.yaml"
        path.write_bytes(b"version: \xff\xfe\n")
        with self.assertRaises(YamlError) as ctx:
            load_file(path)
        self.assertIn("UTF-8", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
