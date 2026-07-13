"""Typed views over the library data files (frontmatter, catalog, lock)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["SkillMeta", "CatalogEntry"]


@dataclass
class SkillMeta:
    """A skill discovered in ``skills/``: parsed SKILL.md frontmatter."""

    name: str
    description: str
    path: Path
    frontmatter: dict = field(default_factory=dict)

    @property
    def dir_name(self) -> str:
        return self.path.name


@dataclass
class CatalogEntry:
    """One entry of the root ``skills.yaml`` catalog."""

    name: str
    path: str
    version: str = "0.0.0"
    status: str = "draft"
    summary: str = ""
    platforms: list = field(default_factory=list)
    license: str = ""
    # Optional layer flags: {"knowledge": bool, "data": bool, "observations": bool}.
    capabilities: dict = field(default_factory=dict)
    # Optional per-skill content policy; merged over validator defaults.
    content_policy: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "CatalogEntry":
        name = str(data.get("name", ""))
        return cls(
            name=name,
            path=str(data.get("path", "")),
            version=str(data.get("version", "0.0.0")),
            status=str(data.get("status", "draft")),
            summary=str(data.get("summary", "")),
            platforms=_typed_list(data.get("platforms"), "platforms", name),
            license=str(data.get("license", "")),
            capabilities=_typed_mapping(data.get("capabilities"), "capabilities", name),
            content_policy=_typed_mapping(data.get("content_policy"), "content_policy", name),
        )


def _typed_list(value: object, field_name: str, skill_name: str) -> list:
    """A catalog list field: absent -> []; a wrong type is a hard error.

    Coercing e.g. ``platforms: linux`` with ``list("linux")`` would silently
    yield ``['l','i','n','u','x']`` — so reject non-lists instead of guessing.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"skill {skill_name!r}: '{field_name}' must be a list, "
            f"got {type(value).__name__}"
        )
    return list(value)


def _typed_mapping(value: object, field_name: str, skill_name: str) -> dict:
    """A catalog mapping field: absent -> {}; a wrong type is a hard error.

    ``dict(['knowledge', 'data'])`` raises an opaque ``ValueError``; turn it
    into a clear, attributable message the validator can report fail-closed.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(
            f"skill {skill_name!r}: '{field_name}' must be a mapping, "
            f"got {type(value).__name__}"
        )
    return dict(value)
