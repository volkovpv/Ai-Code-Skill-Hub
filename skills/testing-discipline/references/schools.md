# Schools of unit testing — declared by the project, never by this skill

A unit test is an automated test that

1. verifies a small piece of code (a *unit*),
2. does it quickly,
3. and does it **in isolation**.

The first two attributes are uncontroversial. The third is not: *isolation*
has two readings, and everything else the two schools disagree about — what
a "unit" is, which dependencies get a test double, what counts as an
integration test, which direction test-driven development runs — follows
from which reading a project adopts.

**This skill legislates neither reading.** The school is a project
decision: it is declared in the host project's rules, and those rules take
precedence over anything here. This file is the catalog to choose from, the
vocabulary the choice is made in, and the set of rules that hold whichever
way the choice goes.

## The vocabulary the choice is made in

The schools argue about *which* dependencies are replaced, so the argument
is unreadable without agreed names for kinds of dependency.

| Term | Meaning |
|------|---------|
| **Shared dependency** | one that two tests can both reach and through which one test can change another's result — a mutable global, a database |
| **Private dependency** | any dependency that is not shared |
| **Out-of-process dependency** | one that lives outside the process: database, broker, mail server, third-party API. Usually shared, but not necessarily — a per-test container instance, or a read-only service, is out-of-process and private |
| **Value / value object** | an immutable dependency with no identity, interchangeable with any other of equal content |
| **Collaborator** | a dependency that is mutable, or is a proxy for data not yet in memory. This is the thing the schools argue about |
| **Peer** | a collaborator the subject talks to directly, as opposed to something *inside* it. Only peers are ever replaced; the three kinds of peer, and why the distinction decides what a double may stand for, are in [isolation-and-fakes.md](isolation-and-fakes.md) |
| **Managed dependency** | an out-of-process dependency reachable *only* through your application, so interactions with it are invisible outside and are an implementation detail — typically your own database |
| **Unmanaged dependency** | an out-of-process dependency whose side effects other applications can see, so interactions with it are part of your observable behaviour — a broker, a mail server, a shared table |

Three consequences hold under either school:

- **A value is never replaced by a double.** If it is immutable and
  identity-free, pass the real one; there is nothing to isolate.
- A dependency is shared **because tests reuse it**, not because production
  has one instance of it. A registry or configuration object that each test
  constructs fresh is private, however singular it is in production.
- Shared and out-of-process are near-synonyms in practice, but not
  identical, and the distinction decides whether a dependency can simply be
  re-created per test instead of being replaced.

## The London school (mockist)

**Isolation means: the unit under test is isolated from its
collaborators.** Every mutable collaborator is replaced by a double, so a
red test has exactly one suspect.

- **A unit is a class** — occasionally a single method. One production
  class ↔ one test class is the default map.
- **Every collaborator is doubled**, values excepted. That requires a
  declared seam (an interface, an injected dependency, a parameter) at each
  collaboration point.
- **Verification leans on interactions**: which method the subject called
  on which collaborator, with which arguments, how many times.
- **An integration test is any test that runs a real collaborator.** Most
  tests the classical school calls unit tests are integration tests here.
- **Test-driven development runs outside-in**: start from a high-level test
  stating the expectation of the whole operation, express the collaborators
  it needs as doubles, then walk down the object graph implementing each.
  The doubles are heavy in this school because **the collaborators do not
  exist yet** — naming them in a test is how they come into existence.
  That process, and the outer loop it lives in, is
  [outside-in-cycle.md](outside-in-cycle.md).
- Its claimed benefits: fine granularity; a large object graph becomes
  testable without constructing it; a failure names the defective class
  directly instead of cascading through its clients.
- Its cost, and the reason it needs discipline: replacing every
  collaboration binds the tests to *how* the unit reaches its result.
  Interactions that never leave the application are implementation details,
  so tests that assert them go red on refactorings that changed no
  behaviour — see
  [unit-test-value.md](unit-test-value.md).
- **The discipline that pays that cost down is not optional under this
  school**, and it is specific: replace peers and never internals, and
  double only roles you named yourself
  ([isolation-and-fakes.md](isolation-and-fakes.md)); allow queries and
  expect only commands, keep the expectations few, match arguments only
  as precisely as the scenario requires, and constrain call order only
  where the order is part of the contract
  ([unit-test-value.md](unit-test-value.md)). A project that declares
  London and skips these has bought the cost without the benefit.

## The classical (Detroit) school

**Isolation means: unit tests are isolated from each other** — they can run
in parallel, sequentially, or in any order without changing one another's
results.

- **A unit is a unit of behaviour**, not a unit of code: however many
  classes it takes to tell one story that makes sense to a domain expert.
  *"When I call my dog, she comes to me"* — not *"she extends her left
  front paw, then the right one, then turns her head…"*.
- **Only shared dependencies are doubled** — in practice, the out-of-process
  ones. Private collaborators are used for real, whether or not they are
  mutable.
