"""Fail-closed path and name checks shared by all mutating operations."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

__all__ = [
    "SecurityError",
    "MAX_SKILL_NAME_LENGTH",
    "validate_skill_name",
    "validate_relative_path",
    "safe_join",
    "ensure_within",
    "ensure_no_symlinks",
]

MAX_SKILL_NAME_LENGTH = 64

# lowercase ASCII, digits and hyphens; must start and end with [a-z0-9]
_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class SecurityError(Exception):
    """Raised when an operation would leave its sandbox or looks unsafe."""


def validate_skill_name(name: str) -> str:
    """Return *name* if it is a valid skill name, raise otherwise."""
    if not isinstance(name, str) or not name:
        raise SecurityError("skill name must be a non-empty string")
    if len(name) > MAX_SKILL_NAME_LENGTH:
        raise SecurityError(
            f"skill name {name!r} is longer than {MAX_SKILL_NAME_LENGTH} characters"
        )
    if not _NAME_RE.match(name):
        raise SecurityError(
            f"invalid skill name {name!r}: use lowercase ASCII letters, digits and "
            "hyphens; must start and end with a letter or digit"
        )
    return name


def validate_relative_path(rel: str) -> str:
    """Validate a relative file path used inside a skill or a lock entry."""
    if not isinstance(rel, str) or not rel:
        raise SecurityError("relative path must be a non-empty string")
    if "\\" in rel or "\x00" in rel:
        raise SecurityError(f"unsupported characters in path {rel!r}")
    if PurePosixPath(rel).is_absolute():
        raise SecurityError(f"absolute paths are not allowed: {rel!r}")
    # Check raw segments: PurePosixPath.parts silently normalizes "." away.
    for part in rel.split("/"):
        if part in ("..", ".", ""):
            raise SecurityError(f"path traversal is not allowed: {rel!r}")
    return rel


def safe_join(base: Path, *parts: str) -> Path:
    """Join *parts* onto *base* and guarantee the result stays inside *base*.

    Every part is validated as a relative path (no ``..``, no absolute
    segments). The final candidate is resolved (following symlinks) and must
    remain within the resolved *base* — this catches symlink escapes.
    """
    base_resolved = Path(base).resolve()
    candidate = base_resolved
    for part in parts:
        validate_relative_path(str(part))
        candidate = candidate / part
    resolved = candidate.resolve()
    if resolved != base_resolved and not resolved.is_relative_to(base_resolved):
        raise SecurityError(f"path {candidate} escapes base directory {base_resolved}")
    return candidate


def ensure_within(base: Path, path: Path) -> None:
    """Raise unless *path* (after resolution) lives inside *base*."""
    base_resolved = Path(base).resolve()
    resolved = Path(path).resolve()
    if resolved != base_resolved and not resolved.is_relative_to(base_resolved):
        raise SecurityError(f"path {path} escapes base directory {base_resolved}")


def ensure_no_symlinks(root: Path) -> None:
    """Raise if *root* or anything inside it is a symlink (fail-closed copy)."""
    root = Path(root)
    if root.is_symlink():
        raise SecurityError(f"{root} is a symlink")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SecurityError(f"symlink inside skill is not allowed: {path}")
