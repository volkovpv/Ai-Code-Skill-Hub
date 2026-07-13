#!/usr/bin/env python3
"""check_version_drift.py — one version, many files: any drift is an error.

The source of truth for the project version is ``pyproject.toml``
([project].version). The following must match it:

- ``src/skill_library/__init__.py`` — ``__version__``;
- ``CHANGELOG.md`` — the first ``## [X.Y.Z]`` entry.

Skill versions in ``skills.yaml`` are independent skill-content versions and
are not checked here (their discipline is described in AGENTS.md).

Usage: ``python3 scripts/check_version_drift.py [--root DIR] [--print-version]``.
``--print-version`` prints the version from pyproject.toml and nothing else —
that is how workflows obtain the version from the single source.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSION_RE = re.compile(r"^\d+(\.\d+)*$")


def read_pyproject_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def read_init_version(root: Path) -> str | None:
    text = (root / "src" / "skill_library" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def read_changelog_version(root: Path) -> str | None:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[([^\]]+)\]", text, re.MULTILINE)
    return match.group(1) if match else None


def check(root: Path) -> list[str]:
    """Return the list of mismatches; empty list — no drift."""
    problems: list[str] = []
    version = read_pyproject_version(root)
    if not VERSION_RE.match(version):
        problems.append(f"pyproject.toml: version '{version}' is not X.Y.Z")

    init_version = read_init_version(root)
    if init_version is None:
        problems.append("src/skill_library/__init__.py: no __version__ found")
    elif init_version != version:
        problems.append(
            f"src/skill_library/__init__.py: __version__ '{init_version}' "
            f"!= pyproject.toml '{version}'"
        )

    changelog_version = read_changelog_version(root)
    if changelog_version is None:
        problems.append("CHANGELOG.md: no '## [X.Y.Z]' entry found")
    elif changelog_version != version:
        problems.append(
            f"CHANGELOG.md: first entry [{changelog_version}] "
            f"!= pyproject.toml '{version}'"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--print-version", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.print_version:
        print(read_pyproject_version(root))
        return 0

    problems = check(root)
    if problems:
        for problem in problems:
            print(f"FAIL(version-drift): {problem}", file=sys.stderr)
        return 1
    print(f"  ok (ver)  project {read_pyproject_version(root)} "
          "(pyproject = __init__ = CHANGELOG)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
