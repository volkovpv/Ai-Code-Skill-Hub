#!/usr/bin/env python3
"""bump_version.py — the only correct way to bump the project version.

Atomically stamps the new version into every version-carrying file:

- ``pyproject.toml`` — [project].version (the source of truth);
- ``src/skill_library/__init__.py`` — ``__version__``;
- ``CHANGELOG.md`` — inserts a ``## [X.Y.Z] — YYYY-MM-DD`` entry stub before
  the previous entry; the change description is filled in by hand;
- ``uv.lock`` (when present) — the project package version. Patched with the
  same textual substitution, without invoking ``uv``: the script stays
  stdlib-only and offline, and the result is byte-identical to what
  ``uv lock`` would write. Otherwise the lock would trail pyproject by one
  step: ``uv run`` freezes the lock BEFORE the script starts.

Afterwards it runs the drift gate itself (scripts/check_version_drift.py) and
fails if the files diverged. Never edit the version by hand in three files —
both developers and agents use only this script (see AGENTS.md
"Release discipline" and the README section on project versioning and
auto-releases).

Usage:
    python3 scripts/bump_version.py 0.0.1        # explicit version
    python3 scripts/bump_version.py --patch      # 0.0.0 -> 0.0.1
    python3 scripts/bump_version.py --minor      # 0.0.1 -> 0.1.0
    python3 scripts/bump_version.py --major      # 0.1.0 -> 1.0.0

The new version must be strictly greater than the current one (SemVer,
monotonic growth).
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version_drift import VERSION_RE, check, read_pyproject_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CHANGELOG_STUB = """## [{version}] — {date}

- TODO: describe this version's changes (the text becomes the GitHub release notes).

"""


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def next_version(current: str, part: str) -> str:
    major, minor, patch = (list(parse_version(current)) + [0, 0, 0])[:3]
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _substitute(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"ERROR: no version line matched in {path}")
    path.write_text(new_text, encoding="utf-8")


def _project_name(root: Path) -> str:
    """Package name from pyproject.toml, normalized per uv's rules (PEP 503)."""
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise SystemExit("ERROR: no [project].name found in pyproject.toml")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def bump(root: Path, new_version: str, date: datetime.date) -> None:
    current = read_pyproject_version(root)
    if not VERSION_RE.match(new_version):
        raise SystemExit(f"ERROR: '{new_version}' is not a valid X.Y.Z version")
    if parse_version(new_version) <= parse_version(current):
        raise SystemExit(
            f"ERROR: new version {new_version} must be greater than current {current}"
        )

    _substitute(
        root / "pyproject.toml",
        r'^version\s*=\s*"[^"]*"',
        f'version = "{new_version}"',
    )
    _substitute(
        root / "src" / "skill_library" / "__init__.py",
        r'^__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
    )

    # uv.lock is optional (the zero-tooling fallback lives without uv), but
    # when present the project package version must match pyproject.toml.
    uv_lock = root / "uv.lock"
    if uv_lock.is_file():
        _substitute(
            uv_lock,
            rf'^(name = "{re.escape(_project_name(root))}"\nversion) = "[^"]*"',
            rf'\1 = "{new_version}"',
        )

    changelog = root / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    match = re.search(r"^## \[", text, re.MULTILINE)
    if match is None:
        raise SystemExit("ERROR: CHANGELOG.md has no '## [X.Y.Z]' entry to insert before")
    stub = CHANGELOG_STUB.format(version=new_version, date=date.isoformat())
    changelog.write_text(text[: match.start()] + stub + text[match.start():], encoding="utf-8")

    problems = check(root)
    if problems:  # self-check: no drift may remain after a bump
        for problem in problems:
            print(f"FAIL(bump): {problem}", file=sys.stderr)
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="explicit new version X.Y.Z")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--patch", action="store_true")
    group.add_argument("--minor", action="store_true")
    group.add_argument("--major", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    part = "major" if args.major else "minor" if args.minor else "patch" if args.patch else None
    if bool(args.version) == bool(part):
        parser.error("pass either an explicit version or exactly one of --patch/--minor/--major")

    root = args.root.resolve()
    current = read_pyproject_version(root)
    new_version = args.version or next_version(current, part)
    bump(root, new_version, datetime.date.today())

    print(f"Version bumped: {current} -> {new_version}")
    print("Next: fill in the CHANGELOG.md entry (the TODO line) — "
          "its text becomes the release notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
