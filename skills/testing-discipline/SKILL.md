---
name: testing-discipline
description: Discipline for unit and integration tests, with no language, runner, framework, or platform assumptions; testing a whole deployed system from outside is out of scope. The school — London (mockist) or classical (Detroit) — is declared by the host project's rules, never here, and it also draws the line between a unit test and an integration test. No change without its tests; a bug fix ships a regression test that fails first; a test is not evidence until seen red, its failure message made legible before the code; Arrange/Act/Assert, one scenario per test, names stating behaviour and condition; unit tests touch nothing external and replace peers, never internals; under London each role is discovered from its client; an external fake is pinned by live observation; exact about the claim, silent about the rest; async tests wait for success; persistence cleans on the way in and commits; hygiene — no focus/skip, no tuning to the gate. Use when writing or reviewing unit or integration tests, in any language.
---

# Testing discipline (universal)

Write tests that establish what they claim to establish. This skill is
**universal by contract**: every rule here holds for any language, test
runner, framework and platform — it assumes no ecosystem, no mocking
library, no architectural style. *How* a rule is spelled in a given
language (which marker, which assertion helper, which patching facility)
belongs to that language's own standard.

It is **scoped to two levels: unit and integration.** Testing a whole
deployed system from outside it — its packaging, its environment, its
release process, its users — is a different discipline with different
subjects and owners, and nothing here should be read as advice about it.

It is also **neutral on the unit-testing school**. Whether "isolation"
means isolating the unit from its collaborators (London / mockist) or
isolating the tests from one another (classical / Detroit) is a project
decision that decides which collaborators get a test double, what counts
as a unit, and where the line between a unit test and an integration test
runs. The host project's rules declare it and always take precedence;
this skill carries the catalog and the rules that hold either way — see
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
2. **Know which of the two levels you are writing at.** A test that
   answers "does our code work against code we cannot change?" and one
   that answers "does this object do the right thing?" have different
   subjects, speeds and lifecycles — and *where the line between them
   falls is the school's decision*, not a constant. Never let one grow
   quietly inside the other — see
   [references/test-levels.md](references/test-levels.md).
3. **Ship the tests with the change, and see each one red before trusting
   it.** A code change without its tests is not done; every bug fix ships
   a regression test that reproduces the defect and fails before the fix;
   a test that has never been observed to fail for its own reason has not
   yet been verified — see
   [references/tdd-cycle.md](references/tdd-cycle.md).
4. **Read the failure before writing the code that fixes it.** The cycle
   has four steps — fail, *report*, pass, refactor — and the report step
   happens while the failure is in front of you: if the message would not
   tell a stranger what is wrong, fix the test until it would — see
   [references/test-diagnostics.md](references/test-diagnostics.md).
5. **Where the project practises test-driven development, work the
   cycle.** Never more than one red test at once, the smallest change that
   reaches green, then remove the duplication — including the duplication
   between the test and the code — see
   [references/tdd-cycle.md](references/tdd-cycle.md).
6. **Where the project declares London, discover each collaborator from
   its client.** The role is named from the point of view of the object
   that needs it, before any implementation exists, and the double in the
   test is what brings it into being — see
   [references/interface-discovery.md](references/interface-discovery.md).
7. **Structure and name each test so it reads as a claim.**
   Arrange/Act/Assert, one act step, no branching, a name that states the
   behaviour and the condition, assertions that pin the error *and* its
   condition, data whose expected value visibly follows from the inputs —
   see
   [references/structure-and-naming.md](references/structure-and-naming.md).
8. **Keep the arrange step from swallowing the test.** State only the
   fields the scenario depends on and default the rest; move the
   mechanics into builders and helpers that take a builder rather than
   its arguments — see
   [references/test-data-builders.md](references/test-data-builders.md).
9. **Assert observable behaviour, never implementation detail.** Judge the
   test by protection against bugs, resistance to refactoring, feedback
   speed and maintenance cost; prefer output verification to state
   verification and state verification to asserting interactions; where
   you do assert an interaction, specify precisely what must happen and
   no more — see
   [references/unit-test-value.md](references/unit-test-value.md).
