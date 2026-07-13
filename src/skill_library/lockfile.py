"""Read/write the per-project ``.agent-skills.lock.yaml``.

The lock file lives in the root of the *target* project and records the
provenance of every installed skill::

    version: 1
    skills:
      - name: example-skill
        source: /absolute/path/to/the/library        # or a git repository URL
        source_commit: <hex or null>
        skill_version: 0.1.0
        agent: universal
        mode: copy                                   # copy | link
        target_path: .agents/skills/example-skill    # relative to the project
        checksum: sha256:<aggregate over files>
        installed_at: 2026-07-12T12:00:00+00:00
        updated_at: null
        files:                                       # managed files only
          - path: SKILL.md
            sha256: <hex>
"""

from __future__ import annotations


import os
import tempfile
from pathlib import Path

from . import yamlio

__all__ = [
    "LOCKFILE_NAME",
    "LOCK_VERSION",
    "LockError",
    "lock_path",
    "load_lock",
    "save_lock",
    "get_entry",
    "upsert_entry",
    "remove_entry",
]

LOCKFILE_NAME = ".agent-skills.lock.yaml"
LOCK_VERSION = 1


class LockError(Exception):
    """Raised when the lock file is unreadable or malformed."""


def lock_path(target_root: Path) -> Path:
    return Path(target_root) / LOCKFILE_NAME


def _empty_lock() -> dict:
    return {"version": LOCK_VERSION, "skills": []}


def load_lock(target_root: Path) -> dict:
    path = lock_path(target_root)
    if not path.is_file():
        return _empty_lock()
    try:
        data = yamlio.load_file(path)
    except yamlio.YamlError as exc:
        raise LockError(f"{path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("skills", []), list):
        raise LockError(f"{path}: malformed lock file")
    if data.get("version") != LOCK_VERSION:
        raise LockError(
            f"{path}: unsupported lock version {data.get('version')!r} (expected {LOCK_VERSION})"
        )
    data.setdefault("skills", [])
    return data


def save_lock(target_root: Path, data: dict) -> None:
    data = {"version": LOCK_VERSION, "skills": data.get("skills", [])}
    path = lock_path(target_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        yamlio.dump_file(tmp_path, data)
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def get_entry(data: dict, name: str) -> dict | None:
    for entry in data.get("skills", []):
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def upsert_entry(data: dict, entry: dict) -> None:
    skills = data.setdefault("skills", [])
    for i, existing in enumerate(skills):
        if isinstance(existing, dict) and existing.get("name") == entry.get("name"):
            skills[i] = entry
            return
    skills.append(entry)
    skills.sort(key=lambda e: str(e.get("name", "")))


def remove_entry(data: dict, name: str) -> bool:
    skills = data.get("skills", [])
    for i, existing in enumerate(skills):
        if isinstance(existing, dict) and existing.get("name") == name:
            del skills[i]
            return True
    return False
