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

    def test_description_declares_the_school_neutrality_contract(self):
        fm, _ = split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        description = fm["description"]
        # A caller reads only the description before deciding to load the
        # skill; if it does not say the school is the project's call, an
        # agent can apply the wrong one without ever opening schools.md.
        self.assertIn("London (mockist) or classical (Detroit)", description)
        self.assertIn("declared by the host project's rules, never here", description)

    def test_skill_md_routes_to_every_reference(self):
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        expected = {
            "schools.md",
            "structure-and-naming.md",
            "unit-test-value.md",
            "isolation-and-fakes.md",
            "hygiene.md",
            "anti-patterns.md",
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


class TestSchoolsAreCatalogedButNeverChosen(unittest.TestCase):
    """The skill carries both unit-testing schools and picks neither.

    Which collaborators are replaced by a test double is not a property of
    tests in general — it follows from what a project means by *isolation*.
    Both readings are coherent and in wide use, so a universal skill that
    silently assumed one would be wrong in half the codebases that install
    it. The pins below hold three things at once: both schools are actually
    described (not merely named), the choice is routed to the host project's
    rules, and the fallback for an undeclared project is a proposal rather
    than a guess.
    """

    DOC = REFERENCES / "schools.md"

    RULE_PROJECT_DECLARES = (
        "The school is a project decision: it is declared in the host "
        "project's rules"
    )
    RULE_LONDON = (
        "**Isolation means: the unit under test is isolated from its "
        "collaborators.**"
    )
    RULE_CLASSICAL = (
        "**Isolation means: unit tests are isolated from each other**"
    )
    RULE_UNDECLARED_FALLBACK = (
        "Anything a project leaves undeclared falls back to the rules above "
        "that hold under both schools"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_the_project_declares_the_school(self):
        self.assertIn(self.RULE_PROJECT_DECLARES, self._text())

    def test_both_schools_are_described_by_their_reading_of_isolation(self):
        text = self._text()
        self.assertIn(self.RULE_LONDON, text)
        self.assertIn(self.RULE_CLASSICAL, text)

    def test_each_school_carries_its_unit_and_its_doubling_line(self):
        # Naming the schools is not enough: an agent has to be able to act on
        # the declaration, which needs the unit granularity and the rule for
        # which dependencies get a double.
        text = self._text()
        self.assertIn("| **London (mockist)** | units | a class |", text)
        self.assertIn(
            "| **Classical (Detroit)** | tests | a class or a cluster of classes |",
            text,
        )

    def test_resolution_order_ends_in_a_proposal_not_a_guess(self):
        text = self._text()
        self.assertIn("The project's rules declare a school → follow it exactly.", text)
        self.assertIn("follow the suite, and propose recording the school", text)
        self.assertIn(self.RULE_UNDECLARED_FALLBACK, text)

    def test_the_reference_lists_what_project_rules_must_declare(self):
        text = self._text()
        self.assertIn("## What the project rules must declare", text)
        for item in (
            "**The school**",
            "**What a unit is**",
            "**Which dependencies get a double**",
            "**Which out-of-process dependencies count as managed and which as unmanaged**",
            "**Where an interaction is asserted**",
        ):
            self.assertIn(item, text)

    def test_the_school_independent_rules_are_stated_as_such(self):
        # Guards against the catalog turning into a licence: the rules that
        # hold either way must stay attached to the schools file, or a reader
        # who adopted London could read the whole file as permission.
        text = self._text()
        self.assertIn("## What holds whichever school is declared", text)
        self.assertIn("Never assert an interaction with a stub.", text)

    def test_skill_md_routes_the_school_decision_before_faking_anything(self):
        body = flat(SKILL / "SKILL.md")
        self.assertIn("**Find the project's declared school.**", body)
        self.assertIn("**The school belongs to the project, not to this skill.**", body)

    def test_user_facing_readme_documents_the_choice(self):
        # The library's consumer, not the agent, is the one who has to write
        # the declaration into the project rules — so it has to be documented
        # where a person reads.
        readme = flat(SKILL / "README.md")
        self.assertIn("## The unit-testing school is your project's decision", readme)
        self.assertIn("**The skill never picks one.**", readme)

    def test_openai_adapter_carries_the_school_neutrality(self):
        data = yamlio.load_file(SKILL / "agents" / "openai.yaml")
        prompt = data["interface"]["default_prompt"]
        self.assertIn("neutral on the unit-testing school", prompt)
        self.assertIn("do not pick the school yourself", prompt)

    def test_no_school_is_prescribed_outside_the_undeclared_fallback(self):
        # False-positive guard: the single recommendation in the whole skill
        # is the greenfield tie-break, and it must stay inside the resolution
        # order — a second one anywhere would make the skill choose.
        recommendation = "recommend the **classical** one"
        occurrences = sum(
            flat(path).count(recommendation)
            for path in sorted(SKILL.rglob("*.md"))
        )
        self.assertEqual(occurrences, 1)


class TestUnitTestValueAndAntiPatterns(unittest.TestCase):
    """A test is judged, and the known ways of failing that judgement named.

    The pre-existing references said how to shape a test, what it may touch
    and where its cases come from, but never how to tell a valuable test
    from a worthless one — the judgement every other rule serves. These pins cover the evaluation
    framework, the ordering of the three verification styles, and the
    anti-pattern catalog that the ordering implies.
    """

    VALUE = REFERENCES / "unit-test-value.md"
    ANTI = REFERENCES / "anti-patterns.md"

    RULE_PRODUCT = "A test's value is the **product** of the four, not their sum"
    RULE_RESISTANCE_NOT_TRADED = (
        "Resistance to refactoring is the attribute you do not trade"
    )
    RULE_SINGLE_CAUSE = (
        "**Coupling to implementation details is the single cause of false "
        "positives.**"
    )
    RULE_BOUNDARY = (
        "**Interactions inside the application are implementation details; "
        "interactions that cross the application boundary are not.**"
    )

    def test_the_four_attributes_are_multiplied_not_added(self):
        self.assertIn(self.RULE_PRODUCT, flat(self.VALUE))

    def test_resistance_to_refactoring_is_the_one_not_traded(self):
        text = flat(self.VALUE)
        self.assertIn(self.RULE_RESISTANCE_NOT_TRADED, text)
        self.assertIn(self.RULE_SINGLE_CAUSE, text)

    def test_the_three_styles_are_ranked(self):
        text = flat(self.VALUE)
        for style in (
            "| **Output verification** |",
            "| **State verification** |",
            "| **Communication verification** |",
        ):
            self.assertIn(style, text)
        self.assertIn("**Prefer output verification.**", text)
        self.assertIn("**Communication verification is the last resort.**", text)

    def test_where_an_interaction_may_be_asserted_is_pinned(self):
        text = flat(self.VALUE)
        self.assertIn(self.RULE_BOUNDARY, text)
        self.assertIn(
            "**Assert at the last point before the call leaves your process**", text
        )

    def test_what_deserves_a_unit_test_is_pinned(self):
        text = flat(self.VALUE)
        self.assertIn(
            "the more important or complex the code, the fewer collaborators "
            "it should have",
            text,
        )
        self.assertIn("**Better no test than a bad one.**", text)

    def test_every_anti_pattern_of_the_catalog_is_present(self):
        text = flat(self.ANTI)
        for heading in (
            "## Testing a private method directly",
            "## Exposing private state to enable an assertion",
            "## Leaking the algorithm into the test",
            "## Code pollution — production code that exists only for tests",
            "## Doubling a concrete type to keep part of it",
            "## Time as ambient context",
            "## Sharing the arrange step through a per-test setup hook",
        ):
            self.assertIn(heading, text)

    def test_stub_versus_mock_decides_what_may_be_asserted(self):
        text = flat(REFERENCES / "isolation-and-fakes.md")
        self.assertIn("**Never assert an interaction with a stub.**", text)
        self.assertIn("**Double only types you own.**", text)

    def test_structure_rules_gained_the_act_and_naming_constraints(self):
        text = flat(REFERENCES / "structure-and-naming.md")
        self.assertIn("**One act step per test.**", text)
        self.assertIn("**No branching in a test.**", text)
        self.assertIn(
            "**Do not put the name of the method under test in the test's name.**",
            text,
        )
        self.assertIn("**State a fact, not a wish**", text)

    def test_negative_pre_existing_isolation_rules_survive_untouched(self):
        # False-positive guard: the school-aware rewrite of the isolation
        # preamble must not have dropped or duplicated the rules that were
        # already there.
        text = flat(REFERENCES / "isolation-and-fakes.md")
        for needle in (
            "never someone else's internals",
            "A unit test touches nothing external",
            "no fake, and no re-reading of a project norm, an RFC, or vendor "
            "documentation, can establish what that system actually does",
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
        "The school is a project decision: it is declared in the host "
        "project's rules",
        "**Isolation means: unit tests are isolated from each other**",
        "A test's value is the **product** of the four, not their sum",
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
