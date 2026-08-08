"""Dedicated tests for skills/testing-discipline (run via `skillctl test testing-discipline`).

The skill has no scripts — it is a pure test-writing standard — so the tests
pin its structural contract (valid layout, routed references, no empty
layers), its neutrality (no language, runner or framework mechanics), and
the observation-backed rules it now owns.

Those rules were pinned against ``references/testing.md`` of the two
language skills before the split; they are language-independent by their
own universality checks, so both copies collapse into the single set of
pins below and the language skills keep only their spelling maps. The
de-duplication itself is guarded here (``TestRulesAreNotDuplicatedInOtherSkills``)
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
            "test-levels.md",
            "tdd-cycle.md",
            "interface-discovery.md",
            "test-diagnostics.md",
            "tests-as-design-feedback.md",
            "structure-and-naming.md",
            "test-data-builders.md",
            "unit-test-value.md",
            "isolation-and-fakes.md",
            "async-and-concurrency.md",
            "adapters-and-persistence.md",
            "hygiene.md",
            "anti-patterns.md",
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


class TestScopeIsUnitAndIntegrationOnly(unittest.TestCase):
    """The skill covers two levels and says so; a third would dilute both.

    A test-writing standard that also advises on exercising a deployed
    system carries rules with different subjects, lifecycles and owners
    under one name — and an agent reading it applies unit-test reasoning
    (isolate, double the collaborators, run in milliseconds) to a question
    where every one of those moves is wrong. The limit is therefore part
    of the contract, stated where a caller reads it, and enforced here.
    """

    # Tokens that can only appear if a level beyond the two is being taught.
    # The exclusion itself is phrased without them ("a whole deployed system
    # from outside it"), so their absence is a real signal rather than a
    # vocabulary ban.
    OUT_OF_SCOPE = (
        "acceptance",
        "end-to-end",
        "end to end",
        "e2e",
        "walking skeleton",
    )

    def test_no_third_level_is_taught_anywhere_in_the_skill(self):
        for rel, text in skill_texts(SKILL).items():
            lowered = text.lower()
            for token in self.OUT_OF_SCOPE:
                self.assertNotIn(token, lowered, f"{rel} mentions {token!r}")

    def test_the_scanner_itself_detects_a_planted_third_level(self):
        # Guards the guard, exactly as the neutrality scanner does.
        planted = "Open each feature with a failing acceptance test."
        self.assertTrue(any(token in planted.lower() for token in self.OUT_OF_SCOPE))

    def test_the_description_states_the_limit(self):
        # The description is all a caller reads before loading the skill, so
        # the limit has to survive there or it is not part of the contract.
        fm, _ = split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        description = fm["description"]
        self.assertIn("Discipline for unit and integration tests", description)
        self.assertIn(
            "testing a whole deployed system from outside is out of scope",
            description,
        )

    def test_the_limit_is_a_rule_not_only_a_preamble(self):
        # Stated only in prose, an agent reads the scope as a description of
        # the contents rather than as an instruction about what to decline.
        body = flat(SKILL / "SKILL.md")
        self.assertIn("**The scope is unit and integration tests.**", body)
        self.assertIn(
            "say so rather than answering them from these rules", body
        )

    def test_the_levels_file_carries_exactly_two_levels_and_names_the_exclusion(self):
        text = flat(REFERENCES / "test-levels.md")
        self.assertIn(
            "This skill covers exactly two kinds of test: **unit** and "
            "**integration**.",
            text,
        )
        self.assertIn("It is **out of scope here**", text)

    def test_the_adapter_carries_the_limit_too(self):
        prompt = yamlio.load_file(SKILL / "agents" / "openai.yaml")["interface"][
            "default_prompt"
        ]
        self.assertIn("Its scope is unit and integration tests and nothing else", prompt)
        self.assertIn("say the skill does not cover it", prompt)


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


class TestPureWiringLineCoverageIsNotEvidenceGuidance(unittest.TestCase):
    """Regression for a field report (Reviewer-confirmed C3, five occurrences
    across five consecutive tasks in two distinct modules, plus a
    deterministic, project-independent minimal reproduction).

    Distinct from the class above (``TestOutboundMutationAndWiringLevelFakeGuidance``):
    that class is about *which seam* a wiring-construction test must exercise
    (the production factory, not a hand-built copy). This one is about a line
    that already sits inside the production wiring path and is already
    "exercised" by an existing, unrelated test — a composition-root line with
    no return value of its own, executed only as a side effect of a test that
    asserts a different collaborator entirely. Rule 12 ("exercise the
    production wiring") and the hygiene coverage guidance ("use coverage to
    find untested areas, not as a target") both approach this from adjacent
    angles and neither states it: passing rule 12's letter is exactly what
    happens here, and it still proves nothing about the new line.
    """

    DOC = REFERENCES / "isolation-and-fakes.md"

    RULE_NO_RETURN_VALUE = (
        "computes nothing and asserts nothing on its own"
    )
    RULE_SIDE_EFFECT_NOT_EVIDENCE = (
        "reached only as a side effect of running the real startup path is "
        "not evidence"
    )
    RULE_TARGETED_CHECK = (
        "a targeted mutation of that exact line"
    )
    RULE_LETTER_NOT_ENOUGH = (
        "exercising the real wiring path for an unrelated reason is not the "
        "same as making a claim about the new line"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_no_return_value_framing_is_present(self):
        self.assertIn(self.RULE_NO_RETURN_VALUE, self._text())

    def test_side_effect_coverage_is_not_evidence_rule_is_present(self):
        self.assertIn(self.RULE_SIDE_EFFECT_NOT_EVIDENCE, self._text())

    def test_targeted_mutation_check_rule_is_present(self):
        self.assertIn(self.RULE_TARGETED_CHECK, self._text())

    def test_rule_12_letter_vs_substance_distinction_is_present(self):
        self.assertIn(self.RULE_LETTER_NOT_ENOUGH, self._text())

    def test_rule_ships_its_reproduction(self):
        text = self._text()
        self.assertIn(
            "constructs a collaborator via a factory and stores or registers it",
            text,
        )
        self.assertIn("deleting it leaves the suite green", text)

    def test_negative_sibling_reproductions_survive_untouched(self):
        # False-positive guard: the adjacent construction-seam rule and its
        # own reproduction must not have been replaced or duplicated.
        text = self._text()
        needle = (
            "A test that constructs the collaborator itself establishes "
            "nothing about"
        )
        self.assertIn(needle, text)
        self.assertEqual(text.count(needle), 1, needle)

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (
            self.RULE_NO_RETURN_VALUE,
            self.RULE_SIDE_EFFECT_NOT_EVIDENCE,
            self.RULE_TARGETED_CHECK,
            self.RULE_LETTER_NOT_ENOUGH,
        ):
            self.assertEqual(text.count(needle), 1, needle)

    def test_skill_md_rule_12_carries_the_pointer_clause(self):
        skill_text = flat(SKILL / "SKILL.md")
        self.assertIn(
            "a pure wiring/DI line reached only as a side effect of an "
            "unrelated test is not evidence",
            skill_text,
        )


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


class TestCycleAndEvidenceGuidance(unittest.TestCase):
    """The process axis: when a test exists relative to the code it covers.

    Every other file in the skill judges a test that already exists.
    Nothing said when it comes into being — so an agent applying the skill
    could write a flawless test that had never been seen to fail, and
    nothing in the skill objected.

    The file is deliberately narrow: it carries the cycle as it bears on
    the test, not the surrounding development process. Choosing the next
    item off a list, sizing a step and ending a session are project
    workflow, and a skill scoped to unit and integration tests does not
    legislate them.

    The pins below split into two groups, and the split is the point:
    ``test_evidence_rule_*`` covers what holds in any project whatever its
    process, and the rest covers the cycle, which the host project declares
    the same way it declares the school.
    """

    DOC = REFERENCES / "tdd-cycle.md"

    RULE_EVIDENCE = (
        "**A test that has never been observed to fail is not yet evidence "
        "of anything.**"
    )
    RULE_CONDITIONAL = "applies where the host project declares that it practises it"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_evidence_rule_is_present_and_stated_unconditionally(self):
        text = self._text()
        self.assertIn(self.RULE_EVIDENCE, text)
        # It must sit in the section that explicitly holds regardless of
        # process; burying it inside the cycle would make it opt-in.
        self.assertIn(
            "## Holds regardless of process: a test is not evidence until it "
            "has been red",
            text,
        )

    def test_evidence_rule_gives_the_test_after_procedure(self):
        # Without a way to satisfy it when the test is written last, the rule
        # is only reachable by projects that already practise the cycle.
        text = self._text()
        self.assertIn("break the behaviour the test names", text)
        self.assertIn("**Watch which failure you got.**", text)
        self.assertIn("**An unexpected green is information, never a relief.**", text)

    def test_the_two_generating_rules_are_present(self):
        text = self._text()
        self.assertIn(
            "**Write a failing automated test before writing any production "
            "code.**",
            text,
        )
        self.assertIn("**Remove duplication.**", text)

    def test_the_loop_constraints_are_pinned(self):
        text = self._text()
        self.assertIn("**Never more than one red test at a time.**", text)
        self.assertIn("**A green bar is a place you can stand.**", text)

    def test_the_refactor_step_removes_the_test_to_code_duplication(self):
        # Without this the cycle is just "write the test first"; the second
        # generating rule is what turns a constant into the general case.
        text = self._text()
        self.assertIn("## The refactor step", text)
        self.assertIn(
            "**Duplication between the test and the production code counts.**",
            text,
        )

    def test_the_cycle_owes_the_learning_test_and_the_regression_test(self):
        # The two places the cycle reaches into rules that hold regardless of
        # it: pinning an unfamiliar facility, and reproducing every defect.
        text = self._text()
        self.assertIn(
            "**Before the first use of an unfamiliar external facility, write "
            "a test against it**",
            text,
        )
        self.assertIn(
            "**Every defect starts with the smallest test that reproduces "
            "it**",
            text,
        )

    def test_the_cycle_is_scoped_to_a_project_declaration(self):
        # The skill is universal; it must not impose a development process on
        # a project that never asked for one.
        self.assertIn(self.RULE_CONDITIONAL, self._text())
        self.assertIn(
            "**Where the project practises test-driven development, work the",
            flat(SKILL / "SKILL.md"),
        )
        self.assertIn(
            "**Whether the project practises test-driven development at all**",
            flat(REFERENCES / "schools.md"),
        )
        self.assertIn(
            "do not impose the cycle on a project that has not declared it",
            yamlio.load_file(SKILL / "agents" / "openai.yaml")["interface"][
                "default_prompt"
            ],
        )

    def test_the_evidence_rule_is_not_scoped_to_that_declaration(self):
        # False-positive guard for the test above: the one rule of this file
        # that holds unconditionally must be stated unconditionally in
        # SKILL.md too, not behind the cycle's "where declared".
        body = flat(SKILL / "SKILL.md")
        self.assertIn(
            "A test that has never been observed to fail for its own reason "
            "is not yet evidence.",
            body,
        )

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (self.RULE_EVIDENCE, self.RULE_CONDITIONAL):
            self.assertEqual(text.count(needle), 1, needle)


class TestDesignFeedbackGuidance(unittest.TestCase):
    """A painful test is a report on the product, not on the test file.

    The pre-existing references answer "is this test any good?" in seven
    ways and never answer the question that follows from a bad answer: the
    code is what made the test bad. Without this file an agent's only
    licensed response to a hundred-line arrange step is to write it more
    tidily.
    """

    DOC = REFERENCES / "tests-as-design-feedback.md"

    RULE_DESIGN_FIRST = "**Change the design first, and the test second.**"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_every_symptom_of_the_catalog_is_present(self):
        text = self._text()
        for symptom in (
            "| **A long arrange step**",
            "| **Arrange duplication with no natural home**",
            "| **A slow test** |",
            "| **A fragile test**",
            "| **The urge to reach private state**",
            "| **An act step of more than one call** |",
            "| **No name fits**",
            "| **You cannot replace a collaborator without special machinery**",
            "| **A long construction argument list** |",
            "| **A long argument list that will not group** |",
            "| **The test class for one type falls into slices that share "
            "nothing** |",
            "| **Every interaction in the test is required, so none stands "
            "out** |",
        ):
            self.assertIn(symptom, text, symptom)

    def test_a_hidden_dependency_is_diagnosed_rather_than_worked_around(self):
        # Tooling that intercepts a global without touching the code makes the
        # test pass and spends the only signal the design weakness was giving.
        text = self._text()
        self.assertIn("## Implicit dependencies are still dependencies", text)
        self.assertIn(
            "**Tools that break such dependencies without touching the code "
            "spend the feedback.**",
            text,
        )
        self.assertIn("**The seam is often not the end of the improvement.**", text)

    def test_support_reporting_is_separated_from_diagnostic_tracing(self):
        # Treated as one thing, reporting is either all test-driven (absurd)
        # or none of it is (and the audit trail nobody tested breaks silently).
        text = self._text()
        self.assertIn(
            "## Support reporting is a feature; diagnostic tracing is "
            "scaffolding",
            text,
        )
        self.assertIn("| **Support reporting** | **Diagnostic tracing** |", text)
        self.assertIn("**test-driven, like any other output**", text)
        self.assertIn(
            '**"I would have to pass a reporter everywhere"** is itself the '
            "signal.",
            text,
        )

    def test_each_symptom_names_the_change_it_asks_for(self):
        # A symptom list with no prescribed response is a diagnosis nobody
        # can act on; the table's third column is the load-bearing one.
        text = self._text()
        self.assertIn(
            "| Symptom in the test | What it says about the code | The change "
            "it asks for |",
            text,
        )
        self.assertIn(self.RULE_DESIGN_FIRST, text)

    def test_the_rule_ships_its_escape_valve(self):
        # Stated without one, the rule licenses blocking on a design insight
        # that may not arrive — so the honest fallback is part of the rule.
        text = self._text()
        self.assertIn("**if the design idea does not come, it does not come.**", text)
        self.assertIn("with the cost recorded rather than hidden", text)

    def test_isolation_is_named_as_a_design_force(self):
        text = self._text()
        self.assertIn(
            "**Isolating tests from one another is a design force, not just a "
            "hygiene rule.**",
            text,
        )

    def test_the_file_states_what_it_does_not_license(self):
        # False-positive guard against the obvious misreading: "the design is
        # to blame" must not become a licence to widen a surface or to test
        # everything.
        text = self._text()
        self.assertIn("## What this does not license", text)
        self.assertIn(
            "A member made public so a test can reach it is a design made "
            "worse to make a test easier",
            text,
        )

    def test_rule_is_not_accidentally_duplicated(self):
        self.assertEqual(self._text().count(self.RULE_DESIGN_FIRST), 1)


class TestInterfaceDiscoveryGuidance(unittest.TestCase):
    """The London school's own technique, kept when its outer loop went.

    ``schools.md`` catalogued London and named its cost — replacing every
    collaboration binds the tests to *how* the unit reaches its result —
    while every operational file in the skill was calibrated against the
    classical school's primary source. An agent told to follow a declared
    London project therefore had a catalog entry and nothing to act on: no
    account of where the doubled collaborators come from, and no
    discipline for paying the cost the catalog warned about.

    The account of it that lives here is the unit-test half. Its former
    home also carried a feature-level outer loop driven by tests of a
    deployed system, which is outside this skill's two levels and is not
    replaced by anything.
    """

    DOC = REFERENCES / "interface-discovery.md"

    RULE_NOT_YET = "**The collaborator does not exist yet**"
    RULE_PULL_NOT_PUSH = (
        "**Pull interfaces into existence from the client, do not push them "
        "out from the implementation.**"
    )
    RULE_NARROW = "**Keep the discovered surface narrow.**"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_discovery_is_presented_as_the_source_of_the_doubles(self):
        # Without this, London's heavy use of doubles looks like a taste for
        # mocking rather than the mechanism by which collaborators are found.
        text = self._text()
        self.assertIn(self.RULE_NOT_YET, text)
        self.assertIn('**"If this worked, who would know?"**', text)
        self.assertIn(self.RULE_PULL_NOT_PUSH, text)
        self.assertIn(self.RULE_NARROW, text)

    def test_the_loop_names_the_role_before_any_implementation_exists(self):
        text = self._text()
        self.assertIn("## The loop, per object", text)
        self.assertIn("**Name the service in the client's terms**", text)

    def test_the_technique_is_scoped_to_a_project_declaration(self):
        # Same contract as the cycle: universal skill, opt-in technique. Under
        # the classical school the collaborators are real and none of this
        # applies.
        text = self._text()
        self.assertIn(
            "it applies where the host project declares the London school",
            text,
        )
        self.assertIn(
            "Under the classical school the collaborators are mostly real, "
            "and this file does not apply.",
            text,
        )
        self.assertIn(
            "**Where the project declares London, discover each collaborator "
            "from its client.**",
            flat(SKILL / "SKILL.md"),
        )

    def test_the_cost_of_discovery_is_named_with_what_pays_it_down(self):
        # A technique that manufactures doubles, offered without the rules
        # that keep a double-heavy suite survivable, is the cost alone.
        text = self._text()
        self.assertIn("## What discovery costs, and the discipline that pays it", text)
        self.assertIn(
            "**A project that declares London and skips these has bought the "
            "cost without the benefit.**",
            text,
        )

    def test_the_file_states_what_discovery_cannot_establish(self):
        # False-positive guard: naming collaborators well says nothing about
        # whether the assembled product runs — and that question is out of
        # this skill's scope rather than answered by it.
        text = self._text()
        self.assertIn("## Where this does not reach", text)
        self.assertIn(
            "whether the entry point reaches your objects at all", text
        )

    def test_schools_file_routes_london_to_its_discipline(self):
        # The catalog entry must not keep naming a cost with no remedy.
        text = flat(REFERENCES / "schools.md")
        self.assertIn(
            "**The discipline that pays that cost down is not optional under "
            "this school**",
            text,
        )
        self.assertIn("interface-discovery.md", text)

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (self.RULE_NOT_YET, self.RULE_PULL_NOT_PUSH, self.RULE_NARROW):
            self.assertEqual(text.count(needle), 1, needle)


class TestLevelsGuidance(unittest.TestCase):
    """Two levels, two questions, and a line the schools draw differently.

    The skill judged tests without ever saying which kind of test it was
    judging, so nothing objected when a unit test quietly acquired a real
    connection: it kept being run and trusted as a fast, isolated test
    while being neither.

    The second half is what makes the rule enforceable rather than
    rhetorical. "Move it to the integration suite" presupposes a boundary,
    and the two schools put it in different places — so a file that stated
    one would be legislating the school the rest of the skill refuses to
    pick.
    """

    DOC = REFERENCES / "test-levels.md"

    RULE_NO_QUIET_PROMOTION = (
        "**Never let an integration test grow quietly inside the unit "
        "suite.**"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_each_level_is_defined_by_the_question_it_answers(self):
        text = self._text()
        self.assertIn(
            "| **Unit** | do our objects do the right thing, and are they "
            "convenient to work with? |",
            text,
        )
        self.assertIn(
            "| **Integration** | does our code work against code we cannot "
            "change? |",
            text,
        )

    def test_the_line_between_them_is_owned_by_the_declared_school(self):
        text = self._text()
        self.assertIn(
            "## The line between them is what the schools disagree about", text
        )
        self.assertIn(
            "There is no level boundary this skill can hand you", text
        )
        # Each school's own answer, or the section names a disagreement it
        # never resolves for either reader.
        self.assertIn(
            "| **London (mockist)** | every collaborator is a double | any "
            "real collaborator runs |",
            text,
        )
        self.assertIn("| **Classical (Detroit)** |", text)
        self.assertIn("**The project declares which line it draws**", text)

    def test_the_boundary_is_enforced_however_it_was_drawn(self):
        # False-positive guard for the test above: "the school decides" must
        # not read as "so anything goes".
        text = self._text()
        self.assertIn(
            "What does *not* vary by school: once the line is drawn, it is "
            "enforced.",
            text,
        )
        self.assertIn(self.RULE_NO_QUIET_PROMOTION, text)

    def test_writing_a_unit_test_is_what_reports_on_internal_quality(self):
        # The asymmetry is why neither level substitutes for the other.
        text = self._text()
        self.assertIn("**internal quality**", text)
        self.assertIn("**configuration and assumptions**", text)
        self.assertIn("Neither substitutes for the other.", text)

    def test_the_integration_level_doubles_only_the_callback_you_own(self):
        text = self._text()
        self.assertIn(
            "### The one thing you do double in an integration test", text
        )
        self.assertIn("**Doubles are of limited use here by construction.**", text)

    def test_the_split_between_the_two_levels_is_revisited(self):
        text = self._text()
        self.assertIn(
            "**The split between what is unit-tested with doubles and what is "
            "left to integration is a decision the project revisits, not a "
            "constant.**",
            text,
        )

    def test_fidelity_trades_are_named_rather_than_assumed(self):
        text = self._text()
        self.assertIn("**Name the gap and cover it somewhere.**", text)

    def test_rule_is_not_accidentally_duplicated(self):
        self.assertEqual(self._text().count(self.RULE_NO_QUIET_PROMOTION), 1)


class TestDiagnosticsGuidance(unittest.TestCase):
    """The report step: a failure nobody can read is a test nobody keeps.

    The skill already required that a test be *seen* red before it counts
    as evidence, and stopped there. Seeing a red bar says nothing about
    whether the message explains the failure — so an agent could satisfy
    the evidence rule in full and still ship a test that, on the day it
    fires, sends its reader to a debugger.
    """

    DOC = REFERENCES / "test-diagnostics.md"

    RULE_FAIL_WELL = "**The point of a test is not to pass but to fail well.**"
    RULE_REPORT_STEP = (
        "| 3 | **Read the failure message; improve it if it does not explain "
        "itself** | it would tell a stranger what is wrong |"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_the_purpose_of_a_test_is_stated_as_failing_well(self):
        self.assertIn(self.RULE_FAIL_WELL, self._text())

    def test_the_cycle_gained_the_report_step_in_both_files(self):
        self.assertIn("## The cycle has four steps, not three", self._text())
        cycle = flat(REFERENCES / "tdd-cycle.md")
        self.assertIn(self.RULE_REPORT_STEP, cycle)
        self.assertIn("**Step 3 is not optional and does not belong later.**", cycle)

    def test_the_report_step_precedes_the_production_code(self):
        # Placed after the code is written, it becomes a review chore nobody
        # does; placed before, it is the moment the intent gets clarified.
        text = self._text()
        self.assertIn("**before any production code is written**", text)
        self.assertIn(
            "**Read the failure before writing the code that fixes it.**",
            flat(SKILL / "SKILL.md"),
        )

    def test_the_three_value_shaping_techniques_are_present(self):
        text = self._text()
        for technique in (
            "**Self-describing value.**",
            "**Obviously canned value.**",
            "**Tracer object.**",
        ):
            self.assertIn(technique, text, technique)

    def test_the_cause_is_reported_rather_than_the_consequence(self):
        text = self._text()
        self.assertIn(
            "**Check the interactions explicitly before the value "
            "assertions**",
            text,
        )

    def test_rules_are_not_accidentally_duplicated(self):
        self.assertEqual(self._text().count(self.RULE_FAIL_WELL), 1)
        self.assertEqual(flat(REFERENCES / "tdd-cycle.md").count(self.RULE_REPORT_STEP), 1)


class TestDataBuilderGuidance(unittest.TestCase):
    """How the arrange step scales, and the trap in the obvious refactorings.

    ``structure-and-naming.md`` carried a single line preferring builders to
    copy-pasted fixtures, which is advice rather than a rule: it does not
    say when a factory method is enough, it does not warn that a reused
    chainable builder leaks one object's override into the next, and it
    does not stop a shared helper from growing an overload per variation.
    """

    DOC = REFERENCES / "test-data-builders.md"

    RULE_SHARED_BUILDER_TRAP = (
        "**This is only safe while the objects differ in the *same* field.**"
    )
    RULE_PASS_THE_BUILDER = (
        "**Pass the builder into the helper instead of its arguments.**"
    )
    RULE_SAFE_DEFAULTS = "**Defaults must be safe, not realistic.**"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_the_three_approaches_are_ranked_by_where_each_stops_working(self):
        text = self._text()
        for row in (
            "| **Literal construction** |",
            "| **Named factory method** |",
            "| **Builder** |",
        ):
            self.assertIn(row, text, row)
        self.assertIn(
            "**A named factory method is the right answer where there is no "
            "variation.**",
            text,
        )

    def test_defaults_must_be_unable_to_decide_a_test(self):
        self.assertIn(self.RULE_SAFE_DEFAULTS, self._text())

    def test_the_shared_builder_accumulation_trap_is_pinned(self):
        text = self._text()
        self.assertIn(self.RULE_SHARED_BUILDER_TRAP, text)
        # And both escapes, since the trap is silent without one of them.
        self.assertIn("**Copy the builder**", text)
        self.assertIn("**Make the override steps functional**", text)

    def test_builders_are_passed_rather_than_the_objects_they_produce(self):
        self.assertIn(
            "**pass the builders, not the objects they produce**", self._text()
        )

    def test_the_helper_takes_a_builder_not_its_arguments(self):
        # The alternative is the object-mother explosion, one overload per
        # variation, which is the whole reason builders were introduced.
        self.assertIn(self.RULE_PASS_THE_BUILDER, self._text())

    def test_the_limit_of_abstracting_the_arrange_step_is_stated(self):
        # False-positive guard: "factor it out" must not become licence to
        # make a test unreadable.
        self.assertIn(
            "**a test can become so declarative that a reader can no longer "
            "tell what it does.**",
            self._text(),
        )

    def test_structure_file_routes_to_the_builder_rules(self):
        self.assertIn("test-data-builders.md", flat(REFERENCES / "structure-and-naming.md"))

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (
            self.RULE_SHARED_BUILDER_TRAP,
            self.RULE_PASS_THE_BUILDER,
            self.RULE_SAFE_DEFAULTS,
        ):
            self.assertEqual(text.count(needle), 1, needle)


class TestAsyncAndConcurrencyGuidance(unittest.TestCase):
    """Two whole failure families the skill previously covered in four lines.

    ``isolation-and-fakes.md`` said not to sleep and to give every awaited
    assertion a deadline. Neither rule catches the shape below, which is a
    false positive rather than a slow test: an asynchronous test that waits
    for a state the system was *already* in is satisfied before the system
    has begun, and stays green when the work never happens at all.
    """

    DOC = REFERENCES / "async-and-concurrency.md"

    RULE_RUNAWAY = (
        "**An asynchronous test that asserts the system is in a state it was "
        "already in can pass before the system has started.**"
    )
    RULE_LOST_UPDATES = "**Lost updates are the sampling-specific failure.**"
    RULE_SPLIT_POLICY = (
        "**Take the scheduling out of the object and pass it in.**"
    )
    RULE_EXTERNALIZE = (
        "**A system that schedules its own activity internally cannot be "
        "tested deterministically.**"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_functionality_and_concurrency_policy_are_separated(self):
        text = self._text()
        self.assertIn(self.RULE_SPLIT_POLICY, text)
        self.assertIn("| **Functional tests** |", text)
        self.assertIn("| **Synchronization tests** |", text)
        self.assertIn("**Write both kinds of test before writing the code.**", text)

    def test_the_wait_asymmetry_is_pinned(self):
        text = self._text()
        self.assertIn("## Wait for success; time out for failure", text)
        self.assertIn("**Succeed fast.**", text)
        self.assertIn("**Keep the timeout value in one place.**", text)

    def test_sampling_and_listening_are_compared_by_their_blind_spot(self):
        text = self._text()
        self.assertIn("| **Listening** | **Sampling** |", text)
        self.assertIn(self.RULE_LOST_UPDATES, text)

    def test_the_runaway_test_rule_ships_its_reproduction(self):
        # The rule is only actionable with the shape in front of you: the
        # assertion looks correct and the test looks like it passed.
        text = self._text()
        self.assertIn(self.RULE_RUNAWAY, text)
        self.assertIn("**Minimal reproduction.** The holding for a stock starts at zero.", text)
        self.assertIn(
            "**wherever an asynchronous test expects the system to return to "
            "a previous state, it must first wait for a state it could not "
            "already have been in.**",
            text,
        )

    def test_the_runaway_tell_is_reachable_from_skill_md(self):
        # Measured against the live gate: an agent that never opened this file
        # diagnosed the reproduction as merely tautological and missed the
        # asynchronous point — that the wait was satisfied before it began.
        # The tell has to survive in the file that is always loaded.
        body = flat(SKILL / "SKILL.md")
        self.assertIn(
            "**A wait whose condition already held at the starting state "
            "never waited for anything**",
            body,
        )
        self.assertIn("a quantity that returns to the value it began at", body)
        self.assertIn(
            "wait for a state the initial one could not have been in", body
        )

    def test_asserting_an_absence_of_effect_has_its_own_technique(self):
        text = self._text()
        self.assertIn("## Testing that an action has *no* effect", text)
        self.assertIn(
            "**Trigger a second action that is detectable and must complete "
            "after the first, then assert on that.**",
            text,
        )

    def test_synchronizing_is_named_apart_from_asserting(self):
        text = self._text()
        self.assertIn("## Distinguish synchronizing from asserting", text)
        self.assertIn("**Name them apart**", text)

    def test_the_stress_test_procedure_requires_a_dependable_failure_first(self):
        text = self._text()
        self.assertIn("**Watch it fail, and tune until it fails on every run.**", text)
        self.assertIn(
            "**Making a single field atomic is not the same as making an "
            "operation atomic.**",
            text,
        )
        self.assertIn(
            "**Stress tests buy a degree of reassurance, never a "
            "guarantee.**",
            text,
        )

    def test_flickering_is_treated_as_breakage_in_both_files(self):
        self.assertIn("## Flickering tests are broken tests", self._text())
        self.assertIn(
            "**A test that fails intermittently is a broken test, not a "
            "mostly working one.**",
            flat(REFERENCES / "hygiene.md"),
        )

    def test_self_scheduled_activity_is_pulled_out(self):
        self.assertIn(self.RULE_EXTERNALIZE, self._text())

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (
            self.RULE_RUNAWAY,
            self.RULE_LOST_UPDATES,
            self.RULE_SPLIT_POLICY,
            self.RULE_EXTERNALIZE,
        ):
            self.assertEqual(text.count(needle), 1, needle)


class TestAdaptersAndPersistenceGuidance(unittest.TestCase):
    """Tests whose subject is a mapping onto infrastructure you do not own.

    Two of these rules are silent-failure rules rather than convenience
    rules: isolating a test by rolling its transaction back never exercises
    the commit where constraints actually fire, and exercising generic
    mapping code with a production domain type leaves the suite green over
    a case that stopped existing when someone edited that type.
    """

    DOC = REFERENCES / "adapters-and-persistence.md"

    RULE_CLEAN_AT_START = (
        "## Clean persistent state at the *start* of a test, not at the end"
    )
    RULE_NO_ROLLBACK_ISOLATION = "**Commit is where the work happens.**"
    RULE_SILENT_ROT = "**Silent rot.**"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_persistent_state_is_cleaned_on_the_way_in(self):
        text = self._text()
        self.assertIn(self.RULE_CLEAN_AT_START, text)
        self.assertIn("| Clean at the start | Clean at the end |", text)

    def test_rollback_isolation_is_rejected_with_its_reason(self):
        text = self._text()
        self.assertIn(self.RULE_NO_ROLLBACK_ISOLATION, text)
        self.assertIn(
            "**Interactions between transactions become untestable**", text
        )

    def test_round_trip_tests_localize_mapping_failures(self):
        text = self._text()
        self.assertIn("## Round-trip the mapping, one entity at a time", text)
        self.assertIn(
            "Applies to every reflective translation, not only databases", text
        )

    def test_the_reflection_exception_is_argued_and_bounded(self):
        # An unbounded exception to "never reach into private state" would
        # dissolve the rule it is an exception to.
        text = self._text()
        self.assertIn("### Reflection is legitimate here, and only here", text)
        self.assertIn(
            "**The subject is the mapping configuration, not the object's "
            "design.**",
            text,
        )
        self.assertIn(
            "It licenses round-tripping a mapped type; it does not license "
            "reaching into private state in any test whose subject is your "
            "own behaviour.",
            text,
        )
        # And the anti-pattern file it qualifies points back at it.
        anti = flat(REFERENCES / "anti-patterns.md")
        self.assertIn(
            "**The one sanctioned exception is a round-trip test of a "
            "reflective mapping**",
            anti,
        )

    def test_guinea_pig_types_are_required_for_generic_mapping_code(self):
        text = self._text()
        self.assertIn(
            "## Do not exercise generic mapping code with production domain "
            "types",
            text,
        )
        self.assertIn(self.RULE_SILENT_ROT, text)
        self.assertIn("**and no test fails.**", text)

    def test_the_cleanup_position_is_reachable_from_skill_md(self):
        # The rule lived only here, and a question that never opens this file
        # gets the habitual answer instead: clean up in teardown. It has to
        # survive in the file that is always loaded.
        body = flat(SKILL / "SKILL.md")
        self.assertIn(
            "Persistent state is cleaned at the **start** of a test, not at "
            "the end",
            body,
        )
        self.assertIn("Nor is a test isolated by rolling its transaction back", body)
        self.assertIn("never commits never exercises any of it", body)

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (
            self.RULE_CLEAN_AT_START,
            self.RULE_NO_ROLLBACK_ISOLATION,
            self.RULE_SILENT_ROT,
        ):
            self.assertEqual(text.count(needle), 1, needle)


class TestPeerStereotypesAndSubstitutionBoundary(unittest.TestCase):
    """What may be replaced at all, before what a double may assert.

    "Fake the seams the code exposes, never someone else's internals" was
    the whole boundary the skill drew. It does not say what makes something
    a seam rather than an internal of the subject itself, and it gives no
    vocabulary for the constructor-shaped design feedback that follows —
    which is why a bloated argument list had no diagnosis in the skill.
    """

    DOC = REFERENCES / "isolation-and-fakes.md"

    RULE_ONLY_PEERS = "**Only peers are ever replaced.**"
    RULE_NAMED_ROLE = "**Double a named role, not a concrete type.**"

    def _text(self) -> str:
        return flat(self.DOC)

    def test_the_peer_versus_internal_boundary_is_drawn(self):
        text = self._text()
        self.assertIn("## Peers, not internals", text)
        self.assertIn(self.RULE_ONLY_PEERS, text)
        self.assertIn(
            "they disagree about *which* peers are replaced, never about "
            "peers versus internals",
            text,
        )

    def test_the_three_kinds_of_peer_are_distinguished_by_their_defaults(self):
        text = self._text()
        self.assertIn(
            "| **Dependency** | a service the subject cannot function "
            "without | required at construction | **none exists** |",
            text,
        )
        self.assertIn("| **Notification** |", text)
        self.assertIn("| **Adjustment** |", text)
        self.assertIn(
            "**A dependency has no safe default, so it is required at "
            "construction.**",
            text,
        )
        # Contextual, not intrinsic — otherwise the table reads as a taxonomy
        # of types rather than of relationships.
        self.assertIn(
            "The classification is contextual, not intrinsic.", text
        )

    def test_a_named_role_is_preferred_to_a_concrete_type(self):
        text = self._text()
        self.assertIn(self.RULE_NAMED_ROLE, text)
        self.assertIn("**Do not override a type's internal features, ever**", text)

    def test_skill_md_carries_the_boundary_and_the_stereotypes(self):
        body = flat(SKILL / "SKILL.md")
        self.assertIn("Replace **peers**, never internals.", body)
        self.assertIn("Distinguish the three kinds of peer:", body)

    def test_negative_the_pre_existing_seam_rule_survives_untouched(self):
        # False-positive guard: the peer vocabulary must refine the seam rule,
        # not replace or duplicate it.
        text = self._text()
        self.assertEqual(text.count("never someone else's internals"), 1, text)
        self.assertEqual(text.count("**Double only types you own.**"), 1, text)

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (self.RULE_ONLY_PEERS, self.RULE_NAMED_ROLE):
            self.assertEqual(text.count(needle), 1, needle)


class TestInteractionPrecisionGuidance(unittest.TestCase):
    """The discipline that makes an interaction-heavy suite survivable.

    The skill ranked the three verification styles and said where an
    interaction may be asserted, then stopped. It never said how *tightly*
    to pin one — so a test could legitimately assert a boundary-crossing
    call and still go red when a cache was introduced, an argument gained a
    field, or two independent calls swapped order.
    """

    DOC = REFERENCES / "unit-test-value.md"

    RULE_HEADING = "### Specify precisely what should happen, and no more"
    RULE_QUERIES_COMMANDS = "**Allow queries; expect commands.**"
    RULE_FEW = "**Write few expectations.**"
    RULE_ORDER = (
        "**Constrain call order only where the order is part of the "
        "contract.**"
    )

    def _text(self) -> str:
        return flat(self.DOC)

    def test_the_precision_rule_is_present(self):
        self.assertIn(self.RULE_HEADING, self._text())

    def test_cardinality_follows_the_command_query_split(self):
        text = self._text()
        self.assertIn(self.RULE_QUERIES_COMMANDS, text)
        # And its own exception, or the rule forbids testing a cache.
        self.assertIn(
            "Where the *subject* is a cache, the call count is the "
            "behaviour, and then you do pin it.",
            text,
        )

    def test_expectations_are_kept_few_and_arguments_loosely_matched(self):
        text = self._text()
        self.assertIn(self.RULE_FEW, text)
        self.assertIn(
            "**Match arguments only as precisely as the scenario constrains "
            "them.**",
            text,
        )

    def test_call_order_is_pinned_only_when_contractual(self):
        self.assertIn(self.RULE_ORDER, self._text())

    def test_ignoring_a_peer_does_not_contradict_asserting_both_directions(self):
        # These two read as a contradiction unless the scopes are written
        # down: one governs the dependency under test, the other the peers
        # that are not.
        text = self._text()
        self.assertIn("**Ignoring a collaborator wholesale is a power tool.**", text)
        self.assertIn(
            "that rule governs the dependency the test is about, this one "
            "governs the ones it is not",
            text,
        )
        self.assertEqual(text.count("**Assert in both directions**"), 1)

    def test_skill_md_and_schools_carry_the_rule(self):
        self.assertIn(
            "**Specify precisely what should happen and no more.**",
            flat(SKILL / "SKILL.md"),
        )
        self.assertIn(
            "allow queries and expect only commands", flat(REFERENCES / "schools.md")
        )

    def test_rules_are_not_accidentally_duplicated(self):
        text = self._text()
        for needle in (
            self.RULE_HEADING,
            self.RULE_QUERIES_COMMANDS,
            self.RULE_FEW,
            self.RULE_ORDER,
        ):
            self.assertEqual(text.count(needle), 1, needle)


class TestCoexistenceBoundariesWithPreExistingRules(unittest.TestCase):
    """Four places where the process rules and the artifact rules collide.

    Each pair below reads as a contradiction unless the boundary between
    them is written down: a reader who meets only one half applies it to
    the other half's case. These pins exist because dropping a boundary
    clause is a silent, plausible edit that leaves both rules intact and
    the skill self-contradicting.
    """

    def test_a_constant_first_implementation_is_distinguished_from_a_tuned_test(self):
        cycle = flat(REFERENCES / "tdd-cycle.md")
        hygiene = flat(REFERENCES / "hygiene.md")
        self.assertIn("**Faking it is not tuning a test to the gate.**", cycle)
        self.assertIn("the constant goes into the *production* code", cycle.lower())
        # And the rule it is being distinguished from is still there, once.
        self.assertEqual(
            hygiene.count('never hardcode an expected value "so it passes"'), 1
        )
        self.assertIn(
            "a deliberately constant first implementation in the *production* "
            "code",
            hygiene,
        )

    def test_a_red_test_after_a_refactor_is_investigated_before_the_expectation_moves(
        self,
    ):
        # "Do not tune a test to the gate" reads as being about laziness, so a
        # refactor that intentionally changed behaviour looks like a licensed
        # exception and refreshing the snapshot looks like the normal
        # workflow. What closes it is that a refactor changes no behaviour by
        # definition: a red one is a finding, and the replacement expectation
        # comes from the specification rather than from the new output.
        hygiene = flat(REFERENCES / "hygiene.md")
        body = flat(SKILL / "SKILL.md")
        for text in (hygiene, body):
            self.assertIn(
                "refactor that changes no behaviour cannot turn a test red", text
            )
            self.assertIn("more than a refactor or it introduced a defect", text)
        self.assertIn(
            "never read back from what the code now produces", hygiene
        )
        # The refusal has to lead: measured against the live gate, an agent
        # that meets the "behaviour changed on purpose" branch first answers
        # "yes, that's the normal move" and never reaches the rest.
        self.assertIn(
            "**A red test is answered with a diagnosis, never with a "
            "refreshed expectation**",
            body,
        )
        self.assertLess(
            body.index("answered with a diagnosis"),
            body.index("did change on purpose"),
            "the refusal must precede the intentional-change branch",
        )
        self.assertIn(
            "rather than reading it back from what the code now produces", body
        )
        # And the rule this clause extends survives, exactly once.
        self.assertEqual(hygiene.count("**Do not tune a test to the gate:**"), 1)

    def test_visible_derivation_is_distinguished_from_leaking_the_algorithm(self):
        structure = flat(REFERENCES / "structure-and-naming.md")
        anti = flat(REFERENCES / "anti-patterns.md")
        self.assertIn(
            "**Make the relationship between input and expected value "
            "visible.**",
            structure,
        )
        self.assertIn(
            "**This is not recomputing the expected value with the code under "
            "test.**",
            structure,
        )
        self.assertIn("**Where the boundary runs.**", anti)
        self.assertIn(
            "not that it computes, but *whose* computation it reuses", anti
        )
        # The anti-pattern's own prescription survives, exactly once.
        self.assertEqual(anti.count("**Hardcode the expected results**"), 1)

    def test_an_unfinished_test_is_kept_local_rather_than_silenced(self):
        # "Never more than one red test at a time" tells you to leave one
        # red; "no committed skip markers" forbids the obvious way to carry
        # it. Without the boundary between them an agent silences the test,
        # which is the one resolution both rules reject.
        hygiene = flat(REFERENCES / "hygiene.md")
        self.assertIn(
            "**while it is red it stays in the working copy**", hygiene
        )
        self.assertIn("**Never share a red suite.**", hygiene)
        # And the rule it is being distinguished from survives, exactly once.
        self.assertEqual(hygiene.count("**No focused or skipped tests committed.**"), 1)

    def test_the_silence_stays_forbidden_under_a_different_marker(self):
        # The documented-skip exception one clause above is the loophole an
        # agent takes: it re-emerges as "commit it as an expected failure
        # with a tracking ticket", which is the same silenced test in a
        # suite that is supposed to be green.
        hygiene = flat(REFERENCES / "hygiene.md")
        self.assertIn("**Renaming the silence does not lift the rule:**", hygiene)
        self.assertIn("expected-failure or pending marker", hygiene)
        self.assertIn(
            "it never covers a test whose behaviour is simply not written yet",
            hygiene,
        )

    def test_the_unfinished_test_resolution_is_reachable_from_skill_md(self):
        # Both rules already lived in hygiene.md, and an agent answering a
        # one-line question never opened it: the resolution has to survive in
        # the file that is always loaded, not only in the reference.
        body = flat(SKILL / "SKILL.md")
        self.assertIn(
            "A test that is red only because its behaviour is not written yet "
            "stays in the working copy until it passes",
            body,
        )
        self.assertIn("renaming the silence to an expected-failure or pending marker", body)
        self.assertIn("references/hygiene.md", body)

    def test_naming_the_expected_value_is_scoped_apart_from_over_asserting(self):
        # "Say exactly 50" and "do not assert what the inputs did not drive"
        # are halves of one rule; separated, the first licenses comparing
        # whole structures and the second licenses asserting nothing.
        text = flat(REFERENCES / "structure-and-naming.md")
        self.assertIn(
            "**Name the expected value; do not settle for a property of it.**",
            text,
        )
        self.assertIn(
            "The pair reads as one rule: **exact about the claim, silent "
            "about the rest.**",
            text,
        )

    def test_the_classical_direction_is_corrected_against_its_primary_sources(self):
        # The pre-existing summary ("inside-out") is not how the classical
        # school describes itself; leaving it unqualified made the skill
        # assert something its own source rejects.
        schools = flat(REFERENCES / "schools.md")
        self.assertIn(
            "**Test-driven development is usually summarized as running "
            "inside-out**",
            schools,
        )
        self.assertIn(
            "the school's primary sources reject the vertical metaphor "
            "outright",
            schools,
        )
        self.assertIn(
            "The direction that predicts anything is **known-to-unknown**",
            schools,
        )
        # London's outside-in direction is a live claim of that school and
        # stays — as a statement about how its collaborators are discovered,
        # which is a unit-level technique, not about a feature-level loop.
        self.assertIn("**Development runs outside-in**", schools)
        self.assertIn("interface-discovery.md", schools)


class TestDataDeletionAndScopeRules(unittest.TestCase):
    """Smaller rules the process work brought with it, pinned where they live."""

    def test_the_data_a_test_carries_is_governed(self):
        text = flat(REFERENCES / "structure-and-naming.md")
        self.assertIn("## The data a test carries", text)
        self.assertIn("**Never let one constant mean two things in the same test.**", text)
        self.assertIn("**Use the smallest data that forces the same decisions.**", text)
        self.assertIn("**Realistic data is for the cases that require it**", text)

    def test_an_assertion_names_the_value_not_a_property_of_it(self):
        text = flat(REFERENCES / "structure-and-naming.md")
        self.assertIn(
            "**Name the expected value; do not settle for a property of it.**", text
        )

    def test_assert_first_is_offered_as_a_writing_order(self):
        text = flat(REFERENCES / "structure-and-naming.md")
        self.assertIn(
            "**Write it backwards when the shape is unclear: assertion "
            "first.**",
            text,
        )

    def test_deletion_requires_both_criteria(self):
        text = flat(REFERENCES / "hygiene.md")
        self.assertIn("## When a test may be deleted", text)
        self.assertIn("| **Confidence** |", text)
        self.assertIn("| **Communication** |", text)
        self.assertIn("**Deleting a test is a change to what the suite claims.**", text)

    def test_only_code_you_wrote_is_on_the_hook(self):
        text = flat(REFERENCES / "unit-test-value.md")
        self.assertIn("### What is on the hook, and how deep to go", text)
        self.assertIn("**Do not test other people's code.**", text)
        self.assertIn("**Depth is calibrated by the cost of being wrong.**", text)

    def test_the_external_observation_has_a_lifecycle(self):
        text = flat(REFERENCES / "isolation-and-fakes.md")
        self.assertIn("### The observation is a test, and it has a lifecycle", text)
        self.assertIn(
            "**Re-run it on every upgrade of that dependency, before anything "
            "else.**",
            text,
        )
        self.assertIn(
            "**The fake and the real thing should answer to the same tests.**", text
        )

    def test_negative_the_live_observation_rule_it_extends_survives_untouched(self):
        # False-positive guard: the lifecycle subsection must extend the
        # provenance rule, not restate or replace it.
        text = flat(REFERENCES / "isolation-and-fakes.md")
        self.assertEqual(
            text.count(
                "no fake, and no re-reading of a project norm, an RFC, or "
                "vendor documentation, can establish what that system "
                "actually does"
            ),
            1,
        )


class TestRulesAreNotDuplicatedInOtherSkills(unittest.TestCase):
    """The split is only worth its cost while the rules live in one place.

    Every anchor pinned above must be absent from the standards that also
    speak about tests: the language ones keep spelling maps ("how a rule is
    expressed in this language") and the framework one keeps its own seams,
    not copies of the rules. A silent re-import of any clause into any of
    them is exactly the drift this skill exists to prevent.

    Verbatim copies are what this catches. A *paraphrase* of a rule reads
    differently and slips through, so the anchors are a backstop for drift,
    never the whole review.
    """

    SKILLS_THAT_MUST_NOT_RESTATE = (
        "python-coding",
        "typescript-coding",
        "typescript-nestjs",
    )

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
        "**A test that has never been observed to fail is not yet evidence "
        "of anything.**",
        "**Change the design first, and the test second.**",
        "**Faking it is not tuning a test to the gate.**",
        "**An asynchronous test that asserts the system is in a state it was "
        "already in can pass before the system has started.**",
        "**Pass the builder into the helper instead of its arguments.**",
        "**Only peers are ever replaced.**",
        "**Allow queries; expect commands.**",
        "**The point of a test is not to pass but to fail well.**",
        "**Never let an integration test grow quietly inside the unit "
        "suite.**",
        "**Commit is where the work happens.**",
        "**Pull interfaces into existence from the client, do not push them "
        "out from the implementation.**",
    )

    def test_no_universal_rule_text_remains_in_another_skill(self):
        for skill in self.SKILLS_THAT_MUST_NOT_RESTATE:
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

    def test_adapter_carries_every_axis_the_skill_owns(self):
        # A harness that only reads this prompt must not silently lose a
        # whole axis of the standard; each needle below is the shortest
        # phrase that can only have come from its own reference file.
        prompt = yamlio.load_file(SKILL / "agents" / "openai.yaml")["interface"][
            "default_prompt"
        ]
        for needle in (
            "the cycle having four steps (fail, report, pass, refactor)",
            "the level a test belongs to be chosen deliberately and kept",
            "replacing peers and never internals",
            "distinguishing dependencies (required at construction, no safe "
            "default) from notifications and adjustments",
            "queries allowed any number of times, commands expected exactly "
            "as often as the contract says",
            "helpers that take a builder rather than its arguments",
            "never asserting a state the system could already have been in "
            "before it started",
            "generic mapping code exercised with purpose-built types",
            "persistent state cleaned at the start of a test rather than at "
            "the end",
            "no flickering test tolerated",
            "Where the project declares the London school",
            "the role is named from the point of view of the object that "
            "needs it before any implementation of it exists",
        ):
            self.assertIn(needle, prompt, needle)

    def test_adapter_does_not_impose_the_declared_only_processes(self):
        prompt = yamlio.load_file(SKILL / "agents" / "openai.yaml")["interface"][
            "default_prompt"
        ]
        self.assertIn("do not impose the cycle on a project that has not declared it", prompt)
        self.assertIn(
            "do not impose interface discovery on a project that has not "
            "declared London",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
