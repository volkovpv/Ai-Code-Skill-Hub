# The two levels, and the line between them

This skill covers exactly two kinds of test: **unit** and **integration**.
Each answers a question the other cannot, and mixing them up produces
tests that are slow without being thorough, or thorough about the wrong
thing.

Testing a whole deployed system from outside it — its packaging, its
environment, its operators, its users — is a different discipline with
different subjects, lifecycles and owners. It is **out of scope here**,
and nothing in this skill should be read as advice about it.

## The two questions

| Level | The question it answers | Runs against |
|---|---|---|
| **Unit** | do our objects do the right thing, and are they convenient to work with? | our own code, in memory |
| **Integration** | does our code work against code we cannot change? | our abstraction plus the real third-party thing |

## The line between them is what the schools disagree about

There is no level boundary this skill can hand you, because the two
schools draw it in different places — and that disagreement is the whole
of their disagreement, restated. See [schools.md](schools.md).

| | A test is a **unit** test when… | …and an **integration** test when… |
|---|---|---|
| **London (mockist)** | every collaborator is a double | any real collaborator runs |
| **Classical (Detroit)** | it is fast, isolated from other tests, and covers one unit of behaviour | it reaches a shared dependency, or is slow, or spans more than one unit of behaviour |

- Under London the boundary is **structural**: it is drawn by what was
  doubled, so it is visible in the test's own text.
- Under the classical school it is **behavioural**: two of your classes
  running for real is still one unit test, and the boundary is crossed by
  the dependency, not by the object count.
- **The project declares which line it draws**, and that declaration is
  what makes "move it to the integration suite" an instruction rather
  than an opinion. Absent a declaration, follow the existing suite.

What does *not* vary by school: once the line is drawn, it is enforced.

## What each level reports on

**Writing** unit tests reports on **internal quality** — whether the code
is loosely coupled and cohesive, because a unit that is awkward to
construct, arrange and interrogate in a test is a unit that will be
awkward to change. That report is produced by writing the test; a passing
run does not carry it. See
[tests-as-design-feedback.md](tests-as-design-feedback.md).

Integration tests report on something else entirely: **configuration and
assumptions**. They say nothing about whether the code inside can be
changed next month, and unit tests say nothing about whether the pieces
are configured correctly or reached at all. Neither substitutes for the
other.

## The integration level exists because you do not own the other side

An integration test is not "a unit test with more objects in it". Its
subject is **the seam between code you control and code you do not**: a
persistence mapper, a driver, a broker client, a platform facility, a
library from another team.

- Its job is to confirm that **the abstraction you built over the
  third-party thing behaves the way you assumed**. That assumption is the
  part that silently rots — on an upgrade, on a configuration change, on
  a version of the external system you did not test against.
- **Doubles are of limited use here by construction.** You cannot vouch
  for a double of behaviour you have never observed, and a test that
  drives a faked third-party surface through enough state to be
  interesting is usually telling you the design is wrong rather than
  telling you anything about the dependency. This is the same rule as
  *double only types you own*, seen from the other side — see
  [isolation-and-fakes.md](isolation-and-fakes.md).
- There are legitimately few of these tests relative to unit tests, and
  they are allowed to be slower and to require an environment.
- What such a test looks like in practice — cleaning persistent state on
  the way in, writing transaction boundaries into the test, round-tripping
  each mapped type — is in
  [adapters-and-persistence.md](adapters-and-persistence.md).

### The one thing you do double in an integration test

When the third-party facility calls *back* into your code — an event
listener, a handler, a subscription — the adapter must translate those
callbacks into your own vocabulary. **Double the callback interface you
defined**, and assert that the adapter translated correctly:

```
 real external facility → [ your adapter ] → doubled application callback
       (not doubled)         (the subject)      (doubled: you own it)
```

That is a double of a type you own, standing at the boundary of the
adapter under test — not a double of the facility. Where the facility
delivers callbacks on a thread of its own, the adapter's synchronization
is part of what this test is exercising; see
[async-and-concurrency.md](async-and-concurrency.md).

## Order the suite by cost, and keep the levels apart

```
 fast, in memory ──────────────────────────► slow, needs an environment
   unit tests                                  integration tests
   (many)                                      (few)
```

- **Never let an integration test grow quietly inside the unit suite.** A
  unit test that acquires a real connection, a real file or a real clock
  has changed level without saying so: it is now slow, order-dependent
  and environment-dependent, while still being run and trusted as a unit
  test. Move it and give it the lifecycle its level carries.
- Naming, location and invocation should make the level obvious from the
  outside, so that the fast suite can be run without a thought — which is
  the only condition under which it actually gets run.
- Each level should be able to fail on its own. When one defect turns
  both suites red, the level that pinpoints it is the cheaper one; that
  is the value of having the unit level at all.
- **The split between what is unit-tested with doubles and what is left
  to integration is a decision the project revisits, not a constant.**
  Test only at the coarse grain and the combinations explode while
  obscure failure paths stay unreachable; test only at the fine grain and
  every unit passes while the assembly does not work. Reflect on which
  failures are getting through: fiddly logic wants more unit tests (or
  simplification), unhandled failures want more integration coverage.

## Fidelity is a deliberate trade, and it is stated

Some techniques buy speed and reliability by making the tested system
less like the real one — replacing a scheduler with an externally driven
one, standing in for a far endpoint, running a component out of its
container. Each is usually correct, and each leaves a gap.

- **Name the gap and cover it somewhere.** Typically a small number of
  slow tests, in a separate run, that exercise the real arrangement.
- **Do not let the gap be discovered by production.** A stop-gap that was
  never revisited is indistinguishable from an oversight after a few
  months, so record what remains untested rather than relying on memory.
