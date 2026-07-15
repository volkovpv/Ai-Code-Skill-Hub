"""Shared conformance battery for the two skill checkers' lexical scanners.

The ``typescript-coding`` and ``typescript-nestjs`` checkers deliberately
duplicate one scanner (each skill ships self-contained); this mixin pins the
scanner's exact behaviour once and both dedicated test modules run it against
their own copy, so the copies cannot drift apart — and mutation testing gets
precise, output-equality kills in both files.

Not named ``test_*``: unittest must not discover the mixin itself.
"""

from __future__ import annotations

TRICKY_SOURCE = (
    "const a = 'str'; // tail note\n"
    "/* block\n"
    "still */const b = `t ${go(1)} u`;\n"
    "const r = /re[/]x/g; const d = 8 / 2;\n"
    "const s = \"d\\\"q\"; return /k/;\n"
)

# Exact per-line views: literals and comments blank to spaces (columns kept),
# interpolation code stays, comment text (without delimiters) lands in the
# comment view. The regex flag `g` is an identifier and stays code.
TRICKY_CODE_VIEW = [
    "const a =      ;             ",
    "        ",
    "        const b =      go(1)    ;",
    "const r =         g; const d = 8 / 2;",
    "const s =       ; return    ;",
    "",
]
TRICKY_COMMENT_VIEW = [
    "                    tail note",
    "   block",
    "still                            ",
    "                                     ",
    "                             ",
    "",
]


class ScannerConformanceMixin:
    """Requires: self.MODULE (the imported checker module) + unittest.TestCase."""

    MODULE = None  # set by the concrete test class

    # --- mask_source -------------------------------------------------------

    def test_mask_source_exact_views(self):
        code, comment = self.MODULE.mask_source(TRICKY_SOURCE)
        self.assertEqual(code, TRICKY_CODE_VIEW)
        self.assertEqual(comment, TRICKY_COMMENT_VIEW)

    def test_mask_source_empty_and_no_trailing_newline(self):
        self.assertEqual(self.MODULE.mask_source(""), ([""], [""]))
        code, comment = self.MODULE.mask_source("a // b")
        self.assertEqual(code, ["a     "])
        self.assertEqual(comment, ["     b"])

    def test_mask_source_unterminated_states_reset_at_newline(self):
        code, _ = self.MODULE.mask_source("const s = 'open\nnext();")
        self.assertEqual(code, ["const s =      ", "next();"])
        code, _ = self.MODULE.mask_source("const r = /open\nnext();")
        self.assertEqual(code, ["const r =      ", "next();"])

    def test_mask_source_block_comment_spans_lines_until_closed(self):
        code, comment = self.MODULE.mask_source("/*a\nb\nc*/d()")
        self.assertEqual(code, ["   ", " ", "   d()"])
        self.assertEqual(comment, ["  a", "b", "c     "])

    def test_mask_source_template_nesting_and_escapes(self):
        # Escaped backtick stays inside the template; only the innermost
        # interpolation variable `z` survives as code.
        code, _ = self.MODULE.mask_source("const t = `a \\` ${`b ${z} c`} d`;")
        self.assertEqual(code, ["const t =              z        ;"])

    def test_mask_source_escaped_quotes_stay_inside_string(self):
        code, _ = self.MODULE.mask_source("const s = 'a\\'b'; f();")
        self.assertEqual(code, ["const s =       ; f();"])

    def test_mask_source_regex_class_hides_slash(self):
        code, _ = self.MODULE.mask_source("const r = /a[/]b/; g();")
        self.assertEqual(code, ["const r =        ; g();"])

    def test_mask_source_division_keeps_operands_in_code(self):
        code, _ = self.MODULE.mask_source("const d = total / 2; h();")
        self.assertEqual(code, ["const d = total / 2; h();"])

    def test_mask_source_keyword_starts_regex(self):
        code, _ = self.MODULE.mask_source("return /pat/.test(s);")
        self.assertEqual(code, ["return      .test(s);"])

    # --- path contexts -----------------------------------------------------

    def test_is_test_path_truth_table(self):
        true_paths = [
            "a.spec.ts", "a.spec.mts", "a.spec.cts",
            "b.integration-spec.ts", "c.test.ts", "c.test.mts", "d_test.ts",
            "test_e.ts", "pkg/__test__/f.ts", "pkg/__tests__/g.ts",
            "pkg/test/h.ts", "pkg/tests/i.ts", "UP/CASE.SPEC.TS",
            "win\\tests\\j.ts",
        ]
        false_paths = [
            "src/a.ts", "latest.ts", "protest.ts", "contest/x.ts",
            "src/testing/x.ts", "xspec.ts", "spec.ts", "attest.ts",
        ]
        for p in true_paths:
            self.assertTrue(self.MODULE.is_test_path(p), p)
        for p in false_paths:
            self.assertFalse(self.MODULE.is_test_path(p), p)

    # --- suppression pragmas -------------------------------------------------

    def test_parse_pragmas_accepts_only_the_strict_form(self):
        known = frozenset({"AA-BB", "CC-DD"})
        parse = self.MODULE.parse_pragmas

        self.assertEqual(parse("plain comment", "x.ts", 1, known), (set(), []))
        self.assertEqual(
            parse("skill-check-ignore: AA-BB -- why not", "x.ts", 1, known),
            ({"AA-BB"}, []),
        )
        self.assertEqual(
            parse("skill-check-ignore: AA-BB, CC-DD -- both fine", "x.ts", 1, known),
            ({"AA-BB", "CC-DD"}, []),
        )

        for text, fragment in [
            ("skill-check-ignore everything", "malformed"),
            ("skill-check-ignore: AA-BB", "malformed"),
            ("skill-check-ignore: aa-bb -- lower", "malformed"),
            ("skill-check-ignore: * -- star", "malformed"),
            ("skill-check-ignore: AA-BB --   ", "justification must not be empty"),
            ("skill-check-ignore: ZZ-XX -- oops", "unknown rule code"),
            ("skill-check-ignore: AA-BB -- a skill-check-ignore: CC-DD -- b", "multiple"),
        ]:
            with self.subTest(text=text):
                suppressed, errors = parse(text, "f.ts", 7, known)
                self.assertEqual(suppressed, set(), text)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(fragment, errors[0])
                self.assertTrue(errors[0].startswith("f.ts:7: "), errors[0])

    # --- driver output contract ---------------------------------------------

    def test_main_reports_finding_count_on_stderr(self):
        import contextlib
        import io
        import sys

        out, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("")
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = self.MODULE.main([])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "# 0 finding(s)\n")
