"""Install / diff / update / remove skills in a target project.

Safety model (fail-closed):

* every destination path is built with :func:`skill_library.security.safe_join`;
* skills containing symlinks are refused;
* only files recorded in the lock entry are ever deleted;
* locally modified installed copies are never overwritten without ``--force``;
* every mutating command supports ``dry_run``.
"""

from __future__ import annotations

from contextlib import contextmanager
import difflib
import hashlib
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import lockfile
from .discovery import SKILLS_DIRNAME, catalog_entry
from .security import (
    SecurityError,
    ensure_no_symlinks,
    safe_join,
    validate_relative_path,
    validate_skill_name,
)
from .validator import validate_skill_dir

__all__ = [
    "InstallError",
    "AGENT_TARGET_DIRS",
    "INSTALL_MODES",
    "RUNTIME_EXCLUDED_PREFIXES",
    "RUNTIME_EXCLUDED_FILES",
    "resolve_skills_root",
    "snapshot",
    "aggregate_checksum",
    "library_commit",
    "installed_state",
    "install_skill",
    "diff_skill",
    "update_skill",
    "remove_skill",
    "status",
]

# Where each harness expects installed skills, relative to the target project.
# "hermes" has no fixed location: its skills directory is user configuration
# that may live outside the project, so it must be passed explicitly.
AGENT_TARGET_DIRS: dict[str, str | None] = {
    "universal": ".agents/skills",
    "codex": ".agents/skills",
    "opencode": ".agents/skills",
    "claude": ".claude/skills",
    "hermes": None,
}

_IGNORED_FILES = {".DS_Store", "Thumbs.db"}
_IGNORED_DIRS = {"__pycache__"}

# Distribution profiles. "runtime" ships what an agent needs at run time and
# leaves development-only content behind; "full" ships the whole skill module.
INSTALL_MODES = ("runtime", "full")
RUNTIME_EXCLUDED_PREFIXES = (
    "observations/candidates/",  # unreviewed observations never reach consumers
    "observations/rejected/",    # kept in the library for audit only
    "data/fixtures/",            # test-only fixtures
)
RUNTIME_EXCLUDED_FILES = (
    "README.md",  # library-user documentation; the agent reads SKILL.md
)


def _runtime_excluded(rel_posix: str) -> bool:
    if rel_posix in RUNTIME_EXCLUDED_FILES:
        return True
    return any(rel_posix.startswith(prefix) for prefix in RUNTIME_EXCLUDED_PREFIXES)


class InstallError(Exception):
    """Raised when an install/update/remove operation cannot proceed safely."""


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def resolve_skills_root(target_root: Path, agent: str, skills_dir_override: Path | None) -> Path:
    """Directory that holds installed skills for *agent* in *target_root*."""
    target_root = Path(target_root).resolve()
    if skills_dir_override is not None:
        override = Path(skills_dir_override)
        return (override if override.is_absolute() else target_root / override).resolve()
    if agent not in AGENT_TARGET_DIRS:
        raise InstallError(f"unknown agent {agent!r}; known: {', '.join(sorted(AGENT_TARGET_DIRS))}")
    rel = AGENT_TARGET_DIRS[agent]
    if rel is None:
        raise InstallError(
            f"agent {agent!r} has no default skills directory; pass --target-skills-dir"
        )
    return target_root / rel


def iter_skill_files(skill_dir: Path, install_mode: str = "full") -> list[str]:
    """Relative POSIX paths of the skill files shipped in *install_mode*, sorted."""
    if install_mode not in INSTALL_MODES:
        raise InstallError(f"unknown install mode {install_mode!r}; allowed: {', '.join(INSTALL_MODES)}")
    skill_dir = Path(skill_dir)
    result: list[str] = []
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        if any(part in _IGNORED_DIRS for part in rel.parts):
            continue
        if rel.name in _IGNORED_FILES or rel.name.endswith(".pyc"):
            continue
        rel_posix = rel.as_posix()
        if install_mode == "runtime" and _runtime_excluded(rel_posix):
            continue
        result.append(rel_posix)
    return result


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(skill_dir: Path, install_mode: str = "full") -> list[dict]:
    """``[{path, sha256}, ...]`` for every file shipped in *install_mode*."""
    skill_dir = Path(skill_dir)
    return [
        {"path": rel, "sha256": file_sha256(skill_dir / rel)}
        for rel in iter_skill_files(skill_dir, install_mode)
    ]


