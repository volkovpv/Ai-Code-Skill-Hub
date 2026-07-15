#!/usr/bin/env python3
"""Local convenience wrapper around ``mutmut run``: throttled parallelism and
change-scoped runs.

A full mutation run is expensive twice over: ``mutmut`` forks ``os.cpu_count()``
workers (saturating every core, so the machine becomes unusable) and it re-tests
every mutant across all ``only_mutate`` files (~hours on a cold cache). This
wrapper addresses both:

* ``--max-children`` defaults to ``cpu - 2`` (min 1), leaving headroom instead of
  pinning the whole box. ``mutmut run`` has no config-file knob for this, only the
  CLI flag, hence a wrapper.
* Given a changed source file (or its short name), it runs ``mutmut run`` for just
  that file's mutants. A scoped run passes explicit mutant globs, which ``mutmut``
  always re-tests (the "skip already-resolved" path only applies to full runs), so
  the result reflects the current tests without re-doing the whole library.

The mutant-name globs are derived the same way ``mutmut`` derives them from a file
path (drop the suffix, ``os.sep`` → ``.``, strip a leading ``src.``), and the set
of mutatable files is read straight from ``[tool.mutmut].only_mutate`` in
``pyproject.toml`` — so this wrapper needs no hand-maintained module list and stays
correct if that config changes.

Not used by CI: the scheduled ``mutation.yml`` job still calls ``mutmut run``
directly at full parallelism over the whole scope. This is a developer / coding-agent
ergonomic layer only.

Usage::

    python scripts/mutation.py                       # whole scope, throttled
    python scripts/mutation.py security              # one module by short name
    python scripts/mutation.py src/skill_library/security.py   # ...or by path
    python scripts/mutation.py -j 4 validator        # override parallelism
    python scripts/mutation.py --list                # show scopeable modules
    python scripts/mutation.py --dry-run security     # print the command only
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_only_mutate(pyproject: Path) -> list[str]:
    """Return the ``[tool.mutmut].only_mutate`` source paths (repo-relative)."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    only = data.get("tool", {}).get("mutmut", {}).get("only_mutate", [])
    return [str(p) for p in only]


def module_glob(source_path: str) -> str:
    """Mirror mutmut's path → module-name derivation and append a mutant glob.

    ``src/skill_library/security.py`` → ``skill_library.security.*``;
    ``skills/typescript-coding/scripts/check_conventions.py`` →
    ``skills.typescript-coding.scripts.check_conventions.*``.
    """
    normalized = source_path.replace("\\", "/").strip("/")
    if normalized.endswith(".py"):
        normalized = normalized[: -len(".py")]
    module = normalized.replace("/", ".")
    if module.startswith("src."):
        module = module[len("src.") :]
    return f"{module}.*"


def _looks_like_path(arg: str) -> bool:
    return "/" in arg or "\\" in arg or arg.endswith(".py")


def resolve_scope(arg: str | None, only_mutate: list[str]) -> tuple[str, list[str]]:
    """Resolve a user scope argument to (kind, mutmut-patterns).

    kind is one of:
      * ``"all"``          — no scope; run the whole configured scope.
      * ``"glob"``         — the argument already contains ``*``; passed through.
      * ``"module"``       — matched a file in ``only_mutate``; one derived glob.
      * ``"out-of-scope"`` — a source path that is not under mutation scope; a
                             no-op run (a healthy outcome, e.g. after editing a
                             module that mutmut does not mutate).
      * ``"unknown"``      — could not be resolved to anything; caller errors out.
    """
    if not arg:
        return "all", []
    if "*" in arg:
        return "glob", [arg]

    normalized = arg.replace("\\", "/").strip("/")
    # Build match keys for each mutatable source: full path, basename, stem.
    for source in only_mutate:
        src_norm = source.replace("\\", "/").strip("/")
        stem = Path(src_norm).stem
        candidates = {src_norm, Path(src_norm).name, stem}
        if normalized in candidates:
            return "module", [module_glob(source)]
        # Tolerate absolute paths or extra leading dirs on either side.
        if normalized.endswith(src_norm) or src_norm.endswith(normalized):
            return "module", [module_glob(source)]

    if _looks_like_path(arg):
        # A real source path that simply is not in the mutation scope: nothing to
        # mutate is the correct answer, not an error.
        return "out-of-scope", []
    return "unknown", []


def default_max_children(cpu: int | None) -> int:
    """Leave two cores free so the machine stays usable; never drop below 1."""
    return max(1, (cpu or 4) - 2)


def build_mutmut_args(patterns: list[str], max_children: int) -> list[str]:
    """The argument vector passed to ``mutmut`` (without the interpreter prefix)."""
    return ["run", *patterns, "--max-children", str(max_children)]


def _short_names(only_mutate: list[str]) -> list[str]:
    return [Path(p.replace("\\", "/")).stem for p in only_mutate]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "scope",
        nargs="?",
        help="module short name (e.g. 'security'), source path, or a mutant glob; "
        "omit to run the whole configured scope",
    )
    parser.add_argument(
        "-j",
        "--max-children",
        type=int,
        default=None,
        help="parallel workers (default: CPU count minus 2, min 1)",
    )
    parser.add_argument("--list", action="store_true", help="list scopeable modules and exit")
    parser.add_argument("--dry-run", action="store_true", help="print the mutmut command without running it")
    parser.add_argument("--pyproject", type=Path, default=ROOT / "pyproject.toml", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    only_mutate = read_only_mutate(args.pyproject)

    if args.list:
        print("Scopeable modules (short name — source path):")
        for name, path in zip(_short_names(only_mutate), only_mutate):
            print(f"  {name} — {path}")
        return 0

    kind, patterns = resolve_scope(args.scope, only_mutate)
    if kind == "unknown":
        print(
            f"mutation: unknown scope {args.scope!r}. Known modules: "
            f"{', '.join(_short_names(only_mutate))} (or pass a source path / mutant glob).",
            file=sys.stderr,
        )
        return 2
    if kind == "out-of-scope":
        print(f"mutation: {args.scope} is not under mutation scope ([tool.mutmut].only_mutate); nothing to run.")
        return 0

    max_children = args.max_children if args.max_children is not None else default_max_children(os.cpu_count())
    if max_children < 1:
        parser.error("--max-children must be >= 1")

    mutmut_args = build_mutmut_args(patterns, max_children)
    command = [sys.executable, "-m", "mutmut", *mutmut_args]
    scope_label = "whole scope" if kind == "all" else " ".join(patterns)
    print(f"mutation: {scope_label} with --max-children {max_children}")
    if args.dry_run:
        print(" ".join(command))
        return 0
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
