"""Dedicated tests for skills/go-coding (run via `skillctl test go-coding`).

Exercise the convention checker two ways:

* **in-process** (importing the script as a module) — this is what puts the
  analyzer under line/branch coverage and mutation testing;
* **as a CLI** (subprocess with a sandboxed environment) — this pins the
  exit-code and output contract consumers rely on.

The scanner masks *Go* lexical structure (``//`` and ``/* */`` comments,
interpreted strings, raw strings that may span lines, rune literals), so the
shared conformance mixin for the TypeScript analyzers does not apply; the
equivalent battery is pinned here against Go sources instead.

The second half pins the skill's prose: the rules a consumer relies on must
stay stated where the routing table says they are.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from __test__.helpers import bound_analyzer, sandboxed_env, skip_in_mutants_sandbox

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "go-coding"
SCRIPT = SKILL / "scripts" / "check_go_conventions.py"
FIXTURES = SKILL / "data" / "fixtures"
EXAMPLES = SKILL / "data" / "examples"
REFERENCES = SKILL / "references"

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_FENCED_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _broken_markdown_links(root: Path) -> list[str]:
    """Every markdown-link target under *root* that does not resolve on disk.

    Only relative, non-anchor targets are checked; ``http(s)``/``mailto:``
    links and same-document ``#anchor`` fragments are out of scope. Fenced and
    inline code spans are stripped first so Go's own bracket/paren syntax
    (``m[k](x)``, generic instantiations) is never mistaken for a link.
    """
    offenders: list[str] = []
    for md in sorted(root.rglob("*.md")):
        text = _FENCED_CODE_BLOCK.sub("", md.read_text(encoding="utf-8"))
        text = _INLINE_CODE_SPAN.sub("", text)
        for target in _MD_LINK.findall(text):
            target = target.split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.is_file():
                offenders.append(f"{md.relative_to(root)} -> {target}")
    return offenders


# Every rule the checker enforces; violations.go triggers each exactly once.
ALL_CODES = {
    "GO-PRINT",
    "GO-ENV",
    "GO-SUPPRESS",
    "GO-EXIT",
    "GO-CTX-ROOT",
    "GO-INIT",
    "GO-PANIC-ERR",
    "GO-LEGACY-API",
    "GO-LEGACY-IMPORT",
    "GO-ERR-MATCH",
    "GO-TYPE-ASSERT",
    "GO-SQL-FMT",
    "GO-SHELL",
    "GO-TLS-INSECURE",
    "GO-HTTP-TIMEOUT",
    "GO-DURATION",
    "GO-EMBED-LOCK",
    "GO-PKG-NAME",
}

# What a test file relaxes, as references/testing.md documents it: environment
# *reads* (gating integration tests); every other rule — GO-ENV writes included
# — keeps firing, as the reference lint configuration does in tests.
TEST_RELAXED = {"GO-ENV"}
# What package main relaxes: os.Exit and the root context (log.Fatal and
# printing are findings there too).
MAIN_RELAXED = {"GO-EXIT", "GO-CTX-ROOT"}


def load_checker():
    """Import the checker script as a module (measured by coverage/mutmut).

    The module name matches mutmut's path-derived mutant naming
    (skills.go-coding.scripts.check_go_conventions), so trampoline hits
    recorded during the stats run associate with the generated mutants.
    """
    spec = importlib.util.spec_from_file_location(
        "skills.go-coding.scripts.check_go_conventions", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Bounded in one place so every in-process call site inherits the deadline:
    # a mutation that turns a scanner loop non-terminating must fail the test,
    # not hang the process (see helpers.bound_analyzer).
    return bound_analyzer(module)


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


def check(source: str, label: str = "sample.go") -> tuple[list[str], list[str]]:
    """In-process shorthand: (finding codes, pragma errors)."""
    findings, errors = CHECKER.check_text(source, label)
    return [f[2] for f in findings], errors


def check_ctx(source: str, label: str, context: str) -> list[str]:
    """In-process shorthand with an explicit context path: finding codes."""
    findings, _ = CHECKER.check_text(source, label, context)
    return [f[2] for f in findings]


def flat(path: Path) -> str:
    """File text with whitespace runs collapsed (markdown hard-wraps prose)."""
    return " ".join(path.read_text(encoding="utf-8").split())


class TempDirMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="go-coding-test-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, rel: str, content: str) -> Path:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


# --- Checker: fixture contract ---------------------------------------------------


class TestFixtureContract(TempDirMixin):
    """The skill's own data layer is the calibrated ground truth."""

    def test_clean_sample_has_no_findings(self):
        result = run_checker(str(FIXTURES / "clean_sample.go"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_violations_fixture_flags_every_rule_once(self):
        result = run_checker(str(FIXTURES / "violations.go"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        found = codes_in(result.stdout)
        # Exactly one finding per rule — no rule missing, none doubled.
        self.assertEqual(sorted(found), sorted(ALL_CODES))

    def test_known_codes_are_exactly_the_documented_set(self):
        self.assertEqual(set(CHECKER.KNOWN_CODES), ALL_CODES)

    def test_masked_literals_fixture_is_silent(self):
        # Every rule is quoted inside strings/raw strings/runes/comments there.
        result = run_checker(str(FIXTURES / "masked_literals.go"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_justified_nolint_fixture_is_clean(self):
        # The sanctioned single-linter/-check/-rule forms with a written reason
        # must not be reported by GO-SUPPRESS.
        result = run_checker(str(FIXTURES / "justified_nolint.go"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_main_package_fixture_is_clean(self):
        result = run_checker(str(FIXTURES / "cmd_main.go"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_generated_fixture_is_skipped(self):
        result = run_checker(str(FIXTURES / "generated_sample.go"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_generated_fixture_body_would_be_flagged_without_its_header(self):
        # Negative guard: the skip is earned by the header, not by the body.
        text = (FIXTURES / "generated_sample.go").read_text(encoding="utf-8")
        body = text.replace("DO NOT EDIT.", "edit freely.")
        codes, _ = check(body)
        self.assertTrue({"GO-INIT", "GO-LEGACY-IMPORT", "GO-PRINT"} <= set(codes), codes)

    def test_example_pair_matches_expected(self):
        source = (EXAMPLES / "checked_input.go").read_text(encoding="utf-8")
        expected = (EXAMPLES / "checked_input.expected").read_text(encoding="utf-8")
        result = run_checker(stdin=source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.strip(), expected.strip())

    def test_checker_writes_nothing_to_disk(self):
        run_checker(str(FIXTURES / "clean_sample.go"))
        self.assertEqual(list(self.tmp.iterdir()), [])


@skip_in_mutants_sandbox()
class TestRuntimeInstallLinkResolution(TempDirMixin):
    """Shipped prose must not link into paths a ``runtime`` install strips."""

    def test_no_dangling_markdown_links_in_runtime_install(self):
        sys.path.insert(0, str(ROOT / "src"))
        from skill_library.installer import install_skill

        target = self.tmp / "consumer"
        target.mkdir()
        install_skill(ROOT, "go-coding", target, install_mode="runtime")
        installed = target / ".agents" / "skills" / "go-coding"
        self.assertEqual(_broken_markdown_links(installed), [])
        # The runtime install ships the checker but not the calibration set.
        self.assertTrue((installed / "scripts" / "check_go_conventions.py").is_file())
        self.assertFalse((installed / "data" / "fixtures").exists())

    def test_full_install_keeps_the_same_links_resolving(self):
        sys.path.insert(0, str(ROOT / "src"))
        from skill_library.installer import install_skill

        target = self.tmp / "consumer-full"
        target.mkdir()
        install_skill(ROOT, "go-coding", target, install_mode="full")
        installed = target / ".agents" / "skills" / "go-coding"
        self.assertEqual(_broken_markdown_links(installed), [])


# --- Checker: the scanner ----------------------------------------------------------


class TestScannerExactViews(unittest.TestCase):
    """The masking scanner's exact per-line output for Go lexical forms."""

    def test_line_comment_split_into_views(self):
        code, comment = CHECKER.mask_source("f() // note")
        self.assertEqual(code, ["f()        "])
        self.assertEqual(comment, ["       note"])

    def test_block_comment_spans_lines_until_closed(self):
        code, comment = CHECKER.mask_source("/*a\nb\nc*/d()")
        self.assertEqual(code, ["   ", " ", "   d()"])
        self.assertEqual(comment, ["  a", "b", "c     "])

    def test_interpreted_string_masked_columns_kept(self):
        code, comment = CHECKER.mask_source('a := "x"; g()')
        self.assertEqual(code, ["a :=    ; g()"])
        self.assertEqual(comment, [" " * len('a := "x"; g()')])

    def test_raw_string_spans_lines(self):
        code, _ = CHECKER.mask_source("s := `a\nb\n`\nnext()")
        self.assertEqual(code, ["s :=   ", " ", " ", "next()"])

    def test_raw_string_has_no_escapes(self):
        # A backslash does not escape the closing backtick in a raw string.
        code, _ = CHECKER.mask_source("s := `a\\`; f()")
        self.assertEqual(code, ["s :=     ; f()"])

    def test_rune_literals_are_masked(self):
        code, _ = CHECKER.mask_source("r := '\"'; t := '`'; q := '\\''; f()")
        self.assertEqual(code, ["r :=    ; t :=    ; q :=     ; f()"])

    def test_escaped_quote_stays_inside_string(self):
        code, _ = CHECKER.mask_source('s := "a\\"b"; f()')
        self.assertEqual(code, ["s :=       ; f()"])

    def test_unterminated_string_resets_at_newline(self):
        code, _ = CHECKER.mask_source('s := "open\nnext()')
        self.assertEqual(code, ["s :=      ", "next()"])

    def test_unterminated_rune_resets_at_newline(self):
        code, _ = CHECKER.mask_source("r := 'x\nnext()")
        self.assertEqual(code, ["r :=   ", "next()"])

    def test_comment_markers_inside_strings_are_data(self):
        code, comment = CHECKER.mask_source('u := "http://x/*y"; f()')
        self.assertEqual(code, ["u :=              ; f()"])
        self.assertEqual(comment, [" " * len('u := "http://x/*y"; f()')])

    def test_division_is_code(self):
        code, _ = CHECKER.mask_source("d := total / 2")
        self.assertEqual(code, ["d := total / 2"])

    def test_empty_and_no_trailing_newline(self):
        self.assertEqual(CHECKER.mask_source(""), ([""], [""]))
        code, comment = CHECKER.mask_source("a // b")
        self.assertEqual(code, ["a     "])
        self.assertEqual(comment, ["     b"])

    def test_mask_source_preserves_line_count_and_columns(self):
        torture = (
            'a := "x\\ty" + `raw\nstill raw` // tail\n'
            "/* block */ b := 'c' /* two\nlines */ c()\n"
            "s := \"\\\\\" + '\\n'\n"
        )
        code, comment = CHECKER.mask_source(torture)
        originals = torture.split("\n")
        self.assertEqual(len(code), len(originals))
        self.assertEqual(len(comment), len(originals))
        for original, code_line, comment_line in zip(originals, code, comment):
            self.assertEqual(len(code_line), len(original), repr(original))
            self.assertEqual(len(comment_line), len(original), repr(original))


class TestScannerMutationPins(unittest.TestCase):
    """Targeted pins for scanner mechanics that only in-process runs can kill."""

    def test_line_comment_state_resets_at_newline(self):
        code, comment = CHECKER.mask_source("// a\nb()")
        self.assertEqual(code, ["    ", "b()"])
        self.assertEqual(comment, ["   a", "   "])
        # Behaviour: a comment on line 1 must not mask code on line 2.
        codes, _ = check('package p\n// fmt.Println("quoted")\nfunc f() { fmt.Println("real") }\n')
        self.assertEqual(codes, ["GO-PRINT"])

    def test_block_comment_close_returns_to_code(self):
        codes, _ = check('package p\n/* os.Getenv("A") */ var v = os.Getenv("B")\n')
        self.assertEqual(codes, ["GO-ENV"])

    def test_pragma_errors_carry_the_real_label(self):
        _, errors = CHECKER.check_text("var a = 1 // skill-check-ignore\n", "boot.go")
        self.assertTrue(errors and errors[0].startswith("boot.go:1: "), errors)

    def test_check_text_applies_path_contexts_in_process(self):
        self.assertEqual(check('package p\nvar u = os.Getenv("U")\n', label="a_test.go"), ([], []))
        self.assertEqual(
            check('package config\nvar u = os.Getenv("U")\n', label="app_config.go"), ([], [])
        )
        self.assertEqual(check('package p\nvar u = os.Getenv("U")\n', label="a.go")[0], ["GO-ENV"])
        # The explicit context wins over the label.
        self.assertEqual(
            check_ctx('package p\nvar u = os.Getenv("U")\n', "/abs/tests/x.go", "internal/x.go"),
            ["GO-ENV"],
        )

    def test_unknown_codes_error_lists_codes_exactly(self):
        _, errors = CHECKER.parse_pragmas(
            "skill-check-ignore: ZZ-XX, YY-QQ -- oops",
            "x.go",
            2,
            frozenset({"AA-BB", "CC-DD"}),
        )
        self.assertEqual(
            errors,
            ["x.go:2: unknown rule code(s) YY-QQ, ZZ-XX; known codes: AA-BB, CC-DD"],
        )

    def test_finding_line_numbers_match_source(self):
        findings, _ = CHECKER.check_text("package p\n\nfunc init() {}\n", "x.go")
        self.assertEqual([(f[1], f[2]) for f in findings], [(3, "GO-INIT")])

    def test_check_text_returns_exact_findings(self):
        findings, errors = CHECKER.check_text("package p\nfunc init() {}\n", "m.go")
        self.assertEqual(errors, [])
        self.assertEqual(
            findings,
            [(
                "m.go",
                2,
                "GO-INIT",
                "init() runs implicitly on import, cannot return an error and hides "
                "dependencies; initialize explicitly from main or a constructor",
            )],
        )

    def test_one_finding_per_code_per_line(self):
        # Two alternatives of GO-SQL-FMT on one line report the code once.
        codes, _ = check(
            'package p\nfunc f() { db.Query(fmt.Sprintf("SELECT a FROM t WHERE id = %d", id)) }\n'
        )
        self.assertEqual(codes, ["GO-SQL-FMT"])

    def test_findings_are_sorted_by_line_then_code(self):
        findings, _ = CHECKER.check_text(
            'package p\nfunc f() { fmt.Println(os.Getenv("A")) }\nfunc init() {}\n', "s.go"
        )
        self.assertEqual(
            [(f[1], f[2]) for f in findings],
            [(2, "GO-ENV"), (2, "GO-PRINT"), (3, "GO-INIT")],
        )

    def test_messages_cover_every_code(self):
        self.assertEqual(set(CHECKER.MESSAGES), ALL_CODES)
        for code, message in CHECKER.MESSAGES.items():
            self.assertTrue(message.strip(), code)


class TestLiteralMasking(unittest.TestCase):
    """Rule text inside literals and comments must not fire."""

    def test_interpreted_strings_are_masked(self):
        codes, errors = check('package p\nvar a = "fmt.Println(1) os.Getenv(x) interface{}"\n')
        self.assertEqual((codes, errors), ([], []))

    def test_raw_strings_are_masked_across_lines(self):
        codes, _ = check('package p\nvar doc = `\nfunc init() {}\npanic(err)\nv.(string)\n`\n')
        self.assertEqual(codes, [])

    def test_line_and_block_comments_are_masked_for_code_rules(self):
        codes, _ = check(
            "package p\n// context.Background() and os.Exit(1)\n/* http.Get(u) */\nvar x = 1\n"
        )
        self.assertEqual(codes, [])

    def test_suppress_rule_fires_only_in_comments_not_strings(self):
        self.assertEqual(check("package p\nvar a = 1 //nolint\n")[0], ["GO-SUPPRESS"])
        self.assertEqual(check('package p\nvar s = "//nolint"\n')[0], [])

    def test_import_inside_raw_string_is_not_an_import(self):
        codes, _ = check('package p\nvar s = `\nimport "io/ioutil"\n`\n')
        self.assertEqual(codes, [])


class TestSuppressionContract(TempDirMixin):
    """Only 'skill-check-ignore: CODE -- reason' suppresses; all bypasses fail."""

    def test_scoped_suppression_with_justification_works(self):
        codes, errors = check(
            'package p\nvar a = os.Getenv("A") // skill-check-ignore: GO-ENV -- bootstrap probe\n'
        )
        self.assertEqual((codes, errors), ([], []))

    def test_multi_code_suppression_works(self):
        codes, errors = check(
            "package p\nfunc f() { fmt.Println(os.Getenv(\"A\")) } "
            "// skill-check-ignore: GO-ENV, GO-PRINT -- calibrated demo line\n"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_suppression_is_scoped_to_listed_codes_only(self):
        codes, errors = check(
            "package p\nfunc f() { fmt.Println(os.Getenv(\"A\")) } "
            "// skill-check-ignore: GO-ENV -- env part is fine\n"
        )
        self.assertEqual(errors, [])
        self.assertEqual(codes, ["GO-PRINT"])

    def test_suppression_applies_to_its_line_only(self):
        source = (
            "package p\n"
            'var a = os.Getenv("A") // skill-check-ignore: GO-ENV -- documented probe\n'
            'var b = os.Getenv("B")\n'
        )
        path = self.write("boot.go", source)
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(codes_in(result.stdout), ["GO-ENV"])
        self.assertIn(":3:", result.stdout)
        self.assertNotIn(":2:", result.stdout)

    def test_suppression_covers_import_findings(self):
        codes, errors = check(
            'package p\nimport "math/rand" // skill-check-ignore: GO-LEGACY-IMPORT -- '
            "reproducible simulation needs the v1 source\n"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_bare_marker_is_a_hard_error(self):
        codes, errors = check("package p\nfunc init() {} // skill-check-ignore keep noise down\n")
        self.assertEqual(codes, ["GO-INIT"])  # nothing suppressed
        self.assertEqual(len(errors), 1)
        self.assertIn("malformed", errors[0])

    def test_missing_justification_is_a_hard_error(self):
        for tail in ("", " ", "\t"):
            codes, errors = check(f"package p\nfunc init() {{}} // skill-check-ignore: GO-INIT --{tail}\n")
            self.assertEqual(codes, ["GO-INIT"], tail)
            self.assertTrue(errors and "justification" in errors[0], errors)

    def test_unknown_code_is_a_hard_error(self):
        codes, errors = check("package p\nfunc init() {} // skill-check-ignore: GO-NOPE -- because\n")
        self.assertEqual(codes, ["GO-INIT"])
        self.assertTrue(errors and "unknown rule code" in errors[0], errors)

    def test_wildcard_and_lowercase_are_rejected(self):
        for pragma in ("* -- everything", "go-init -- case matters"):
            codes, errors = check(f"package p\nfunc init() {{}} // skill-check-ignore: {pragma}\n")
            self.assertEqual(codes, ["GO-INIT"], pragma)
            self.assertTrue(errors, pragma)

    def test_go_suppress_can_never_be_suppressed(self):
        codes, errors = check("package p\nvar a = 1 //nolint skill-check-ignore: GO-SUPPRESS -- hide it\n")
        self.assertEqual(codes, ["GO-SUPPRESS"])
        self.assertTrue(errors and "can never be suppressed" in errors[0], errors)

    def test_go_suppress_suppression_error_is_specific(self):
        _, errors = CHECKER.parse_pragmas("skill-check-ignore: GO-SUPPRESS -- please", "x.go", 3)
        self.assertEqual(
            errors,
            ["x.go:3: GO-SUPPRESS can never be suppressed; fix the suppression instead"],
        )

    def test_pragma_inside_a_string_neither_suppresses_nor_errors(self):
        codes, errors = check(
            'package p\nvar s, v = "skill-check-ignore: GO-ENV -- fake", os.Getenv("A")\n'
        )
        self.assertEqual(errors, [])
        self.assertEqual(codes, ["GO-ENV"])

    def test_multiple_pragmas_on_one_line_are_rejected(self):
        codes, errors = check(
            "package p\nfunc init() {} "
            "// skill-check-ignore: GO-INIT -- a skill-check-ignore: GO-ENV -- b\n"
        )
        self.assertEqual(codes, ["GO-INIT"])
        self.assertTrue(errors and "multiple" in errors[0], errors)

    def test_pragma_error_exits_2_via_cli(self):
        path = self.write("bad.go", "package p\nfunc init() {} // skill-check-ignore\n")
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("malformed", result.stderr)
        # Findings are still reported so nothing is silently hidden.
        self.assertIn("GO-INIT", result.stdout)

    def test_parse_pragmas_error_battery(self):
        known = frozenset({"AA-BB", "CC-DD"})
        parse = CHECKER.parse_pragmas
        self.assertEqual(parse("plain comment", "x.go", 1, known), (set(), []))
        self.assertEqual(
            parse("skill-check-ignore: AA-BB -- why not", "x.go", 1, known),
            ({"AA-BB"}, []),
        )
        self.assertEqual(
            parse("skill-check-ignore: AA-BB, CC-DD -- both fine", "x.go", 1, known),
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
                suppressed, errors = parse(text, "f.go", 7, known)
                self.assertEqual(suppressed, set(), text)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(fragment, errors[0])
                self.assertTrue(errors[0].startswith("f.go:7: "), errors[0])


class TestGoSuppressScope(unittest.TestCase):
    """GO-SUPPRESS targets suppression smells, not the sanctioned narrow forms.

    A line-scoped ``//nolint:<linter> // <reason>`` naming exactly one linter
    (never ``all``) with a written reason is the correct way to hold a
    documented limitation of one linter; the single-check
    ``//lint:ignore <CHECK> <reason>`` (standalone staticcheck) and
    ``#nosec <RULE> -- <reason>`` (standalone gosec) are the same shape for
    those tools. Everything wider, blanket, or unjustified stays a finding.
    """

    def assertClean(self, line: str) -> None:
        self.assertEqual(check(f"package p\n{line}\n"), ([], []), line)

    def assertFlagged(self, line: str) -> None:
        self.assertEqual(check(f"package p\n{line}\n")[0], ["GO-SUPPRESS"], line)

    def test_justified_single_linter_nolint_is_clean(self):
        self.assertClean("var s = sha1.Sum(b) //nolint:gosec // git object IDs are SHA-1")
        self.assertClean("var s = sha1.Sum(b) //nolint:gosec// tight spacing still names a reason")

    def test_justified_single_check_lint_ignore_is_clean(self):
        self.assertClean("//lint:ignore SA1019 upstream fixes the algorithm")

    def test_justified_single_rule_nosec_is_clean(self):
        self.assertClean("var s = sha1.Sum(b) // #nosec G401 -- git object IDs are SHA-1")

    # --- negative guard: every wider/unjustified form is still a finding ----

    def test_bare_nolint_still_flagged(self):
        self.assertFlagged("var x = compute() //nolint")

    def test_nolint_with_linter_but_no_reason_still_flagged(self):
        self.assertFlagged("var x = compute() //nolint:errcheck")

    def test_nolint_with_empty_reason_still_flagged(self):
        for tail in ("//", "// ", "//\t"):
            with self.subTest(tail=tail):
                self.assertFlagged(f"var x = compute() //nolint:errcheck {tail}")

    def test_multi_linter_nolint_still_flagged(self):
        self.assertFlagged("var x = compute() //nolint:errcheck,gosec // two at once")

    def test_nolint_all_still_flagged(self):
        self.assertFlagged("var x = compute() //nolint:all // everything")

    def test_spaced_nolint_still_flagged(self):
        self.assertFlagged("var x = compute() // nolint")

    def test_lint_file_ignore_still_flagged(self):
        self.assertFlagged("//lint:file-ignore SA1019 whole file")

    def test_lint_ignore_multi_check_or_unjustified_still_flagged(self):
        self.assertFlagged("//lint:ignore SA1019,SA4006 two checks")
        self.assertFlagged("//lint:ignore SA1019")

    def test_bare_or_unjustified_nosec_still_flagged(self):
        self.assertFlagged("var s = sha1.Sum(b) // #nosec")
        self.assertFlagged("var s = sha1.Sum(b) // #nosec G401")
        self.assertFlagged("var s = sha1.Sum(b) // #nosec G401 G505 -- two rules")

    def test_revive_and_exhaustive_directives_still_flagged(self):
        self.assertFlagged("//revive:disable:var-naming")
        self.assertFlagged("//revive:disable-next-line")
        self.assertFlagged("//exhaustive:ignore")

    def test_unjustified_form_next_to_a_justified_one_still_flagged(self):
        # The justified directive is cut out; a blanket one earlier on the
        # same line must survive as a finding. (Everything after the reason
        # separator is the reason, consumed to end of line.)
        self.assertFlagged("var x = f() // #nosec //nolint:gosec // reason text")
        self.assertFlagged("var x = f() //nolint //nolint:gosec // reason text")

    def test_directive_text_inside_a_string_is_data(self):
        self.assertClean('var doc = "//nolint:gosec // how-to example"')


# --- Checker: rules -------------------------------------------------------------------


class TestSecurityRules(unittest.TestCase):
    """Positive and near-miss pins for the security-focused rules."""

    def codes(self, body: str, label: str = "sample.go") -> list[str]:
        return check(f"package p\nfunc f() {{\n{body}\n}}\n", label)[0]

    def test_sql_built_with_sprintf_is_flagged(self):
        self.assertEqual(
            self.codes('rows, err := db.QueryContext(ctx, fmt.Sprintf("SELECT a FROM t WHERE id = %d", id))'),
            ["GO-SQL-FMT"],
        )
        self.assertEqual(self.codes('q := fmt.Sprintf("DELETE FROM t WHERE id = %s", id)'), ["GO-SQL-FMT"])
        self.assertEqual(self.codes("q := fmt.Sprintf(`update t set a = %d`, v)"), ["GO-SQL-FMT"])
        self.assertEqual(self.codes("db.Exec(fmt.Sprintf(q, v))"), ["GO-SQL-FMT"])

    def test_sql_built_by_concatenation_is_flagged(self):
        self.assertEqual(self.codes('q := "SELECT a FROM b WHERE c = " + input'), ["GO-SQL-FMT"])
        self.assertEqual(self.codes('q := "insert into t values (" + v + ")"'), ["GO-SQL-FMT"])

    def test_placeholders_and_non_sql_text_are_clean(self):
        self.assertEqual(self.codes('row := db.QueryRowContext(ctx, "SELECT a FROM t WHERE id = $1", id)'), [])
        self.assertEqual(self.codes('msg := "Select an item from " + list'), [])
        self.assertEqual(self.codes('msg := fmt.Sprintf("Selected %d items", n)'), [])
        self.assertEqual(self.codes('u := client.Get(fmt.Sprintf("%s/users/%d", base, id))'), [])

    def test_sql_lookalike_inside_one_literal_is_clean(self):
        self.assertEqual(self.codes('doc := "q := \\"SELECT a FROM b WHERE c = \\" + input"'), [])

    def test_shell_invocation_is_flagged(self):
        for call in (
            'exec.Command("sh", "-c", line)',
            'exec.CommandContext(ctx, "bash", "-c", line)',
            'exec.Command("/bin/sh", "-c", line)',
            'exec.Command("/usr/bin/bash", "-c", line)',
            'exec.Command("cmd", "/C", line)',
            'exec.Command("powershell", "-Command", line)',
        ):
            with self.subTest(call=call):
                self.assertEqual(self.codes(f"out, err := {call}.Output()"), ["GO-SHELL"])

    def test_direct_program_invocation_is_clean(self):
        self.assertEqual(self.codes('cmd := exec.CommandContext(ctx, "git", "rev-parse", "HEAD")'), [])
        self.assertEqual(self.codes('cmd := exec.Command("sh", "script.sh")'), [])

    def test_insecure_tls_is_flagged(self):
        self.assertEqual(self.codes("cfg := &tls.Config{InsecureSkipVerify: true}"), ["GO-TLS-INSECURE"])
        self.assertEqual(self.codes("cfg.InsecureSkipVerify = true"), ["GO-TLS-INSECURE"])
        self.assertEqual(self.codes("cfg := &tls.Config{MinVersion: tls.VersionTLS10}"), ["GO-TLS-INSECURE"])

    def test_secure_tls_forms_are_clean(self):
        self.assertEqual(self.codes("cfg := &tls.Config{MinVersion: tls.VersionTLS12}"), [])
        self.assertEqual(self.codes("cfg.InsecureSkipVerify = false"), [])

    def test_http_without_timeouts_is_flagged(self):
        for line in (
            'resp, err := http.Get(url)',
            'resp, err := http.Post(url, "application/json", body)',
            "resp, err := http.DefaultClient.Do(req)",
            "client := &http.Client{}",
            'err := http.ListenAndServe(":8080", mux)',
            'err := http.ListenAndServeTLS(":8443", crt, key, mux)',
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-HTTP-TIMEOUT"])

    def test_configured_http_client_and_server_are_clean(self):
        self.assertEqual(self.codes("client := &http.Client{Timeout: 10 * time.Second}"), [])
        self.assertEqual(self.codes("srv := &http.Server{Addr: addr, ReadHeaderTimeout: 5 * time.Second}"), [])
        self.assertEqual(self.codes("err := srv.ListenAndServe()"), [])
        self.assertEqual(self.codes("req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)"), [])

    def test_security_rules_apply_in_test_files_too(self):
        # Unlike the documented relaxations, the security rules keep firing in
        # tests: a shell-built command in a test helper is still one.
        self.assertEqual(
            self.codes('out, err := exec.Command("sh", "-c", line).Output()', "helpers_test.go"),
            ["GO-SHELL"],
        )
        self.assertEqual(
            self.codes("cfg := &tls.Config{InsecureSkipVerify: true}", "x_test.go"),
            ["GO-TLS-INSECURE"],
        )

    def test_security_rules_are_suppressible_with_justification(self):
        codes, errors = check(
            "package p\nvar cfg = &tls.Config{InsecureSkipVerify: true} "
            "// skill-check-ignore: GO-TLS-INSECURE -- probe of a self-signed test fixture\n"
        )
        self.assertEqual((codes, errors), ([], []))


class TestCorrectnessRules(unittest.TestCase):
    """Positive and near-miss pins for the non-security rules."""

    def codes(self, body: str, label: str = "sample.go", package: str = "p") -> list[str]:
        return check(f"package {package}\nfunc f() {{\n{body}\n}}\n", label)[0]

    def test_print_family_is_flagged(self):
        for line in (
            'fmt.Println("x")', 'fmt.Printf("%d", n)', 'fmt.Print(v)', "println(v)", "print(v)",
            'log.Printf("x %d", n)', "log.Println(v)", "log.Print(v)",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-PRINT"])

    def test_writer_and_logger_output_is_clean(self):
        for line in (
            'fmt.Fprintln(w, "x")',
            'fmt.Sprintf("%d", n)',
            'logger.Info("x")',
            "s.println(v)",
            't.Logf("got %v", v)',
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), [])

    def test_environment_reads_are_flagged(self):
        for line in (
            'v := os.Getenv("A")',
            'v, ok := os.LookupEnv("A")',
            "all := os.Environ()",
            'os.Setenv("A", "b")',
            'p := os.ExpandEnv("$HOME/x")',
            'v, ok := syscall.Getenv("A")',
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-ENV"])

    def test_error_matching_by_equality_or_message_is_flagged(self):
        for line in (
            "if err == sql.ErrNoRows {}",
            "if err != ErrNotFound {}",
            'if err.Error() == "not found" {}',
            'if "x" == err.Error() {}',
            'if strings.Contains(err.Error(), "timeout") {}',
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-ERR-MATCH"])

    def test_errors_is_and_nil_checks_are_clean(self):
        for line in (
            "if errors.Is(err, sql.ErrNoRows) {}",
            "if err != nil {}",
            "if err == io.EOF {}",
            "return target == ErrGone",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), [])

    def test_unchecked_type_assertion_is_flagged(self):
        for line in ("s := v.(string)", "use(v.(*Order))", "m := v.(map[string]any)"):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-TYPE-ASSERT"])

    def test_comma_ok_and_type_switch_are_clean(self):
        for line in (
            "s, ok := v.(string)",
            "if o, ok := v.(*Order); ok {}",
            "switch x := v.(type) {}",
            "var s, ok = v.(string)",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), [])

    def test_panic_on_an_ordinary_error_is_flagged(self):
        for line in ("panic(err)", 'panic(fmt.Errorf("load: %w", err))', 'panic(errors.New("boom"))'):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-PANIC-ERR"])

    def test_panic_on_an_impossible_state_is_clean(self):
        self.assertEqual(self.codes('panic(fmt.Sprintf("unreachable state %d", s))'), [])
        self.assertEqual(self.codes('panic("unreachable")'), [])

    def test_exit_below_main_is_flagged(self):
        for line in ("os.Exit(1)", "log.Fatal(err)", 'log.Fatalf("x: %v", err)', "log.Fatalln(err)"):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-EXIT"])

    def test_main_may_exit_but_never_through_log_fatal(self):
        self.assertEqual(self.codes("os.Exit(1)", package="main"), [])
        self.assertEqual(self.codes("log.Fatal(err)", package="main"), ["GO-EXIT"])
        self.assertEqual(self.codes('fmt.Println("done")', package="main"), ["GO-PRINT"])

    def test_environment_writes_stay_flagged_in_tests(self):
        for line in ('os.Setenv("A", "b")', 'os.Unsetenv("A")', "os.Clearenv()"):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line, label="x_test.go"), ["GO-ENV"])
        self.assertEqual(self.codes('v, ok := os.LookupEnv("DB_URL")', label="x_test.go"), [])

    def test_root_context_below_main_is_flagged(self):
        self.assertEqual(self.codes("ctx := context.Background()"), ["GO-CTX-ROOT"])
        self.assertEqual(self.codes("ctx := context.TODO()"), ["GO-CTX-ROOT"])
        self.assertEqual(self.codes("ctx := context.WithoutCancel(parent)"), [])

    def test_init_function_is_flagged(self):
        self.assertEqual(check("package p\nfunc init() {\n}\n")[0], ["GO-INIT"])
        self.assertEqual(check("package p\nfunc initialize() {}\nfunc (s *S) init() {}\n")[0], [])

    def test_legacy_api_forms_are_flagged(self):
        for line in (
            "var v interface{}",
            "var v interface{ }",
            "sort.Slice(xs, less)",
            "sort.Strings(names)",
            "atomic.AddInt64(&n, 1)",
            "p := atomic.LoadPointer(&ptr)",
            "t := reflect.TypeOf((*error)(nil)).Elem()",
            "s := strings.Title(name)",
            "if errors.As(err, &target) {}",
            "for i := 0; i < b.N; i++ {}",
            "v := v",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-LEGACY-API"])

    def test_modern_forms_are_clean(self):
        for line in (
            "var v any",
            "var s interface{ Close() error }",
            "slices.Sort(names)",
            "var n atomic.Int64",
            "t := reflect.TypeFor[error]()",
            "e, ok := errors.AsType[*PathError](err)",
            "for b.Loop() {}",
            "v := w",
            "sort.Sort(byAge(people))",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), [])

    def test_legacy_imports_are_flagged_and_successors_are_clean(self):
        for path in (
            "io/ioutil",
            "math/rand",
            "golang.org/x/exp/slices",
            "golang.org/x/exp/maps",
            "golang.org/x/exp/constraints",
            "golang.org/x/exp/slog",
            "golang.org/x/exp/rand",
            "golang.org/x/net/context",
            "github.com/pkg/errors",
            "go.uber.org/automaxprocs",
        ):
            with self.subTest(path=path):
                self.assertEqual(check(f'package p\nimport "{path}"\n')[0], ["GO-LEGACY-IMPORT"])
        for path in ("math/rand/v2", "crypto/rand", "slices", "log/slog", "context", "errors"):
            with self.subTest(path=path):
                self.assertEqual(check(f'package p\nimport "{path}"\n')[0], [])

    def test_bare_integer_durations_are_flagged(self):
        for line in (
            "time.Sleep(250)",
            "t := time.NewTimer(5)",
            "tk := time.NewTicker(1_000)",
            "c := time.After(30)",
            "ctx, cancel := context.WithTimeout(ctx, 100)",
            "client := &http.Client{Timeout: 30}",
            "srv.ReadHeaderTimeout = 5",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), ["GO-DURATION"])

    def test_unit_scaled_and_zero_durations_are_clean(self):
        for line in (
            "time.Sleep(250 * time.Millisecond)",
            "t := time.NewTimer(0)",
            "c := time.After(d)",
            "ctx, cancel := context.WithTimeout(ctx, 2*time.Second)",
            "client := &http.Client{Timeout: 30 * time.Second}",
            "srv.ReadHeaderTimeout = cfg.HeaderTimeout",
            "retries := 5",
        ):
            with self.subTest(line=line):
                self.assertEqual(self.codes(line), [])

    def test_embedded_locks_are_flagged_named_fields_are_clean(self):
        source = (
            "package p\n"
            "type a struct {\n\tsync.Mutex\n}\n"
            "type b struct {\n\t*sync.RWMutex // shared\n}\n"
            "type c struct {\n\tmu sync.Mutex\n\trw sync.RWMutex\n\tsync.Once\n}\n"
        )
        findings, _ = CHECKER.check_text(source, "locks.go")
        self.assertEqual([(f[1], f[2]) for f in findings], [(3, "GO-EMBED-LOCK"), (6, "GO-EMBED-LOCK")])

    def test_vague_package_names_are_flagged(self):
        for name in ("util", "utils", "common", "shared", "base", "helper", "helpers", "misc"):
            with self.subTest(name=name):
                self.assertEqual(check(f"package {name}\n")[0], ["GO-PKG-NAME"])
        for name in ("utility", "orders", "basex", "commonmark", "util_test", "sharedmem"):
            with self.subTest(name=name):
                self.assertEqual(check(f"package {name}\n")[0], [])

    def test_import_forms_are_all_parsed(self):
        source = (
            "package p\n"
            'import r "math/rand"\n'
            "import (\n"
            '\t"fmt" // "io/ioutil" in a trailing comment is not an import\n'
            "\t// \"github.com/pkg/errors\"\n"
            '\t_ "golang.org/x/exp/slices"\n'
            '\t. "golang.org/x/net/context"\n'
            ")\n"
            'import ("os"; "io/ioutil")\n'
            "import `golang.org/x/exp/maps`\n"
        )
        findings, _ = CHECKER.check_text(source, "imports.go")
        self.assertEqual(
            [(f[1], f[2]) for f in findings],
            [(2, "GO-LEGACY-IMPORT"), (6, "GO-LEGACY-IMPORT"), (7, "GO-LEGACY-IMPORT"),
             (9, "GO-LEGACY-IMPORT"), (10, "GO-LEGACY-IMPORT")],
        )

    def test_import_paths_helper_reads_code_anchored_specs_only(self):
        text = 'package p\n/* import "io/ioutil" */\nimport (\n\t"fmt"\n)\n'
        code, comment = CHECKER.mask_source(text)
        self.assertEqual(CHECKER.import_paths(code, comment, text.split("\n")), [(4, "fmt")])


class TestPathContexts(TempDirMixin):
    """Test files, config files and package main relax specific rules."""

    VIOLATION_PER_RELAXABLE_RULE = (
        "package p\n"
        "func f() {\n"
        '\tfmt.Println("x")\n'
        "\ts := v.(string)\n"
        "\tctx := context.Background()\n"
        "\tresp, err := http.Get(url)\n"
        '\tv := os.Getenv("A")\n'
        "\tos.Exit(1)\n"
        "}\n"
    )

    def test_test_file_context_relaxes_exactly_the_documented_rules(self):
        everywhere = set(check(self.VIOLATION_PER_RELAXABLE_RULE, "service.go")[0])
        in_test = set(check(self.VIOLATION_PER_RELAXABLE_RULE, "service_test.go")[0])
        self.assertEqual(everywhere - in_test, TEST_RELAXED)
        for code in ("GO-PRINT", "GO-TYPE-ASSERT", "GO-CTX-ROOT", "GO-HTTP-TIMEOUT", "GO-EXIT"):
            self.assertIn(code, in_test)

    def test_main_package_relaxes_exactly_the_documented_rules(self):
        as_lib = set(check(self.VIOLATION_PER_RELAXABLE_RULE, "cmd.go")[0])
        as_main = set(check(self.VIOLATION_PER_RELAXABLE_RULE.replace("package p", "package main"), "cmd.go")[0])
        self.assertEqual(as_lib - as_main, MAIN_RELAXED)

    def test_package_clause_decides_main_not_the_path(self):
        self.assertEqual(check("package cmd\nfunc f() { os.Exit(1) }\n", "main.go")[0], ["GO-EXIT"])
        self.assertEqual(check("// package main\npackage tool\nfunc f() { os.Exit(1) }\n")[0], ["GO-EXIT"])
        self.assertEqual(check("package main\nfunc f() { os.Exit(1) }\n")[0], [])

    def test_package_name_helper(self):
        code, _ = CHECKER.mask_source("// doc\n\npackage   widgets // trailing\n")
        self.assertEqual(CHECKER.package_name(code), "widgets")
        self.assertIsNone(CHECKER.package_name(["func f() {}"]))

    def test_is_test_path_truth_table(self):
        true_paths = [
            "a_test.go", "pkg/sub/b_test.go", "pkg/testdata/c.go", "testdata/d.go",
            "pkg/__test__/f.go", "pkg/__tests__/g.go", "pkg/test/h.go", "tests/i.go",
            "UP/CASE_TEST.GO", "win\\tests\\j.go",
        ]
        false_paths = [
            "src/a.go", "latest.go", "protest.go", "contest/x.go", "testing/x.go",
            "attest.go", "a_test.go.txt", "testutil/x.go", "test.go",
        ]
        for p in true_paths:
            self.assertTrue(CHECKER.is_test_path(p), p)
        for p in false_paths:
            self.assertFalse(CHECKER.is_test_path(p), p)

    def test_is_config_path_truth_table(self):
        true_paths = [
            "config.go", "settings.go", "app_config.go", "db_settings.go",
            "config_loader.go", "settings_prod.go", "internal/config/env.go",
            "src/settings/base.go", "UP/APP_CONFIG.GO", "win\\config\\x.go", "config/x.go",
        ]
        false_paths = [
            "reconfig.go", "configuration.go", "myconfig.go", "app.go", "configs.go",
        ]
        for p in true_paths:
            self.assertTrue(CHECKER.is_config_path(p), p)
        for p in false_paths:
            self.assertFalse(CHECKER.is_config_path(p), p)

    def test_config_env_flagged_via_stdin_not_by_path(self):
        # Evidence for the documented path-context limitation.
        config = FIXTURES / "app_config.go"
        by_path = run_checker(str(config))
        self.assertEqual(by_path.returncode, 0, by_path.stdout)
        self.assertNotIn("GO-ENV", by_path.stdout)

        via_stdin = run_checker(stdin=config.read_text(encoding="utf-8"))
        self.assertEqual(via_stdin.returncode, 1)
        self.assertIn("GO-ENV", via_stdin.stdout)

    def test_context_is_decided_below_the_module_root(self):
        # A checkout living under a directory named tests/ or config/ must not
        # turn every file of the module into a test or config file.
        module = self.tmp / "tests" / "config" / "svc"
        (module / "internal" / "orders").mkdir(parents=True)
        (module / "go.mod").write_text("module example.com/svc\n\ngo 1.27\n", encoding="utf-8")
        path = module / "internal" / "orders" / "orders.go"
        path.write_text('package orders\nvar u = os.Getenv("U")\n', encoding="utf-8")
        self.assertEqual(CHECKER.context_path(path), "internal/orders/orders.go")
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), ["GO-ENV"])
        test_file = module / "internal" / "orders" / "orders_test.go"
        test_file.write_text('package orders\nvar u = os.Getenv("U")\n', encoding="utf-8")
        self.assertEqual(CHECKER.context_path(test_file), "internal/orders/orders_test.go")

    def test_context_path_without_a_module_falls_back_to_the_given_path(self):
        outside = Path("/nonexistent-root-for-go-coding-test/pkg/x.go")
        self.assertEqual(CHECKER.context_path(outside), outside.as_posix())

    def test_config_context_does_not_relax_other_rules(self):
        path = self.write("app_config.go", 'package config\nfunc f() { fmt.Println(os.Getenv("U")) }\n')
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), ["GO-PRINT"])

    def test_generated_header_must_precede_the_package_clause(self):
        header = "// Code generated by tool. DO NOT EDIT.\n"
        body = "package p\nfunc init() {}\n"
        self.assertEqual(check(header + body)[0], [])
        self.assertEqual(check(body + header)[0], ["GO-INIT"])
        # The exact convention: a line comment, "Code generated", "DO NOT EDIT."
        self.assertEqual(check("// Code generated by tool, do not edit\n" + body)[0], ["GO-INIT"])
        self.assertEqual(check("/* Code generated by tool. DO NOT EDIT. */\n" + body)[0], ["GO-INIT"])

    def test_is_generated_helper(self):
        self.assertTrue(CHECKER.is_generated(["// Code generated by x. DO NOT EDIT.\r", "package p"]))
        self.assertFalse(CHECKER.is_generated(["package p", "// Code generated by x. DO NOT EDIT."]))
        self.assertFalse(CHECKER.is_generated([]))


class TestDirectoryScanAndDeterminism(TempDirMixin):
    def test_directory_argument_scans_go_files_only(self):
        pkg = self.tmp / "pkg"
        (pkg / "nested").mkdir(parents=True)
        (pkg / "a.go").write_text("package a\nfunc init() {}\n", encoding="utf-8")
        (pkg / "nested" / "b.go").write_text("package b\nfunc init() {}\n", encoding="utf-8")
        (pkg / "notes.txt").write_text("func init() {}\n", encoding="utf-8")
        (pkg / "c.go.orig").write_text("func init() {}\n", encoding="utf-8")
        result = run_checker(str(pkg))
        self.assertEqual(codes_in(result.stdout), ["GO-INIT"] * 2)
        for expected in ("a.go", "b.go"):
            self.assertIn(expected, result.stdout)
        self.assertNotIn("notes.txt", result.stdout)
        self.assertNotIn("c.go.orig", result.stdout)

    def test_directory_walk_skips_vendor_and_hidden_dirs(self):
        root = self.tmp / "mod"
        for rel in (
            "own.go", "vendor/dep/x.go", ".cache/y.go", "internal/vendor/z.go", "sub/.git/w.go",
            "pkg/testdata/fixture.go",
        ):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("package x\nfunc init() {}\n", encoding="utf-8")
        result = run_checker(str(root))
        self.assertEqual(codes_in(result.stdout), ["GO-INIT"])
        self.assertIn("own.go", result.stdout)

    def test_explicit_file_in_vendor_is_still_checked(self):
        path = self.write("vendor/dep/x.go", "package x\nfunc init() {}\n")
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), ["GO-INIT"])

    def test_duplicate_arguments_do_not_double_findings(self):
        path = self.write("dup.go", "package d\nfunc init() {}\n")
        result = run_checker(str(path), str(path), str(self.tmp))
        self.assertEqual(codes_in(result.stdout), ["GO-INIT"])

    def test_output_is_stable_across_runs_and_argument_order(self):
        a = self.write("a.go", 'package a\nfunc init() {}\nvar v = os.Getenv("A")\n')
        b = self.write("b.go", "package b\nvar x interface{}\n")
        first = run_checker(str(a), str(b)).stdout
        second = run_checker(str(b), str(a)).stdout
        third = run_checker(str(a), str(b)).stdout
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        lines = [line for line in first.splitlines() if line.strip()]
        self.assertEqual(lines, sorted(lines))


class TestErrorInputsAndEdgeCases(TempDirMixin):
    def test_missing_path_reports_error_exit_2(self):
        result = run_checker(str(self.tmp / "nope.go"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_non_utf8_file_reports_error_exit_2(self):
        bad = self.tmp / "bad.go"
        bad.write_bytes(b"\xff\xfepackage p\n")
        result = run_checker(str(bad))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_one_bad_file_does_not_hide_findings_in_others(self):
        good = self.write("good.go", "package g\nfunc init() {}\n")
        bad = self.tmp / "broken.go"
        bad.write_bytes(b"\xff\xfe")
        result = run_checker(str(bad), str(good))
        self.assertEqual(result.returncode, 2)
        self.assertIn("GO-INIT", result.stdout)

    def test_empty_stdin_and_empty_file_are_clean(self):
        self.assertEqual(run_checker(stdin="").returncode, 0)
        path = self.write("empty.go", "")
        self.assertEqual(run_checker(str(path)).returncode, 0)

    def test_missing_trailing_newline_is_handled(self):
        self.assertEqual(check("package p\nfunc init() {}")[0], ["GO-INIT"])

    def test_crlf_line_endings_are_handled(self):
        self.assertEqual(check("package p\r\nfunc init() {}\r\n")[0], ["GO-INIT"])
        self.assertEqual(check("package main\r\nfunc main() { os.Exit(1) }\r\n")[0], [])


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
        rc, out, err = self.run_main(stdin="package p\nfunc init() {}\n")
        self.assertEqual(rc, 1)
        self.assertIn("GO-INIT", out)
        self.assertIn("1 finding(s)", err)

    def test_main_empty_stdin_reports_zero_findings(self):
        rc, out, err = self.run_main(stdin="")
        self.assertEqual((rc, out, err), (0, "", "# 0 finding(s)\n"))

    def test_main_clean_file_exit_0(self):
        path = self.write("ok.go", "package ok\nvar a = 1\n")
        rc, out, _ = self.run_main(str(path))
        self.assertEqual((rc, out.strip()), (0, ""))

    def test_main_pragma_error_exit_2(self):
        path = self.write("bad.go", "package b\nfunc init() {} // skill-check-ignore: GO-INIT --\n")
        rc, _, err = self.run_main(str(path))
        self.assertEqual(rc, 2)
        self.assertIn("justification", err)

    def test_main_missing_file_exit_2(self):
        rc, _, err = self.run_main(str(self.tmp / "absent.go"))
        self.assertEqual(rc, 2)
        self.assertIn("cannot read", err)

    def test_main_dash_reads_stdin(self):
        rc, out, _ = self.run_main("-", stdin="package p\nfunc init() {}\n")
        self.assertEqual(rc, 1)
        self.assertIn("GO-INIT", out)

    def test_main_directory_argument(self):
        self.write("tree/a.go", "package a\nfunc init() {}\n")
        rc, out, _ = self.run_main(str(self.tmp / "tree"))
        self.assertEqual(rc, 1)
        self.assertIn("GO-INIT", out)

    def test_main_uses_sys_argv_when_argv_is_none(self):
        path = self.write("argv.go", "package a\nfunc init() {}\n")
        out, err = io.StringIO(), io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = ["check_go_conventions.py", str(path)]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = CHECKER.main(None)
        finally:
            sys.argv = old_argv
        self.assertEqual(rc, 1)
        self.assertIn("GO-INIT", out.getvalue())




class TestMutationPinsInProcess(TempDirMixin):
    """In-process pins for mechanics the subprocess tests cannot kill.

    Mutants activate only inside the test process, so every behaviour pinned
    through a subprocess above is pinned here once more, directly.
    """

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

    def test_walk_skips_vendor_hidden_and_non_go_files(self):
        root = self.tmp / "mod"
        for rel in (
            "own.go", "sub/deep.go", "notes.txt", "x.go.orig",
            "vendor/dep/v.go", "internal/vendor/w.go", ".cache/h.go", "sub/.git/g.go",
            "sub/testdata/t.go",
        ):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("package x\n", encoding="utf-8")
        (root / "dir.go").mkdir()  # a directory named like a Go file is not a file
        found = [path.relative_to(root).as_posix() for path in CHECKER._iter_paths([str(root)])]
        self.assertEqual(found, ["own.go", "sub/deep.go"])

    def test_explicit_paths_are_kept_even_in_vendor(self):
        path = self.write("vendor/dep/v.go", "package v\n")
        self.assertEqual(CHECKER._iter_paths([str(path)]), [path])

    def test_nested_config_basename_decides(self):
        self.assertTrue(CHECKER.is_config_path("pkg/sub/app_config.go"))
        self.assertTrue(CHECKER.is_config_path("pkg/sub/settings.go"))
        self.assertFalse(CHECKER.is_config_path("pkg/sub/reconfig.go"))
        self.assertTrue(CHECKER.is_config_path("/abs/pkg/config.go"))

    def test_raw_anchored_rules_ignore_comments(self):
        for line in (
            '// out, err := exec.Command("sh", "-c", line).Output()',
            'var n = 1 // q := fmt.Sprintf("SELECT a FROM t WHERE x = %d", v)',
            '/* q := "SELECT a FROM b WHERE c = " + v */',
        ):
            with self.subTest(line=line):
                self.assertEqual(check(f"package p\n{line}\n"), ([], []))

    def test_comma_ok_after_the_assertion_does_not_check_it(self):
        codes, _ = check("package p\nfunc f() { use(v.(string)); a, b := g() }\n")
        self.assertEqual(codes, ["GO-TYPE-ASSERT"])

    def test_import_block_closed_at_column_zero_ends_the_block(self):
        source = 'package p\nimport (\n\t"fmt"\n)\nvar s = "io/ioutil"\n'
        self.assertEqual(check(source), ([], []))
        self.assertEqual(check('package p\nimport ("math/rand")\n')[0], ["GO-LEGACY-IMPORT"])
        self.assertEqual(check('package p\nimport ("fmt"\n\t"math/rand"\n)\n')[0], ["GO-LEGACY-IMPORT"])

    def test_mask_source_comment_opening_at_end_of_text(self):
        self.assertEqual(CHECKER.mask_source("x //"), (["x   "], ["    "]))

    def test_mask_source_trailing_backslash_keeps_columns(self):
        for text in ('s := "a\\', "r := '\\"):
            with self.subTest(text=text):
                code, comment = CHECKER.mask_source(text)
                self.assertEqual(len(code[0]), len(text))
                self.assertEqual(len(comment[0]), len(text))

    def test_a_skipped_rule_does_not_hide_later_rules_on_the_line(self):
        self.assertEqual(
            check('package p\nfunc f() { use(os.Getenv("A"), v.(string)) }\n', "a_test.go")[0],
            ["GO-TYPE-ASSERT"],
        )
        self.assertEqual(
            check('package config\nfunc f() { fmt.Println(os.Getenv("A"), v.(string)) }\n', "app_config.go")[0],
            ["GO-PRINT", "GO-TYPE-ASSERT"],
        )
        self.assertEqual(
            check("package main\nfunc f() { os.Exit(code(v.(string))) }\n", "cmd.go")[0],
            ["GO-TYPE-ASSERT"],
        )

    def test_main_labels_stdin_findings(self):
        rc, out, _ = self.run_main(stdin="package p\nfunc init() {}\n")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("<stdin>:2: GO-INIT "), out)

    def test_main_sorts_output_by_file_then_line(self):
        b = self.write("b.go", "package b\nfunc init() {}\n")
        a = self.write("a.go", 'package a\nfunc init() {}\nvar e = os.Getenv("A")\n')
        _, out, _ = self.run_main(str(b), str(a))
        labels = [(line.split(":")[0].rsplit("/", 1)[-1], int(line.split(":")[1])) for line in out.splitlines()]
        self.assertEqual(labels, [("a.go", 2), ("a.go", 3), ("b.go", 2)])

    def test_main_decides_context_below_the_module_root(self):
        module = self.tmp / "tests" / "svc"
        module.mkdir(parents=True)
        (module / "go.mod").write_text("module example.com/svc\n\ngo 1.27\n", encoding="utf-8")
        path = module / "orders.go"
        path.write_text('package orders\nvar u = os.Getenv("U")\n', encoding="utf-8")
        rc, out, _ = self.run_main(str(path))
        self.assertEqual(rc, 1)
        # Reported under the path as given, judged by the path below go.mod.
        self.assertTrue(out.startswith(f"{path.as_posix()}:2: GO-ENV "), out)

    def test_main_keeps_reading_after_an_unreadable_file(self):
        good = self.write("good.go", "package g\nfunc init() {}\n")
        rc, out, err = self.run_main(str(self.tmp / "missing.go"), str(good))
        self.assertEqual(rc, 2)
        self.assertIn("GO-INIT", out)
        self.assertIn("cannot read", err)


# --- Prose: the rules the checker and the routing table promise ---------------------


REFERENCE_FILES = {
    "duplication-survey.md",
    "style-and-naming.md",
    "packages-and-apis.md",
    "type-design.md",
    "generics-and-interfaces.md",
    "errors-config-logging.md",
    "concurrency.md",
    "security.md",
    "runtime-correctness.md",
    "modern-go.md",
    "lint-clean.md",
    "testing.md",
}


def skill_md() -> str:
    return (SKILL / "SKILL.md").read_text(encoding="utf-8")


def frontmatter_description() -> str:
    text = skill_md()
    match = re.search(r"^description: (.+)$", text, re.MULTILINE)
    return match.group(1) if match else ""


def references_text() -> str:
    return " ".join(flat(path) for path in sorted(REFERENCES.glob("*.md")))


class TestSkillMdContract(unittest.TestCase):
    """SKILL.md is short, routes to every reference, and names the floor."""

    def test_reference_files_on_disk_are_exactly_the_routed_set(self):
        on_disk = {path.name for path in REFERENCES.glob("*.md")}
        self.assertEqual(on_disk, REFERENCE_FILES)
        routed = set(re.findall(r"\(references/([a-z-]+\.md)[)#]", skill_md()))
        self.assertEqual(routed, REFERENCE_FILES)

    def test_description_fits_and_carries_the_trigger_surface(self):
        description = frontmatter_description()
        self.assertLessEqual(len(description), 1024)
        for needle in ("Go 1.27", ".go", "go.mod", "_test.go"):
            self.assertIn(needle, description)

    def test_skill_md_stays_short_for_a_medium_effort_reader(self):
        self.assertLessEqual(len(skill_md().splitlines()), 260)

    def test_workflow_starts_with_the_survey_and_ends_with_the_self_check(self):
        text = " ".join(skill_md().split())
        self.assertIn("1. **Survey before you write.**", text)
        self.assertIn("python scripts/check_go_conventions.py", text)
        self.assertLess(text.index("Survey before you write"), text.index("check_go_conventions.py"))

    def test_the_floor_is_stated_where_it_is_read(self):
        self.assertIn("Go 1.27", skill_md())
        self.assertIn("**Go 1.27**", (REFERENCES / "modern-go.md").read_text(encoding="utf-8"))

    def test_project_instructions_take_precedence(self):
        self.assertIn("Project instructions always take precedence", " ".join(skill_md().split()))


class TestCheckerIsDocumented(unittest.TestCase):
    """Every checker rule is explained somewhere a reader is routed to.

    The code list is read from the checker itself — the set's owner — so a
    rule added to the checker without prose fails here by name.
    """

    def test_every_rule_code_appears_in_the_references(self):
        text = references_text()
        missing = [code for code in sorted(CHECKER.KNOWN_CODES) if code not in text]
        self.assertEqual(missing, [], "rule codes enforced but never explained")

    def test_testing_reference_names_exactly_the_test_relaxation(self):
        text = flat(REFERENCES / "testing.md")
        self.assertIn("relaxes exactly one thing there", text)
        self.assertIn("environment reads (`GO-ENV` for `os.Getenv` / `os.LookupEnv`)", text)
        for code in ("GO-PRINT", "GO-TYPE-ASSERT", "GO-CTX-ROOT", "GO-HTTP-TIMEOUT"):
            self.assertIn(code, text)

    def test_main_package_relaxations_are_documented(self):
        text = references_text()
        self.assertIn("package main", text)
        for code in sorted(MAIN_RELAXED):
            self.assertIn(code, text)

    def test_every_legacy_import_has_its_successor_in_modern_go(self):
        text = flat(REFERENCES / "modern-go.md")
        missing = [path for path in sorted(CHECKER.LEGACY_IMPORTS) if path not in text]
        self.assertEqual(missing, [], "flagged imports without an explained successor")


class TestTestingReferenceIsASpellingMapOnly(unittest.TestCase):
    """The skill keeps Go test *mechanics*, never the universal test rules."""

    TESTING_MD = REFERENCES / "testing.md"

    RELOCATED_RULE_ANCHORS = (
        "never copied from — or parametrized over — the artifact under test",
        "a test that reaches it through the outer layer proves nothing about "
        "the inner one",
        "treat a surviving mutation as evidence of a missing dimension",
        "no fake, and no re-reading of a project norm, an RFC, or vendor "
        "documentation, can establish what that system actually does",
        "a second rejection of the same reading on the same external-system "
        "property",
        "there is no return value to inspect and the fake stands in for the "
        "very code that would decide the outcome",
        "A test that constructs the collaborator itself establishes nothing "
        "about the construction the product performs",
        'never hardcode an expected value "so it passes"',
        "Arrange / Act / Assert",
    )

    REQUIRED_SPELLINGS = (
        "t.Run",
        "t.Helper()",
        "t.Cleanup",
        "t.Context()",
        "testing/synctest",
        "httptest",
        "b.Loop()",
        "f.Add",
        "-race",
        "//go:build integration",
        "package foo_test",
    )

    def test_file_declares_itself_a_spelling_map(self):
        self.assertIn("A spelling map, not a rule list", flat(self.TESTING_MD))

    def test_no_relocated_rule_text(self):
        text = flat(self.TESTING_MD)
        for anchor in self.RELOCATED_RULE_ANCHORS:
            self.assertNotIn(anchor, text, f"universal test rule restated here: {anchor!r}")

    def test_every_go_spelling_is_covered(self):
        text = flat(self.TESTING_MD)
        for spelling in self.REQUIRED_SPELLINGS:
            self.assertIn(spelling, text, spelling)


class TestLibraryWideRulesAreStatedInGoTerms(unittest.TestCase):
    """Rules every language standard of the library carries, restated for Go.

    Each is pinned where the routing table sends a reader, plus its one-line
    pointer in SKILL.md, so none silently disappears in an edit.
    """

    def test_survey_by_shape_and_the_decision_order(self):
        text = flat(REFERENCES / "duplication-survey.md")
        for anchor in (
            "by shape, never by name",
            "The decision order",
            "third occurrence",
            "A new file is the last step, not the first",
            "Two invariants a collapse may not weaken",
        ):
            self.assertIn(anchor, text)
        self.assertIn("by shape, never by name", " ".join(skill_md().split()))

    def test_env_var_is_named_by_role(self):
        text = flat(REFERENCES / "duplication-survey.md")
        self.assertIn("An environment variable is named by its role, not by its caller", text)
        self.assertIn("One process, two principals", text)

    def test_the_measured_reach_of_dupl_is_stated(self):
        text = flat(REFERENCES / "lint-clean.md") + " " + flat(REFERENCES / "duplication-survey.md")
        for anchor in ("rename-blind", "per package", "150 tokens"):
            self.assertIn(anchor, text)

    def test_completeness_check_derives_from_the_sets_owner(self):
        text = flat(REFERENCES / "generics-and-interfaces.md")
        self.assertIn("A completeness check derives its cases from the set's owner", text)
        self.assertIn("self-referential", text)
        self.assertIn("information_schema", text)
        self.assertIn("A completeness check derives its cases from the set's owner", " ".join(skill_md().split()))

    def test_filter_decides_with_the_downstream_normalization(self):
        text = flat(REFERENCES / "security.md")
        self.assertIn("decides with that parser's own normalization", text)
        self.assertIn("http.CanonicalHeaderKey", text)

    def test_defensive_routine_has_one_home_with_the_union_of_cases(self):
        text = flat(REFERENCES / "security.md")
        self.assertIn("union of every caller's cases", text)

    def test_wrapped_cause_that_echoes_input_is_a_disclosure_channel(self):
        text = flat(REFERENCES / "errors-config-logging.md")
        self.assertIn("strconv.NumError", text)
        self.assertIn("disclosure", text)

    def test_no_reporting_project_identifier_leaks_into_the_skill(self):
        for path in SKILL.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("HC-AGENT", text, path)
            self.assertNotIn("SFL-", text, path)


class TestLintReferenceMatchesTheMeasuredStack(unittest.TestCase):
    """lint-clean.md states the facts measured on golangci-lint 2.13."""

    def test_reference_config_shape(self):
        text = (REFERENCES / "lint-clean.md").read_text(encoding="utf-8")
        for needle in (
            'version: "2"',
            "nolintlint",
            "require-explanation: true",
            "require-specific: true",
            "check-type-assertions: true",
            "std-error-handling",
            "uniq-by-line",
        ):
            self.assertIn(needle, text)

    def test_blind_spots_of_the_stack_are_named(self):
        text = flat(REFERENCES / "lint-clean.md")
        for needle in ("err.Error()", "panic(err)", "os.Exit", "fmt.Sprintf", "GO-SQL-FMT"):
            self.assertIn(needle, text)


class TestEvalManifestShape(unittest.TestCase):
    MANIFEST = ROOT / "__test__" / "evals" / "go-coding" / "cases.json"

    def load(self) -> dict:
        return json.loads(self.MANIFEST.read_text(encoding="utf-8"))

    def test_gate_is_the_declared_runtime_environment(self):
        tiers = self.load()["tiers"]
        self.assertEqual(
            tiers["gate"], {"vendor": "anthropic", "model": "claude-sonnet-5", "effort": "medium"}
        )

    def test_every_case_kind_is_present(self):
        kinds = {case["kind"] for case in self.load()["cases"]}
        self.assertEqual(kinds, {"trigger", "behavior", "negative"})

    def test_library_wide_rules_each_have_a_case(self):
        ids = {case["id"] for case in self.load()["cases"]}
        for case_id in (
            "survey-before-writing-extend-dont-duplicate",
            "survey-does-not-block-genuinely-new-capability",
            "completeness-check-derives-from-the-external-owner",
            "completeness-check-in-program-enum-needs-no-introspection",
            "env-var-named-by-role-not-by-caller",
            "filter-uses-the-downstream-normalization",
            "defensive-parser-over-untrusted-input-has-one-home",
            "renamed-cross-package-duplicate-survives-green-dupl",
            "wrapped-cause-that-echoes-input-is-scrubbed",
        ):
            self.assertIn(case_id, ids)


if __name__ == "__main__":
    unittest.main()
