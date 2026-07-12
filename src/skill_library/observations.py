"""Observation lifecycle: candidate -> review -> accepted/rejected.

Observations live inside a skill under ``observations/``::

    observations/
    ├── INDEX.md          # human routing: what is recorded and when to read it
    ├── candidates/       # unreviewed observations (never installed in runtime mode)
    ├── accepted/         # reviewed, evidence-backed observations
    └── rejected/         # kept for audit; never installed in runtime mode

Every observation is a markdown file ``<id>.md`` with YAML frontmatter::

    ---
    id: OBS-20260712-001
    status: accepted            # candidate | accepted | rejected
    observed_at: 2026-07-12
    scope: example-skill/all-platforms
    evidence:
      - data/fixtures/mixed_change.diff
    reviewed_by: volkovpv       # required for accepted/rejected
    reviewed_at: 2026-07-12
    ---
    ...free-form body...

Invariants (enforced here and by the validator):

* ``add`` only ever creates candidates — nothing lands in ``accepted/`` directly;
* promotion requires an explicit ``approve`` with a reviewer name and
  non-empty evidence; rejection likewise records the reviewer;
* the file name always equals ``<id>.md`` and the status always matches the
  directory the file lives in.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import yamlio
from .discovery import DiscoveryError, split_frontmatter

__all__ = [
    "ObservationError",
    "OBS_DIRNAME",
    "STATUSES",
    "STATUS_DIR",
    "OBS_ID_RE",
    "list_observations",
    "collect_observation_problems",
    "add_observation",
    "review_observation",
]

OBS_DIRNAME = "observations"
STATUSES = ("candidate", "accepted", "rejected")
STATUS_DIR = {"candidate": "candidates", "accepted": "accepted", "rejected": "rejected"}
DIR_STATUS = {v: k for k, v in STATUS_DIR.items()}
OBS_ID_RE = re.compile(r"^OBS-\d{8}-\d{3}$")

_ACCEPTED_REQUIRED = ("reviewed_by", "reviewed_at")


class ObservationError(Exception):
    """Raised when an observation operation cannot proceed."""


def _serialize(meta: dict, body: str) -> str:
    return "---\n" + yamlio.dumps(meta) + "---\n\n" + body.strip() + "\n"


def _parse_file(path: Path) -> tuple[dict, str]:
    try:
        return split_frontmatter(path.read_text(encoding="utf-8"))
    except DiscoveryError as exc:
        raise ObservationError(f"{path.name}: {exc}") from exc


def list_observations(skill_dir: Path, status: str | None = None) -> list[dict]:
    """Return records: {id, status, dir_status, path, meta, body}, sorted by id."""
    if status is not None and status not in STATUSES:
        raise ObservationError(f"unknown status {status!r}; allowed: {', '.join(STATUSES)}")
    obs_root = Path(skill_dir) / OBS_DIRNAME
    records: list[dict] = []
    for dirname, dir_status in sorted(DIR_STATUS.items()):
        directory = obs_root / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            meta, body = _parse_file(path)
            records.append(
                {
                    "id": str(meta.get("id", path.stem)),
                    "status": meta.get("status"),
                    "dir_status": dir_status,
                    "path": path,
                    "meta": meta,
                    "body": body,
                }
            )
    if status is not None:
        records = [r for r in records if r["status"] == status]
    return sorted(records, key=lambda r: r["id"])


def collect_observation_problems(skill_dir: Path) -> list[str]:
    """Validation problems of the observations layer (empty list = OK)."""
    problems: list[str] = []
    obs_root = Path(skill_dir) / OBS_DIRNAME
    if not obs_root.is_dir():
        return problems
    for entry in sorted(obs_root.iterdir()):
        if entry.is_dir() and entry.name not in DIR_STATUS:
            problems.append(f"observations/{entry.name}: unknown directory (allowed: "
                            f"{', '.join(sorted(DIR_STATUS))})")
    seen_ids: dict[str, str] = {}
    for dirname, dir_status in sorted(DIR_STATUS.items()):
        directory = obs_root / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.name == ".gitkeep" or path.is_dir():
                continue
            rel = f"observations/{dirname}/{path.name}"
            if path.suffix != ".md":
                problems.append(f"{rel}: only .md observation files are allowed")
                continue
            try:
                meta, _ = _parse_file(path)
            except ObservationError as exc:
                problems.append(f"{rel}: {exc}")
                continue
            obs_id = meta.get("id")
            if not isinstance(obs_id, str) or not OBS_ID_RE.match(obs_id):
                problems.append(f"{rel}: 'id' must match OBS-YYYYMMDD-NNN")
                continue
            if path.stem != obs_id:
                problems.append(f"{rel}: file name must be '{obs_id}.md'")
            if obs_id in seen_ids:
                problems.append(f"{rel}: duplicate observation id {obs_id} "
                                f"(also in {seen_ids[obs_id]})")
            seen_ids[obs_id] = rel
            status = meta.get("status")
            if status not in STATUSES:
                problems.append(f"{rel}: 'status' must be one of {', '.join(STATUSES)}")
            elif status != dir_status:
                problems.append(
                    f"{rel}: status {status!r} does not match directory "
                    f"'{dirname}/' (expected {dir_status!r})"
                )
            if not meta.get("observed_at"):
                problems.append(f"{rel}: 'observed_at' is required")
            if not meta.get("scope"):
                problems.append(f"{rel}: 'scope' is required")
            if status in ("accepted", "rejected"):
                for field in _ACCEPTED_REQUIRED:
                    if not meta.get(field):
                        problems.append(f"{rel}: reviewed observation must set '{field}'")
            if status == "accepted":
                evidence = meta.get("evidence")
                if not isinstance(evidence, list) or not evidence:
                    problems.append(f"{rel}: accepted observation must list non-empty 'evidence'")
    return problems


def _next_id(skill_dir: Path, today: date) -> str:
    prefix = f"OBS-{today.strftime('%Y%m%d')}-"
    taken = set()
    for record in list_observations(skill_dir):
        rid = record["id"]
        if rid.startswith(prefix):
            try:
                taken.add(int(rid[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{(max(taken) + 1 if taken else 1):03d}"


def add_observation(
    skill_dir: Path,
    source_file: Path,
    *,
    scope: str | None = None,
    evidence: list[str] | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> tuple[str, Path]:
    """Create a *candidate* observation from a markdown file.

    This is the only creation path; accepted/ is reachable exclusively via
    :func:`review_observation`.
    """
    skill_dir = Path(skill_dir)
    source_file = Path(source_file)
    if not source_file.is_file():
        raise ObservationError(f"source file {source_file} does not exist")
    text = source_file.read_text(encoding="utf-8")

    meta_in: dict = {}
    body = text
    if text.lstrip().startswith("---"):
        try:
            meta_in, body = split_frontmatter(text.lstrip())
        except DiscoveryError as exc:
            raise ObservationError(f"{source_file.name}: {exc}") from exc
    if not body.strip():
        raise ObservationError("observation body must not be empty")

    today = today or date.today()
    obs_id = _next_id(skill_dir, today)
    meta = {
        "id": obs_id,
        "status": "candidate",  # always; promotion requires explicit review
        "observed_at": str(meta_in.get("observed_at") or today.isoformat()),
        "scope": scope or str(meta_in.get("scope") or skill_dir.name),
        "evidence": list(evidence) if evidence else list(meta_in.get("evidence") or []),
        "reviewed_by": None,
        "reviewed_at": None,
    }
    dest = skill_dir / OBS_DIRNAME / STATUS_DIR["candidate"] / f"{obs_id}.md"
    if dry_run:
        return obs_id, dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_serialize(meta, body), encoding="utf-8")
    return obs_id, dest


def _find(skill_dir: Path, obs_id: str) -> dict:
    for record in list_observations(skill_dir):
        if record["id"] == obs_id:
            return record
    raise ObservationError(f"observation {obs_id} not found in {skill_dir.name}")


def review_observation(
    skill_dir: Path,
    obs_id: str,
    decision: str,
    *,
    reviewed_by: str,
    note: str | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> Path:
    """Approve or reject a candidate observation, keeping audit metadata."""
    if decision not in ("accepted", "rejected"):
        raise ObservationError(f"decision must be 'accepted' or 'rejected', got {decision!r}")
    if not reviewed_by or not reviewed_by.strip():
        raise ObservationError("a non-empty reviewer name is required (--reviewed-by)")
    skill_dir = Path(skill_dir)
    record = _find(skill_dir, obs_id)
    if record["status"] != "candidate":
        raise ObservationError(
            f"{obs_id} has status {record['status']!r}; only candidates can be reviewed"
        )
    meta = dict(record["meta"])
    if decision == "accepted":
        evidence = meta.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ObservationError(
                f"{obs_id}: cannot approve without evidence; edit the candidate file "
                "and add at least one evidence entry first"
            )
    today = today or date.today()
    meta["status"] = decision
    meta["reviewed_by"] = reviewed_by.strip()
    meta["reviewed_at"] = today.isoformat()
    if note:
        meta["review_note"] = note

    dest = skill_dir / OBS_DIRNAME / STATUS_DIR[decision] / f"{obs_id}.md"
    if dry_run:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_serialize(meta, record["body"]), encoding="utf-8")
    Path(record["path"]).unlink()
    return dest
