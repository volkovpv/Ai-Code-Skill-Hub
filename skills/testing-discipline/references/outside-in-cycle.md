# The outside-in cycle: growing a system from its edges inward

[tdd-cycle.md](tdd-cycle.md) describes the loop that produces one test and
the code under it. This file describes the loop *around* that loop: how a
feature is started, what tells you it is finished, and where the
collaborators the inner loop fakes actually come from.

It is the **London school's** process, so it applies where the host project
declares that school — or declares outside-in development explicitly — the
same way test-driven development itself is declared; see
[schools.md](schools.md). Two things in it hold regardless: the
walking-skeleton argument about deployment risk, and the separation of the
suite that measures progress from the suite that catches regressions.

## Two nested loops

```
   ┌──────────────────────────────────────────────┐
   │  OUTER: one failing acceptance test per      │
   │  feature — end-to-end, in domain terms       │
   │                                              │
   │     ┌────────────────────────────────┐       │
   │     │  INNER: red → green → refactor │       │
   │     │  one unit at a time            │       │
   │     └────────────────────────────────┘       │
   │                                              │
   │  green ⇒ the feature exists and is done      │
   └──────────────────────────────────────────────┘
```

| | Outer loop | Inner loop |
|---|---|---|
| **Written in terms of** | the application's domain, never its technology | the unit and its collaborators |
| **Answers** | does the whole system do this? | do these objects do the right thing, and are they convenient to work with? |
| **Reports on** | external quality — does it meet the need | internal quality — is it well structured |
| **Failing means** | the feature is not built yet | the code is wrong, or not written yet |
| **Lifetime of a red** | a whole feature, possibly days | minutes |

A project with only the inner loop is missing the check that the code is
*reached from anywhere*. A suite of well-tested units that the entry point
never calls is a real failure mode, not a hypothetical one — and no unit
test can detect it.

## Kick-start: the walking skeleton

**The first thing built is the thinnest slice of real functionality that
can be automatically built, deployed and exercised from outside** — not
the first feature.

- Keep its behaviour deliberately trivial. Its job is to force the
  build, packaging, deployment and end-to-end invocation into existence
  while nothing else is moving. When the architecture, the harness and the
  product are all unfinished at once, a failure has no obvious first place
  to look.
- **"End-to-end" covers the process, not only the system.** Check out,
  build, package, deploy into a production-like environment, then exercise
  through the external access points. The deployment step is error-prone,
  will be repeated for the system's whole life, and is the moment the team
  discovers what the rest of the organisation requires of it.
- Decide only what must be decided: the major components and how they
  communicate — a few minutes at a whiteboard, not a design document.
  Everything else is discovered.
- **Expose uncertainty early.** The skeleton takes surprisingly long for
  something that does nothing, and that is the point: it front-loads the
  stress that late integration would otherwise deliver at the deadline,
  with no budget left to answer it.
- Where truly end-to-end is unreachable at first, standing in for the far
  end is a stop-gap that carries known remaining risk — not a finished
  job. Say which risk is still outstanding.
- **On an existing system there is no skeleton to build.** Automate the
  build and deployment, then put end-to-end tests around the area that
  must change, and only then start refactoring and adding unit tests
  inside it. Reworking untested code is the risk this order exists to
  avoid.

## Start each feature with a failing acceptance test

- **Write it in the domain's vocabulary, never in the technology's.** A
  test phrased in terms of queues, tables or endpoints has to be rewritten
  when the infrastructure changes, though the requirement did not.
- Prefer it to exercise the system from the outside — through its real
  entry points — rather than by assembling internal objects. A test that
  wires up the internals can pass over a product whose entry point does
  nothing at all.
- While it is red it states what is not built yet; when it goes green the
  feature is done. That is what makes it a measure of progress rather
  than a regression check.

## Separate the suite that measures progress from the suite that catches regressions

**A new acceptance test is expected to fail for as long as the feature
takes.** That is incompatible with a build that must be green, so the two
belong to different suites — never to one suite with the failing test
silenced.

| Suite | Expected state | Contains |
|---|---|---|
| **In progress** | red until the feature lands | the acceptance test for the feature being built |
| **Regression** | always green | every acceptance test for a finished feature |
| **Unit / integration** | always green, and fast | everything the inner loop produced |