10. **Isolate the unit and replace peers, never internals.** No network,
    disk, database or wall-clock dependence; time is injected, not slept
    through; a stub is never asserted on — see
    [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
11. **Pin an external system's behaviour by observing it, not by reading
    about it.** When the property under test belongs to a system this
    project does not own, the fake's contract is established by a probe
    against the real system and then reused as a fixture — see
    [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
12. **Exercise the production wiring, not a hand-built copy of it.** How a
    collaborator gets constructed, and what a client substitutes on the way
    out of a call, are only testable where the product itself does them —
    see [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
13. **Where the test is asynchronous, wait for success and time out for
    failure** — never sleep, never assert a state the system was already
    in, and separate what an object computes from how it schedules — see
    [references/async-and-concurrency.md](references/async-and-concurrency.md).
14. **Derive the case set, the subject and the dimensions from the
    specification.** Never from the artifact under test: a mutation battery
    can score healthy while the specification stays uncovered — see
    [references/hygiene.md](references/hygiene.md).
15. **When the test is hard to write, fix the design first.** A long
    arrange step, setup that resists being shared, a slow or fragile test,
    a hidden dependency, or the urge to reach private state is a report on
    the product, not an inconvenience in the test file — see
    [references/tests-as-design-feedback.md](references/tests-as-design-feedback.md).
16. **Keep the suite honest.** No committed focus/skip markers, no test
    tuned to the gate, no flickering tolerated, no real credentials — see
    [references/hygiene.md](references/hygiene.md).

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Deciding what "isolation" means here, which collaborators get a double, what a unit is, what the project rules must declare | [references/schools.md](references/schools.md) |
| Deciding whether a test is a unit or an integration test, where that line runs for this project, what an integration test is for, where a test that reaches outside the process goes | [references/test-levels.md](references/test-levels.md) |
| Deciding when a test gets written, what makes it verified, how to reach green, what the refactor step owes | [references/tdd-cycle.md](references/tdd-cycle.md) |
| Under a declared London school: needing a collaborator that does not exist yet, naming the role, deciding how wide its surface should be | [references/interface-discovery.md](references/interface-discovery.md) |
| The test failed and the message does not say why; choosing values that explain their own role in a report | [references/test-diagnostics.md](references/test-diagnostics.md) |
| The test is painful to write, slow, fragile, wants access it should not have, or its subject is reached only through a global — and you are deciding whether the test or the code is wrong | [references/tests-as-design-feedback.md](references/tests-as-design-feedback.md) |
| Laying out a test, naming it, asserting an error, choosing its data, grouping similar cases, choosing between example-based and property-based cases | [references/structure-and-naming.md](references/structure-and-naming.md) |
| The arrange step is long, or repeated across many tests with small variations | [references/test-data-builders.md](references/test-data-builders.md) |
| Judging whether a test is worth keeping, choosing between output/state/interaction verification, deciding how precisely an interaction should be pinned, deciding what deserves a unit test at all | [references/unit-test-value.md](references/unit-test-value.md) |
| Deciding what a double may stand for, how a fake's contract is established, testing construction or an outgoing call | [references/isolation-and-fakes.md](references/isolation-and-fakes.md) |
| The test involves threads, callbacks, polling, timeouts, or a system that schedules its own work | [references/async-and-concurrency.md](references/async-and-concurrency.md) |
| Testing a persistence mapper, a serializer, or anything else that maps your objects onto infrastructure you do not own | [references/adapters-and-persistence.md](references/adapters-and-persistence.md) |
| Choosing the case set, judging whether coverage or a mutation score means anything, deciding whether a test may be deleted, reviewing suite hygiene | [references/hygiene.md](references/hygiene.md) |
| A test is red and you are deciding whether to update its expected value or refresh its snapshot, or an unfinished test is red and you are deciding how to carry it | [references/hygiene.md](references/hygiene.md) |
| A test wants to reach a private member, private state, a partially replaced type, the clock, or a shared setup hook | [references/anti-patterns.md](references/anti-patterns.md) |

## Rules

- **The scope is unit and integration tests.** Questions about exercising
  a whole deployed system from outside it are outside this skill; say so
  rather than answering them from these rules.
- **The school belongs to the project, not to this skill.** Follow the
  declared one; where none is declared, follow the existing suite and
  propose recording the choice — never mix the two by accident.
- A code change without its tests is incomplete; every bug fix ships a
  regression test that fails before the fix and passes after it.
- A test that has never been observed to fail for its own reason is not
  yet evidence. Write it first, or break the behaviour it names and watch
  it go red; an unexpected green is investigated, never enjoyed. Read the
  failure message and make it legible **before** writing the code that
  turns it green.
- Where the project practises test-driven development: never hold more
  than one red test, take the shortest route to green (a deliberately
  constant implementation is a step in the cycle, not a tuned test), then
  remove the duplication — including between the test and the code.
- Keep the two levels apart: a unit test that acquires a real connection,
  file or clock has changed level and must be moved, renamed and given the
  lifecycle its level carries. *Where* that line falls is what the project
  declared, not what this skill decides.
- Where the project declares London: a collaborator is named from its
  client's point of view before any implementation of it exists, its
  surface is kept narrow, and roles that turn out to mean the same thing
  are merged rather than left to drift apart.
- One scenario per test, one act step, no branching, Arrange/Act/Assert (or
  Given/When/Then), a name that states the behaviour and the condition as a
  fact — never `test_2`, `works`, or the name of the method under test.
- A test that is hard to write, slow, breaks for reasons it does not
  assert, or can only reach its subject through a global is reporting a
  defect in the design; change the design first and the test second, and
  record the cost when you cannot. Tooling that breaks a hidden dependency
  without changing the code spends the feedback the test was giving you.
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
- **Specify precisely what should happen and no more.** Be exact about the
  outcome the scenario drives and silent about everything it does not.
  Allow queries any number of times; expect commands exactly as often as
  the contract says. Keep required interactions few, match arguments only
  as tightly as the scenario constrains them, and pin call order only
  where the order is part of the contract.
- A unit test touches nothing external: no network, disk, database, or
  wall-clock dependence. Control time by injecting it, preferably as a
  value, never by sleeping and never through an ambient global.
- Replace **peers**, never internals. Fake the seams the code exposes (a
  parameter, an interface, an injected dependency) — never someone else's
  internals, and only types you own. Prefer a named role to a concrete
  type: doubling a class leaves the relationship unnamed and binds the
  subject to more of that class than it uses. Patching whatever the
  language lets you patch is a last resort, used only when no seam exists,
  with a justifying comment.
- Distinguish the three kinds of peer: a **dependency** is required at
  construction and has no safe default; a **notification** and an
  **adjustment** are defaulted and overridden per test. A construction
  argument list that has grown unwieldy is usually adjustments treated as
  dependencies, or an unnamed concept waiting to be extracted.
- Never assert an interaction with a stub: a call made to obtain input is a
  step toward the result, not the result.
- A fake's contract for a system this project does not own is established
  by observing that system once, never by reading about it; reuse the
  pinned observation as a fixture instead of re-deriving it from prose.
- A property that lives in the product's own construction or on the way out
  of a call is tested through the production factory or entry point, never
  through an instance the test assembled itself.
- An asynchronous test waits for success and treats the timeout as the
  failure — never a fixed sleep, and never an assertion the system could
  already have satisfied before it started. **A wait whose condition
  already held at the starting state never waited for anything**: a
  quantity that returns to the value it began at, a collection back to
  empty, a flag back to its default. Such a test passes against a system
  that did nothing at all, so wait for a state the initial one could not
  have been in. Keep the timeout in one place,
  separate what an object computes from how it schedules, and pull
  self-scheduled activity out to somewhere a test can drive it.
- Persistent state is cleaned at the **start** of a test, not at the end:
  tidying up on the way out breaks isolation the moment a test fails
  before its cleanup, and deletes the evidence that would have explained
  the failure. Nor is a test isolated by rolling its transaction back —
  commit is where pending changes flush, integrity constraints are
  checked, generated values are assigned and triggers fire, so a test that
  never commits never exercises any of it.
- Generic mapping code is exercised with purpose-built types, not with
  production domain types: the coupling blocks refactoring, and a domain
  type that later loses the feature under test leaves the suite green over
  a case that no longer exists.
- The case set, the subject under test and the dimensions varied all come
  from the specification, never from the artifact under test; a surviving
  mutation is evidence of a missing dimension, and a healthy mutation score
  is not evidence of specification coverage. Never recompute the expected
  value with the algorithm under test.
- Assert the expected value, not a property that many wrong answers share.
  Where the specification derives the expected value from the inputs, write
  that derivation into the test over literals the test owns; never let one
  constant stand for two different things in the same case. Where a value
  stands for a concept — "nothing found", "not supplied", "irrelevant
  here" — name the concept rather than writing its representation.
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
  conditional assertions, no empty tests, no duplicate test names, and no
  red suite shared. A test that is red only because its behaviour is not
  written yet stays in the working copy until it passes — silencing it and
  committing it is the one resolution both the cycle and this rule reject,
  and renaming the silence to an expected-failure or pending marker, with
  or without a tracking reference, is the same commit.
- Never tune a test to the gate: no expected value hardcoded "so it
  passes", no check disabled, no snapshot refreshed without understanding
  the cause. **A red test is answered with a diagnosis, never with a
  refreshed expectation** — and that holds however deliberate the change
  that turned it red. A refactor that changes no behaviour cannot turn a
  test red, so when one does, establish which happened — the change was
  more than a refactor or it introduced a defect — before any expected
  value or snapshot moves. Even where the behaviour did change on purpose,
  derive the new expectation from the specification that sanctioned it
  rather than reading it back from what the code now produces.
- Tests are deterministic — no reliance on iteration-order accidents,
  wall-clock time, unpinned random seeds, or test execution order. A test
  that fails intermittently is broken, not mostly working.
- Secrets in tests are test-only values, generated or signed for the test;
  never a real credential, and never a verification mocked away to avoid
  one.
- No production code exists only to serve tests: no test-environment
  switches, no members widened for a test. Reporting that operators depend
  on is a feature and is test-driven through a seam you own; tracing you
  added for yourself is scaffolding and is not.
- Keep this skill universal: language spellings, runner mechanics,
  framework and architecture choices belong to the host project or to the
  dedicated skills — never here. Project instructions always take
  precedence over this skill.
