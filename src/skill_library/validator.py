"""Structure, metadata, provenance, content-policy and link validation.

Layer model of a skill (everything beyond SKILL.md + ORIGIN.yaml is optional):

    skills/<name>/
    ├── SKILL.md  ORIGIN.yaml            # required
    ├── agents/  references/  scripts/  assets/   # tools & resources
    ├── knowledge/   (INDEX.md required when non-empty)
    ├── data/        (README.md required when non-empty)
    └── observations/ (INDEX.md required when non-empty; see observations.py)

Content policy is fail-closed: an oversized file or a string that *looks*
like a secret blocks validation until a human reviews it. The secret scan is
a heuristic, not a guarantee — it errs on the side of blocking.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import yamlio
from .discovery import (
    ORIGIN_FILENAME,
    SKILL_FILENAME,
    SKILLS_DIRNAME,
    DiscoveryError,
    discover_skills,
    load_catalog,
    split_frontmatter,
)
from .observations import OBS_DIRNAME, collect_observation_problems
from .security import SecurityError, validate_skill_name

__all__ = [
    "MAX_DESCRIPTION_LENGTH",
    "DEFAULT_CONTENT_POLICY",
    "HARD_MAX_FILE_BYTES",
    "KNOWN_SKILL_DIRS",
    "LAYER_DIRS",
    "resolve_content_policy",
    "layer_has_content",
    "validate_data_layer",
    "validate_skill_dir",
    "validate_library",
]

MAX_DESCRIPTION_LENGTH = 1024
HARD_MAX_FILE_BYTES = 5 * 1024 * 1024  # absolute ceiling a policy may not exceed

DEFAULT_CONTENT_POLICY: dict = {
    "max_tracked_file_bytes": 256 * 1024,
    "pii_allowed": False,
    "secrets_allowed": False,
    "observation_review_required": True,
}

_ORIGIN_TYPES = {"original", "vendored"}

KNOWLEDGE_DIRNAME = "knowledge"
DATA_DIRNAME = "data"
LAYER_DIRS = (KNOWLEDGE_DIRNAME, DATA_DIRNAME, OBS_DIRNAME)
KNOWN_SKILL_DIRS = {"agents", "references", "scripts", "assets", *LAYER_DIRS}

# Auxiliary documents are forbidden inside a skill (the root README.md covers
# the library). The single exception is data/README.md — the dataset contract.
_FORBIDDEN_DOC_NAMES = {"readme.md", "changelog.md", "installation_guide.md", "contributing.md"}

# Markdown links: [text](target) — external URLs and pure anchors are skipped.
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# Inline-code references to bundled resources.
_CODE_PATH_RE = re.compile(
    r"`((?:references|scripts|assets|agents|knowledge|data|observations)/[A-Za-z0-9._/-]+)`"
)

_TOC_RE = re.compile(r"^#{1,3}\s+(contents|table of contents|оглавление|содержание)\s*$",
                     re.IGNORECASE | re.MULTILINE)

_PLACEHOLDER_RE = re.compile(r"\b(?:TODO|TBD|FIXME)\b", re.IGNORECASE)

# Heuristic secret scan. A match fail-closed blocks validation until reviewed.
_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"), "GitHub fine-grained token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "API secret key"),
    (
        re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"\s]{16,}['\"]"),
        "hardcoded credential",
    ),
]


def _read_text(path: Path, label: str, problems: list[str]) -> str | None:
    """Read a UTF-8 text file, recording a fail-closed problem on bad encoding.

    A binary or mis-encoded file must not crash the validator with a bare
    ``UnicodeDecodeError`` — it becomes a reported problem instead so
    ``skillctl validate`` stays fail-closed with a proper exit code.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"{label}: is not valid UTF-8 ({exc})")
        return None


def resolve_content_policy(policy: dict | None) -> dict:
    resolved = dict(DEFAULT_CONTENT_POLICY)
    if isinstance(policy, dict):
        resolved.update(policy)
    return resolved


def layer_has_content(directory: Path) -> bool:
    """A layer counts as present when it holds any file besides .gitkeep."""
    if not directory.is_dir():
        return False
    return any(p.is_file() and p.name != ".gitkeep" for p in directory.rglob("*"))