- **Verification leans on output and state**: the value the operation
  returned, or the state it left behind.
- **An integration test is one that fails any of the three attributes**: it
  reaches a shared dependency, or it is slow, or it covers more than one
  unit of behaviour.
- **Test-driven development is usually summarized as running inside-out** —
  start from the domain model and add layers outward until the operation is
  reachable by its caller. Treat that as a rough contrast with London's
  outside-in, not as the school's own account of itself: the school's
  primary sources reject the vertical metaphor outright, on the grounds
  that a suite grown this way looks top-down from one angle and bottom-up
  from another. The direction that predicts anything is
  **known-to-unknown** — and a first test at application level is
  compatible with it. See [tdd-cycle.md](tdd-cycle.md).
- Its claimed benefit: far fewer doubles, so far less coupling to
  implementation detail; tests survive a class being split, merged or
  renamed, because they were never addressed to the class.
- Its cost: one defect turns many tests red at once, since clients of the
  broken code run for real. Run the suite after each change and the last
  edit names the cause; a wide cascade is also information — it says how
  load-bearing the broken code is.

## Side by side

| | Isolation applies to | A "unit" is | Doubles are used for |
|---|---|---|---|
| **London (mockist)** | units | a class | collaborators — every mutable dependency |
| **Classical (Detroit)** | tests | a class or a cluster of classes | shared dependencies |

## What holds whichever school is declared

The school chooses which collaborators are replaced. It licenses none of
the following:

- **Never assert an interaction with a stub.** A call made to *obtain
  input* is a means to the result, not the result; asserting it is
  over-specification and is fragile under either school. Only a call that
  *changes* something outside the subject may be asserted at all — see
  [isolation-and-fakes.md](isolation-and-fakes.md).
- **An interaction that never crosses the application boundary is an
  implementation detail.** Under the classical school it is simply not
  asserted. Under London it is asserted because the school asks for it —
  which is a cost the project accepted when it declared the school, not a
  licence to assert anything at all.
- **A double for something you do not own is written against an adapter you
  do own**, and its contract is pinned by observing the real system rather
  than by reading about it — see
  [isolation-and-fakes.md](isolation-and-fakes.md).
- **Output verification is preferred by both schools** wherever the code
  admits it, because it is the style least able to couple to an
  implementation detail — see [unit-test-value.md](unit-test-value.md).
- **Tests are isolated from one another under both schools**, and paying
  for that isolation is a design force rather than a chore: the only way
  to make per-test setup cheap is to decompose the problem into small,
  orthogonal, loosely coupled pieces — see
  [tests-as-design-feedback.md](tests-as-design-feedback.md). The schools
  disagree about isolating the *unit*, never about isolating the tests.
- Structure, naming, determinism, secret handling and the rest of suite
  hygiene do not vary by school.

## Resolution order when working in a project

1. The project's rules declare a school → follow it exactly.
2. No declaration, but the existing suite is consistently one or the other
   → follow the suite, and propose recording the school in the project
   rules.
3. No declaration and no consistent suite → propose a school (with a
   recommendation), get it recorded, then write tests. Absent other
   constraints, recommend the **classical** one: resistance to refactoring
   is close to a binary property, and doubling intra-application
   collaborators wholesale is the most common way a suite loses it.

Never mix the two by accident inside one suite. A project may deliberately
declare a split — classical in the domain, interaction-based at the
boundary where unmanaged dependencies are involved is a common one — but
then the split itself is what gets declared, with its boundary named.

## What the project rules must declare

- **The school** — London (mockist) or classical (Detroit) — and, where it
  varies by layer or module, the exact boundary between them.
- **What a unit is** for this project: a class, a unit of behaviour, a
  module.
- **Which dependencies get a double**: under the classical school, whether
  the line is drawn at *shared* or at the stricter *unmanaged*; under
  London, which collaborators are exempt beyond plain values.
- **Which out-of-process dependencies count as managed and which as
  unmanaged** — that is what decides which ones are used for real in
  integration tests and which are replaced and asserted.
- **Where an interaction is asserted**, if any is: at the last adapter
  before the call leaves the process, or earlier.
- **Whether the project practises test-driven development at all**, and if
  so its direction. The cycle itself is only imposed where this is
  declared — see [tdd-cycle.md](tdd-cycle.md), whose evidence rule (a test
  is not evidence until it has been seen red) applies either way.
- **Whether features are started with a failing acceptance test**, and
  where the in-progress acceptance suite lives relative to the regression
  suite — see [outside-in-cycle.md](outside-in-cycle.md). Declaring
  London normally implies this; declaring the classical school does not
  settle it either way.
- **Which levels the suite has and what each is allowed to touch** — see
  [test-levels.md](test-levels.md). The schools disagree about where the
  line between unit and integration falls, so the project has to say
  where *its* line is.
- The mechanics: what the doubles are built with, where tests live, how
  they are named.

Anything a project leaves undeclared falls back to the rules above that
hold under both schools — never to a guess about which school the author of
a given test had in mind.
