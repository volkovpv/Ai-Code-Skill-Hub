"""Dedicated tests for skills/typescript-nestjs (run via `skillctl test typescript-nestjs`).

Exercise the layer-aware NestJS convention checker in-process (coverage,
mutation testing) and as a CLI, against the skill's own fixture module.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from __test__.helpers import sandboxed_env
from __test__.skills.scanner_conformance import ScannerConformanceMixin

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "typescript-nestjs"
SCRIPT = SKILL / "scripts" / "check_nest_conventions.py"
FIXTURES = SKILL / "data" / "fixtures" / "sample-module"

sys.path.insert(0, str(ROOT / "src"))

from skill_library import yamlio  # noqa: E402
from skill_library.validator import validate_skill_dir  # noqa: E402


def load_checker():
    """Import the checker script as a module (measured by coverage/mutmut).

    The module name matches mutmut's path-derived mutant naming
    (skills.typescript-nestjs.scripts.check_nest_conventions), so trampoline
    hits recorded during the stats run associate with the generated mutants.
    """
    spec = importlib.util.spec_from_file_location(
        "skills.typescript-nestjs.scripts.check_nest_conventions", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


def run_checker(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        # cwd is the library root: under mutation testing the script is a
        # trampoline-rewritten copy that imports mutmut, whose config loads
        # from the working directory's pyproject.toml.
        input=stdin,
        cwd=ROOT,
        env=sandboxed_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )


def codes_in(stdout: str) -> list[str]:
    return [line.split()[1] for line in stdout.splitlines() if line.strip()]


def check(source: str, label: str) -> tuple[list[str], list[str]]:
    findings, errors = CHECKER.check_text(source, label)
    return [f[2] for f in findings], errors


class TempDirMixin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="typescript-nestjs-test-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, rel: str, content: str) -> Path:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class TestFixtureContract(TempDirMixin):
    """The fixture module is the calibrated ground truth, per data/README.md."""

    def test_clean_files_have_no_findings(self):
        for rel in ("domain/user.entity.ts", "application/clean.use-case.ts"):
            with self.subTest(rel=rel):
                result = run_checker(str(FIXTURES / rel))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_domain_violations(self):
        result = run_checker(str(FIXTURES / "domain" / "bad.entity.ts"))
        self.assertEqual(sorted(codes_in(result.stdout)),
                         ["NEST-DOMAIN-IMPORT", "NEST-RAW-THROW"])

    def test_application_violations(self):
        result = run_checker(str(FIXTURES / "application" / "bad.use-case.ts"))
        self.assertEqual(sorted(codes_in(result.stdout)),
                         ["NEST-APP-IMPORT", "NEST-DI-TOKEN"])

    def test_infrastructure_flags_token_but_not_raw_throw(self):
        # Pins the layer difference: raw throws are a domain/application rule.
        result = run_checker(str(FIXTURES / "infrastructure" / "user.repository.ts"))
        self.assertEqual(codes_in(result.stdout), ["NEST-DI-TOKEN"])

    def test_whole_module_scan_is_deterministic(self):
        first = run_checker(str(FIXTURES)).stdout
        second = run_checker(str(FIXTURES)).stdout
        self.assertEqual(first, second)
        self.assertEqual(len(codes_in(first)), 5)


class TestLayerDetection(unittest.TestCase):
    RAW_THROW = "export function f(): void { throw new Error('x'); }\n"

    def test_layer_rules_fire_only_under_layer_paths(self):
        self.assertEqual(check(self.RAW_THROW, "modules/a/domain/x.ts")[0], ["NEST-RAW-THROW"])
        self.assertEqual(check(self.RAW_THROW, "modules/a/application/x.ts")[0], ["NEST-RAW-THROW"])
        self.assertEqual(check(self.RAW_THROW, "modules/a/infrastructure/x.ts")[0], [])
        self.assertEqual(check(self.RAW_THROW, "scripts/tool.ts")[0], [])

    def test_stdin_has_no_layer_context(self):
        # Only the layer-free rule applies without a path.
        self.assertEqual(check(self.RAW_THROW, "<stdin>")[0], [])
        codes, _ = check("@Inject('X')\n", "<stdin>")
        self.assertEqual(codes, ["NEST-DI-TOKEN"])

    def test_test_files_are_exempt_from_layer_rules(self):
        codes, _ = check(self.RAW_THROW, "modules/a/application/x.spec.ts")
        self.assertEqual(codes, [])

    def test_di_token_rule_stays_active_in_tests(self):
        codes, _ = check("@Inject('USERS')\n", "modules/a/application/x.spec.ts")
        self.assertEqual(codes, ["NEST-DI-TOKEN"])


class TestRules(unittest.TestCase):
    def test_di_token_string_and_inline_symbol_flagged_named_token_ok(self):
        self.assertEqual(check("@Inject('USERS') x;", "a.ts")[0], ["NEST-DI-TOKEN"])
        self.assertEqual(check('@Inject("USERS") x;', "a.ts")[0], ["NEST-DI-TOKEN"])
        self.assertEqual(check("@Inject(Symbol('USERS')) x;", "a.ts")[0], ["NEST-DI-TOKEN"])
        self.assertEqual(check("@Inject(USER_REPOSITORY) x;", "a.ts")[0], [])

    def test_domain_import_variants(self):
        label = "modules/a/domain/x.ts"
        for line in (
            "import { Injectable } from '@nestjs/common';",
            "import { Observable } from 'rxjs';",
            "import { Model } from 'sequelize-typescript';",
            "export { thing } from '@nestjs/core';",
            "const m = require('@nestjs/common');",
        ):
            with self.subTest(line=line):
                self.assertEqual(check(line, label)[0], ["NEST-DOMAIN-IMPORT"])

    def test_domain_relative_and_neutral_imports_are_clean(self):
        label = "modules/a/domain/x.ts"
        for line in (
            "import { User } from './user.entity';",
            "import { addDays } from 'date-fns';",
        ):
            with self.subTest(line=line):
                self.assertEqual(check(line, label)[0], [])

    def test_domain_type_only_framework_import_is_still_flagged(self):
        # The domain imports NO framework, not even type-only (unlike application).
        codes, _ = check("import type { OnModuleInit } from '@nestjs/common';",
                         "modules/a/domain/x.ts")
        self.assertEqual(codes, ["NEST-DOMAIN-IMPORT"])

    def test_application_runtime_import_flagged_type_only_allowed(self):
        label = "modules/a/application/x.ts"
        self.assertEqual(check("import { Inject } from '@nestjs/common';", label)[0],
                         ["NEST-APP-IMPORT"])
        self.assertEqual(check("import type { OnModuleInit } from '@nestjs/common';", label)[0],
                         [])

    def test_application_non_framework_imports_are_clean(self):
        codes, _ = check("import { UserId } from '../domain/user.entity';",
                         "modules/a/application/x.ts")
        self.assertEqual(codes, [])

    def test_import_text_inside_string_is_not_flagged(self):
        # The masking model: a quoted import statement is data, not an import.
        codes, _ = check("const tpl = \"import { X } from '@nestjs/common';\";",
                         "modules/a/domain/x.ts")
        self.assertEqual(codes, [])

    def test_raw_throw_in_comment_or_string_is_not_flagged(self):
        label = "modules/a/domain/x.ts"
        self.assertEqual(check("// throw new Error('x')", label)[0], [])
        self.assertEqual(check("const s = \"throw new Error('x')\";", label)[0], [])

    def test_typed_domain_error_throw_is_clean(self):
        codes, _ = check("throw new UserBlockedError(id);", "modules/a/domain/x.ts")
        self.assertEqual(codes, [])


class TestHttpStatusLiteralRule(unittest.TestCase):
    """OBS-20260717-001: raw numeric HTTP-status literals go unflagged.

    Regression fixture: data/fixtures/raw_http_status_literal.ts.
    """

    FIXTURE = SKILL / "data" / "fixtures" / "raw_http_status_literal.ts"

    def test_fixture_flags_exactly_the_three_dirty_positions(self):
        result = run_checker(str(self.FIXTURE))
        self.assertEqual(
            codes_in(result.stdout),
            ["NEST-HTTP-STATUS-LITERAL"] * 3,
            result.stdout + result.stderr,
        )

    def test_http_exception_raw_status_argument_is_flagged(self):
        codes, _ = check('throw new HttpException("x", 404);', "a.ts")
        self.assertEqual(codes, ["NEST-HTTP-STATUS-LITERAL"])

    def test_http_code_decorator_raw_argument_is_flagged(self):
        codes, _ = check("@HttpCode(204) noContent() {}", "a.controller.ts")
        self.assertEqual(codes, ["NEST-HTTP-STATUS-LITERAL"])

    def test_status_map_entry_raw_key_is_flagged(self):
        codes, _ = check("const M = new Map([[404, ProblemCode.notFound]]);", "a.ts")
        self.assertEqual(codes, ["NEST-HTTP-STATUS-LITERAL"])

    def test_test_assertion_raw_status_is_flagged_in_spec_files_only(self):
        codes, _ = check("expect(res.status).toBe(404);", "a.spec.ts")
        self.assertEqual(codes, ["NEST-HTTP-STATUS-LITERAL"])
        # Same literal outside a test-path context: the assertion sub-rule
        # (toBe/toEqual) is test-file-scoped by design (SKILL suggested fix).
        codes, _ = check("expect(res.status).toBe(404);", "a.ts")
        self.assertEqual(codes, [])

    def test_http_status_registry_forms_are_clean(self):
        for line in (
            'throw new HttpException("x", HttpStatus.NOT_FOUND);',
            "@HttpCode(HttpStatus.NO_CONTENT) noContent() {}",
            "const M = new Map([[HttpStatus.NOT_FOUND, ProblemCode.notFound]]);",
        ):
            with self.subTest(line=line):
                self.assertEqual(check(line, "a.ts")[0], [])
        codes, _ = check("expect(res.status).toBe(HttpStatus.NOT_FOUND);", "a.spec.ts")
        self.assertEqual(codes, [])

    def test_non_status_three_digit_number_is_clean(self):
        # 999 is not a registered HTTP status code.
        codes, _ = check("const M = new Map([[999, X.thing]]);", "a.ts")
        self.assertEqual(codes, [])
        codes, _ = check("expect(count).toBe(999);", "a.spec.ts")
        self.assertEqual(codes, [])

    def test_number_number_pair_is_not_a_status_map_entry(self):
        # Two numeric literals paired together (e.g. coordinates) are not a
        # status-map entry: the value slot must look like an identifier.
        codes, _ = check("const P = [[404, 200]];", "a.ts")
        self.assertEqual(codes, [])

    def test_literal_inside_comment_or_string_is_not_flagged(self):
        codes, _ = check("// use HttpException(body, 404) here", "a.ts")
        self.assertEqual(codes, [])
        codes, _ = check('const doc = "@HttpCode(204)";', "a.ts")
        self.assertEqual(codes, [])


class TestScannerConformance(ScannerConformanceMixin, unittest.TestCase):
    """The shared scanner battery, run against this skill's checker copy."""

    MODULE = CHECKER

    def test_layer_of_truth_table(self):
        cases = {
            "modules/a/domain/x.ts": "domain",
            "modules/a/application/x.ts": "application",
            "domain/x.ts": "domain",
            "MODULES/A/DOMAIN/x.ts": "domain",
            "win\\application\\x.ts": "application",
            "modules/a/infrastructure/x.ts": None,
            "x/domainy/z.ts": None,
            "domain.ts": None,
            "<stdin>": None,
        }
        for path, expected in cases.items():
            self.assertEqual(CHECKER.layer_of(path), expected, path)

    def test_forbidden_domain_modules_truth_table(self):
        forbidden = [
            "@nestjs/common", "@nestjs/core", "rxjs", "rxjs/operators",
            "reflect-metadata", "sequelize", "sequelize-typescript",
            "typeorm", "fastify", "express", "axios",
            "class-validator", "class-transformer",
        ]
        allowed = ["date-fns", "./user.entity", "../ports/out", "@angular/core", "expressive"]
        for mod in forbidden:
            self.assertTrue(CHECKER._is_forbidden_in_domain(mod), mod)
        for mod in allowed:
            self.assertFalse(CHECKER._is_forbidden_in_domain(mod), mod)

    def test_check_text_returns_exact_findings(self):
        findings, errors = CHECKER.check_text(
            "throw new Error('x');\n", "modules/a/domain/y.ts"
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            findings,
            [(
                "modules/a/domain/y.ts",
                1,
                "NEST-RAW-THROW",
                "throw new Error in domain/application; throw a typed domain error from the registry",
            )],
        )


