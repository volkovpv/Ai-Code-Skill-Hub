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

The bump is all-or-nothing: every file's new text is computed first (pre-flight),
and disk is touched only once all substitutions have matched. Each file is
written through a temp file + ``os.replace``, and a mid-write failure rolls the
already-written files back to their original bytes — a failing bump never leaves
the version half-stamped.

Usage:
    python3 scripts/bump_version.py X.Y.Z        # explicit version
    python3 scripts/bump_version.py --patch      # bump the patch digit
    python3 scripts/bump_version.py --minor      # bump minor, reset patch
    python3 scripts/bump_version.py --major      # bump major, reset minor+patch

The new version must be strictly greater than the current one (SemVer,
monotonic growth).
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_version_drift import VERSION_RE, check, read_pyproject_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CHANGELOG_STUB = """## [{version}] — {date}

- TODO: describe this version's changes (the text becomes the GitHub release notes).

"""


def _require_semver(version: str, label: str) -> None:
    """Reject a non ``X.Y.Z`` version before it reaches ``parse_version``.

    ``parse_version`` calls ``int()`` on each dotted part, so a non-standard
    version read from pyproject (e.g. ``0.1.0rc1``) would otherwise die with a
    bare ``ValueError`` traceback instead of a diagnosable message.
    """
    if not VERSION_RE.match(version):
        raise SystemExit(f"ERROR: {label} version '{version}' is not a valid X.Y.Z version")


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def next_version(current: str, part: str) -> str:
    major, minor, patch = (list(parse_version(current)) + [0, 0, 0])[:3]
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _read_keep_eol(path: Path) -> str:
    """Read UTF-8 text without translating line endings.

    ``newline=""`` disables the universal-newlines pass, so CRLF/CR bytes survive
    verbatim into the string (``Path.read_text`` grew a ``newline`` argument only
    in 3.13; the project still supports 3.12, hence the explicit ``open``).
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _atomic_write(path: Path, text: str) -> None:
    """Write UTF-8 text verbatim via a temp file + ``os.replace``.

    ``newline=""`` keeps whatever line endings ``text`` holds; the temp file
    lives in the target directory so ``os.replace`` is a same-filesystem atomic
    rename (no torn file if the process dies mid-write). Mirrors the lockfile
    writer's idiom in ``skill_library.lockfile``.
    """
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _plan_substitution(path: Path, pattern: str, replacement: str) -> str:
    """Compute a file's new text (no write); fail closed if the anchor is absent.

    Part of the pre-flight: every substitution is validated in memory before any
    file is touched, so a non-matching pattern (e.g. a regenerated ``uv.lock``)
    aborts the whole bump before it can leave a half-stamped tree.
    """
    text = _read_keep_eol(path)
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"ERROR: no version line matched in {path}")
    return new_text


def _plan_changelog(path: Path, new_version: str, date: datetime.date) -> str:
    """Compute the CHANGELOG's new text with the stub inserted (no write)."""
    text = _read_keep_eol(path)
    match = re.search(r"^## \[", text, re.MULTILINE)
    if match is None:
        raise SystemExit("ERROR: CHANGELOG.md has no '## [X.Y.Z]' entry to insert before")
    eol = "\r\n" if "\r\n" in text else "\n"
    stub = CHANGELOG_STUB.format(version=new_version, date=date.isoformat())
    if eol != "\n":  # match the stub's newlines to the file's own style
        stub = stub.replace("\n", eol)
    return text[: match.start()] + stub + text[match.start():]


def _commit(plans: list[tuple[Path, str]]) -> None:
    """Apply every planned (path, new_text) atomically, rolling back on failure.

    The pre-flight already rules out the realistic abort (a non-matching
    pattern); this guards the residual risk of an IO error part-way through the
    write set by snapshotting the originals and restoring the files already
    written before re-raising. Best-effort transactionality across files without
    a journal — the invariant is: a failed bump changes nothing on disk.
    """
    originals = {path: path.read_bytes() for path, _ in plans}
    written: list[Path] = []
    try:
        for path, new_text in plans:
            _atomic_write(path, new_text)
            written.append(path)
    except BaseException:
        for path in reversed(written):
            path.write_bytes(originals[path])
        raise


def _project_name(root: Path) -> str:
    """Package name from pyproject.toml, normalized per uv's rules (PEP 503)."""
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise SystemExit("ERROR: no [project].name found in pyproject.toml")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def bump(root: Path, new_version: str, date: datetime.date) -> None:
    current = read_pyproject_version(root)
    _require_semver(current, "current")
    _require_semver(new_version, "new")
    if parse_version(new_version) <= parse_version(current):
        raise SystemExit(
            f"ERROR: new version {new_version} must be greater than current {current}"
        )

    # --- Pre-flight: compute every file's new text. Any missing anchor raises
    # here, before a single byte is written, so the tree is never left partly
    # stamped (H-4: a non-matching uv.lock used to abort after pyproject and
    # __init__.py had already been rewritten).
    plans: list[tuple[Path, str]] = [
        (
            root / "pyproject.toml",
            _plan_substitution(
                root / "pyproject.toml",
                r'^version\s*=\s*"[^"]*"',
                f'version = "{new_version}"',
            ),
        ),
        (
            root / "src" / "skill_library" / "__init__.py",
            _plan_substitution(
                root / "src" / "skill_library" / "__init__.py",
                r'^__version__\s*=\s*"[^"]*"',
                f'__version__ = "{new_version}"',
            ),
        ),
    ]

    # uv.lock is optional (the zero-tooling fallback lives without uv), but
    # when present the project package version must match pyproject.toml.
    uv_lock = root / "uv.lock"
    if uv_lock.is_file():
        # ``\r?\n`` keeps the two-line anchor matchable on a CRLF-checked-out
        # lock; the captured group reproduces whichever newline was there.
        plans.append((
            uv_lock,
            _plan_substitution(
                uv_lock,
                rf'^(name = "{re.escape(_project_name(root))}"\r?\nversion) = "[^"]*"',
                rf'\1 = "{new_version}"',
            ),
        ))

    plans.append((root / "CHANGELOG.md", _plan_changelog(root / "CHANGELOG.md", new_version, date)))

    # --- Commit: every substitution matched, so write them all (atomic per file,
    # rolled back as a set on any IO failure).
    _commit(plans)

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
    _require_semver(current, "current")  # guard next_version's int() parse
    new_version = args.version or next_version(current, part)
    bump(root, new_version, datetime.date.today())

    print(f"Version bumped: {current} -> {new_version}")
    print("Next: fill in the CHANGELOG.md entry (the TODO line) — "
          "its text becomes the release notes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