- On landing, the acceptance test moves from the first suite to the
  second. When a requirement changes, it moves back, is edited, and moves
  forward again — it is never deleted to make a build green.
- **This is not an exemption from the no-committed-skips rule.** The
  regression suite has no disabled tests in it; the in-progress test is
  not in the regression suite. A skip marker inside a suite that is
  supposed to be green remains forbidden — see [hygiene.md](hygiene.md).
- Failing tests from the *inner* loop are never shared. They live in the
  working copy; see the session-ending table in
  [tdd-cycle.md](tdd-cycle.md).

## Start with the simplest success case

**The first test of a new feature is the simplest case that succeeds** —
not a degenerate case and not an error case.

- Degenerate and failure cases are easier to write and teach almost
  nothing about whether the idea works. A feature that only handles
  errors has demonstrated nothing, and a session spent entirely on error
  branches is bad for morale as well as for feedback.
- **Note the failure cases as you find them; do not chase them.** Keep
  them on the test list, and finish the feature by clearing the list —
  each item either written or deliberately dropped.
- **This does not contradict "start with a degenerate case" in
  [tdd-cycle.md](tdd-cycle.md); the two are scoped differently.** The
  first test of a *feature* has to validate the idea, so it succeeds. The
  first test of a *new operation* inside that feature only has to answer
  *where does this belong?*, so it should be trivially easy to know the
  answer to. Both rules pick the test that maximizes feedback for its own
  question.

## Develop from the inputs to the outputs

**Start from the events that enter the system and work through to the
externally visible response** — not from the domain model outward.

- Write the object that receives the external event; discover what
  services it needs; write those; discover what *they* need. Follow the
  chain until it reaches objects that already exist, or the far boundary
  where the response leaves.
- Starting in the domain model feels faster because nothing constrains it
  yet. That is exactly the problem: without the pull of a real caller, it
  is easy to build functionality that is unnecessary, wrongly shaped, or
  impossible to integrate — and the cost surfaces at integration time,
  when it is most expensive.

## Interface discovery: where collaborators come from

This is the engine of the outside-in cycle and the reason its unit tests
use doubles so heavily. **The collaborator does not exist yet.** The test
is what brings it into existence.

The loop, per object:

1. You are implementing an object and reach something it should not do
   itself.
2. **Name the service in the client's terms**, from the client's point of
   view — what this object needs, not what some future implementation
   will happen to provide.
3. Stand a double in for it and write the test as though the service
   already existed. The test now states the protocol between the two.
4. Then write something that provides the service — and repeat from (1)
   for *its* needs.

- **"If this worked, who would know?"** When the honest answer is not the
  object under test, that answer names a collaborator that ought to
  exist, and the double you are about to write is standing in for it.
- **Pull interfaces into existence from the client, do not push them out
  from the implementation.** An interface designed from the client's need
  leaks nothing about who will implement it; one extracted from an
  existing class carries that class's shape into every future
  implementation.
- **Keep the discovered surface narrow.** The fewer operations it
  declares, the more obvious its role at the call site, and the easier it
  is to write another implementation, adapter or decorator for it. Many
  narrow roles beat few wide ones.
- **A name you cannot find is a signal, not a formality.** If nothing but
  a restatement of the implementation fits, the responsibility is
  probably misplaced, or the "interface" is really a value; see
  [isolation-and-fakes.md](isolation-and-fakes.md).
- **Revisit the roles as they accumulate.** Two that turn out to mean the
  same thing get merged — more things become interchangeable. Two that
  look alike but differ get renamed apart, so they cannot be combined by
  accident.

## Tuning the cycle

The split between what is unit-tested with doubles and what is covered by
integration is **a decision the team revisits, not a constant.**

- Test only at a coarse grain and the combinations explode, while some
  paths — obscure failures in particular — stay unreachable.
- Test only at the finest grain and every unit passes while the assembly
  does not work.
- Reflect on which failures are getting through and adjust: fiddly logic
  wants more unit tests (or simplification); unhandled failures want more
  integration coverage. What the suite is buying is justified confidence
  that the code can be changed without breaking it — so the question to
  ask periodically is whether that confidence is still deserved.
