"""Tests for the human-readable history pair — docs/history.{eng,rus}.md.

Policy (AGENTS.md, "History docs discipline"): the two files are a mandatory
bilingual pair with the same entries in the same order; every entry shows the
defect (AS IS / TO BE diagram, runnable example, tables); one fix is written
once with all carrying releases on a single line; and neither the history pair
nor CHANGELOG.md may attribute a defect to a named consuming project.

The attribution rule is checked by SHAPE, not by a denylist of project names:
naming the projects here would reintroduce exactly what the rule forbids.
"""

from __future__ import annotations

import re
import unittest

from .helpers import ROOT

DOCS = ROOT / "docs"
ENG = DOCS / "history.eng.md"
RUS = DOCS / "history.rus.md"
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"

# Shapes that attribute a defect to a specific consuming project. Each one
# occurred in this repository before the policy existed.
ATTRIBUTION_PATTERNS = (
    re.compile(r"transferred from consumer", re.IGNORECASE),
    re.compile(r"\bconsumer\s+`[^`]+`"),  # "consumer `<repo-name>`"
    re.compile(r"\bin (?:one|a) consumer build\b", re.IGNORECASE),
    re.compile(r"\bharness/observations/"),  # a consumer's internal record path
    re.compile(r"\bharness/review/"),  # a consumer's internal verdict path
)


def read(path) -> str:
    return path.read_text(encoding="utf-8")


def entry_releases(text: str) -> list[tuple[int, ...]]:
    """The project release of each entry, in the order the entries appear.

    An entry's release is the first backticked ``X.Y.Z`` in its body — the
    project version that opens its ``Releases`` line, in either language.
    Sections without a version (the preamble) are not entries.
    """
    releases: list[tuple[int, ...]] = []
    for section in text.split("\n## ")[1:]:
        found = re.search(r"`(\d+)\.(\d+)\.(\d+)`", section)
        if found:
            releases.append(tuple(int(part) for part in found.groups()))
    return releases


class TestHistoryPairExistsAndIsSymmetric(unittest.TestCase):
    def test_both_halves_exist(self):
        self.assertTrue(ENG.is_file(), "docs/history.eng.md is missing")
        self.assertTrue(RUS.is_file(), "docs/history.rus.md is missing")

    def test_the_pair_has_the_same_number_of_sections(self):
        eng_sections = re.findall(r"(?m)^## ", read(ENG))
        rus_sections = re.findall(r"(?m)^## ", read(RUS))
        self.assertEqual(
            len(eng_sections),
            len(rus_sections),
            "the two halves must carry the same entries in the same order",
        )

    def test_the_pair_carries_the_same_release_lines(self):
        # The "Releases:" line is the entry's identity: the same fix must name
        # the same carrying versions in both languages.
        def versions(text: str) -> list[str]:
            return sorted(re.findall(r"`(\d+\.\d+\.\d+)`", text))

        self.assertEqual(versions(read(ENG)), versions(read(RUS)))

    def test_entries_are_newest_first(self):
        # Same order as CHANGELOG.md: the latest release heads the file.
        for path in (ENG, RUS):
            with self.subTest(path=path.name):
                releases = entry_releases(read(path))
                self.assertGreater(len(releases), 1, "expected several entries")
                self.assertEqual(
                    releases,
                    sorted(releases, reverse=True),
                    "entries must run newest-first; insert a new one above the others",
                )

    def test_each_half_links_to_the_other(self):
        self.assertIn("history.rus.md", read(ENG))
        self.assertIn("history.eng.md", read(RUS))


class TestEntriesShowTheDefect(unittest.TestCase):
    """An entry must be visual: diagrams and tables, not a bullet list."""

    def test_both_halves_carry_at_least_two_diagrams(self):
        # One AS IS + one TO BE per entry, at minimum.
        for path in (ENG, RUS):
            with self.subTest(path=path.name):
                self.assertGreaterEqual(
                    read(path).count("```mermaid"),
                    2,
                    "an entry needs an AS IS and a TO BE diagram",
                )

    def test_both_halves_carry_tables(self):
        for path in (ENG, RUS):
            with self.subTest(path=path.name):
                self.assertIn("|---|", read(path).replace(" ", ""))

    def test_both_halves_carry_a_runnable_example(self):
        for path in (ENG, RUS):
            with self.subTest(path=path.name):
                self.assertIn("```python", read(path))


class TestNoConsumerProjectAttribution(unittest.TestCase):
    """Neither the history pair nor CHANGELOG.md may name a consuming project."""

    def test_history_and_changelog_are_free_of_attribution_shapes(self):
        for path in (ENG, RUS, CHANGELOG):
            text = read(path)
            for pattern in ATTRIBUTION_PATTERNS:
                with self.subTest(path=path.name, pattern=pattern.pattern):
                    match = pattern.search(text)
                    self.assertIsNone(
                        match,
                        f"{path.name} attributes a defect to a named consuming "
                        f"project: {match.group(0) if match else ''!r}",
                    )

    def test_the_scanner_itself_detects_a_planted_attribution(self):
        # Guards the guard: a rule that cannot fail is not a rule.
        planted = "- Fixed OBS-1 (transferred from consumer `some-project`)."
        self.assertTrue(
            any(pattern.search(planted) for pattern in ATTRIBUTION_PATTERNS)
        )


class TestPolicyIsDocumented(unittest.TestCase):
    def test_readme_links_both_halves(self):
        readme = read(README)
        self.assertIn("docs/history.rus.md", readme)
        self.assertIn("docs/history.eng.md", readme)

    def test_agents_md_carries_the_history_section(self):
        self.assertIn("## History docs discipline", read(AGENTS))


if __name__ == "__main__":
    unittest.main()
