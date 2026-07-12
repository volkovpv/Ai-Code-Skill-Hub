"""Shared helpers for the test suite: temp libraries and temp target projects."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "__test__" / "fixtures"

SKILL_MD_TEMPLATE = """---
name: {name}
description: {description}
---

# {name}

## Workflow

1. Do the thing described in [references/notes.md](references/notes.md).
"""

ORIGIN_TEMPLATE = """type: original
source: null
source_commit: null
license: MIT
imported_at: null
update_policy: manual
changes: []
"""


class TempDirTestCase(unittest.TestCase):
    """Base class providing an auto-cleaned temporary directory."""

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory(prefix="skill-lib-test-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()

    def make_dir(self, name: str) -> Path:
        path = self.tmp / name
        path.mkdir(parents=True, exist_ok=True)
        return path


def write_skill(
    skills_dir: Path,
    name: str,
    *,
    frontmatter_name: str | None = None,
    description: str = "A synthetic skill used by the test suite.",
    body_extra: str = "",
) -> Path:
    """Create a minimal valid skill (unless overridden) and return its path."""
    skill_dir = skills_dir / name
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_MD_TEMPLATE.format(
        name=frontmatter_name or name, description=description
    )
    (skill_dir / "SKILL.md").write_text(skill_md + body_extra, encoding="utf-8")
    (skill_dir / "ORIGIN.yaml").write_text(ORIGIN_TEMPLATE, encoding="utf-8")
    (skill_dir / "references" / "notes.md").write_text("# notes\n", encoding="utf-8")
    return skill_dir


KNOWLEDGE_INDEX = """# Knowledge index

| File | Read when |
|------|-----------|
| [patterns.md](patterns.md) | applying the skill |
"""

DATA_README = """# Data contract

- Purpose: synthetic test data. Source: hand-written. License: MIT.
- Format: plain text. PII/secrets: none. Update: edit and re-validate.
"""

OBS_INDEX = """# Observations

Candidate -> review -> accepted/rejected. Candidates are not installed in
runtime mode.
"""

ACCEPTED_OBS = """---
id: OBS-20260101-001
status: accepted
observed_at: 2026-01-01
scope: {name}
evidence:
  - data/fixtures/sample.txt
reviewed_by: test-reviewer
reviewed_at: 2026-01-02
---

# Accepted synthetic observation

Reproducible via data/fixtures/sample.txt.
"""

CANDIDATE_OBS = """---
id: OBS-20260101-002
status: candidate
observed_at: 2026-01-01
scope: {name}
evidence: []
reviewed_by: null
reviewed_at: null
---

# Candidate synthetic observation

Awaiting evidence and review.
"""


def add_layers(skill_dir: Path, name: str | None = None) -> None:
    """Attach knowledge/data/observations layers to an existing skill."""
    name = name or skill_dir.name
    knowledge = skill_dir / "knowledge"
    knowledge.mkdir(exist_ok=True)
    (knowledge / "INDEX.md").write_text(KNOWLEDGE_INDEX, encoding="utf-8")
    (knowledge / "patterns.md").write_text("# Patterns\n\nA verified pattern.\n", encoding="utf-8")

    data = skill_dir / "data"
    (data / "fixtures").mkdir(parents=True, exist_ok=True)
    (data / "examples").mkdir(parents=True, exist_ok=True)
    (data / "README.md").write_text(DATA_README, encoding="utf-8")
    (data / "fixtures" / "sample.txt").write_text("fixture input\n", encoding="utf-8")
    (data / "examples" / "sample.txt").write_text("example input\n", encoding="utf-8")

    obs = skill_dir / "observations"
    (obs / "accepted").mkdir(parents=True, exist_ok=True)
    (obs / "candidates").mkdir(parents=True, exist_ok=True)
    (obs / "INDEX.md").write_text(OBS_INDEX, encoding="utf-8")
    (obs / "accepted" / "OBS-20260101-001.md").write_text(
        ACCEPTED_OBS.format(name=name), encoding="utf-8"
    )
    (obs / "candidates" / "OBS-20260101-002.md").write_text(
        CANDIDATE_OBS.format(name=name), encoding="utf-8"
    )


CAPABILITIES_YAML = """    capabilities:
      knowledge: true
      data: true
      observations: true
    content_policy:
      max_tracked_file_bytes: 262144
      pii_allowed: false
      secrets_allowed: false
      observation_review_required: true
"""


def make_library(base: Path, names: tuple[str, ...] = ("alpha-skill",), version: str = "0.1.0") -> Path:
    """Create a temporary library root with a skills/ dir and a catalog."""
    library = base / "library"
    skills_dir = library / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for name in names:
        write_skill(skills_dir, name)
        entries.append(
            f"  - name: {name}\n"
            f"    path: skills/{name}\n"
            f"    version: {version}\n"
            f"    status: stable\n"
            f"    summary: synthetic test skill\n"
            f"    platforms: [universal]\n"
            f"    license: MIT\n"
        )
    (library / "skills.yaml").write_text(
        "version: 1\nskills:\n" + "".join(entries), encoding="utf-8"
    )
    return library


def make_layered_library(base: Path, name: str = "alpha-skill", version: str = "0.1.0") -> Path:
    """A library with one skill carrying knowledge/data/observations layers."""
    library = base / "library"
    skills_dir = library / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = write_skill(skills_dir, name)
    add_layers(skill_dir, name)
    (library / "skills.yaml").write_text(
        "version: 1\nskills:\n"
        f"  - name: {name}\n"
        f"    path: skills/{name}\n"
        f"    version: {version}\n"
        "    status: stable\n"
        "    summary: synthetic layered test skill\n"
        "    platforms: [universal]\n"
        "    license: MIT\n" + CAPABILITIES_YAML,
        encoding="utf-8",
    )
    return library


def bump_library_skill(library: Path, name: str, new_version: str = "0.2.0") -> None:
    """Change a skill's content and its catalog version (simulated upstream update)."""
    skill_md = library / "skills" / name / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\n## Changelog\n\n- updated upstream\n",
        encoding="utf-8",
    )
    catalog = library / "skills.yaml"
    catalog.write_text(
        catalog.read_text(encoding="utf-8").replace("version: 0.1.0", f"version: {new_version}"),
        encoding="utf-8",
    )


def copy_fixture(fixture_name: str, skills_dir: Path, dest_name: str | None = None) -> Path:
    """Copy a fixture skill into a library's skills/ directory."""
    dest = skills_dir / (dest_name or fixture_name)
    shutil.copytree(FIXTURES / fixture_name, dest)
    return dest
