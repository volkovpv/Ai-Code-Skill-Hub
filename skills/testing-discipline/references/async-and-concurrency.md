# Asynchrony and concurrency

An ordinary test knows that when the call returns, the work is done. An
asynchronous test does not: control comes back while the work is still
running, so the test can assert too early, assert too late, or assert
against a system that has not started. Failures surface as timeouts with
no explanation, or — worse — as green runs that check nothing.

Everything here is in addition to the baseline rules: a unit test still
touches nothing external, and time is still injected rather than waited
for — see [isolation-and-fakes.md](isolation-and-fakes.md).

## Keep the two problems apart

An object that manages threads mixes **what it computes** with **how it
schedules**. Either can break a test, and while they are entangled a
failure does not say which.

**Take the scheduling out of the object and pass it in.** Give the object
something that runs tasks, rather than letting it start them:

| | The object receives | The test supplies | What is under test |
|---|---|---|---|
| **Functional tests** | a task runner | one that runs tasks on the test's own thread, on demand | what the object computes and whom it notifies |
| **Synchronization tests** | a task runner | one that really runs tasks concurrently | whether the object's state survives concurrent access |

- The functional tests then have no threads in them at all: trigger the
  operation, run the queued tasks deliberately, assert. Failures are
  reported normally instead of vanishing on a background thread.
- The object's concurrency policy stops being hidden inside it. Whoever
  assembles the application decides it — a pool, a single thread, an
  inline runner — without touching the object. That is the same context
  independence that makes the object testable in the first place.
- **Write both kinds of test before writing the code.** Making only the
  functional ones pass first is fine for learning the technique, but
  shipping on that basis means shipping code that passes its tests and
  still has a race in it.

## Wait for success; time out for failure

An asynchronous test cannot block until the work finishes, so it must
**wait for the expected state and treat the timeout as the failure.**

- Every awaited condition carries a deadline. A test that can hang has
  taken the whole suite hostage.
- **Succeed fast.** A passing test must return the instant the condition
  holds — never after a fixed delay. Fixed sleeps are affordable in one
  test and ruinous across a suite, and any delay tuned for the slowest
  machine is wasted everywhere else.
- **This requires that the activity has an observable effect.** If
  nothing about the system becomes different, there is nothing to wait
  for and no way to synchronize; that is a statement about the design,
  not about the test.
- **Keep the timeout value in one place.** It is a balance between
  reliability and the cost of failing runs, it differs by environment,
  and it will need changing as the system grows.

## Two ways to observe, and what each one misses

| | **Listening** | **Sampling** |
|---|---|---|
| How | the system notifies; the test records notifications and waits | the test polls the system's visible state |
| Speed | wakes the instant the event arrives | one poll interval of latency |
| Availability | needs the system to emit events | works against anything observable |
| **Blind spot** | none for recorded events | **state changes that are overwritten between polls** |

**Lost updates are the sampling-specific failure.** If the system passes
through a state and leaves it before the next poll, the test never sees
it:

```
system:   ──A──────B───────C────────►      (B is transient)
polls:    ─↑───────────↑────────↑───►      B never observed
```

A recorded stream of notifications has no such gap: the test searches
everything that arrived, not only what is true right now.

- Where the system emits events, **prefer listening**, and keep the whole
  trace so a failure can report what did arrive.
- Where you must sample, **structure the test in phases**: stimulate, then
  wait until the change becomes visible, and only then stimulate again.
  Triggering the next step before the previous one is visible is how a
  transient state gets skipped.

## Runaway tests: the green run that never tested anything

**An asynchronous test that asserts the system is in a state it was
already in can pass before the system has started.**

- **Minimal reproduction.** The holding for a stock starts at zero. The
  test sends a buy of 10 and a sell of 10, then waits for the holding to
  become 0. Both messages are still in flight; the wait is satisfied
  immediately by the initial state; the test is green. It stays green if
  the messages are never delivered, if the handler throws, or if the
  arithmetic is wrong in both directions — and it was green on the day it
  was written, so nobody looks at it again.

The fix is to **assert an intermediate state first**, so the test cannot
outrun the system:

```
send(buy 10);   wait until holding == 10     ← proves the system responded
send(sell 10);  wait until holding == 0      ← now this means something
```

