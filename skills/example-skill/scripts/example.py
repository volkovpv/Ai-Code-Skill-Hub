#!/usr/bin/env python3
"""Suggest a Conventional Commits header for a diff read from stdin.

Usage:
    git diff --staged | python scripts/example.py

Deterministic, offline, stdlib-only. The output is a suggestion that the
agent must review against references/example.md.
"""

from __future__ import annotations

import re
import sys
from collections import Counter

_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)

_DOC_SUFFIXES = (".md", ".rst", ".txt")
_CI_MARKERS = (".github/", ".gitlab-ci", "Jenkinsfile", ".circleci/")
_BUILD_MARKERS = (
    "pyproject.toml",
    "setup.py",
    "package.json",
    "requirements",
    "Makefile",
    "Dockerfile",
)


def changed_files(diff: str) -> list[str]:
    return _FILE_RE.findall(diff)


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (
        "__test__" in path
        or "/tests/" in path
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js"))
    )


def classify(diff: str) -> tuple[str, str, str]:
    """Return (type, scope, subject) for the diff."""
    files = changed_files(diff)
    if not files:
        return "chore", "", "describe the change (no files detected in diff)"

    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))

    if all(is_test_path(f) for f in files):
        ctype = "test"
    elif all(f.endswith(_DOC_SUFFIXES) for f in files):
        ctype = "docs"
    elif all(any(m in f for m in _CI_MARKERS) for f in files):
        ctype = "ci"
    elif all(any(m in f for m in _BUILD_MARKERS) for f in files):
        ctype = "build"
    elif re.search(r"^\+.*\b(fix|bug|regression)\b", diff, re.IGNORECASE | re.MULTILINE):
        ctype = "fix"
    elif removed > added * 2:
        ctype = "refactor"
    else:
        ctype = "feat"

    top_dirs = Counter(f.split("/", 1)[0] for f in files if "/" in f)
    scope = top_dirs.most_common(1)[0][0] if top_dirs else ""

    if len(files) == 1:
        subject = f"update {files[0].rsplit('/', 1)[-1]}"
    else:
        subject = f"update {len(files)} files (+{added}/-{removed} lines)"
    return ctype, scope, subject


def main() -> int:
    diff = sys.stdin.read()
    if not diff.strip():
        print("error: empty diff on stdin", file=sys.stderr)
        return 1
    ctype, scope, subject = classify(diff)
    header = f"{ctype}({scope}): {subject}" if scope else f"{ctype}: {subject}"
    print(header)
    print(f"# files changed: {len(changed_files(diff))}", file=sys.stderr)
    print("# review against references/example.md before using", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