def _local_link_targets(body: str) -> list[str]:
    targets: set[str] = set()
    for match in _MD_LINK_RE.finditer(body):
        target = match.group(1)
        if "://" in target or target.startswith(("mailto:", "#")):
            continue
        targets.add(target.split("#", 1)[0])
    for match in _CODE_PATH_RE.finditer(body):
        targets.add(match.group(1))
    return sorted(t for t in targets if t)


def _check_local_links(
    body: str, base_dir: Path, skill_dir: Path, label: str, problems: list[str]
) -> None:
    """Every relative link must resolve to an existing file inside the skill."""
    skill_root = skill_dir.resolve()
    for target in _local_link_targets(body):
        joined = Path(os.path.normpath(base_dir.resolve() / target))
        if joined != skill_root and not joined.is_relative_to(skill_root):
            problems.append(f"{label} links outside the skill directory: {target}")
            continue
        if not joined.exists():
            problems.append(f"{label} links to a missing local resource: {target}")


def _check_origin(skill_dir: Path, problems: list[str]) -> None:
    origin_path = skill_dir / ORIGIN_FILENAME
    if not origin_path.is_file():
        problems.append(f"missing {ORIGIN_FILENAME}")
        return
    try:
        origin = yamlio.load_file(origin_path)
    except yamlio.YamlError as exc:
        problems.append(f"{ORIGIN_FILENAME}: {exc}")
        return
    if not isinstance(origin, dict):
        problems.append(f"{ORIGIN_FILENAME}: top level must be a mapping")
        return
    origin_type = origin.get("type")
    if origin_type not in _ORIGIN_TYPES:
        problems.append(
            f"{ORIGIN_FILENAME}: 'type' must be one of {sorted(_ORIGIN_TYPES)}, got {origin_type!r}"
        )
        return
    if origin_type == "vendored":
        for required in ("source", "license", "imported_at"):
            if not origin.get(required):
                problems.append(f"{ORIGIN_FILENAME}: vendored skill must set '{required}'")


def _check_content_policy(skill_dir: Path, policy: dict, problems: list[str]) -> None:
    """File sizes and the heuristic secret scan (both fail-closed)."""
    try:
        max_bytes = int(policy.get("max_tracked_file_bytes") or 0)
    except (TypeError, ValueError):
        # A non-numeric policy value (e.g. ``max_tracked_file_bytes: abc``) must
        # not crash the validator with a bare ValueError — treat it as invalid so
        # the range check below reports a problem and falls back to the default.
        max_bytes = -1
    if max_bytes <= 0 or max_bytes > HARD_MAX_FILE_BYTES:
        problems.append(
            f"content_policy: max_tracked_file_bytes must be within 1..{HARD_MAX_FILE_BYTES}"
        )
        max_bytes = DEFAULT_CONTENT_POLICY["max_tracked_file_bytes"]
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir).as_posix()
        size = path.stat().st_size
        if size > max_bytes:
            problems.append(
                f"{rel}: {size} bytes exceeds max_tracked_file_bytes={max_bytes}; "
                "regenerate via script, move to external versioned storage / Git LFS, "
                "or raise the skill's content_policy deliberately"
            )
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue  # binary: size policy still applies; scan is text-only (heuristic)
        for pattern, kind in _SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(
                    f"{rel}: possible {kind} detected; secrets are forbidden — "
                    "remove it or replace with an obviously fake test marker"
                )


def _check_layout(skill_dir: Path, problems: list[str]) -> None:
    """Known directory names, forbidden documents, unexpected executables."""
    for entry in sorted(skill_dir.iterdir()):
        if entry.is_dir() and entry.name not in KNOWN_SKILL_DIRS:
            problems.append(
                f"unknown directory '{entry.name}/'; allowed: {', '.join(sorted(KNOWN_SKILL_DIRS))}"
            )
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        rel_posix = rel.as_posix()
        if rel.name.lower() in _FORBIDDEN_DOC_NAMES and rel_posix != "data/README.md":
            problems.append(
                f"{rel_posix}: auxiliary documents are not allowed inside a skill "
                "(the only exception is data/README.md — the dataset contract)"
            )
        outside_scripts = rel.parts[0] != "scripts"
        if outside_scripts and rel.suffix in (".sh", ".bash", ".exe", ".bat", ".cmd"):
            problems.append(f"{rel_posix}: executable files belong in scripts/ only")
        elif outside_scripts and os.access(path, os.X_OK) and rel.name != ".gitkeep":
            problems.append(f"{rel_posix}: unexpected executable bit outside scripts/")


