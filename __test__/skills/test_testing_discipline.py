"""Dedicated tests for skills/testing-discipline (run via `skillctl test testing-discipline`).

The skill has no scripts — it is a pure test-writing standard — so the tests
pin its structural contract (valid layout, routed references, no empty
layers), its neutrality (no language, runner or framework mechanics), and
the observation-backed rules it now owns.

Those rules were pinned against ``references/testing.md`` of the two
language skills before the split; they are language-independent by their
own universality checks, so both copies collapse into the single set of
pins below and the language skills keep only their spelling maps. The
de-duplication itself is guarded here (``TestRulesAreNotDuplicatedInLanguageSkills``)
and in each language skill's own test module.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "testing-discipline"
REFERENCES = SKILL / "references"

sys.path.insert(0, str(ROOT / "src"))

from skill_library import yamlio  # noqa: E402
from skill_library.discovery import split_frontmatter  # noqa: E402
from skill_library.validator import validate_skill_dir  # noqa: E402

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_FENCED_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_SPAN = re.compile(r"`[^`\n]*`")


def flat(path: Path) -> str:
    """The file's text with every whitespace run collapsed to one space.

    Markdown hard-wraps prose at ~80 columns, so a multi-word anchor phrase
    can straddle a line break; collapsing reads the file exactly as a human
    skimming the rendered text would.
    """
    return " ".join(path.read_text(encoding="utf-8").split())


def skill_texts(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in (".md", ".yaml")
    }


def broken_markdown_links(root: Path) -> list[str]:
    """Every markdown-link target under *root* that does not resolve on disk."""
    offenders: list[str] = []
    for md in sorted(root.rglob("*.md")):
        text = _FENCED_CODE_BLOCK.sub("", md.read_text(encoding="utf-8"))
        text = _INLINE_CODE_SPAN.sub("", text)
        for target in _MD_LINK.findall(text):
            target = target.split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / target).resolve().is_file():
                offenders.append(f"{md.relative_to(root)} -> {target}")
    return offenders


class TestStructure(unittest.TestCase):
    def test_skill_directory_validates_clean(self):
        self.assertEqual(validate_skill_dir(SKILL), [])

    def test_description_declares_the_universal_contract(self):
        fm, _ = split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        description = fm["description"]
        # The activation scope (any language, any runner) is the whole point
        # of splitting these rules out of the language standards.
        self.assertIn("no language, runner, framework, or platform assumptions", description)
        self.assertIn("in any language", description)

    def test_skill_md_routes_to_every_reference(self):
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        expected = {
            "structure-and-naming.md",
            "isolation-and-fakes.md",
            "hygiene.md",
            "types-and-tests.md",
        }
        self.assertEqual(
            expected,
            {path.name for path in REFERENCES.glob("*.md")},
            "reference set changed — update the routing pins",
        )
        for name in expected:
            self.assertIn(f"references/{name}", body, name)

    def test_no_optional_layers_created_for_structure(self):
        # The skill is references-only; empty layer dirs would violate AGENTS.md.
        for layer in ("knowledge", "data", "observations"):
            self.assertFalse((SKILL / layer).exists(), layer)

    def test_no_dangling_markdown_links_in_a_runtime_install(self):
        from skill_library.installer import install_skill

        with tempfile.TemporaryDirectory(prefix="testing-discipline-") as tmp:
            target = Path(tmp) / "consumer"
            target.mkdir()
            install_skill(ROOT, "testing-discipline", target, install_mode="runtime")
            installed = target / ".agents" / "skills" / "testing-discipline"
            self.assertEqual(broken_markdown_links(installed), [])


class TestNeutrality(unittest.TestCase):
    """The skill must not smuggle in language, runner or framework mechanics."""

    FORBIDDEN = (
        "python",
        "typescript",
        "pytest",
        "unittest",
        "jest",
        "vitest",
        "hypothesis",
        "monkeypatch",
        "mypy",
        "pyright",
        "eslint",
        "tsconfig",
        "asyncio",
        "typeguard",
        "ts-expect-error",
        "describe(",
        ".only",
        ".skip",
    )

    def test_no_language_or_runner_mechanics_in_content(self):
        for rel, text in skill_texts(SKILL).items():
            lowered = text.lower()
            for token in self.FORBIDDEN:
                self.assertNotIn(token, lowered, f"{rel} mentions {token!r}")

    def test_the_scanner_itself_detects_a_planted_mechanic(self):
        # Guards the guard: a neutrality check that cannot fail is not a check.
        planted = "Mark it with @pytest.mark.skip and move on."
        self.assertTrue(any(token in planted.lower() for token in self.FORBIDDEN))


class TestCaseProvenanceSubjectAndDimensionGuidance(unittest.TestCase):
    """Regression for OBS-20260726-001 of both language skills (Reviewer-
    confirmed C3, occurrences: 9), relocated here with the rules themselves.

    The pre-split ``references/testing.md`` §Hygiene had a rule against
    hardcoding an expected value "so it passes", but no rule against the
    distinct pattern of choosing a test's *case set*, its *subject*, or its
    *dimensional coverage* from the artifact under test rather than from the
    specification — a gap that recurred nine times in one build, never caught
    by the suite that was supposed to guard the property. Each of the three
    anchor phrases below is a load-bearing clause of one of the three rules,
    not an incidental word choice; their absence is exactly the silence the
    observation reports.
    """

    DOC = REFERENCES / "hygiene.md"

    # One literal, specific clause per rule — chosen so a superficial mention
    # of "specification" or "dimension" elsewhere in the file cannot satisfy
    # the check by accident.
    RULE_PROVENANCE = (
        "never copied from — or parametrized over — the artifact under test"
    )
    RULE_SUBJECT = (
        "a test that reaches it through the outer layer proves nothing about "
        "the inner one"
    )
    RULE_DIMENSION = "treat a surviving mutation as evidence of a missing dimension"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_provenance_rule_is_present(self):
        self.assertIn(self.RULE_PROVENANCE, self._text())

    def test_layered_subject_rule_is_present(self):
        self.assertIn(self.RULE_SUBJECT, self._text())

    def test_dimensional_totality_rule_is_present(self):
        self.assertIn(self.RULE_DIMENSION, self._text())

    def test_each_rule_ships_an_illustrative_reproduction(self):
        # The rule must be checkable, not merely aspirational: each of the
        # three carries its own minimal, deterministic reproduction.
        text = self._text()
        self.assertIn("ALLOWED = {", text, "rule 1 (provenance) needs its enum/mutation snippet")
        self.assertIn("downstream", text)
        self.assertIn("overwrite", text)
        self.assertIn("normalized", text)
        self.assertIn("raw key", text)

    def test_negative_do_not_tune_the_gate_rule_survives_untouched(self):
        # False-positive guard: the block must not have replaced or duplicated
        # the distinct "do not tune a test to the gate" rule it does NOT cover.
        text = self._text()
        needle = 'never hardcode an expected value "so it passes"'
        self.assertEqual(text.count(needle), 1, text)

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (self.RULE_PROVENANCE, self.RULE_SUBJECT, self.RULE_DIMENSION):
            self.assertEqual(text.count(needle), 1, needle)


class TestExternalReferenceBehaviourGuidance(unittest.TestCase):
    """Regression for OBS-20260727-001 / OBS-20260726-002 of the language
    skills (Reviewer-confirmed C3, occurrences: 3, both claimed minimal
    reproductions independently re-executed), relocated here with the rule.

    The pre-split guidance said *what* to fake (a seam the code exposes,
    never someone else's internals) but was silent on *how the fake's own
    return values are known to be true of the real system* before the fake is
    written. Across three independent occurrences in one build — a broker's
    dead-letter key rewriting, an auth encoder's identity substitution for an
    absent/empty user, and a driver's row-shape column collapse — a unit-test
    fake for a third-party seam stayed green while encoding a belief about
    that system's runtime behaviour that was simply wrong, and only a live
    probe against the real system (never a re-reading of project norms or
    vendor prose) ever caught it.
    """

    DOC = REFERENCES / "isolation-and-fakes.md"

    RULE_NO_READING_ESTABLISHES_IT = (
        "no fake, and no re-reading of a project norm, an RFC, or vendor "
        "documentation, can establish what that system actually does"
    )
    RULE_SWITCH_TRIGGER = (
        "a second rejection of the same reading on the same external-system "
        "property"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_external_system_observation_rule_is_present(self):
        self.assertIn(self.RULE_NO_READING_ESTABLISHES_IT, self._text())

    def test_second_rejection_switch_trigger_is_present(self):
        self.assertIn(self.RULE_SWITCH_TRIGGER, self._text())

    def test_rule_ships_two_illustrative_reproductions(self):
        # Two deterministic, project- and language-independent reproductions,
        # one per occurrence family (an empty-vs-absent URL identity; a
        # column-name-keyed row collapse) — the third occurrence (a live
        # two-hop broker DLX cycle) is not reducible to a snippet, per the
        # observation's own record.
        text = self._text()
        self.assertIn("amqp://:p@h:1", text)
        self.assertIn("?column?", text)
        self.assertIn("SELECT true AS a, false AS b", text)

    def test_negative_fake_the_seam_rule_survives_untouched(self):
        # False-positive guard: the rule must not have replaced or duplicated
        # the pre-existing, distinct "fake the seams the code exposes, never
        # someone else's internals" rule it is silent-not-wrong about.
        text = self._text()
        self.assertEqual(text.count("never someone else's internals"), 1, text)

    def test_rule_is_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (self.RULE_NO_READING_ESTABLISHES_IT, self.RULE_SWITCH_TRIGGER):
            self.assertEqual(text.count(needle), 1, needle)


class TestOutboundMutationAndWiringLevelFakeGuidance(unittest.TestCase):
    """Regression for OBS-20260728-001 of both language skills (Reviewer-
    confirmed C3, occurrences: 6 across two consecutive tasks, at least three
    of them after the sibling fix for the adjacent external-system-fake class
    was already pinned), relocated here with the rules.

    Two sub-shapes of the same root as the class above — "evidence collected
    somewhere other than where the property lives" — that its own scope
    sentence did not make legible:

    1. **Outbound-mutation / input-side.** The parent rule scopes itself to
       "a fake's own return values", i.e. a fake computing a WRONG OUTPUT for
       a given input. A fake bound at the exact layer that substitutes a value
       the caller does not fully control on the way OUT of a call (a header,
       an id, a default) has no return value to inspect at all, so a reader
       keying on "return values" would not recognise this shape as covered.
    2. **Wiring-level.** A test that constructs its own copy of a third-party
       collaborator (to assert a property of *how* it is built — which
       constructor arguments, which interceptors/hooks) establishes nothing
       about the construction the product's own factory performs; the two are
       different code paths and only the second one ships.
    """

    DOC = REFERENCES / "isolation-and-fakes.md"

    RULE_OUTBOUND_NO_RETURN_VALUE = (
        "there is no return value to inspect and the fake stands in for the "
        "very code that would decide the outcome"
    )
    RULE_OUTBOUND_BELIEF = "the caller's argument reaches the wire unmodified"
    RULE_WIRING_LEAD = (
        "A test that constructs the collaborator itself establishes nothing "
        "about the construction the product performs"
    )
    RULE_WIRING_PROVES_ACHIEVABLE = (
        "proves only that the property is achievable, never that the "
        "product's own wiring achieves it"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_outbound_mutation_no_return_value_rule_is_present(self):
        self.assertIn(self.RULE_OUTBOUND_NO_RETURN_VALUE, self._text())

    def test_outbound_mutation_belief_framing_is_present(self):
        self.assertIn(self.RULE_OUTBOUND_BELIEF, self._text())

    def test_wiring_level_lead_rule_is_present(self):
        self.assertIn(self.RULE_WIRING_LEAD, self._text())

    def test_wiring_level_achievable_vs_achieves_distinction_is_present(self):
        self.assertIn(self.RULE_WIRING_PROVES_ACHIEVABLE, self._text())

    def test_rules_ship_their_two_reproductions(self):
        # One per sub-shape: an outbound header/id substitution the caller does
        # not control, and a factory whose interceptor argument has zero test
        # coverage.
        text = self._text()
        self.assertIn("request-id, retry token, or default identity header", text)
        self.assertIn(
            "leave the suite fully green while the running product wires "
            "no interceptors at all",
            text,
        )

    def test_negative_sibling_reproductions_survive_untouched(self):
        # False-positive guard: the adjacent external-system rule and its two
        # reproductions must not have been replaced or duplicated.
        text = self._text()
        for needle in (
            "amqp://:p@h:1",
            "SELECT true AS a, false AS b",
            "no fake, and no re-reading of a project norm, an RFC, or vendor "
            "documentation, can establish what that system actually does",
            "a second rejection of the same reading on the same "
            "external-system property",
        ):
            self.assertEqual(text.count(needle), 1, needle)

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (
            self.RULE_OUTBOUND_NO_RETURN_VALUE,
            self.RULE_OUTBOUND_BELIEF,
            self.RULE_WIRING_LEAD,
            self.RULE_WIRING_PROVES_ACHIEVABLE,
        ):
            self.assertEqual(text.count(needle), 1, needle)


class TestRulesAreNotDuplicatedInLanguageSkills(unittest.TestCase):
    """The split is only worth its cost while the rules live in one place.

    Every anchor pinned above must be absent from the language standards:
    they keep spelling maps ("how a rule is expressed in this language"), not
    copies of the rules. A silent re-import of any clause into either skill
    is exactly the drift this skill exists to prevent.
    """

    LANGUAGE_SKILLS = ("python-coding", "typescript-coding")

    ANCHORS = (
        "never copied from — or parametrized over — the artifact under test",
        "a test that reaches it through the outer layer proves nothing about "
        "the inner one",
        "treat a surviving mutation as evidence of a missing dimension",
        "no fake, and no re-reading of a project norm, an RFC, or vendor "
        "documentation, can establish what that system actually does",
        "a second rejection of the same reading on the same external-system "
        "property",
        "there is no return value to inspect and the fake stands in for the "
        "very code that would decide the outcome",
        "A test that constructs the collaborator itself establishes nothing "
        "about the construction the product performs",
        'never hardcode an expected value "so it passes"',
    )

    def test_no_universal_rule_text_remains_in_a_language_skill(self):
        for skill in self.LANGUAGE_SKILLS:
            root = ROOT / "skills" / skill
            for rel, _ in skill_texts(root).items():
                if rel.startswith("observations/"):
                    continue  # accepted records quote the rule they reported
                text = flat(root / rel)
                for anchor in self.ANCHORS:
                    self.assertNotIn(anchor, text, f"{skill}/{rel} re-states {anchor!r}")


class TestOpenAiAdapter(unittest.TestCase):
    def test_adapter_parses_in_yaml_subset_and_aligns_with_skill(self):
        data = yamlio.load_file(SKILL / "agents" / "openai.yaml")
        prompt = data["interface"]["default_prompt"]
        self.assertTrue(prompt.strip())
        self.assertIn("testing-discipline", prompt)
        self.assertIn("no language, runner, framework or platform assumptions", prompt)
        self.assertIn("precedence", prompt)


if __name__ == "__main__":
    unittest.main()
