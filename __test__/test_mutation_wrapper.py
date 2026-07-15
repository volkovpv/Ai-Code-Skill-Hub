"""Unit tests for the local mutation wrapper (``scripts/mutation.py``).

Pure resolution logic is exercised directly; ``main`` is driven only through
``--list``/``--dry-run``/no-op paths so no real ``mutmut`` subprocess is ever
spawned (mutation runs are expensive and forbidden in the suite).
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
import sys
from pathlib import Path
from unittest import TestCase

from .helpers import ROOT

SCRIPTS = ROOT / "scripts"


def _load_script(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mutation = _load_script("mutation")

# A representative slice of the real ``only_mutate`` config: one packaged module
# (src-prefixed) and one out-of-package skill script (hyphenated dir).
SAMPLE = [
    "src/skill_library/security.py",
    "skills/typescript-coding/scripts/check_conventions.py",
]


class ModuleGlobTests(TestCase):
    def test_src_prefix_is_stripped(self):
        self.assertEqual(mutation.module_glob("src/skill_library/security.py"), "skill_library.security.*")

    def test_out_of_package_script_keeps_full_dotted_path(self):
        self.assertEqual(
            mutation.module_glob("skills/typescript-coding/scripts/check_conventions.py"),
            "skills.typescript-coding.scripts.check_conventions.*",
        )

    def test_matches_mutmuts_own_derivation(self):
        # Guards against drift from mutmut's get_mutant_name: module name is the
        # suffix-less path with os.sep -> '.', minus a leading 'src.'.
        for source in SAMPLE:
            derived = mutation.module_glob(source)
            self.assertTrue(derived.endswith(".*"))
            self.assertNotIn("/", derived)
            self.assertFalse(derived.startswith("src."))


class ResolveScopeTests(TestCase):
    def test_none_runs_whole_scope(self):
        self.assertEqual(mutation.resolve_scope(None, SAMPLE), ("all", []))
        self.assertEqual(mutation.resolve_scope("", SAMPLE), ("all", []))

    def test_short_name_resolves_to_module_glob(self):
        self.assertEqual(mutation.resolve_scope("security", SAMPLE), ("module", ["skill_library.security.*"]))

    def test_source_path_resolves_to_module_glob(self):
        self.assertEqual(
            mutation.resolve_scope("src/skill_library/security.py", SAMPLE),
            ("module", ["skill_library.security.*"]),
        )

    def test_basename_resolves_to_module_glob(self):
        self.assertEqual(
            mutation.resolve_scope("check_conventions.py", SAMPLE),
            ("module", ["skills.typescript-coding.scripts.check_conventions.*"]),
        )

    def test_absolute_path_suffix_matches(self):
        abs_path = f"/home/dev/{SAMPLE[0]}"
        self.assertEqual(mutation.resolve_scope(abs_path, SAMPLE), ("module", ["skill_library.security.*"]))

    def test_explicit_glob_passthrough(self):
        self.assertEqual(
            mutation.resolve_scope("skill_library.validator.*", SAMPLE),
            ("glob", ["skill_library.validator.*"]),
        )

    def test_in_repo_but_unmutated_path_is_out_of_scope(self):
        # Editing a real module that is not under mutation scope is a no-op, not an
        # error — the AI wrapper must exit 0 so the edit flow is not blocked.
        kind, patterns = mutation.resolve_scope("src/skill_library/discovery.py", SAMPLE)
        self.assertEqual((kind, patterns), ("out-of-scope", []))

    def test_unknown_bare_name_is_unknown(self):
        self.assertEqual(mutation.resolve_scope("nonsense", SAMPLE), ("unknown", []))


class MaxChildrenTests(TestCase):
    def test_leaves_two_cores_free(self):
        self.assertEqual(mutation.default_max_children(32), 30)
        self.assertEqual(mutation.default_max_children(4), 2)

    def test_never_below_one(self):
        self.assertEqual(mutation.default_max_children(2), 1)
        self.assertEqual(mutation.default_max_children(1), 1)
        self.assertEqual(mutation.default_max_children(None), 2)


class BuildArgsTests(TestCase):
    def test_scoped_argv(self):
        self.assertEqual(
            mutation.build_mutmut_args(["skill_library.security.*"], 8),
            ["run", "skill_library.security.*", "--max-children", "8"],
        )

    def test_full_scope_argv(self):
        self.assertEqual(mutation.build_mutmut_args([], 4), ["run", "--max-children", "4"])


class RealConfigTests(TestCase):
    def test_reads_real_only_mutate(self):
        only = mutation.read_only_mutate(ROOT / "pyproject.toml")
        self.assertIn("src/skill_library/security.py", only)
        self.assertIn("skills/typescript-coding/scripts/check_conventions.py", only)

    def test_every_configured_source_resolves_by_short_name(self):
        only = mutation.read_only_mutate(ROOT / "pyproject.toml")
        for source in only:
            stem = Path(source).stem
            kind, patterns = mutation.resolve_scope(stem, only)
            self.assertEqual(kind, "module", stem)
            self.assertEqual(patterns, [mutation.module_glob(source)])


class MainTests(TestCase):
    def _run(self, argv):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = mutation.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_list_exits_zero_and_names_modules(self):
        code, out, _ = self._run(["--list"])
        self.assertEqual(code, 0)
        self.assertIn("security", out)
        self.assertIn("src/skill_library/security.py", out)

    def test_dry_run_prints_command_without_spawning(self):
        code, out, _ = self._run(["--dry-run", "security"])
        self.assertEqual(code, 0)
        self.assertIn("-m mutmut run skill_library.security.*", out)
        self.assertIn("--max-children", out)

    def test_dry_run_honours_explicit_max_children(self):
        code, out, _ = self._run(["--dry-run", "-j", "3", "security"])
        self.assertEqual(code, 0)
        self.assertIn("--max-children 3", out)

    def test_out_of_scope_path_exits_zero_without_running(self):
        code, out, _ = self._run(["--dry-run", "src/skill_library/discovery.py"])
        self.assertEqual(code, 0)
        self.assertIn("not under mutation scope", out)

    def test_unknown_scope_exits_two(self):
        code, _, err = self._run(["--dry-run", "nonsense"])
        self.assertEqual(code, 2)
        self.assertIn("unknown scope", err)
