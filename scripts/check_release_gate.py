#!/usr/bin/env python3
"""check_release_gate.py — release-discipline gate ("version ⇔ code changes").

Compares the changes since the last release tag (``vX.Y.Z``) against the
current version in ``pyproject.toml`` and enforces three rules:

1. Used code changed → the version must have been bumped (otherwise a merge
   into main produces no release and the changes go nowhere).
2. Infrastructure-only changes (tests, CI, documentation) → the version must
   stay the same: infrastructure edits are never published as a release.
3. The version grows monotonically — rolling it back is forbidden.

"Used code" is what a consumer of the library receives:
``skills/``, ``src/``, ``scripts/``, ``templates/``, ``skills.yaml``,
``pyproject.toml``, ``LICENSE``. Everything else (``__test__/``, ``.github/``,
``README.md``, ``CHANGELOG.md``, ``AGENTS.md``, …) is infrastructure.
In version-carrying files (pyproject.toml, __init__.py) the version lines
themselves do not count as a code change — otherwise every bump would justify
itself.

While there are no release tags yet the gate always passes: the ``0.0.0``
baseline lives without a release, and the first bump creates the first tag.

Usage: ``python3 scripts/check_release_gate.py [--root DIR]``.
Requires full git history with tags (in CI — checkout with fetch-depth: 0).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version_drift import read_pyproject_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Directories end with a slash; files are exact names.
RELEASE_PATHS = (
    "skills/",
    "src/",
    "scripts/",
    "templates/",
    "skills.yaml",
    "pyproject.toml",
    "LICENSE",
)

# Version-carrying files: lines matching the pattern do not count as a
# used-code change.
VERSION_LINE_RE = {
    "pyproject.toml": re.compile(r'^\s*version\s*=\s*"[^"]*"\s*$'),
    "src/skill_library/__init__.py": re.compile(r'^__version__\s*=\s*"[^"]*"\s*$'),
}

TAG_RE = re.compile(r"^v\d+(\.\d+)*$")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def last_release_tag(root: Path) -> str | None:
    """Highest (by SemVer) release tag reachable from HEAD."""
    tags = [
        tag
        for tag in git(root, "tag", "--list", "v*", "--merged", "HEAD").splitlines()
        if TAG_RE.match(tag)
    ]
    if not tags:
        return None
    return max(tags, key=lambda tag: parse_version(tag[1:]))


def in_release_paths(path: str) -> bool:
    """Whether the path lives under a released (used-code) location."""
    return any(
        path.startswith(prefix) if prefix.endswith("/") else path == prefix
        for prefix in RELEASE_PATHS
    )


def is_release_relevant(root: Path, tag: str, path: str) -> bool:
    """Whether an in-place edit of the file counts as a used-code change."""
    if not in_release_paths(path):
        return False
    version_line = VERSION_LINE_RE.get(path)
    if version_line is None:
        return True
    # Version carrier: inspect the diff content minus the version lines.
    diff = git(root, "diff", tag, "HEAD", "--", path)
    for line in diff.splitlines():
        if line.startswith(("+++", "---")) or not line.startswith(("+", "-")):
            continue
        if not version_line.match(line[1:]):
            return True
    return False


def relevant_changes(root: Path, tag: str) -> list[str]:
    """Used-code paths changed since ``tag`` — rename- and delete-aware.

    ``git diff --name-only`` collapses a rename to its *new* path only, so
    moving used code out of a released location (e.g. ``src/foo.py`` →
    ``_attic/foo.py``) would look like an infra-only change and silently skip
    the release. ``--name-status -M`` exposes both endpoints of every rename;
    such a change is release-relevant if *either* endpoint is used code, and a
    deletion is relevant by its (old) path.
    """
    out = git(root, "diff", "--name-status", "-M", tag, "HEAD")
    relevant: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        code = fields[0][:1]
        if code == "R":  # rename: old path leaves, new path arrives
            relevant.extend(p for p in (fields[1], fields[2]) if in_release_paths(p))
        elif code == "C":  # copy: only the new path is a fresh file
            if in_release_paths(fields[2]):
                relevant.append(fields[2])
        elif code == "D":  # deletion: relevant by the removed (old) path
            if in_release_paths(fields[1]):
                relevant.append(fields[1])
        else:  # A, M, T, … — in-place; honour the version-line exclusion
            if is_release_relevant(root, tag, fields[1]):
                relevant.append(fields[1])
    return relevant


def check(root: Path) -> list[str]:
    """Return the list of release-discipline violations; empty list — all good."""
    version = read_pyproject_version(root)
    tag = last_release_tag(root)
    if tag is None:
        return []
    released = tag[1:]

    relevant = relevant_changes(root, tag)

    problems: list[str] = []
    if relevant and version == released:
        listing = ", ".join(relevant[:10])
        problems.append(
            f"used code changed since {tag} ({listing}) but version is still "
            f"{released} — bump the version in pyproject.toml, __init__.py "
            "and CHANGELOG.md"
        )
    if not relevant and version != released:
        problems.append(
            f"only infrastructure changed since {tag} — version must stay "
            f"{released}, but pyproject.toml says {version}; no release is "
            "published for infra-only changes"
        )
    if relevant and version != released and parse_version(version) < parse_version(released):
        problems.append(
            f"version went backwards: {version} < already released {released}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    problems = check(root)
    if problems:
        for problem in problems:
            print(f"FAIL(release-gate): {problem}", file=sys.stderr)
        return 1

    tag = last_release_tag(root)
    baseline = tag or "no release tags yet (baseline)"
    print(f"  ok (rel)  version {read_pyproject_version(root)} vs {baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