class TestSuppressionContract(TempDirMixin):
    LABEL = "modules/a/domain/x.ts"

    def test_scoped_suppression_with_justification_works(self):
        codes, errors = check(
            "throw new Error('boot'); // skill-check-ignore: NEST-RAW-THROW -- bootstrap guard predates the registry",
            self.LABEL,
        )
        self.assertEqual((codes, errors), ([], []))

    def test_bare_marker_is_a_hard_error(self):
        codes, errors = check("throw new Error('x'); // skill-check-ignore", self.LABEL)
        self.assertEqual(codes, ["NEST-RAW-THROW"])
        self.assertTrue(errors and "malformed" in errors[0], errors)

    def test_unknown_code_is_a_hard_error(self):
        codes, errors = check(
            "throw new Error('x'); // skill-check-ignore: TS-ENV -- wrong checker",
            self.LABEL,
        )
        self.assertEqual(codes, ["NEST-RAW-THROW"])
        self.assertTrue(errors and "unknown rule code" in errors[0], errors)

    def test_empty_justification_is_a_hard_error(self):
        codes, errors = check(
            "throw new Error('x'); // skill-check-ignore: NEST-RAW-THROW --",
            self.LABEL,
        )
        self.assertEqual(codes, ["NEST-RAW-THROW"])
        self.assertTrue(errors and "justification" in errors[0], errors)

    def test_pragma_error_exits_2_via_cli(self):
        path = self.write("modules/a/domain/x.ts",
                          "throw new Error('x'); // skill-check-ignore\n")
        result = run_checker(str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("malformed", result.stderr)


class TestDriverAndErrors(TempDirMixin):
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

    def test_missing_file_exit_2(self):
        rc, _, err = self.run_main(str(self.tmp / "absent.ts"))
        self.assertEqual(rc, 2)
        self.assertIn("cannot read", err)

    def test_directory_scan_only_ts_suffixes(self):
        self.write("modules/a/domain/x.ts", "throw new Error('x');\n")
        self.write("modules/a/domain/notes.txt", "throw new Error('ignored');\n")
        rc, out, _ = self.run_main(str(self.tmp))
        self.assertEqual(rc, 1)
        self.assertEqual(codes_in(out), ["NEST-RAW-THROW"])

    def test_stdin_clean_exit_0(self):
        rc, out, _ = self.run_main(stdin="const a = 1;\n")
        self.assertEqual((rc, out.strip()), (0, ""))


class TestSkillStructure(unittest.TestCase):
    @unittest.skipIf(
        os.environ.get("MUTANT_UNDER_TEST") is not None,
        "mutmut sandbox: the trampoline-rewritten script exceeds the size policy",
    )
    def test_skill_directory_validates_clean(self):
        self.assertEqual(validate_skill_dir(SKILL), [])

    def test_openai_adapter_parses_and_aligns_with_skill(self):
        data = yamlio.load_file(SKILL / "agents" / "openai.yaml")
        prompt = data["interface"]["default_prompt"]
        self.assertTrue(prompt.strip())
        self.assertIn("typescript-nestjs", prompt)
        self.assertIn("hexagonal", prompt)
        self.assertIn("precedence", prompt)


if __name__ == "__main__":
    unittest.main()