def aggregate_checksum(files: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in sorted(files, key=lambda r: r["path"]):
        digest.update(f"{record['path']}:{record['sha256']}\n".encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def library_commit(library_root: Path) -> str | None:
    """Current git commit of the library, or None outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(library_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = out.stdout.strip()
    return commit if out.returncode == 0 and commit else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _source_skill_dir(library_root: Path, name: str) -> Path:
    validate_skill_name(name)
    skill_dir = Path(library_root) / SKILLS_DIRNAME / name
    if not skill_dir.is_dir():
        raise InstallError(f"skill {name!r} not found in {Path(library_root) / SKILLS_DIRNAME}")
    return skill_dir


def _dest_dir(target_root: Path, entry: dict) -> Path:
    """Resolve the installed directory recorded in a lock entry (fail-closed)."""
    target_root = Path(target_root).resolve()
    raw = str(entry.get("target_path", ""))
    if not raw:
        raise InstallError(f"lock entry {entry.get('name')!r} has no target_path")
    path = Path(raw)
    if path.is_absolute():
        return path
    parts = path.parts
    # Validate containment on the parent and attach the leaf unresolved:
    # for link-mode installs the leaf itself is a (managed) symlink that
    # legitimately points outside the project.
    validate_relative_path(parts[-1])
    parent = safe_join(target_root, *parts[:-1]) if len(parts) > 1 else target_root
    dest = parent / parts[-1]
    if entry.get("mode") != "link" and dest.is_symlink():
        raise InstallError(
            f"installed path {dest} is a symlink but the lock entry is copy-mode; refusing"
        )
    return dest


def _record_target_path(target_root: Path, dest: Path) -> str:
    """Store the path relative to the project when possible, absolute otherwise.

    *dest* must already be absolute (it comes from ``safe_join``) and is NOT
    resolved here: for link-mode installs it is a symlink whose resolution
    would point at the library source instead of the installed location.
    """
    target_root = Path(target_root).resolve()
    dest = Path(dest)
    if dest.is_relative_to(target_root):
        return dest.relative_to(target_root).as_posix()
    return str(dest)


def installed_state(target_root: Path, entry: dict) -> str:
    """State of an installed skill: ``ok`` | ``modified`` | ``missing``."""
    dest = _dest_dir(target_root, entry)
    if entry.get("mode") == "link":
        if not dest.is_symlink():
            return "missing" if not dest.exists() else "modified"
        expected = Path(str(entry.get("link_target", "")))
        try:
            actual = dest.resolve(strict=True)
        except OSError:
            return "missing"
        return "ok" if expected != Path("") and actual == expected else "modified"
    if not dest.is_dir():
        return "missing"
    state = "ok"
    for record in entry.get("files", []):
        path = dest / record["path"]
        if not path.is_file():
            return "missing"
        if file_sha256(path) != record["sha256"]:
            state = "modified"
    return state


def _validated_source(
    library_root: Path, name: str, install_mode: str = "full"
) -> tuple[Path, list[dict], str]:
    skill_dir = _source_skill_dir(library_root, name)
    cat = catalog_entry(library_root, name)
    problems = validate_skill_dir(
        skill_dir,
        cat.content_policy if cat else None,
        status=cat.status if cat else None,
    )
    if problems:
        raise InstallError(
            f"skill {name!r} fails validation:\n  - " + "\n  - ".join(problems)
        )
    ensure_no_symlinks(skill_dir)
    files = snapshot(skill_dir, install_mode)
    if not files:
        raise InstallError(f"skill {name!r} contains no files")
    return skill_dir, files, aggregate_checksum(files)


def _copy_files(skill_dir: Path, dest: Path, files: list[dict]) -> None:
    for record in files:
        rel = record["path"]
        target = safe_join(dest, *Path(rel).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_dir / rel, target)


def _remove_destination(path: Path) -> None:
    """Remove a file, symlink, or directory without following symlinks."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


@contextmanager
def _rollback_destinations(*paths: Path | None):
    """Restore destination trees if a mutating operation fails."""
    unique: list[Path] = []
    for raw in paths:
        if raw is None:
            continue
        path = Path(raw)
        if path not in unique:
            unique.append(path)

    snapshots: list[tuple[Path, Path, bool]] = []
    try:
        for path in unique:
            path.parent.mkdir(parents=True, exist_ok=True)
            backup_root = Path(
                tempfile.mkdtemp(prefix=f".{path.name}.skillctl-backup-", dir=path.parent)
            )
            snapshot_path = backup_root / "snapshot"
            existed = path.exists() or path.is_symlink()
            if path.is_symlink():
                snapshot_path.symlink_to(path.readlink(), target_is_directory=True)
            elif path.is_dir():
                shutil.copytree(path, snapshot_path, symlinks=True)
            elif path.exists():
                # A plain file may legitimately sit where the skill goes;
                # copytree would raise NotADirectoryError, so snapshot it flat.
                shutil.copy2(path, snapshot_path)
            snapshots.append((backup_root, snapshot_path, existed))
        yield
    except BaseException:
        for path, (_, snapshot_path, existed) in zip(unique, snapshots):
            _remove_destination(path)
            if existed:
                if snapshot_path.is_symlink():
                    path.symlink_to(snapshot_path.readlink(), target_is_directory=True)
                else:
                    snapshot_path.replace(path)
        raise
    finally:
        for backup_root, _, _ in snapshots:
            shutil.rmtree(backup_root, ignore_errors=True)


def _delete_managed_files(dest: Path, entry: dict, *, verify: bool, force: bool) -> None:
    """Delete only the files listed in the lock entry, bottom-up prune of dirs."""
    if verify and not force:
        for record in entry.get("files", []):
            path = dest / record["path"]
            if path.is_file() and file_sha256(path) != record["sha256"]:
                raise InstallError(
                    f"installed file {record['path']!r} was modified locally; "
                    "use --force to override"
                )
    for record in entry.get("files", []):
        path = safe_join(dest, *Path(record["path"]).parts)
        if path.is_file():
            path.unlink()
    # Prune directories that became empty (deepest first).
    if dest.is_dir():
        for directory in sorted((p for p in dest.rglob("*") if p.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            dest.rmdir()
        except OSError:
            pass


def _build_entry(
    *,
    name: str,
    library_root: Path,
    agent: str,
    mode: str,
    install_mode: str,
    target_root: Path,
    dest: Path,
    files: list[dict],
    checksum: str,
    installed_at: str | None = None,
    updated_at: str | None = None,
    link_target: str | None = None,
) -> dict:
    cat = catalog_entry(library_root, name)
    entry = {
        "name": name,
        "source": str(Path(library_root).resolve()),
        "source_commit": library_commit(library_root),
        "skill_version": cat.version if cat else "0.0.0",
        "agent": agent,
        "mode": mode,
        "install_mode": install_mode,
        "target_path": _record_target_path(target_root, dest),
        "checksum": checksum,
        "installed_at": installed_at or _now_iso(),
        "updated_at": updated_at,
        "files": files,
    }
    if link_target is not None:
        entry["link_target"] = link_target
    return entry


def _entry_install_mode(entry: dict) -> str:
    # Lock entries written before install modes existed shipped every file.
    return str(entry.get("install_mode") or "full")


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

def install_skill(
    library_root: Path,
    name: str,
    target_root: Path,
    *,
    agent: str = "universal",
    link: bool = False,
    force: bool = False,
    dry_run: bool = False,
    skills_dir_override: Path | None = None,
    install_mode: str = "runtime",
) -> str:
    library_root = Path(library_root).resolve()
    target_root = Path(target_root).resolve()
    if not target_root.is_dir():
        raise InstallError(f"target project {target_root} does not exist")
    if install_mode not in INSTALL_MODES:
        raise InstallError(f"unknown install mode {install_mode!r}; allowed: {', '.join(INSTALL_MODES)}")
    if link:
        # a symlink exposes the whole source directory, candidates included
        install_mode = "full"

    skill_dir, files, checksum = _validated_source(library_root, name, install_mode)
    skills_root = resolve_skills_root(target_root, agent, skills_dir_override)
    skills_root.mkdir(parents=True, exist_ok=True)
    dest = safe_join(skills_root, name)
    mode = "link" if link else "copy"

    lock = lockfile.load_lock(target_root)
    entry = lockfile.get_entry(lock, name)

    if entry is not None:
        state = installed_state(target_root, entry)
        if (
            state == "ok"
            and entry.get("checksum") == checksum
            and entry.get("mode") == mode
            and _entry_install_mode(entry) == install_mode
            and _dest_dir(target_root, entry) == dest
        ):
            return f"{name}: already installed and up to date ({checksum[:19]}…)"
        if not force:
            if state == "modified":
                raise InstallError(
                    f"{name}: installed copy has local modifications; use --force to overwrite"
                )
            if _entry_install_mode(entry) != install_mode:
                raise InstallError(
                    f"{name}: installed in {_entry_install_mode(entry)!r} mode; re-run with "
                    f"--force to switch to {install_mode!r}"
                )
            if entry.get("checksum") != checksum:
                raise InstallError(
                    f"{name}: an older version is installed; run "
                    f"'skillctl update {name} --target {target_root}' (or --force to reinstall)"
                )
            if _dest_dir(target_root, entry) != dest or entry.get("mode") != mode:
                raise InstallError(
                    f"{name}: already installed with different agent/mode/path; "
                    "remove it first or use --force"
                )
    elif dest.exists() and not force:
        if not dest.is_dir():
            # A regular file (or foreign non-dir node) blocks the skill dir;
            # iterdir() on it would raise NotADirectoryError before the guard,
            # so --force could never recover — classify the node type first.
            raise InstallError(
                f"{name}: destination {dest} exists and is not a directory; "
                "use --force to replace it"
            )
        if any(dest.iterdir()):
            raise InstallError(
                f"{name}: destination {dest} exists but is not managed by skillctl; "
                "use --force to replace it"
            )

    if dry_run:
        action = "symlink" if link else f"copy {len(files)} file(s)"
        return f"[dry-run] {name}: would {action} to {dest} and record it in {lockfile.LOCKFILE_NAME}"

    old_dest = _dest_dir(target_root, entry) if entry is not None else None
    with _rollback_destinations(old_dest, dest):
        # Clear whatever we manage (or, with --force, whatever is in the way).
        if entry is not None:
            if entry.get("mode") == "link" and old_dest.is_symlink():
                old_dest.unlink()
            elif old_dest.is_dir():
                _delete_managed_files(old_dest, entry, verify=True, force=force)
        if dest.is_symlink():
            dest.unlink()
        elif dest.exists() and force:
            # dest may be a non-managed directory OR a plain file in the way;
            # _remove_destination handles both (rmtree would fail on a file).
            _remove_destination(dest)

        link_target: str | None = None
        if link:
            link_target = str(skill_dir.resolve())
            dest.symlink_to(skill_dir.resolve(), target_is_directory=True)
            files_record: list[dict] = []
        else:
            _copy_files(skill_dir, dest, files)
            files_record = files

        new_entry = _build_entry(
            name=name,
            library_root=library_root,
            agent=agent,
            mode=mode,
            install_mode=install_mode,
            target_root=target_root,
            dest=dest,
            files=files_record,
            checksum=checksum,
            link_target=link_target,
        )
        lockfile.upsert_entry(lock, new_entry)
        lockfile.save_lock(target_root, lock)
    detail = "symlink to the library" if link else f"{len(files)} file(s)"
    return f"{name}: installed to {dest} ({mode}, {install_mode} mode, {detail})"


def diff_skill(library_root: Path, name: str, target_root: Path) -> str:
    """Unified diff: installed copy -> current library source. '' if identical."""
    library_root = Path(library_root).resolve()
    target_root = Path(target_root).resolve()
    lock = lockfile.load_lock(target_root)
    entry = lockfile.get_entry(lock, name)
    if entry is None:
        raise InstallError(f"{name}: not installed in {target_root} (no lock entry)")
    if entry.get("mode") == "link":
        return ""  # a symlink always reflects the library source
    skill_dir = _source_skill_dir(library_root, name)
    dest = _dest_dir(target_root, entry)

    # Compare against the file set of the recorded install mode, so a runtime
    # install does not show excluded development files as "new".
    source_files = set(iter_skill_files(skill_dir, _entry_install_mode(entry)))
    installed_files = set(iter_skill_files(dest)) if dest.is_dir() else set()

    chunks: list[str] = []
    for rel in sorted(source_files | installed_files):
        src = skill_dir / rel
        inst = dest / rel
        src_bytes = src.read_bytes() if rel in source_files else None
        inst_bytes = inst.read_bytes() if rel in installed_files else None
        if src_bytes == inst_bytes:
            continue
        try:
            src_text = src_bytes.decode("utf-8") if src_bytes is not None else None
            inst_text = inst_bytes.decode("utf-8") if inst_bytes is not None else None
        except UnicodeDecodeError:
            chunks.append(f"Binary files differ: {rel}\n")
            continue
        diff = difflib.unified_diff(
            (inst_text or "").splitlines(keepends=True),
            (src_text or "").splitlines(keepends=True),
            fromfile=f"installed/{name}/{rel}",
            tofile=f"library/{name}/{rel}",
        )
        chunks.append("".join(diff))
    return "".join(chunks)


def update_skill(
    library_root: Path,
    name: str,
    target_root: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> str:
    library_root = Path(library_root).resolve()
    target_root = Path(target_root).resolve()
    lock = lockfile.load_lock(target_root)
    entry = lockfile.get_entry(lock, name)
    if entry is None:
        raise InstallError(
            f"{name}: not installed in {target_root}; use 'skillctl install' first"
        )

    install_mode = _entry_install_mode(entry)
    skill_dir, files, checksum = _validated_source(library_root, name, install_mode)
    dest = _dest_dir(target_root, entry)
    state = installed_state(target_root, entry)

    if entry.get("mode") == "link":
        if dry_run:
            return f"[dry-run] {name}: symlink install, would refresh lock metadata only"
        cat = catalog_entry(library_root, name)
        entry["checksum"] = checksum
        entry["skill_version"] = cat.version if cat else entry.get("skill_version")
        entry["source_commit"] = library_commit(library_root)
        entry["updated_at"] = _now_iso()
        lockfile.upsert_entry(lock, entry)
        lockfile.save_lock(target_root, lock)
        return f"{name}: symlink install refreshed in lock ({checksum[:19]}…)"

    if state == "modified" and not force:
        raise InstallError(
            f"{name}: installed copy has local modifications; review "
            f"'skillctl diff {name}' and re-run with --force to overwrite"
        )
    if state == "ok" and entry.get("checksum") == checksum:
        return f"{name}: already up to date ({entry.get('skill_version')})"

    if dry_run:
        return f"[dry-run] {name}: would update {dest} to library version ({len(files)} file(s))"

    with _rollback_destinations(dest):
        _delete_managed_files(dest, entry, verify=True, force=force or state == "missing")
        _copy_files(skill_dir, dest, files)

        new_entry = _build_entry(
            name=name,
            library_root=library_root,
            agent=str(entry.get("agent", "universal")),
            mode="copy",
            install_mode=install_mode,
            target_root=target_root,
            dest=dest,
            files=files,
            checksum=checksum,
            installed_at=str(entry.get("installed_at") or _now_iso()),
            updated_at=_now_iso(),
        )
        lockfile.upsert_entry(lock, new_entry)
        lockfile.save_lock(target_root, lock)
    return f"{name}: updated to version {new_entry['skill_version']} ({len(files)} file(s))"


def remove_skill(
    library_root: Path,
    name: str,
    target_root: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> str:
    target_root = Path(target_root).resolve()
    lock = lockfile.load_lock(target_root)
    entry = lockfile.get_entry(lock, name)
    if entry is None:
        raise InstallError(f"{name}: not installed in {target_root} (no lock entry)")
    dest = _dest_dir(target_root, entry)

    if entry.get("mode") == "link":
        if dry_run:
            return f"[dry-run] {name}: would remove symlink {dest} and the lock entry"
        with _rollback_destinations(dest):
            if dest.is_symlink():
                expected = str(entry.get("link_target", ""))
                if not force and expected and str(dest.resolve()) != expected:
                    raise InstallError(
                        f"{name}: symlink {dest} points to an unexpected location; use --force"
                    )
                dest.unlink()
            lockfile.remove_entry(lock, name)
            lockfile.save_lock(target_root, lock)
        return f"{name}: removed (symlink)"

    managed = len(entry.get("files", []))
    if dry_run:
        return f"[dry-run] {name}: would delete {managed} managed file(s) under {dest}"

    with _rollback_destinations(dest):
        if dest.is_dir():
            _delete_managed_files(dest, entry, verify=True, force=force)
        lockfile.remove_entry(lock, name)
        lockfile.save_lock(target_root, lock)
    leftover = ""
    if dest.is_dir() and any(dest.iterdir()):
        leftover = f"; unmanaged files were kept in {dest}"
    return f"{name}: removed {managed} managed file(s){leftover}"


def status(library_root: Path, target_root: Path) -> list[dict]:
    """Status of every installed skill: state + update availability."""
    library_root = Path(library_root).resolve()
    target_root = Path(target_root).resolve()
    lock = lockfile.load_lock(target_root)
    rows: list[dict] = []
    for entry in lock.get("skills", []):
        if not isinstance(entry, dict):
            # get_entry/upsert_entry/remove_entry already tolerate non-mapping
            # lock entries; status() must stay consistent and not raise.
            continue
        name = str(entry.get("name", "?"))
        try:
            state = installed_state(target_root, entry)
        except (InstallError, SecurityError) as exc:
            rows.append({"name": name, "state": f"error: {exc}", "update": "?", "entry": entry})
            continue
        update = "none"
        skill_dir = Path(library_root) / SKILLS_DIRNAME / name
        if not skill_dir.is_dir():
            update = "missing in library"
        else:
            current = aggregate_checksum(snapshot(skill_dir, _entry_install_mode(entry)))
            if current != entry.get("checksum"):
                cat = catalog_entry(library_root, name)
                new_version = cat.version if cat else "?"
                update = f"available ({entry.get('skill_version')} -> {new_version})"
        rows.append({"name": name, "state": state, "update": update, "entry": entry})
    return rows
