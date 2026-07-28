---
name: testing-discipline
description: Test discipline with no language, runner, framework, or platform assumptions. The school — London (mockist) or classical (Detroit) — is declared by the host project's rules, never here. No change without its tests; a test is not evidence until seen red; every bug fix ships a regression test that fails first; red/green/refactor where declared; Arrange/Act/Assert, one scenario per test, names stating behaviour and condition; unit tests touch nothing external and fake only the seams the code exposes; an external fake is pinned by live observation, not reading; construction and outbound substitution go through production wiring; judged by protection, refactoring resistance, speed, maintenance cost; assert observable behaviour, never implementation detail; cases come from the specification, not the artifact tested; a hard-to-write test reports a design defect; hygiene — no committed focus/skip, no tuning to the gate, determinism, test-only secrets. Use when writing, reviewing or reworking tests, in any language.
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
   for it before deciding what to fake — and while there, find whether the
   project declares test-driven development. No declaration but a
   consistent suite → follow the suite and propose recording the choice;
   neither → propose one, get it recorded, then write tests — see
   [references/schools.md](references/schools.md).
2. **Ship the tests with the change, and see each one red before trusting
   it.** A code change without its tests is not done; every bug fix ships
   a regression test that reproduces the defect and fails before the fix;
   and a test that has never been observed to fail for its own reason has
   not yet been verified — see
   [references/tdd-cycle.md](references/tdd-cycle.md).
3. **Where the project practises test-driven development, work the
   cycle.** One test at a time off a written list, never more than one red
   at once, the shortest route to green, then remove the duplication —
   including the duplication between the test and the code — see
   [references/tdd-cycle.md](references/tdd-cycle.md).
4. **Structure and name each test so it reads as a claim.**
   Arrange/Act/Assert, one act step, no branching, a name that states the
   behaviour and the condition, assertions that pin the error *and* its
   condition, data whose expected value visibly follows from the inputs —
   see
   [references/structure-and-naming.md](references/structure-and-naming.md).
5. **Assert observable behaviour, never implementation detail.** Judge the
   test by protection against bugs, resistance to refactoring, feedback
   speed and maintenance cost; prefer output verification to state
   verification and state verification to asserting interactions — see
   [references/unit-test-value.md](references/unit-test-value.md).
6. **Isolate the unit and fake only the seams the code exposes.** No
   network, disk, database or wall-clock dependence; time is injected, not
   slept through; a stub is never asserted on — see
   [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
7. **Pin an external system's behaviour by observing it, not by reading
   about it.** When the property under test belongs to a system this
   project does not own, the fake's contract is established by a probe
   against the real system and then reused as a fixture — see
   [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
8. **Exercise the production wiring, not a hand-built copy of it.** How a
   collaborator gets constructed, and what a client substitutes on the way
   out of a call, are only testable where the product itself does them —
   see [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
9. **Derive the case set, the subject and the dimensions from the
   specification.** Never from the artifact under test: a mutation battery
   can score healthy while the specification stays uncovered — see
   [references/hygiene.md](references/hygiene.md).
10. **When the test is hard to write, fix the design first.** A long
    arrange step, setup that resists being shared, a slow or fragile test,
    or the urge to reach private state is a report on the product, not an
    inconvenience in the test file — see
    [references/tests-as-design-feedback.md](references/tests-as-design-feedback.md).
11. **Keep the suite honest.** No committed focus/skip markers, no test
    tuned to the gate, no non-determinism, no real credentials — see
    [references/hygiene.md](references/hygiene.md).
12. **Let the static checks and the tests divide the work.** Where the
    project has a type checker, do not test what it already forbids, and do
    test the guards, bypasses and type-level utilities it cannot verify —
    see [references/types-and-tests.md](references/types-and-tests.md).

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Deciding what "isolation" means here, which collaborators get a double, what a unit is, what the project rules must declare | [references/schools.md](references/schools.md) |
| Deciding when a test gets written, what makes it verified, which test to write next, how to reach green, how big a step to take, how to end a session | [references/tdd-cycle.md](references/tdd-cycle.md) |
| The test is painful to write, slow, fragile, or wants access it should not have, and you are deciding whether the test or the code is wrong | [references/tests-as-design-feedback.md](references/tests-as-design-feedback.md) |
| Laying out a test, naming it, asserting an error, choosing its data, grouping similar cases, choosing between example-based and property-based cases | [references/structure-and-naming.md](references/structure-and-naming.md) |
| Judging whether a test is worth keeping, choosing between output/state/interaction verification, deciding what deserves a unit test at all | [references/unit-test-value.md](references/unit-test-value.md) |
| Deciding what a double may stand for, how a fake's contract is established, testing construction or an outgoing call | [references/isolation-and-fakes.md](references/isolation-and-fakes.md) |
| Choosing the case set, judging whether coverage or a mutation score means anything, deciding whether a test may be deleted, reviewing suite hygiene | [references/hygiene.md](references/hygiene.md) |
| A test wants to reach a private member, private state, a partially replaced type, the clock, or a shared setup hook | [references/anti-patterns.md](references/anti-patterns.md) |
| The project has a static type checker and you are deciding what still needs a test | [references/types-and-tests.md](references/types-and-tests.md) |

## Rules

- **The school belongs to the project, not to this skill.** Follow the
  declared one; where none is declared, follow the existing suite and
  propose recording the choice — never mix the two by accident.
- A code change without its tests is incomplete; every bug fix ships a
  regression test that fails before the fix and passes after it.
- A test that has never been observed to fail for its own reason is not
  yet evidence. Write it first, or break the behaviour it names and watch
  it go red; an unexpected green is investigated, never enjoyed.
- Where the project practises test-driven development: work a written test
  list one item at a time, never hold more than one red test, pick the next
  test for what it teaches against what you can make pass, take the
  shortest route to green (a deliberately constant implementation is a step
  in the cycle, not a tuned test), then remove the duplication — including
  between the test and the code. Step size is chosen deliberately, not by
  habit. Leave a shared branch green; a bookmark left red stays local.
- One scenario per test, one act step, no branching, Arrange/Act/Assert (or
  Given/When/Then), a name that states the behaviour and the condition as a
  fact — never `test_2`, `works`, or the name of the method under test.
- A test that is hard to write, slow, or breaks for reasons it does not
  assert is reporting a defect in the design; change the design first and
  the test second, and record the cost when you cannot.
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
- Assert the expected value, not a property that many wrong answers share.
  Where the specification derives the expected value from the inputs, write
  that derivation into the test over literals the test owns; never let one
  constant stand for two different things in the same case.
- Test the subject as a black box; use coverage to find untested areas, not
  as a target. Trivial code needs no test, and better no test than a bad
  one. Test the conditionals, loops, operations and dispatch **you** wrote
  — not a dependency's own behaviour, except to learn a facility before
  first use or to pin a defect you must work around. Depth follows the cost
  of being wrong, not a case count.
- A test is deleted only when it is redundant on **both** counts — it adds
  nothing to what the suite establishes, and it describes no scenario a
  reader would otherwise miss — and the deletion ships with the change that
  made it redundant.
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
