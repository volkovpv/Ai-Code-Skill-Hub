"""Discovery of skills in the canonical ``skills/`` directory."""

from __future__ import annotations

from pathlib import Path

from . import yamlio
from .models import CatalogEntry, SkillMeta

__all__ = [
    "DiscoveryError",
    "SKILLS_DIRNAME",
    "CATALOG_FILENAME",
    "SKILL_FILENAME",
    "ORIGIN_FILENAME",
    "split_frontmatter",
    "load_skill",
    "discover_skills",
    "load_catalog",
    "catalog_entry",
]

SKILLS_DIRNAME = "skills"
CATALOG_FILENAME = "skills.yaml"
SKILL_FILENAME = "SKILL.md"
ORIGIN_FILENAME = "ORIGIN.yaml"


class DiscoveryError(Exception):
    """Raised when a skill or the catalog cannot be read."""


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown document (SKILL.md, observation) into (frontmatter, body)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DiscoveryError("document must start with a '---' YAML frontmatter block")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise DiscoveryError("frontmatter is not terminated by '---'") from None
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        fm = yamlio.loads(fm_text)
    except yamlio.YamlError as exc:
        raise DiscoveryError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise DiscoveryError("frontmatter must be a YAML mapping")
    return fm, body


def load_skill(skill_dir: Path) -> SkillMeta:
    """Load one skill directory; raises DiscoveryError on malformed input."""
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / SKILL_FILENAME
    if not skill_md.is_file():
        raise DiscoveryError(f"{skill_dir.name}: missing {SKILL_FILENAME}")
    try:
        fm, _ = split_frontmatter(skill_md.read_text(encoding="utf-8"))
    except DiscoveryError as exc:
        raise DiscoveryError(f"{skill_dir.name}: {SKILL_FILENAME}: {exc}") from exc
    name = fm.get("name")
    description = fm.get("description")
    if not isinstance(name, str) or not name.strip():
        raise DiscoveryError(f"{skill_dir.name}: frontmatter field 'name' is missing or empty")
    if not isinstance(description, str) or not description.strip():
        raise DiscoveryError(
            f"{skill_dir.name}: frontmatter field 'description' is missing or empty"
        )
    return SkillMeta(name=name, description=description, path=skill_dir, frontmatter=fm)


def discover_skills(library_root: Path) -> tuple[list[SkillMeta], list[str]]:
    """Scan ``<library_root>/skills``.

    Returns (skills, problems): parseable skills sorted by directory name and
    human-readable messages for the ones that could not be loaded.
    """
    skills_dir = Path(library_root) / SKILLS_DIRNAME
    skills: list[SkillMeta] = []
    problems: list[str] = []
    if not skills_dir.is_dir():
        return skills, [f"missing '{SKILLS_DIRNAME}/' directory in {library_root}"]
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        try:
            skills.append(load_skill(entry))
        except DiscoveryError as exc:
            problems.append(str(exc))
    return skills, problems


def load_catalog(library_root: Path) -> list[CatalogEntry]:
    """Load ``skills.yaml``; returns an empty list when the file is absent."""
    catalog_path = Path(library_root) / CATALOG_FILENAME
    if not catalog_path.is_file():
        return []
    try:
        data = yamlio.load_file(catalog_path)
    except yamlio.YamlError as exc:
        raise DiscoveryError(f"{CATALOG_FILENAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise DiscoveryError(f"{CATALOG_FILENAME}: top level must be a mapping")
    entries = data.get("skills") or []
    if not isinstance(entries, list):
        raise DiscoveryError(f"{CATALOG_FILENAME}: 'skills' must be a list")
    result = []
    for item in entries:
        if not isinstance(item, dict):
            raise DiscoveryError(f"{CATALOG_FILENAME}: every skill entry must be a mapping")
        result.append(CatalogEntry.from_dict(item))
    return result


def catalog_entry(library_root: Path, name: str) -> CatalogEntry | None:
    for entry in load_catalog(library_root):
        if entry.name == name:
            return entry
    return None
