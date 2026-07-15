#!/usr/bin/env python3
"""Fail when Cyrillic text appears outside the allowlisted locations.

Language policy (AGENTS.md): only the root ``README.md`` and
``__test__/README.md`` are written in Russian; audit reports under ``_audit/``
are exempt; everything else — skill content, source code, scripts, templates,
workflows, tests, docs — is English-only.

Usage::

    python scripts/check_language.py            # scan the repository root
    python scripts/check_language.py <dir>      # scan another tree (tests)

Output: one ``<path>:<line>: non-English (Cyrillic) text ...`` line per
finding. Exit codes: ``0`` clean, ``1`` findings, ``2`` usage error.

A line that legitimately needs non-English characters (e.g. Unicode test
data) carries an inline waiver with a mandatory non-empty reason::

    bad = ["тест"]  # non-english-ok: non-ASCII input rejection sample

A waiver without a reason does not count — the line stays flagged.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files allowed to contain Russian text, relative to the scanned root.
ALLOWED_FILES = frozenset(
    {
        "README.md",  # the root README is written in Russian by policy
        "__test__/README.md",  # the test-suite guide is written in Russian by policy
        "pyproject.toml",  # carries the author's legal name in project metadata
        "uv.lock",  # mirrors pyproject.toml metadata verbatim
    }
)

# Directories (relative prefixes) whose whole content is exempt.
ALLOWED_DIR_PREFIXES = ("_audit/",)

# Never scanned: VCS internals, environments, caches, generated trees.
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "mutants",
        "node_modules",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
    }
)

CYRILLIC_RE = re.compile(r"[Ѐ-ӿԀ-ԯ]")  # non-english-ok: the detection range itself
WAIVER_RE = re.compile(r"non-english-ok:\s*\S")


def is_allowed(rel_posix: str) -> bool:
    if rel_posix in ALLOWED_FILES:
        return True
    return rel_posix.startswith(ALLOWED_DIR_PREFIXES)


def scan_file(path: Path, rel_posix: str) -> list[tuple[str, int]]:
    """Findings for one file: [(relative path, line number)]. Binary → []."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []  # binary or unreadable: the language policy is about text
    findings: list[tuple[str, int]] = []
    for line_no, line in enumerate(text.split("\n"), start=1):
        if not CYRILLIC_RE.search(line):
            continue
        if WAIVER_RE.search(line):
            continue
        findings.append((rel_posix, line_no))
    return findings


def scan_tree(root: Path) -> list[tuple[str, int]]:
    findings: list[tuple[str, int]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(
            part in SKIP_DIR_NAMES or part.endswith(".egg-info")
            for part in rel.parts[:-1]
        ):
            continue
        rel_posix = rel.as_posix()
        if is_allowed(rel_posix):
            continue
        findings.extend(scan_file(path, rel_posix))
    return findings


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print("usage: check_language.py [root-dir]", file=sys.stderr)
        return 2
    root = Path(args[0]) if args else REPO_ROOT
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    findings = scan_tree(root)
    for rel_posix, line_no in findings:
        print(
            f"{rel_posix}:{line_no}: non-English (Cyrillic) text outside the "
            "allowlist (README.md, __test__/README.md, _audit/); translate it "
            "or add an inline 'non-english-ok: <reason>' waiver"
        )
    summary = "OK(language)" if not findings else "FAIL(language)"
    print(f"{summary}: {len(findings)} finding(s)", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
