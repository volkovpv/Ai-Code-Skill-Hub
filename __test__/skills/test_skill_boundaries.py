"""Boundary gate: every skill must stand on its own.

Skills are installed one at a time into a target project, so a skill that
names another one — or quotes its rule codes, its file paths, or its pinned
versions — is incomplete without a skill the consumer may never install.
Naming a sibling is allowed in exactly one shape: a **conditional** sentence
("where the host project also declares ..."), which an agent can act on when
both skills happen to be attached and can ignore when they are not.

Scope: every authored file of every skill. The skill-root ``README.md`` is
library-user documentation and is never installed (see
``installer.RUNTIME_EXCLUDED_FILES``), so it may cross-reference freely.

Not covered: the observation *records* themselves
(``observations/{accepted,candidates,rejected}/``). A record is a dated
field report that agents may not edit (AGENTS.md), so its wording cannot be
brought into compliance by this gate; what a *new* record may say about a
sibling is a policy question, recorded in AGENTS.md, not an assertion here.
``observations/INDEX.md`` is authored, not append-only, and is covered.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

sys.path.insert(0, str(ROOT / "src"))

from skill_library import yamlio  # noqa: E402
from skill_library.installer import RUNTIME_EXCLUDED_FILES  # noqa: E402

SKILL_NAMES = tuple(sorted(path.name for path in SKILLS.iterdir() if path.is_dir()))

# A sibling may be named only inside a sentence that makes the mention
# conditional on the host project having attached that skill as well.
CONDITIONAL_MARKERS = (
    "where the host project",
    "when the host project",
    "if the host project",
    "where the project",
    "when the project",
    "also declares",
    "also attaches",
    "also uses",
)

# The rule-code prefix each checker owns. A code carrying another skill's
# prefix pins that skill's checker internals into this one.
OWN_CODE_PREFIX = {
    "typescript-coding": "TS",
    "python-coding": "PY",
    "typescript-nestjs": "NEST",
}
RULE_CODE = re.compile(r"\b(TS|PY|NEST)-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\b")

TEXT_SUFFIXES = (".md", ".yaml", ".py", ".ts")

# Records an agent may not edit (AGENTS.md); their authored index is gated.
OBSERVATION_RECORD_DIRS = (
    "observations/accepted/",
    "observations/candidates/",
    "observations/rejected/",
)

# Sentence splitting must not break on the abbreviations that actually occur
# in skill prose, or a marker lands in a different "sentence" than its
# mention and a compliant line reads as a violation.
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.")
_ABBREVIATION_GUARD = "\x00"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    """Whitespace-flattened *text* split into sentences.

    Markdown hard-wraps prose, so a sentence straddles line breaks; flatten
    first and the gate reads the file as a human reading the rendered page
    would.
    """
    flat = " ".join(text.split())
    for abbreviation in _ABBREVIATIONS:
        flat = flat.replace(abbreviation, abbreviation.replace(".", _ABBREVIATION_GUARD))
    return [
        part.replace(_ABBREVIATION_GUARD, ".")
        for part in _SENTENCE_END.split(flat)
        if part
    ]


def is_conditional(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in CONDITIONAL_MARKERS)


def authored_texts(skill: str) -> dict[str, str]:
    """Every authored file of *skill* that the gate covers, as ``rel -> text``."""
    root = SKILLS / skill
    texts: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in RUNTIME_EXCLUDED_FILES:
            continue  # library-user documentation, never installed
        if rel.startswith(OBSERVATION_RECORD_DIRS) or "__pycache__/" in rel:
            continue  # append-only field reports; see the module docstring
        texts[rel] = path.read_text(encoding="utf-8")
    return texts


def siblings_of(skill: str) -> tuple[str, ...]:
    return tuple(name for name in SKILL_NAMES if name != skill)


class TestSkillsDoNotDependOnEachOther(unittest.TestCase):
    def test_a_sibling_is_named_only_in_a_conditional_sentence(self):
        for skill in SKILL_NAMES:
            for rel, text in authored_texts(skill).items():
                for sentence in sentences(text):
                    named = [name for name in siblings_of(skill) if name in sentence]
                    if not named:
                        continue
                    self.assertTrue(
                        is_conditional(sentence),
                        f"{skill}/{rel} names {named} unconditionally — a "
                        f"consumer installing only {skill} cannot follow it: "
                        f"{sentence!r}",
                    )

    def test_no_rule_code_from_another_skills_checker(self):
        for skill in SKILL_NAMES:
            own = OWN_CODE_PREFIX.get(skill)
            for rel, text in authored_texts(skill).items():
                for match in RULE_CODE.finditer(text):
                    self.assertEqual(
                        match.group(1),
                        own,
                        f"{skill}/{rel} quotes {match.group(0)!r}, a rule code "
                        f"of another skill's checker",
                    )

    def test_no_path_into_another_skills_directory(self):
        for skill in SKILL_NAMES:
            for rel, text in authored_texts(skill).items():
                for sibling in siblings_of(skill):
                    self.assertNotIn(
                        f"skills/{sibling}/",
                        text,
                        f"{skill}/{rel} points at another skill's file tree",
                    )

    def test_no_pinned_version_of_another_skill(self):
        for skill in SKILL_NAMES:
            for rel, text in authored_texts(skill).items():
                for sibling in siblings_of(skill):
                    found = re.search(rf"{re.escape(sibling)}@\d+\.\d+\.\d+", text)
                    self.assertIsNone(
                        found,
                        f"{skill}/{rel} pins another skill's version "
                        f"({found.group(0) if found else ''})",
                    )


class TestTheGateCoversTheWholeLibrary(unittest.TestCase):
    def test_every_catalogued_skill_is_gated(self):
        catalogued = {
            entry["name"] for entry in yamlio.load_file(ROOT / "skills.yaml")["skills"]
        }
        self.assertEqual(catalogued, set(SKILL_NAMES))

    def test_skill_root_readme_is_the_only_exempt_file(self):
        # The exemption exists because that file is never installed; if the
        # installer stops excluding it, the exemption must go too.
        self.assertEqual(RUNTIME_EXCLUDED_FILES, ("README.md",))


class TestGateMechanics(unittest.TestCase):
    """The detector itself, on synthetic input — a false negative here would
    silently retire the whole gate."""

    def test_a_semicolon_does_not_separate_a_marker_from_its_mention(self):
        # The canonical compliant form joins the two halves with a semicolon.
        text = (
            "Wiring conventions live in the `hexagonal-service` skill; when "
            "the host project uses it, apply that skill on top of this one."
        )
        self.assertEqual(len(sentences(text)), 1)
        self.assertTrue(is_conditional(sentences(text)[0]))

    def test_an_abbreviation_does_not_end_a_sentence(self):
        text = "Pair it with a language skill (e.g. `python-coding`) for the mechanics."
        self.assertEqual(sentences(text), [text])

    def test_an_unconditional_mention_is_caught(self):
        text = "Layer rules come from the `hexagonal-service` skill."
        self.assertFalse(is_conditional(sentences(text)[0]))

    def test_a_line_break_between_marker_and_mention_still_reads_as_one_sentence(self):
        text = "Where the host project also declares an\narchitecture standard, apply it."
        self.assertEqual(len(sentences(text)), 1)
        self.assertTrue(is_conditional(sentences(text)[0]))

    def test_the_rule_code_pattern_matches_the_shapes_checkers_emit(self):
        found = [m.group(0) for m in RULE_CODE.finditer("TS-ENV PY-TLS-NOVERIFY NEST-DI-TOKEN")]
        self.assertEqual(found, ["TS-ENV", "PY-TLS-NOVERIFY", "NEST-DI-TOKEN"])


if __name__ == "__main__":
    unittest.main()
