# Levels of testing: what each one can tell you

A suite is a hierarchy of feedback loops, and each level answers a
question the others cannot. Mixing them up produces tests that are slow
without being thorough, or thorough about the wrong thing.

This file is school-neutral: both schools run all three levels and
disagree only about where the line between the bottom two falls — see
[schools.md](schools.md).

## The three questions

| Level | The question it answers | Runs against |
|---|---|---|
| **Acceptance / end-to-end** | does the whole system do this? | the system as deployed, driven from outside |
| **Integration** | does our code work against code we cannot change? | our abstraction plus the real third-party thing |
| **Unit** | do our objects do the right thing, and are they convenient to work with? | our own code, in memory |

## What each level reports on

**Running** acceptance tests reports on **external quality** — whether the
system meets the need. **Writing** unit tests reports on **internal
quality** — whether the code is loosely coupled and cohesive, because a
unit that is awkward to construct, arrange and interrogate in a test is a
unit that will be awkward to change. Integration tests sit in between and
report on neither very well; what they report on is *configuration and
assumptions*.

That asymmetry is the reason none of the three substitutes for another:

- End-to-end tests passing says nothing about whether the code inside can
  be changed next month.
- Unit tests passing says nothing about whether the pieces work together,
  are configured correctly, or are reached at all.
- The pain of writing a unit test is information you only get by writing
  it; a passing run does not carry it. See
  [tests-as-design-feedback.md](tests-as-design-feedback.md).

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
 fast, in memory ────────────────────────────────► slow, deployed
   unit tests        focused integration          end-to-end
   (many)            (few, need an environment)   (fewest)
```

- **Never let an integration test grow quietly inside the unit suite.** A
  unit test that acquires a real connection, a real file or a real clock
  has changed level without saying so: it is now slow, order-dependent
  and environment-dependent, while still being run and trusted as a unit
  test. Move it and give it the lifecycle its level carries.
- Naming, location and invocation should make the level obvious from the
  outside, so that the fast suite can be run without a thought — which is
  the only condition under which it actually gets run.
- Each level should be able to fail on its own. When a defect turns the
  whole pyramid red at once, the level that pinpoints it is the cheapest
  one that caught it; that is the value of having the lower levels at all.

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