The general rule: **wherever an asynchronous test expects the system to
return to a previous state, it must first wait for a state it could not
already have been in.** Check every displayed or observable transition
along the way, not only the final one.

## Testing that an action has *no* effect

There is nothing to wait for, so the test cannot tell "correctly ignored"
from "not received yet". Waiting a fixed period to see whether something
happened breaks *succeed fast* and is unreliable anyway.

**Trigger a second action that is detectable and must complete after the
first, then assert on that.** If the ignored input would have contributed
to a total, send a second input that does contribute and assert the total
equals only the second one's contribution.

- This buys reliability with an assumption — usually that the two are
  processed in order. **Say so.** The test is no longer fully black-box,
  and if the system later processes inputs in parallel the test starts
  lying rather than failing.
- Keep such tests near the tests that confirm the assumption, so a change
  to one is likely to reach the other.

## Distinguish synchronizing from asserting

Waiting for a condition and asserting a condition use the same mechanism
and mean different things. If they are spelled the same way, a later
reader deletes what looks like a duplicated assertion and silently
reintroduces the race the wait existed to prevent.

**Name them apart** — one vocabulary for "wait until the system has got
here", another for "and this is what must be true" — and keep the naming
consistent across the suite.

## Stress-testing synchronization

Correctness under concurrency cannot be demonstrated by running the code
once. What can be done is to make a race likely enough that it shows up
reliably.

1. **State an invariant that does not depend on the number of threads** —
   "the completion notification is sent exactly once per request,
   whatever the number of workers"; "after N increments from any number
   of threads, the count is N". Invariants of this shape let you turn the
   stress up without rewriting the assertions.
2. **Write the test so that many threads exercise the object many times.**
   For an object that starts its own tasks, give it a real concurrent
   runner. For a **passive** object — one that many threads merely call
   into — the test starts the threads itself, and the invariant is that
   the final state matches what sequential calls would have produced.
3. **Watch it fail, and tune until it fails on every run.** A stress test
   that passes against unsynchronized code is worse than none: it
   certifies a race. Raise the thread count or the iteration count until
   the failure is dependable, then read the failure and make sure it is
   the race you expected.
4. **Only then add the synchronization.**

Two things this procedure catches that intuition does not:

- **Making a single field atomic is not the same as making an operation
  atomic.** A counter incremented before launching each task and
  decremented as each finishes can still reach zero early — the scheduler
  may run and complete the first tasks before the launching thread has
  created the rest — so the "all done" notification fires more than once.
  Every field was atomic; the sequence was not. Set the count to its
  final value before launching anything.
- **The failure report is the tool.** Races cannot be stepped through:
  attaching a debugger or adding output changes the scheduling that
  causes them. What you have is the recorded sequence of what happened,
  which is a strong argument for doubles that record their calls — see
  [test-diagnostics.md](test-diagnostics.md).

**Stress tests buy a degree of reassurance, never a guarantee.** Scheduling
differs by machine, by platform version and by what else is running.
Run them often and in more than one environment, and treat unit-level
stress tests as one layer among several rather than as proof.

## Flickering tests are broken tests

A test that fails intermittently is not "mostly working".

- It **masks real defects**: once the suite has known-unreliable tests,
  a genuine intermittent failure is indistinguishable from noise and gets
  re-run away.
- It **scales badly**: as the suite grows, the probability that some
  flickering test fails on a given run approaches one, and the build stops
  meaning anything.
- It **costs the habit of trusting the suite**, which is the expensive
  part and the hardest to get back.

Diagnose the cause — a timeout too close to the real duration, a missing
synchronization, a test that runs ahead of the system — before deciding
anything. If a flicker really must be lived with for now, it carries a
written reason and a date, exactly like any other deliberate exception in
[hygiene.md](hygiene.md).

## Externalize the sources of events

**A system that schedules its own activity internally cannot be tested
deterministically.** A test cannot tell whether the system is stable or
merely between timers; a periodic job can fire in the middle of an
unrelated test; and behaviour scheduled days ahead is unreachable
entirely.

Pull the scheduling out into something driven from outside the components
that use it, and let tests play the part of the scheduler and step the
system through its behaviour.

- The same separation usually pays for itself in operations: scheduled
  activity becomes visible, monitorable and re-triggerable in production
  too.
- It trades fidelity for determinism, so name what is no longer covered
  and cover it elsewhere — see [test-levels.md](test-levels.md).
