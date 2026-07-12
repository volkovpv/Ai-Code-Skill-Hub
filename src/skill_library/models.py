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
        return cls(
            name=str(data.get("name", "")),
            path=str(data.get("path", "")),
            version=str(data.get("version", "0.0.0")),
            status=str(data.get("status", "draft")),
            summary=str(data.get("summary", "")),
            platforms=list(data.get("platforms") or []),
            license=str(data.get("license", "")),
            capabilities=dict(data.get("capabilities") or {}),
            content_policy=dict(data.get("content_policy") or {}),
        )