def _check_knowledge_layer(skill_dir: Path, problems: list[str]) -> None:
    knowledge = skill_dir / KNOWLEDGE_DIRNAME
    if not layer_has_content(knowledge):
        return
    index = knowledge / "INDEX.md"
    if not index.is_file():
        problems.append(f"{KNOWLEDGE_DIRNAME}/ has content but no {KNOWLEDGE_DIRNAME}/INDEX.md")
        return
    index_text = _read_text(index, f"{KNOWLEDGE_DIRNAME}/INDEX.md", problems)
    if index_text is None:
        return
    _check_local_links(
        index_text, knowledge, skill_dir, f"{KNOWLEDGE_DIRNAME}/INDEX.md", problems,
    )
    for path in sorted(knowledge.rglob("*.md")):
        text = _read_text(path, path.relative_to(skill_dir).as_posix(), problems)
        if text is None:
            continue
        if len(text.splitlines()) > 100 and not _TOC_RE.search(text):
            problems.append(
                f"{path.relative_to(skill_dir).as_posix()}: files longer than 100 lines "
                "must start with a short table of contents ('## Contents' / '## Оглавление')"
            )


def validate_data_layer(
    skill_dir: Path, policy: dict | None = None, *, scan_policy: bool = True
) -> list[str]:
    """Checks specific to ``data/``; also used by ``skillctl data validate``.

    ``scan_policy=False`` skips the size/secret scan — used when the caller
    already scans the whole skill directory.
    """
    skill_dir = Path(skill_dir)
    problems: list[str] = []
    data_dir = skill_dir / DATA_DIRNAME
    if not layer_has_content(data_dir):
        return problems
    readme = data_dir / "README.md"
    if not readme.is_file():
        problems.append(
            f"{DATA_DIRNAME}/ has content but no {DATA_DIRNAME}/README.md (the dataset "
            "contract: purpose, source, license, format, PII statement, update procedure)"
        )
    elif (readme_text := _read_text(readme, f"{DATA_DIRNAME}/README.md", problems)) is not None \
            and not readme_text.strip():
        problems.append(f"{DATA_DIRNAME}/README.md is empty")
    if scan_policy:
        resolved = resolve_content_policy(policy)
        scoped: list[str] = []
        _check_content_policy(data_dir, resolved, scoped)
        problems.extend(
            p if p.startswith("content_policy") else f"{DATA_DIRNAME}/{p}" for p in scoped
        )
    return problems


def _check_observations_layer(skill_dir: Path, problems: list[str]) -> None:
    obs_dir = skill_dir / OBS_DIRNAME
    if not layer_has_content(obs_dir):
        return
    if not (obs_dir / "INDEX.md").is_file():
        problems.append(f"{OBS_DIRNAME}/ has content but no {OBS_DIRNAME}/INDEX.md")
    problems.extend(collect_observation_problems(skill_dir))


