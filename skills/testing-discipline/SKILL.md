---
name: testing-discipline
description: Universal discipline for tests, with no language, runner, framework, or platform assumptions. The unit-testing school — London (mockist) or classical (Detroit) — is declared by the host project's rules, never here. No change without its tests; every bug fix ships a regression test that fails first; Arrange/Act/Assert, one scenario per test, names stating behaviour and condition; unit tests touch nothing external and fake only the seams the code exposes; an external system's fake is pinned by a live observation, not by reading; construction and outbound substitution are tested through the production wiring; judged by protection, refactoring resistance, feedback speed and maintenance cost; assert observable behaviour, never implementation detail; case sets, subjects and dimensions come from the specification, not the artifact under test; suite hygiene — no committed focus/skip, no tuning a test to the gate, determinism, test-only secrets. Use whenever writing, reviewing or reworking tests, in any language.
---

# Testing discipline (universal)

Write tests that establish what they claim to establish. This skill is
**universal by contract**: every rule here holds for any language, test
runner, framework and platform — it assumes no ecosystem, no mocking
library, no architectural style. *How* a rule is spelled in a given
language (which marker, which assertion helper, which patching facility)
belongs to that language's own standard.

It is also **neutral on the unit-testing school**. Whether "isolation"
means isolating the unit from its collaborators (London / mockist) or
isolating the tests from one another (classical / Detroit) is a project
decision that decides which collaborators get a test double, what counts as
a unit, and what counts as an integration test. The host project's rules
declare it and always take precedence; this skill carries the catalog and
the rules that hold either way — see
[references/schools.md](references/schools.md). Wiring conventions for a
ports-and-adapters codebase — which collaborator sits at which seam, where
the DI boundary is — live in the `hexagonal-service` skill; when the host
project uses it, apply that skill on top of this one.

## Workflow

1. **Find the project's declared school.** Read the host project's rules
   for it before deciding what to fake. No declaration but a consistent
   suite → follow the suite and propose recording the choice; neither →
   propose one, get it recorded, then write tests — see
   [references/schools.md](references/schools.md).
2. **Ship the tests with the change.** A code change without its tests is
   not done, and every bug fix ships a regression test that reproduces the
   defect and fails before the fix.
3. **Structure and name each test so it reads as a claim.**
   Arrange/Act/Assert, one act step, no branching, a name that states the
   behaviour and the condition, assertions that pin the error *and* its
   condition — see
   [references/structure-and-naming.md](references/structure-and-naming.md).
4. **Assert observable behaviour, never implementation detail.** Judge the
   test by protection against bugs, resistance to refactoring, feedback
   speed and maintenance cost; prefer output verification to state
   verification and state verification to asserting interactions — see
   [references/unit-test-value.md](references/unit-test-value.md).
