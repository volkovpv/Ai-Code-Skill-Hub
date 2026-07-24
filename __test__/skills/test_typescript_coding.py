"""Dedicated tests for skills/typescript-coding (run via `skillctl test typescript-coding`).

Exercise the convention checker two ways:

* **in-process** (importing the script as a module) — this is what puts the
  analyzer under line/branch coverage and mutation testing;
* **as a CLI** (subprocess with a sandboxed environment) — this pins the
  exit-code and output contract consumers rely on.

The fixture files under the skill's data layer double as evidence for the
skill's candidate observations.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from __test__.helpers import sandboxed_env
from __test__.skills.scanner_conformance import ScannerConformanceMixin

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "typescript-coding"
SCRIPT = SKILL / "scripts" / "check_conventions.py"
FIXTURES = SKILL / "data" / "fixtures"
EXAMPLES = SKILL / "data" / "examples"

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_FENCED_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _broken_markdown_links(root: Path) -> list[str]:
    """Every markdown-link target under *root* that does not resolve on disk.

    Only relative, non-anchor targets are checked; ``http(s)``/``mailto:``
    links and same-document ``#anchor`` fragments are out of scope (regression
    for OBS-20260721-002: a runtime install strips ``data/fixtures/`` and
    ``observations/candidates/``, but the shipped prose kept linking into
    them). Fenced and inline code spans are stripped first so a language's
    own bracket/paren syntax is never mistaken for a markdown link.
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

# Every rule the checker enforces; violations.ts triggers each exactly once.
ALL_CODES = {
    "TS-CONSOLE",
    "TS-ENV",
    "TS-ENUM",
    "TS-ANY",
    "TS-NONNULL",
    "TS-SUPPRESS",
    "TS-FOCUSED",
}