def validate_skill_dir(
    skill_dir: Path, policy: dict | None = None, *, status: str | None = None
) -> list[str]:
    """Validate one skill directory. Returns a list of problems (empty = OK)."""
    skill_dir = Path(skill_dir)
    problems: list[str] = []

    if not skill_dir.is_dir():
        return [f"{skill_dir} is not a directory"]

    try:
        validate_skill_name(skill_dir.name)
    except SecurityError as exc:
        problems.append(str(exc))

    if skill_dir.is_symlink():
        problems.append("skill directory must not be a symlink")
    for path in sorted(skill_dir.rglob("*")):
        if path.is_symlink():
            problems.append(f"symlink is not allowed: {path.relative_to(skill_dir)}")

    skill_md = skill_dir / SKILL_FILENAME
    if not skill_md.is_file():
        problems.append(f"missing {SKILL_FILENAME}")
        return problems

    skill_md_text = _read_text(skill_md, SKILL_FILENAME, problems)
    if skill_md_text is None:
        return problems
    try:
        fm, body = split_frontmatter(skill_md_text)
    except DiscoveryError as exc:
        problems.append(f"{SKILL_FILENAME}: {exc}")
        return problems

    name = fm.get("name")
    description = fm.get("description")
    if not isinstance(name, str) or not name.strip():
        problems.append("frontmatter: 'name' is missing or empty")
    else:
        try:
            validate_skill_name(name)
        except SecurityError as exc:
            problems.append(f"frontmatter: {exc}")
        if name != skill_dir.name:
            problems.append(
                f"frontmatter 'name' ({name!r}) does not match directory name ({skill_dir.name!r})"
            )
    if not isinstance(description, str) or not description.strip():
        problems.append("frontmatter: 'description' is missing or empty")
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        problems.append(
            f"frontmatter: 'description' is longer than {MAX_DESCRIPTION_LENGTH} characters"
        )

    if not body.strip():
        problems.append(f"{SKILL_FILENAME} body is empty")
    if status == "stable" and _PLACEHOLDER_RE.search(skill_md_text):
        problems.append(
            f"{SKILL_FILENAME}: stable skill must not contain TODO/TBD/FIXME placeholders"
        )

    _check_origin(skill_dir, problems)
    _check_layout(skill_dir, problems)
    _check_local_links(body, skill_dir, skill_dir, SKILL_FILENAME, problems)
    _check_knowledge_layer(skill_dir, problems)
    problems.extend(validate_data_layer(skill_dir, policy, scan_policy=False))
    _check_observations_layer(skill_dir, problems)

    resolved = resolve_content_policy(policy)
    if resolved.get("pii_allowed") or resolved.get("secrets_allowed"):
        problems.append(
            "content_policy: pii_allowed/secrets_allowed must stay false — this library "
            "never publishes PII or secrets"
        )
    if not resolved.get("observation_review_required", True):
        problems.append("content_policy: observation_review_required must stay true")
    _check_content_policy(skill_dir, resolved, problems)

    return problems


def _check_capabilities(entry, skill_dir: Path, problems: list[str]) -> None:
    caps = getattr(entry, "capabilities", None)
    if not isinstance(caps, dict) or not caps:
        return  # capabilities are optional; skills without the block stay valid
    for layer in LAYER_DIRS:
        declared = bool(caps.get(layer, False))
        actual = layer_has_content(skill_dir / layer)
        if declared and not actual:
            problems.append(
                f"skills.yaml: {entry.name}: capability '{layer}: true' but "
                f"{layer}/ is missing or empty"
            )
        elif actual and not declared:
            problems.append(
                f"skills.yaml: {entry.name}: {layer}/ has content but the capability "
                f"flag is not declared as '{layer}: true'"
            )


def validate_library(library_root: Path) -> list[str]:
    """Validate the whole library: every skill, duplicates, catalog consistency."""
    library_root = Path(library_root)
    problems: list[str] = []

    skills, discovery_problems = discover_skills(library_root)
    problems.extend(discovery_problems)

    try:
        catalog = load_catalog(library_root)
    except DiscoveryError as exc:
        problems.append(str(exc))
        catalog = []
    catalog_by_name = {entry.name: entry for entry in catalog}

    skills_dir = library_root / SKILLS_DIRNAME
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            cat = catalog_by_name.get(entry.name)
            policy = cat.content_policy if cat else None
            for problem in validate_skill_dir(
                entry, policy, status=cat.status if cat else None
            ):
                problems.append(f"{entry.name}: {problem}")

    seen: dict[str, str] = {}
    for skill in skills:
        if skill.name in seen:
            problems.append(
                f"duplicate skill name {skill.name!r} in directories "
                f"{seen[skill.name]!r} and {skill.dir_name!r}"
            )
        else:
            seen[skill.name] = skill.dir_name

    catalog_names = set()
    for entry in catalog:
        if not entry.name:
            problems.append("skills.yaml: entry without 'name'")
            continue
        if entry.name in catalog_names:
            problems.append(f"skills.yaml: duplicate entry {entry.name!r}")
        catalog_names.add(entry.name)
        expected_path = f"{SKILLS_DIRNAME}/{entry.name}"
        if entry.path != expected_path:
            problems.append(
                f"skills.yaml: entry {entry.name!r} has path {entry.path!r}, expected {expected_path!r}"
            )
        if entry.name not in seen:
            problems.append(f"skills.yaml: entry {entry.name!r} has no directory in {SKILLS_DIRNAME}/")
        else:
            _check_capabilities(entry, skills_dir / entry.name, problems)
        if not entry.version or entry.version == "0.0.0":
            problems.append(f"skills.yaml: entry {entry.name!r} must declare a version")

    for name in sorted(seen):
        if name not in catalog_names:
            problems.append(f"skills.yaml: skill {name!r} is not listed in the catalog")

    return problems
