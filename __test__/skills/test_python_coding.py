"""Dedicated tests for skills/python-coding (run via `skillctl test python-coding`).

Exercise the convention checker two ways:

* **in-process** (importing the script as a module) — this is what puts the
  analyzer under line/branch coverage and mutation testing;
* **as a CLI** (subprocess with a sandboxed environment) — this pins the
  exit-code and output contract consumers rely on.

The scanner masks *Python* lexical structure (``#`` comments, string
literals including triple-quoted strings, f-string interpolations), so the
shared conformance mixin for the other analyzers does not apply; the
equivalent battery is pinned here against Python sources instead.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from __test__.helpers import sandboxed_env

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "python-coding"
SCRIPT = SKILL / "scripts" / "check_py_conventions.py"
FIXTURES = SKILL / "data" / "fixtures"
EXAMPLES = SKILL / "data" / "examples"

# Every rule the checker enforces; violations.py triggers each exactly once.
ALL_CODES = {
    "PY-PRINT",
    "PY-ENV",
    "PY-ANY",
    "PY-SUPPRESS",
    "PY-BARE-EXCEPT",
    "PY-ASSERT",
    "PY-DEBUG",
}


def load_checker():
    """Import the checker script as a module (measured by coverage/mutmut).

    The module name matches mutmut's path-derived mutant naming
    (skills.python-coding.scripts.check_py_conventions), so trampoline hits
    recorded during the stats run associate with the generated mutants.
    """
    spec = importlib.util.spec_from_file_location(
        "skills.python-coding.scripts.check_py_conventions", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


def run_checker(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    # Sanitized environment: skill scripts must not need or see any secrets.
    env = sandboxed_env()
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        # cwd is the library root: under mutation testing the script is a
        # trampoline-rewritten copy that imports mutmut, whose config loads
        # from the working directory's pyproject.toml.
        input=stdin,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def codes_in(stdout: str) -> list[str]:
    """The finding code of every non-empty output line ('<path>:<line>: CODE msg')."""
    return [line.split()[1] for line in stdout.splitlines() if line.strip()]


def check(source: str, label: str = "sample.py") -> tuple[list[str], list[str]]:
    """In-process shorthand: (finding codes, pragma errors)."""
    findings, errors = CHECKER.check_text(source, label)
    return [f[2] for f in findings], errors


class TempDirMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="python-coding-test-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, rel: str, content: str) -> Path:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class TestFixtureContract(TempDirMixin):
    """The skill's own data layer is the calibrated ground truth."""

    def test_clean_sample_has_no_findings(self):
        result = run_checker(str(FIXTURES / "clean_sample.py"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_violations_fixture_flags_every_rule_once(self):
        result = run_checker(str(FIXTURES / "violations.py"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        found = codes_in(result.stdout)
        # Exactly one finding per rule — no rule missing, none doubled.
        self.assertEqual(sorted(found), sorted(ALL_CODES))

    def test_masked_literals_fixture_is_silent(self):
        # Every rule is quoted inside strings/f-string literals/comments there.
        result = run_checker(str(FIXTURES / "masked_literals.py"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_justified_noqa_fixture_is_clean(self):
        # A line-scoped `# noqa: <RULE> -- <reason>` naming exactly one rule
        # and carrying a written justification is the sanctioned workaround
        # for a documented upstream lint-rule limitation — the checker must
        # stay silent on it.
        result = run_checker(str(FIXTURES / "justified_noqa.py"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_example_pair_matches_expected(self):
        source = (EXAMPLES / "checked_input.py").read_text(encoding="utf-8")
        expected = (EXAMPLES / "checked_input.expected").read_text(encoding="utf-8")
        result = run_checker(stdin=source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.strip(), expected.strip())

    def test_checker_writes_nothing_to_disk(self):
        run_checker(str(FIXTURES / "clean_sample.py"))
        self.assertEqual(list(self.tmp.iterdir()), [])


class TestScannerExactViews(unittest.TestCase):
    """The masking scanner's exact per-line output for Python lexical forms."""

    def test_comment_split_into_views(self):
        code, comment = CHECKER.mask_source("f()  # note")
        self.assertEqual(code, ["f()        "])
        self.assertEqual(comment, ["       note"])

    def test_string_masked_columns_kept(self):
        code, comment = CHECKER.mask_source("a = 'x'; g()")
        self.assertEqual(code, ["a =    ; g()"])
        self.assertEqual(comment, [" " * len("a = 'x'; g()")])

    def test_triple_quoted_string_spans_lines(self):
        code, _ = CHECKER.mask_source('s = """a\nb\n"""\nnext()')
        self.assertEqual(code, ["s =     ", " ", "   ", "next()"])

    def test_fstring_literal_masked_interpolation_kept(self):
        code, _ = CHECKER.mask_source('t = f"a {z} b"')
        self.assertEqual(code, ["t = f    z    "])

    def test_escaped_quote_stays_inside_string(self):
        code, _ = CHECKER.mask_source("s = 'a\\'b'; f()")
        self.assertEqual(code, ["s =       ; f()"])

    def test_unterminated_string_resets_at_newline(self):
        code, _ = CHECKER.mask_source("s = 'open\nnext()")
        self.assertEqual(code, ["s =      ", "next()"])

    def test_empty_and_no_trailing_newline(self):
        self.assertEqual(CHECKER.mask_source(""), ([""], [""]))
        code, comment = CHECKER.mask_source("a # b")
        self.assertEqual(code, ["a    "])
        self.assertEqual(comment, ["    b"])

    def test_mask_source_preserves_line_count_and_columns(self):
        src = 'a = "x"\n# note\nb = 2\n'
        code_lines, comment_lines = CHECKER.mask_source(src)
        self.assertEqual(len(code_lines), 4)  # trailing newline -> empty last line
        self.assertEqual(len(comment_lines), 4)
        for original, masked in zip(src.split("\n"), code_lines):
            self.assertEqual(len(original), len(masked))


class TestScannerMutationPins(unittest.TestCase):
    """Targeted pins for scanner mechanics that only in-process runs can kill."""

    def test_comment_state_resets_at_newline(self):
        code, comment = CHECKER.mask_source("# a\nb()")
        self.assertEqual(code, ["   ", "b()"])
        self.assertEqual(comment, ["  a", "   "])
        # Behaviour: a comment on line 1 must not mask code on line 2.
        self.assertEqual(check("# print('quoted')\nprint('real')\n")[0], ["PY-PRINT"])

    def test_pragma_errors_carry_the_real_label(self):
        _, errors = CHECKER.check_text("a = 1  # skill-check-ignore\n", "boot.py")
        self.assertTrue(errors and errors[0].startswith("boot.py:1: "), errors)

    def test_check_text_applies_path_contexts_in_process(self):
        self.assertEqual(check("print('x')\n", label="test_x.py"), ([], []))
        self.assertEqual(
            check("import os\nu = os.environ\n", label="app_config.py"), ([], [])
        )
        self.assertEqual(check("print('x')\n", label="app.py")[0], ["PY-PRINT"])

    def test_unknown_codes_error_lists_codes_exactly(self):
        _, errors = CHECKER.parse_pragmas(
            "skill-check-ignore: ZZ-XX, YY-QQ -- oops",
            "x.py",
            2,
            frozenset({"AA-BB", "CC-DD"}),
        )
        self.assertEqual(
            errors,
            ["x.py:2: unknown rule code(s) YY-QQ, ZZ-XX; known codes: AA-BB, CC-DD"],
        )

    def test_nested_directory_paths_are_recognized(self):
        self.assertTrue(CHECKER.is_test_path("pkg/sub/test_a.py"))
        self.assertTrue(CHECKER.is_test_path("pkg/sub/conftest.py"))
        self.assertTrue(CHECKER.is_config_path("pkg/sub/app_config.py"))
        # The basename decides, not the whole path: bare `config.py` nested
        # two levels deep is still the config layer.
        self.assertTrue(CHECKER.is_config_path("pkg/sub/config.py"))

    def test_triple_fstring_spans_lines_and_scans_interpolations(self):
        findings, _ = CHECKER.check_text(
            'm = f"""\nheader print(1)\n{os.environ}\n"""\n', "sample.py"
        )
        self.assertEqual([(f[1], f[2]) for f in findings], [(3, "PY-ENV")])

    def test_unterminated_fstring_pops_at_newline(self):
        code, _ = CHECKER.mask_source('x = f"{y\nz()')
        self.assertEqual(code[1], "z()")

    def test_plain_string_braces_are_not_interpolations(self):
        self.assertEqual(check("s = 'x {os.environ} y'")[0], [])
        self.assertEqual(check("s = rb'{os.environ}'")[0], [])

    def test_fstring_prefix_requires_adjacent_word(self):
        # `f` bound earlier as a name; the un-prefixed string keeps its braces
        # as data.
        self.assertEqual(check("f = 1\ns = ' {os.environ} '\n")[0], [])

    def test_dict_literal_inside_interpolation_keeps_frame_depth(self):
        codes, _ = check("v = f\"{ {'k': os.environ}['k'] } end\"")
        self.assertEqual(codes, ["PY-ENV"])

    def test_escaped_quote_inside_fstring_literal(self):
        code, _ = CHECKER.mask_source('s = f"a\\" {b}"')
        self.assertIn("b", code[0])
        self.assertNotIn("a", code[0])

    def test_early_quotes_inside_triple_string_do_not_close_it(self):
        code, _ = CHECKER.mask_source('s = """a"b""c"""; d()')
        self.assertEqual(code, ["s = " + " " * 12 + "; d()"])

    def test_column_preservation_across_all_constructs(self):
        # Every masking path must emit exactly one character per input
        # character: escapes in plain and f-strings, {{ }} literals,
        # interpolations, triple quotes, prefixes, braces, comments.
        torture = (
            "s1 = 'a\\tb' + \"q\\\"z\"  # esc\n"
            's2 = f"a {{b}} {v} \\n w"\n'
            's3 = """t\n'
            '"mid" done"""\n'
            "s4 = rb'raw' + f'{x!r:>10}'\n"
            "d = {'k': [1]}\n"
            "m = f'a{ {\"n\": 1} }b'\n"
        )
        code, comment = CHECKER.mask_source(torture)
        originals = torture.split("\n")
        self.assertEqual(len(code), len(originals))
        for original, code_line, comment_line in zip(originals, code, comment):
            self.assertEqual(len(code_line), len(original), repr(original))
            self.assertEqual(len(comment_line), len(original), repr(original))

    def test_no_phantom_fstring_frame_survives_the_newline(self):
        # After an unterminated single-line f-string, a `}` on the next line
        # is plain code — a leftover frame would flip the rest into literal.
        code, _ = CHECKER.mask_source('x = f"{y\n} p()')
        self.assertEqual(code[1], "} p()")

    def test_deeply_nested_braces_keep_interpolation_depth(self):
        codes, _ = check("v = f\"{ {'a': 1, 'b': {'c': 2}} and os.environ }\"")
        self.assertEqual(codes, ["PY-ENV"])

    def test_stray_closing_brace_at_top_level_is_code(self):
        code, _ = CHECKER.mask_source("a = 1\n} \nb()")
        self.assertEqual(code, ["a = 1", "} ", "b()"])


class TestLiteralMasking(unittest.TestCase):
    """Rule text inside literals must not fire; interpolated code must."""

    def test_single_and_double_quoted_strings_are_masked(self):
        codes, errors = check("a = 'print(1)'; b = \": Any\"")
        self.assertEqual((codes, errors), ([], []))

    def test_triple_quoted_string_content_is_masked(self):
        codes, _ = check('doc = """\nprint("x")\nflag: Any = 1\nexcept:\n"""\n')
        self.assertEqual(codes, [])

    def test_docstring_is_masked(self):
        codes, _ = check('def f() -> None:\n    """Calls print("x") never."""\n')
        self.assertEqual(codes, [])

    def test_fstring_literal_part_is_masked(self):
        codes, _ = check('msg = f"never call print(1) or assert {flag}"')
        self.assertEqual(codes, [])

    def test_fstring_interpolation_code_is_scanned(self):
        codes, _ = check('v = f"{os.environ}"')
        self.assertEqual(codes, ["PY-ENV"])

    def test_nested_fstring_interpolation_is_scanned(self):
        codes, _ = check('v = f"a {f"b {os.environ}"} c"')
        self.assertEqual(codes, ["PY-ENV"])

    def test_double_braces_are_literal_in_fstrings(self):
        codes, _ = check('v = f"{{os.environ}} {name}"')
        self.assertEqual(codes, [])

    def test_raw_and_byte_strings_are_masked(self):
        codes, _ = check("p = r'print\\(x\\)'; b = b'breakpoint('")
        self.assertEqual(codes, [])

    def test_line_comments_are_masked_for_code_rules(self):
        codes, _ = check("a = 1  # print('x') and os.environ and except:\n")
        self.assertEqual(codes, [])

    def test_suppress_rule_fires_only_in_comments_not_strings(self):
        self.assertEqual(check("# type: ignore\na = 1\n")[0], ["PY-SUPPRESS"])
        self.assertEqual(check("s = '# type: ignore'")[0], [])
        self.assertEqual(check("x = 1  # noqa\n")[0], ["PY-SUPPRESS"])

    def test_string_prefix_letters_stay_in_code_view(self):
        # The masked prefix must not corrupt neighbouring findings.
        codes, _ = check("value = rb'data'; print(value)")
        self.assertEqual(codes, ["PY-PRINT"])


class TestSuppressionContract(TempDirMixin):
    """Only 'skill-check-ignore: CODE -- reason' suppresses; all bypasses fail."""

    def test_scoped_suppression_with_justification_works(self):
        codes, errors = check(
            "a = os.environ.get('A')  # skill-check-ignore: PY-ENV -- bootstrap probe"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_multi_code_suppression_works(self):
        codes, errors = check(
            "print(os.environ)  # skill-check-ignore: PY-ENV, PY-PRINT -- calibrated demo line"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_suppression_is_scoped_to_listed_codes_only(self):
        codes, errors = check(
            "print(os.environ)  # skill-check-ignore: PY-ENV -- env part is fine"
        )
        self.assertEqual(errors, [])
        self.assertEqual(codes, ["PY-PRINT"])

    def test_suppression_applies_to_its_line_only(self):
        source = (
            "a = os.environ.get('A')  # skill-check-ignore: PY-ENV -- documented probe\n"
            "b = os.environ.get('B')\n"
        )
        path = self.write("boot.py", source)
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(codes_in(result.stdout), ["PY-ENV"])
        self.assertIn(":2:", result.stdout)
        self.assertNotIn(":1:", result.stdout)

    def test_bare_marker_is_a_hard_error(self):
        codes, errors = check("print('x')  # skill-check-ignore keep noise down")
        self.assertEqual(codes, ["PY-PRINT"])  # nothing suppressed
        self.assertEqual(len(errors), 1)
        self.assertIn("malformed", errors[0])

    def test_missing_justification_is_a_hard_error(self):
        for tail in ("", " ", "\t"):
            codes, errors = check(f"a = os.environ  # skill-check-ignore: PY-ENV --{tail}")
            self.assertEqual(codes, ["PY-ENV"], tail)
            self.assertTrue(errors and "justification" in errors[0], errors)

    def test_missing_separator_is_a_hard_error(self):
        codes, errors = check("a = os.environ  # skill-check-ignore: PY-ENV justified: yes")
        self.assertEqual(codes, ["PY-ENV"])
        self.assertTrue(errors and "malformed" in errors[0], errors)

    def test_unknown_code_is_a_hard_error(self):
        codes, errors = check("a = os.environ  # skill-check-ignore: PY-NOPE -- because")
        self.assertEqual(codes, ["PY-ENV"])
        self.assertTrue(errors and "unknown rule code" in errors[0], errors)

    def test_wildcard_is_rejected(self):
        codes, errors = check("a = os.environ  # skill-check-ignore: * -- everything")
        self.assertEqual(codes, ["PY-ENV"])
        self.assertTrue(errors and "malformed" in errors[0], errors)

    def test_lowercase_code_is_rejected(self):
        codes, errors = check("a = os.environ  # skill-check-ignore: py-env -- case matters")
        self.assertEqual(codes, ["PY-ENV"])
        self.assertTrue(errors, errors)

    def test_py_suppress_can_never_be_suppressed(self):
        codes, errors = check("# type: ignore skill-check-ignore: PY-SUPPRESS -- hide it")
        self.assertEqual(codes, ["PY-SUPPRESS"])
        self.assertTrue(errors and "can never be suppressed" in errors[0], errors)

    def test_pragma_inside_a_string_neither_suppresses_nor_errors(self):
        codes, errors = check(
            "s = 'skill-check-ignore: PY-ENV -- fake'; v = os.environ"
        )
        self.assertEqual(errors, [])
        self.assertEqual(codes, ["PY-ENV"])

    def test_multiple_pragmas_on_one_line_are_rejected(self):
        codes, errors = check(
            "a = os.environ  # skill-check-ignore: PY-ENV -- a skill-check-ignore: PY-ANY -- b"
        )
        self.assertEqual(codes, ["PY-ENV"])
        self.assertTrue(errors and "multiple" in errors[0], errors)

    def test_pragma_error_exits_2_via_cli(self):
        path = self.write("bad.py", "print('x')  # skill-check-ignore\n")
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("malformed", result.stderr)
        # Findings are still reported so nothing is silently hidden.
        self.assertIn("PY-PRINT", result.stdout)

    def test_parse_pragmas_error_battery(self):
        known = frozenset({"AA-BB", "CC-DD"})
        parse = CHECKER.parse_pragmas
        self.assertEqual(parse("plain comment", "x.py", 1, known), (set(), []))
        self.assertEqual(
            parse("skill-check-ignore: AA-BB -- why not", "x.py", 1, known),
            ({"AA-BB"}, []),
        )
        self.assertEqual(
            parse("skill-check-ignore: AA-BB, CC-DD -- both fine", "x.py", 1, known),
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
                suppressed, errors = parse(text, "f.py", 7, known)
                self.assertEqual(suppressed, set(), text)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(fragment, errors[0])
                self.assertTrue(errors[0].startswith("f.py:7: "), errors[0])

    def test_py_suppress_suppression_error_is_specific(self):
        _, errors = CHECKER.parse_pragmas(
            "skill-check-ignore: PY-SUPPRESS -- please", "x.py", 3
        )
        self.assertEqual(
            errors,
            ["x.py:3: PY-SUPPRESS can never be suppressed; fix the suppression instead"],
        )


class TestPySuppressScope(unittest.TestCase):
    """PY-SUPPRESS targets suppression smells, not the sanctioned narrow noqa.

    A line-scoped `# noqa: <RULE> -- <reason>` naming exactly one rule with a
    non-empty justification is the correct way to hold a documented upstream
    lint-rule limitation and must not be reported. Everything wider, blanket,
    or unjustified stays a finding — and type-level suppressions have no
    escape at all.
    """

    def test_justified_single_rule_noqa_is_not_flagged(self):
        codes, errors = check(
            "for chunk in source:  # noqa: B007 -- upstream rule limitation: draining is the point\n"
            "    count += 1\n"
        )
        self.assertEqual((codes, errors), ([], []))

    # --- negative guard: every wider/unjustified form is still a finding ----

    def test_bare_noqa_still_flagged(self):
        codes, _ = check("x = compute()  # noqa\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_noqa_with_rule_but_no_justification_still_flagged(self):
        codes, _ = check("x = compute()  # noqa: E501\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_noqa_with_empty_justification_still_flagged(self):
        for tail in ("--", "-- ", "--\t"):
            with self.subTest(tail=tail):
                codes, _ = check(f"x = compute()  # noqa: E501 {tail}\n")
                self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_multi_rule_noqa_still_flagged(self):
        codes, _ = check("x = compute()  # noqa: E501, W605 -- demo hook\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_type_ignore_with_reason_still_flagged(self):
        codes, _ = check("x = broken()  # type: ignore -- reviewed: vendor typing bug\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_type_ignore_with_code_still_flagged(self):
        codes, _ = check("x = broken()  # type: ignore[assignment]\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_pylint_disable_still_flagged(self):
        codes, _ = check("x = compute()  # pylint: disable=invalid-name\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_mypy_ignore_errors_still_flagged(self):
        codes, _ = check("# mypy: ignore-errors\nx = 1\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_type_ignore_next_to_justified_noqa_still_flagged(self):
        # The justified directive is cut out; the remaining type: ignore on
        # the same line must survive as a finding.
        codes, _ = check("x = f()  # type: ignore noqa: E501 -- reason text\n")
        self.assertEqual(codes, ["PY-SUPPRESS"])

    def test_justified_noqa_inside_string_is_still_data(self):
        codes, errors = check("doc = '# noqa: E501 -- how-to example'\n")
        self.assertEqual((codes, errors), ([], []))


class TestPathContexts(TempDirMixin):
    """Layer differences: test files and config files relax specific rules."""

    def test_test_file_context_relaxes_strictness(self):
        for name in ("test_sample.py", "widget_test.py", "conftest.py"):
            with self.subTest(name=name):
                path = self.write(
                    name,
                    "def test_a() -> None:\n"
                    "    value: Any = get_thing()\n"
                    "    print(value)\n"
                    "    assert value is not None\n"
                    "    breakpoint()\n",
                )
                result = run_checker(str(path))
                found = set(codes_in(result.stdout))
                # In a test file, Any/print/assert relaxations apply...
                self.assertEqual(found & {"PY-ANY", "PY-PRINT", "PY-ASSERT"}, set())
                # ...but a left-behind debugger is still flagged.
                self.assertIn("PY-DEBUG", found)

    def test_test_directories_are_recognized(self):
        path = self.write("pkg/__tests__/helper.py", "print('debug')\n")
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), [])

    def test_bare_except_and_suppress_still_flagged_in_tests(self):
        path = self.write(
            "test_a.py", "try:\n    go()\nexcept:\n    pass\n# noqa\n"
        )
        result = run_checker(str(path))
        self.assertEqual(sorted(codes_in(result.stdout)), ["PY-BARE-EXCEPT", "PY-SUPPRESS"])

    def test_is_test_path_truth_table(self):
        true_paths = [
            "test_a.py", "a_test.py", "conftest.py", "pkg/__test__/f.py",
            "pkg/__tests__/g.py", "pkg/test/h.py", "pkg/tests/i.py",
            "UP/TEST_CASE.PY", "win\\tests\\j.py",
        ]
        false_paths = [
            "src/a.py", "latest.py", "protest.py", "contest/x.py",
            "src/testing/x.py", "attest.py", "tests.py",
        ]
        for p in true_paths:
            self.assertTrue(CHECKER.is_test_path(p), p)
        for p in false_paths:
            self.assertFalse(CHECKER.is_test_path(p), p)

    def test_config_layer_allows_env_by_path(self):
        for name in ("config.py", "settings.py", "app_config.py", "pkg/config/env.py"):
            with self.subTest(name=name):
                path = self.write(name, "import os\nurl = os.environ.get('URL')\n")
                result = run_checker(str(path))
                self.assertNotIn("PY-ENV", codes_in(result.stdout))

    def test_is_config_path_truth_table(self):
        true_paths = [
            "config.py", "settings.py", "app_config.py", "db_settings.py",
            "config_loader.py", "settings_prod.py", "src/config/env.py",
            "src/settings/base.py", "UP/APP_CONFIG.PY", "win\\config\\x.py",
        ]
        false_paths = [
            "reconfig.py", "configuration.py", "myconfig.py", "app.py",
            "configs.py",
        ]
        for p in true_paths:
            self.assertTrue(CHECKER.is_config_path(p), p)
        for p in false_paths:
            self.assertFalse(CHECKER.is_config_path(p), p)

    def test_config_env_flagged_via_stdin_not_by_path(self):
        # Evidence for the documented path-context limitation: env access in
        # a config-layer file is allowed when the checker sees the
        # *_config.py path, but flagged when the same content arrives over
        # stdin (no path).
        config = FIXTURES / "app_config.py"
        by_path = run_checker(str(config))
        self.assertEqual(by_path.returncode, 0, by_path.stdout)
        self.assertNotIn("PY-ENV", by_path.stdout)

        via_stdin = run_checker(stdin=config.read_text(encoding="utf-8"))
        self.assertEqual(via_stdin.returncode, 1)
        self.assertIn("PY-ENV", via_stdin.stdout)

    def test_config_context_does_not_relax_other_rules(self):
        path = self.write("app_config.py", "print(os.environ.get('URL'))\n")
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), ["PY-PRINT"])


class TestDirectoryScanAndDeterminism(TempDirMixin):
    def test_directory_argument_scans_python_files_only(self):
        pkg = self.tmp / "pkg"
        (pkg / "nested").mkdir(parents=True)
        (pkg / "a.py").write_text("print('a')\n", encoding="utf-8")
        (pkg / "nested" / "b.py").write_text("print('b')\n", encoding="utf-8")
        (pkg / "notes.txt").write_text("print('ignored')\n", encoding="utf-8")
        (pkg / "c.pyi").write_text("print('ignored too')\n", encoding="utf-8")
        result = run_checker(str(pkg))
        self.assertEqual(codes_in(result.stdout), ["PY-PRINT"] * 2)
        for expected in ("a.py", "b.py"):
            self.assertIn(expected, result.stdout)
        self.assertNotIn("notes.txt", result.stdout)
        self.assertNotIn("c.pyi", result.stdout)

    def test_duplicate_arguments_do_not_double_findings(self):
        path = self.write("dup.py", "print('x')\n")
        result = run_checker(str(path), str(path), str(self.tmp))
        self.assertEqual(codes_in(result.stdout), ["PY-PRINT"])

    def test_output_is_stable_across_runs_and_argument_order(self):
        a = self.write("a.py", "print('a')\nx: Any = 1\n")
        b = self.write("b.py", "breakpoint()\n")
        first = run_checker(str(a), str(b)).stdout
        second = run_checker(str(b), str(a)).stdout
        third = run_checker(str(a), str(b)).stdout
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        lines = [line for line in first.splitlines() if line.strip()]
        self.assertEqual(lines, sorted(lines))


class TestErrorInputsAndEdgeCases(TempDirMixin):
    def test_missing_path_reports_error_exit_2(self):
        result = run_checker(str(self.tmp / "nope.py"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_non_utf8_file_reports_error_exit_2(self):
        bad = self.tmp / "bad.py"
        bad.write_bytes(b"\xff\xfeprint('x')\n")
        result = run_checker(str(bad))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_one_bad_file_does_not_hide_findings_in_others(self):
        good = self.write("good.py", "print('x')\n")
        bad = self.tmp / "broken.py"
        bad.write_bytes(b"\xff\xfe")
        result = run_checker(str(bad), str(good))
        self.assertEqual(result.returncode, 2)
        self.assertIn("PY-PRINT", result.stdout)

    def test_empty_stdin_is_clean(self):
        result = run_checker(stdin="")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_empty_file_is_clean(self):
        path = self.write("empty.py", "")
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 0)

    def test_missing_trailing_newline_is_handled(self):
        codes, _ = check("print('x')")
        self.assertEqual(codes, ["PY-PRINT"])

    def test_crlf_line_endings_are_handled(self):
        codes, _ = check("a = 1\r\nprint('x')\r\n")
        self.assertEqual(codes, ["PY-PRINT"])

    def test_assert_matches_statement_position_only(self):
        # `assert_never(x)` and attribute names must not trip PY-ASSERT.
        self.assertEqual(check("        assert_never(state)\n")[0], [])
        self.assertEqual(check("self.assertTrue(x)\n")[0], [])
        self.assertEqual(check("    assert payload\n")[0], ["PY-ASSERT"])

    def test_except_specific_types_are_clean(self):
        codes, _ = check("try:\n    go()\nexcept (ValueError, OSError) as err:\n    raise AppError('x') from err\n")
        self.assertEqual(codes, [])

    def test_finding_line_numbers_match_source(self):
        findings, _ = CHECKER.check_text("ok = 1\n\nbreakpoint()\n", "x.py")
        self.assertEqual([(f[1], f[2]) for f in findings], [(3, "PY-DEBUG")])

    def test_check_text_returns_exact_findings(self):
        findings, errors = CHECKER.check_text("breakpoint()\n", "m.py")
        self.assertEqual(errors, [])
        self.assertEqual(
            findings,
            [(
                "m.py",
                1,
                "PY-DEBUG",
                "debugger invocation left in code; remove breakpoint()/set_trace()",
            )],
        )


class TestInProcessDriver(TempDirMixin):
    """Drive main() in-process so the CLI paths are under coverage too."""

    def run_main(self, *argv: str, stdin: str = "") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(stdin)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = CHECKER.main(list(argv))
        finally:
            sys.stdin = old_stdin
        return rc, out.getvalue(), err.getvalue()

    def test_main_stdin_findings(self):
        rc, out, err = self.run_main(stdin="print('x')\n")
        self.assertEqual(rc, 1)
        self.assertIn("PY-PRINT", out)
        self.assertIn("1 finding(s)", err)

    def test_main_empty_stdin_reports_zero_findings(self):
        rc, out, err = self.run_main(stdin="")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "# 0 finding(s)\n")

    def test_main_clean_file_exit_0(self):
        path = self.write("ok.py", "a = 1\n")
        rc, out, _ = self.run_main(str(path))
        self.assertEqual((rc, out.strip()), (0, ""))

    def test_main_pragma_error_exit_2(self):
        path = self.write("bad.py", "a = os.environ  # skill-check-ignore: PY-ENV --\n")
        rc, _, err = self.run_main(str(path))
        self.assertEqual(rc, 2)
        self.assertIn("justification", err)

    def test_main_missing_file_exit_2(self):
        rc, _, err = self.run_main(str(self.tmp / "absent.py"))
        self.assertEqual(rc, 2)
        self.assertIn("cannot read", err)

    def test_main_dash_reads_stdin(self):
        rc, out, _ = self.run_main("-", stdin="print('x')\n")
        self.assertEqual(rc, 1)
        self.assertIn("PY-PRINT", out)

    def test_main_uses_sys_argv_when_argv_is_none(self):
        path = self.write("argv.py", "print('x')\n")
        out, err = io.StringIO(), io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = ["check_py_conventions.py", str(path)]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = CHECKER.main(None)
        finally:
            sys.argv = old_argv
        self.assertEqual(rc, 1)
        self.assertIn("PY-PRINT", out.getvalue())


if __name__ == "__main__":
    unittest.main()