def load_checker():
    """Import the checker script as a module (measured by coverage/mutmut).

    The module name matches mutmut's path-derived mutant naming
    (skills.typescript-coding.scripts.check_conventions), so trampoline hits
    recorded during the stats run associate with the generated mutants.
    """
    spec = importlib.util.spec_from_file_location(
        "skills.typescript-coding.scripts.check_conventions", SCRIPT
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


def check(source: str, label: str = "sample.ts") -> tuple[list[str], list[str]]:
    """In-process shorthand: (finding codes, pragma errors)."""
    findings, errors = CHECKER.check_text(source, label)
    return [f[2] for f in findings], errors


class TempDirMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="typescript-coding-test-")
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
        result = run_checker(str(FIXTURES / "clean_sample.ts"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_violations_fixture_flags_every_rule_once(self):
        result = run_checker(str(FIXTURES / "violations.ts"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        found = codes_in(result.stdout)
        # Exactly one finding per rule — no rule missing, none doubled.
        self.assertEqual(sorted(found), sorted(ALL_CODES))

    def test_masked_literals_fixture_is_silent(self):
        # Every rule is quoted inside strings/templates/regex/comments there.
        result = run_checker(str(FIXTURES / "masked_literals.ts"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_justified_rule_disable_fixture_is_clean(self):
        # A line-scoped eslint disable naming exactly one rule and carrying a
        # written justification is the sanctioned workaround for a documented
        # upstream lint-rule limitation (observation OBS-20260715-001) — the
        # checker must stay silent on it.
        result = run_checker(str(FIXTURES / "justified_rule_disable.ts"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_example_pair_matches_expected(self):
        source = (EXAMPLES / "checked_input.ts").read_text(encoding="utf-8")
        expected = (EXAMPLES / "checked_input.expected").read_text(encoding="utf-8")
        result = run_checker(stdin=source)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.strip(), expected.strip())

    def test_checker_writes_nothing_to_disk(self):
        run_checker(str(FIXTURES / "clean_sample.ts"))
        self.assertEqual(list(self.tmp.iterdir()), [])


class TestRuntimeInstallLinkResolution(TempDirMixin):
    """Regression for OBS-20260721-002 (SFL, transferred as OBS-20260724-001):
    shipped content must not reference paths a ``runtime`` install strips
    (``data/fixtures/``, ``observations/candidates/``, ``observations/rejected/``)."""

    def _install(self, install_mode: str) -> Path:
        sys.path.insert(0, str(ROOT / "src"))
        from skill_library.installer import install_skill

        target = self.tmp / f"consumer-{install_mode}"
        target.mkdir()
        install_skill(ROOT, "typescript-coding", target, install_mode=install_mode)
        return target / ".agents" / "skills" / "typescript-coding"

    def test_no_dangling_markdown_links_in_runtime_install(self):
        self.assertEqual(_broken_markdown_links(self._install("runtime")), [])

    def test_full_install_keeps_the_same_links_resolving(self):
        # Negative guard: a `full` install still ships data/fixtures/ and
        # observations/candidates/, so the very same shipped content must
        # keep resolving there too — the fix must not turn working links
        # into dangling ones for `full`.
        self.assertEqual(_broken_markdown_links(self._install("full")), [])

    def test_accepted_observation_evidence_path_is_annotated_as_dev_only(self):
        # Reviewer note (skill-triage-2026-07-22.md, OBS-20260721-002): the
        # shipped accepted/OBS-20260715-001.md cites data/fixtures/... as its
        # own reproduction evidence, unreachable in the tree it ships to. The
        # citation itself is legitimate provenance (kept), but a reader of a
        # runtime install must not be left thinking the path resolves there.
        installed = self._install("runtime")
        accepted = installed / "observations" / "accepted" / "OBS-20260715-001.md"
        self.assertTrue(accepted.is_file())
        text = accepted.read_text(encoding="utf-8")
        self.assertIn("data/fixtures/", text)
        self.assertIn("not shipped in a runtime install", text, text)


class TestLiteralMasking(unittest.TestCase):
    """Rule text inside literals must not fire; interpolated code must."""

    def test_single_and_double_quoted_strings_are_masked(self):
        codes, errors = check("const a = 'console.log(1)'; const b = \": any\";")
        self.assertEqual((codes, errors), ([], []))

    def test_template_literal_content_is_masked(self):
        codes, _ = check("const t = `enum Color { Red } and @ts-ignore`;")
        self.assertEqual(codes, [])

    def test_template_interpolation_code_is_scanned(self):
        codes, _ = check("const v = `${process.env.HOME}`;")
        self.assertEqual(codes, ["TS-ENV"])

    def test_nested_template_interpolation_is_scanned(self):
        codes, _ = check("const v = `a ${`b ${user!.name} c`} d`;")
        self.assertEqual(codes, ["TS-NONNULL"])

    def test_multiline_template_is_masked_across_lines(self):
        codes, _ = check("const doc = `\nconsole.log('x');\nconst y: any = 1;\n`;\n")
        self.assertEqual(codes, [])

    def test_regex_literal_is_masked(self):
        codes, _ = check("const re = /console\\.log\\(|enum X/u;")
        self.assertEqual(codes, [])

    def test_division_is_not_treated_as_regex(self):
        # If `/` after a value opened a bogus regex, the console call would be hidden.
        codes, _ = check("const half = total / 2; console.log(half);")
        self.assertEqual(codes, ["TS-CONSOLE"])

    def test_line_comments_are_masked(self):
        codes, _ = check("const a = 1; // throw console.log('x'); enum E {}\n")
        self.assertEqual(codes, [])

    def test_block_comments_are_masked_across_lines(self):
        codes, _ = check("/*\nconsole.log('x');\nconst y: any = 1;\n*/\nconst ok = 1;\n")
        self.assertEqual(codes, [])

    def test_code_after_closed_block_comment_is_scanned(self):
        # No space after */: an off-by-one in the scanner would eat code.
        codes, _ = check("/*x*/console.log('y');")
        self.assertEqual(codes, ["TS-CONSOLE"])

    def test_suppress_rule_fires_only_in_comments_not_strings(self):
        self.assertEqual(check("// @ts-ignore\nconst a = 1;")[0], ["TS-SUPPRESS"])
        self.assertEqual(check("const s = '@ts-ignore';")[0], [])
        self.assertEqual(check("/* eslint-disable */")[0], ["TS-SUPPRESS"])

    def test_escaped_quote_does_not_end_the_string(self):
        codes, _ = check("const s = 'it\\'s console.log(1) quoted';")
        self.assertEqual(codes, [])

    def test_mask_source_preserves_line_count_and_columns(self):
        src = "const a = 'x';\n// note\nconst b = 2;\n"
        code_lines, comment_lines = CHECKER.mask_source(src)
        self.assertEqual(len(code_lines), 4)  # trailing newline -> empty last line
        self.assertEqual(len(comment_lines), 4)
        for original, masked in zip(src.split("\n"), code_lines):
            self.assertEqual(len(original), len(masked))


class TestSuppressionContract(TempDirMixin):
    """Only 'skill-check-ignore: CODE -- reason' suppresses; all bypasses fail."""

    def test_scoped_suppression_with_justification_works(self):
        codes, errors = check(
            "const a = process.env.A; // skill-check-ignore: TS-ENV -- bootstrap probe"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_multi_code_suppression_works(self):
        codes, errors = check(
            "console.log(process.env.X); // skill-check-ignore: TS-ENV, TS-CONSOLE -- calibrated demo line"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_suppression_is_scoped_to_listed_codes_only(self):
        codes, errors = check(
            "console.log(process.env.X); // skill-check-ignore: TS-ENV -- env part is fine"
        )
        self.assertEqual(errors, [])
        self.assertEqual(codes, ["TS-CONSOLE"])

    def test_suppression_applies_to_its_line_only(self):
        source = (
            "const a = process.env.A; // skill-check-ignore: TS-ENV -- documented probe\n"
            "const b = process.env.B;\n"
        )
        path = self.write("boot.ts", source)
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(codes_in(result.stdout), ["TS-ENV"])
        self.assertIn(":2:", result.stdout)
        self.assertNotIn(":1:", result.stdout)

    def test_bare_marker_is_a_hard_error(self):
        codes, errors = check("console.log('x'); // skill-check-ignore keep noise down")
        self.assertEqual(codes, ["TS-CONSOLE"])  # nothing suppressed
        self.assertEqual(len(errors), 1)
        self.assertIn("malformed", errors[0])

    def test_missing_justification_is_a_hard_error(self):
        for tail in ("", " ", "\t"):
            codes, errors = check(f"process.env.A; // skill-check-ignore: TS-ENV --{tail}")
            self.assertEqual(codes, ["TS-ENV"], tail)
            self.assertTrue(errors and "justification" in errors[0], errors)

    def test_missing_separator_is_a_hard_error(self):
        codes, errors = check("process.env.A; // skill-check-ignore: TS-ENV justified: yes")
        self.assertEqual(codes, ["TS-ENV"])
        self.assertTrue(errors and "malformed" in errors[0], errors)

    def test_unknown_code_is_a_hard_error(self):
        codes, errors = check("process.env.A; // skill-check-ignore: TS-NOPE -- because")
        self.assertEqual(codes, ["TS-ENV"])
        self.assertTrue(errors and "unknown rule code" in errors[0], errors)

    def test_wildcard_is_rejected(self):
        codes, errors = check("process.env.A; // skill-check-ignore: * -- everything")
        self.assertEqual(codes, ["TS-ENV"])
        self.assertTrue(errors and "malformed" in errors[0], errors)

    def test_lowercase_code_is_rejected(self):
        codes, errors = check("process.env.A; // skill-check-ignore: ts-env -- case matters")
        self.assertEqual(codes, ["TS-ENV"])
        self.assertTrue(errors, errors)

    def test_ts_suppress_can_never_be_suppressed(self):
        codes, errors = check("// @ts-ignore skill-check-ignore: TS-SUPPRESS -- hide it")
        self.assertEqual(codes, ["TS-SUPPRESS"])
        self.assertTrue(errors and "can never be suppressed" in errors[0], errors)

    def test_pragma_inside_a_string_neither_suppresses_nor_errors(self):
        codes, errors = check(
            "const s = 'skill-check-ignore: TS-ENV -- fake'; const v = process.env.A;"
        )
        self.assertEqual(errors, [])
        self.assertEqual(codes, ["TS-ENV"])

    def test_multiple_pragmas_on_one_line_are_rejected(self):
        codes, errors = check(
            "process.env.A; // skill-check-ignore: TS-ENV -- a skill-check-ignore: TS-ANY -- b"
        )
        self.assertEqual(codes, ["TS-ENV"])
        self.assertTrue(errors and "multiple" in errors[0], errors)

    def test_block_comment_pragma_works(self):
        codes, errors = check(
            "const a = process.env.A; /* skill-check-ignore: TS-ENV -- calibrated demo */"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_pragma_error_exits_2_via_cli(self):
        path = self.write("bad.ts", "console.log('x'); // skill-check-ignore\n")
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("malformed", result.stderr)
        # Findings are still reported so nothing is silently hidden.
        self.assertIn("TS-CONSOLE", result.stdout)


class TestTsSuppressScope(unittest.TestCase):
    """TS-SUPPRESS targets suppression smells, not the sanctioned narrow disable.

    Regression for observation OBS-20260715-001: a line-scoped eslint disable
    naming exactly one rule with a non-empty `--` justification is the correct
    way to hold a documented upstream lint-rule limitation and must not be
    reported. Everything wider, blanket, or unjustified stays a finding.
    """

    def test_justified_single_rule_next_line_disable_is_not_flagged(self):
        codes, errors = check(
            "// eslint-disable-next-line @typescript-eslint/promise-function-async -- upstream rule limitation: unknown return is not a Promise\n"
            "const passthrough = (value: unknown): unknown => value;\n"
        )
        self.assertEqual((codes, errors), ([], []))

    def test_justified_single_rule_same_line_disable_is_not_flagged(self):
        codes, errors = check(
            "for (const t of tasks) { await run(t); } // eslint-disable-line no-await-in-loop -- sequential on purpose: rate-limited API\n"
        )
        self.assertEqual((codes, errors), ([], []))

    # --- negative guard: every wider/unjustified form is still a finding ----

    def test_bare_file_scoped_disable_still_flagged(self):
        codes, _ = check("/* eslint-disable */\nconst a = 1;\n")
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_file_scoped_disable_with_rule_and_reason_still_flagged(self):
        # Only the LINE-scoped directives qualify; a justified file/block
        # disable silences the whole file and stays a finding.
        codes, _ = check(
            "/* eslint-disable @typescript-eslint/no-explicit-any -- legacy module */\nconst a = 1;\n"
        )
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_multi_rule_line_disable_still_flagged(self):
        codes, _ = check(
            "// eslint-disable-next-line no-console, no-alert -- demo hook\nconsoleLike();\n"
        )
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_line_disable_without_justification_still_flagged(self):
        codes, _ = check("// eslint-disable-next-line no-console\nconsoleLike();\n")
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_line_disable_with_empty_justification_still_flagged(self):
        for tail in ("--", "-- ", "--\t"):
            with self.subTest(tail=tail):
                codes, _ = check(f"// eslint-disable-next-line no-console {tail}\nconsoleLike();\n")
                self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_line_disable_without_any_rule_still_flagged(self):
        codes, _ = check("// eslint-disable-next-line -- because\nconsoleLike();\n")
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_ts_ignore_with_reason_still_flagged(self):
        codes, _ = check("// @ts-ignore -- reviewed: vendor typing bug\nconst a = b;\n")
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_ts_nocheck_still_flagged(self):
        codes, _ = check("// @ts-nocheck\nconst a = 1;\n")
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_type_suppression_next_to_justified_disable_still_flagged(self):
        # The justified directive is cut out; the remaining @ts-ignore on the
        # same line must survive as a finding.
        codes, _ = check(
            "// @ts-ignore eslint-disable-next-line no-console -- reason text\nconst a = b;\n"
        )
        self.assertEqual(codes, ["TS-SUPPRESS"])

    def test_justified_disable_inside_string_is_still_data(self):
        # Masking contract unchanged: directive text inside a string neither
        # fires nor exempts anything.
        codes, errors = check(
            "const doc = 'eslint-disable-next-line no-console -- how-to example';\n"
        )
        self.assertEqual((codes, errors), ([], []))


class TestPathContexts(TempDirMixin):
    """Layer differences: test files and config files relax specific rules."""

    def test_test_file_context_relaxes_strictness(self):
        for name in ("sample.spec.ts", "sample.test.mts", "widget.integration-spec.ts"):
            with self.subTest(name=name):
                path = self.write(
                    name,
                    "it.only('a', () => {\n"
                    "  const y: any = getThing();\n"
                    "  console.log(y!.z);\n"
                    "});\n",
                )
                result = run_checker(str(path))
                found = set(codes_in(result.stdout))
                # In a test file, any/console/non-null relaxations apply...
                self.assertEqual(found & {"TS-ANY", "TS-CONSOLE", "TS-NONNULL"}, set())
                # ...but focused tests are still flagged.
                self.assertIn("TS-FOCUSED", found)

    def test_test_directories_are_recognized(self):
        path = self.write("pkg/__tests__/helper.ts", "console.log('debug');\n")
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), [])

    def test_enum_and_suppress_still_flagged_in_tests(self):
        path = self.write("a.spec.ts", "enum E { A }\n// eslint-disable\n")
        result = run_checker(str(path))
        self.assertEqual(sorted(codes_in(result.stdout)), ["TS-ENUM", "TS-SUPPRESS"])

    def test_config_layer_allows_env_by_path(self):
        for name in ("settings.config.ts", "env.validator.ts", "config/env.ts", "app.config.mts"):
            with self.subTest(name=name):
                path = self.write(name, "export const url = process.env.URL;\n")
                result = run_checker(str(path))
                self.assertNotIn("TS-ENV", codes_in(result.stdout))

    def test_config_env_flagged_via_stdin_not_by_path(self):
        # Evidence for observations/candidates/OBS-20260713-001.md: env access
        # in a config-layer file is allowed when the checker sees the
        # *.config.ts path, but flagged when the same content arrives over
        # stdin (no path).
        config = FIXTURES / "settings.config.ts"
        by_path = run_checker(str(config))
        self.assertEqual(by_path.returncode, 0, by_path.stdout)
        self.assertNotIn("TS-ENV", by_path.stdout)

        via_stdin = run_checker(stdin=config.read_text(encoding="utf-8"))
        self.assertEqual(via_stdin.returncode, 1)
        self.assertIn("TS-ENV", via_stdin.stdout)

    def test_config_context_does_not_relax_other_rules(self):
        path = self.write("app.config.ts", "console.log(process.env.URL);\n")
        result = run_checker(str(path))
        self.assertEqual(codes_in(result.stdout), ["TS-CONSOLE"])


class TestDirectoryScanAndDeterminism(TempDirMixin):
    def test_directory_argument_scans_all_typescript_suffixes_only(self):
        pkg = self.tmp / "pkg"
        (pkg / "nested").mkdir(parents=True)
        (pkg / "a.ts").write_text("console.log('a');\n", encoding="utf-8")
        (pkg / "b.mts").write_text("console.log('b');\n", encoding="utf-8")
        (pkg / "nested" / "c.cts").write_text("console.log('c');\n", encoding="utf-8")
        (pkg / "notes.txt").write_text("console.log('ignored');\n", encoding="utf-8")
        (pkg / "d.tsx").write_text("console.log('ignored too');\n", encoding="utf-8")
        result = run_checker(str(pkg))
        self.assertEqual(codes_in(result.stdout), ["TS-CONSOLE"] * 3)
        for expected in ("a.ts", "b.mts", "c.cts"):
            self.assertIn(expected, result.stdout)
        self.assertNotIn("notes.txt", result.stdout)
        self.assertNotIn("d.tsx", result.stdout)

    def test_duplicate_arguments_do_not_double_findings(self):
        path = self.write("dup.ts", "console.log('x');\n")
        result = run_checker(str(path), str(path), str(self.tmp))
        self.assertEqual(codes_in(result.stdout), ["TS-CONSOLE"])

    def test_output_is_stable_across_runs_and_argument_order(self):
        a = self.write("a.ts", "console.log('a');\nconst x: any = 1;\n")
        b = self.write("b.ts", "enum E { X }\n")
        first = run_checker(str(a), str(b)).stdout
        second = run_checker(str(b), str(a)).stdout
        third = run_checker(str(a), str(b)).stdout
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        lines = [line for line in first.splitlines() if line.strip()]
        self.assertEqual(lines, sorted(lines))


class TestErrorInputsAndEdgeCases(TempDirMixin):
    def test_missing_path_reports_error_exit_2(self):
        result = run_checker(str(self.tmp / "nope.ts"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_non_utf8_file_reports_error_exit_2(self):
        bad = self.tmp / "bad.ts"
        bad.write_bytes(b"\xff\xfeconsole.log('x');\n")
        result = run_checker(str(bad))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_one_bad_file_does_not_hide_findings_in_others(self):
        good = self.write("good.ts", "console.log('x');\n")
        bad = self.tmp / "broken.ts"
        bad.write_bytes(b"\xff\xfe")
        result = run_checker(str(bad), str(good))
        self.assertEqual(result.returncode, 2)
        self.assertIn("TS-CONSOLE", result.stdout)

    def test_empty_stdin_is_clean(self):
        result = run_checker(stdin="")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_empty_file_is_clean(self):
        path = self.write("empty.ts", "")
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 0)

    def test_missing_trailing_newline_is_handled(self):
        codes, _ = check("console.log('x')")
        self.assertEqual(codes, ["TS-CONSOLE"])

    def test_crlf_line_endings_are_handled(self):
        codes, _ = check("const a = 1;\r\nconsole.log('x');\r\n")
        self.assertEqual(codes, ["TS-CONSOLE"])

    def test_unterminated_string_masks_to_end_of_line_only(self):
        codes, _ = check("const s = 'unterminated console.log(\nconsole.log('next');")
        self.assertEqual(codes, ["TS-CONSOLE"])

    def test_finding_line_numbers_match_source(self):
        findings, _ = CHECKER.check_text("const ok = 1;\n\nenum E { A }\n", "x.ts")
        self.assertEqual([(f[1], f[2]) for f in findings], [(3, "TS-ENUM")])


class TestScannerConformance(ScannerConformanceMixin, unittest.TestCase):
    """The shared scanner battery, run against this skill's checker copy."""

    MODULE = CHECKER

    def test_is_config_path_truth_table(self):
        true_paths = [
            "settings.config.ts", "app.config.mts", "env.validator.ts",
            "config.loader.ts", "src/config/env.ts", "UP/APP.CONFIG.TS",
            "win\\config\\x.ts",
        ]
        false_paths = [
            "reconfig.ts", "configs/x.ts", "src/configuration/x.ts",
            "app.ts", "my.settings.ts",
        ]
        for p in true_paths:
            self.assertTrue(CHECKER.is_config_path(p), p)
        for p in false_paths:
            self.assertFalse(CHECKER.is_config_path(p), p)

    def test_check_text_returns_exact_findings(self):
        findings, errors = CHECKER.check_text("enum E { A }\n", "m.ts")
        self.assertEqual(errors, [])
        self.assertEqual(
            findings,
            [(
                "m.ts",
                1,
                "TS-ENUM",
                "native enum; model closed sets as an `as const` object + derived union type",
            )],
        )

    def test_ts_suppress_suppression_error_is_specific(self):
        _, errors = CHECKER.parse_pragmas(
            "skill-check-ignore: TS-SUPPRESS -- please", "x.ts", 3
        )
        self.assertEqual(
            errors,
            ["x.ts:3: TS-SUPPRESS can never be suppressed; fix the suppression instead"],
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
        rc, out, err = self.run_main(stdin="console.log('x');\n")
        self.assertEqual(rc, 1)
        self.assertIn("TS-CONSOLE", out)
        self.assertIn("1 finding(s)", err)

    def test_main_clean_file_exit_0(self):
        path = self.write("ok.ts", "const a = 1;\n")
        rc, out, _ = self.run_main(str(path))
        self.assertEqual((rc, out.strip()), (0, ""))

    def test_main_pragma_error_exit_2(self):
        path = self.write("bad.ts", "process.env.A; // skill-check-ignore: TS-ENV --\n")
        rc, _, err = self.run_main(str(path))
        self.assertEqual(rc, 2)
        self.assertIn("justification", err)

    def test_main_missing_file_exit_2(self):
        rc, _, err = self.run_main(str(self.tmp / "absent.ts"))
        self.assertEqual(rc, 2)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