5. **Isolate the unit and fake only the seams the code exposes.** No
   network, disk, database or wall-clock dependence; time is injected, not
   slept through; a stub is never asserted on — see
   [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
6. **Pin an external system's behaviour by observing it, not by reading
   about it.** When the property under test belongs to a system this
   project does not own, the fake's contract is established by a probe
   against the real system and then reused as a fixture — see
   [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
7. **Exercise the production wiring, not a hand-built copy of it.** How a
   collaborator gets constructed, and what a client substitutes on the way
   out of a call, are only testable where the product itself does them —
   see [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
8. **Derive the case set, the subject and the dimensions from the
   specification.** Never from the artifact under test: a mutation battery
   can score healthy while the specification stays uncovered — see
   [references/hygiene.md](references/hygiene.md).
9. **Keep the suite honest.** No committed focus/skip markers, no test
   tuned to the gate, no non-determinism, no real credentials — see
   [references/hygiene.md](references/hygiene.md).
10. **Let the static checks and the tests divide the work.** Where the
    project has a type checker, do not test what it already forbids, and do
    test the guards, bypasses and type-level utilities it cannot verify —
    see [references/types-and-tests.md](references/types-and-tests.md).

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Deciding what "isolation" means here, which collaborators get a double, what a unit is, what the project rules must declare | [references/schools.md](references/schools.md) |
| Laying out a test, naming it, asserting an error, grouping similar cases, choosing between example-based and property-based cases | [references/structure-and-naming.md](references/structure-and-naming.md) |
| Judging whether a test is worth keeping, choosing between output/state/interaction verification, deciding what deserves a unit test at all | [references/unit-test-value.md](references/unit-test-value.md) |
| Deciding what a double may stand for, how a fake's contract is established, testing construction or an outgoing call | [references/isolation-and-fakes.md](references/isolation-and-fakes.md) |
| Choosing the case set, judging whether coverage or a mutation score means anything, reviewing suite hygiene | [references/hygiene.md](references/hygiene.md) |
| A test wants to reach a private member, private state, a partially replaced type, the clock, or a shared setup hook | [references/anti-patterns.md](references/anti-patterns.md) |
| The project has a static type checker and you are deciding what still needs a test | [references/types-and-tests.md](references/types-and-tests.md) |

## Rules

- **The school belongs to the project, not to this skill.** Follow the
  declared one; where none is declared, follow the existing suite and
  propose recording the choice — never mix the two by accident.
- A code change without its tests is incomplete; every bug fix ships a
  regression test that fails before the fix and passes after it.
- One scenario per test, one act step, no branching, Arrange/Act/Assert (or
  Given/When/Then), a name that states the behaviour and the condition as a
  fact — never `test_2`, `works`, or the name of the method under test.
- A test is worth its place only if it scores on all four attributes at
  once: protection against bugs, resistance to refactoring, feedback speed,
  maintenance cost. Resistance to refactoring is the one never traded away.
- Assert the observable behaviour — the operations and state a client uses
  to reach a goal — never an implementation detail. Never widen a member's
  visibility to make an assertion possible.
- Prefer output verification, then state verification; assert an
  interaction only when it crosses the application boundary and its effect
  is visible outside — and then assert it at the last seam before the call
  leaves the process, in both directions.
- A unit test touches nothing external: no network, disk, database, or
  wall-clock dependence. Control time by injecting it, preferably as a
  value, never by sleeping and never through an ambient global.
- Fake the seams the code exposes (a parameter, an interface, an injected
  dependency) — never someone else's internals, and only types you own.
  Patching whatever the language lets you patch is a last resort, used only
  when no seam exists, with a justifying comment.
- Never assert an interaction with a stub: a call made to obtain input is a
  step toward the result, not the result.
- A fake's contract for a system this project does not own is established
  by observing that system once, never by reading about it; reuse the
  pinned observation as a fixture instead of re-deriving it from prose.
- A property that lives in the product's own construction or on the way out
  of a call is tested through the production factory or entry point, never
  through an instance the test assembled itself.
- The case set, the subject under test and the dimensions varied all come
  from the specification, never from the artifact under test; a surviving
  mutation is evidence of a missing dimension, and a healthy mutation score
  is not evidence of specification coverage. Never recompute the expected
  value with the algorithm under test.
- Test the subject as a black box; use coverage to find untested areas, not
  as a target. Trivial code needs no test, and better no test than a bad
  one.
- No focused or skipped tests committed, no commented-out tests, no
  conditional assertions, no empty tests, no duplicate test names.
- Never tune a test to the gate: no expected value hardcoded "so it
  passes", no check disabled, no snapshot refreshed without understanding
  the cause.
- Tests are deterministic — no reliance on iteration-order accidents,
  wall-clock time, unpinned random seeds, or test execution order.
- Secrets in tests are test-only values, generated or signed for the test;
  never a real credential, and never a verification mocked away to avoid
  one.
- No production code exists only to serve tests: no test-environment
  switches, no members widened for a test.
- Keep this skill universal: language spellings, runner mechanics,
  framework and architecture choices belong to the host project or to the
  dedicated skills — never here. Project instructions always take
  precedence over this skill.
