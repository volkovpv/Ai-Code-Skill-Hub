# Diagnostics: what the test says when it fails

**The point of a test is not to pass but to fail well.** Passing is what
it does most days; the day it earns its place is the day it goes red, and
what it is worth on that day is exactly what its failure message explains.

A failure that sends a reader to a debugger has already cost more than the
test saved. A failure nobody can diagnose under deadline gets deleted, and
the safety net goes with it.

## The cycle has four steps, not three

The familiar loop is *fail → pass → refactor*. Insert one step:

| | Step | Done when |
|---|---|---|
| 1 | **Fail** | the test is red for the reason it names |
| 2 | **Report** | the failure message would tell a stranger what is wrong |
| 3 | **Pass** | the smallest change makes it green |
| 4 | **Refactor** | the duplication is gone, still green |

Step 2 happens **before any production code is written**, while the
failure is in front of you and the intent is fresh.

- If the message does not say what was expected of the system, improve the
  test — its name, its assertion, the values it uses — until it does.
  Rerun; read it again.
- The work is not overhead. Taking the trouble to make a failure legible
  is how you find out whether you actually understood the behaviour: an
  intention you cannot state in a failure message is an intention you have
  not finished forming.
- Keep checking the message as the production code grows behind the test.
  The interesting failures are the intermediate ones, and they are the
  ones a future reader will meet.

This applies whether or not the project practises test-driven
development. Where a test is written after the code, the deliberate
break-and-restore that makes it evidence — see
[tdd-cycle.md](tdd-cycle.md) — is also the moment to read its message.

## The cheapest diagnostic is the test itself

A small, focused, well-named test barely needs a message: its name
already says what was expected, and there is only one thing it could have
been checking. Most diagnostic problems are really the problems in
[structure-and-naming.md](structure-and-naming.md) arriving late.

- **A long test fails ambiguously by construction.** When the name covers
  several claims, the report cannot tell you which one broke.
- **A test that asserts several unrelated things reports the first
  failure and hides the rest**, which is a second reason one scenario per
  test is worth the extra files.

## Say which value failed

An assertion that reports only `expected 16301 but was 16103` describes
the symptom and leaves the cause to be guessed — especially when several
assertions in the test could have produced it.

- **Attach the name of the thing being asserted** wherever the runner
  allows it, so the report reads `outstanding balance: expected 16301 but
  was 16103`.
- Where the runtime supports composable, self-describing predicates,
  prefer them to a bare boolean assertion: `assert(isValid(x))` can only
  report *false*, while a predicate that describes its own mismatch can
  report which element, which field and what value.
- Assert the smallest thing that is actually under test. Comparing whole
  structures when one field is the point produces reports where the
  relevant difference is buried; see
  [structure-and-naming.md](structure-and-naming.md).

## Make the values explain themselves

Detail added to an assertion is often a hint that the *values* could have
carried it instead.

- **Self-describing value.** Give a test value content that states its
  role: an identifier whose value is literally `"a customer account id"`,
  a timestamp whose rendering is `start-of-window` rather than a raw
  instant. Then `expected <start-of-window> but got <end-of-window>` names
  the mistake without a message at all, and a reader of the arrange step
  learns what each value is for.
- **Obviously canned value.** Where the type carries no room for
  explanation — a number, a flag, a short code — choose values that could
  not plausibly have come from the real system: a negative identifier
  where real ones are positive, a length far outside the real range, a
  date long before the system existed. A default that leaks through
  untouched then stands out instead of blending in. Team-wide
  conventions for these values are worth having, so that "this is a canned
  value" is recognisable on sight.
- **Tracer object.** When all a test needs is to show that *this* value
  was carried through and handed to the right collaborator, use a double
  with no behaviour whose only job is to be identifiable in the report.
  Give each one a distinct name, so a failure says which of them went
  missing rather than printing two indistinguishable instances. A tracer
  is also a design tool: an empty, named role in the test marks a domain
  concept before you know what its operations are, and gets filled in as
  the code grows.

## Report the cause, not the consequence

When one test both asserts an interaction and asserts a returned value,
the order in which the runtime checks them decides which one you see.

- A missed collaboration usually makes the returned value wrong too, so
  the value assertion fires first and reports an arithmetic surprise
  whose actual cause was the call that never happened.
- **Check the interactions explicitly before the value assertions** when a
  test carries both, so the report names the cause.
- This is one of the concrete payoffs of watching the test fail: expecting
  a missing-interaction failure and receiving a wrong-value one is exactly
  the signal that the order needs fixing.

## Diagnostics are a first-class feature, and so is not needing them

- **Improve the harness, not just the test.** Where the same unhelpful
  report keeps appearing, the fix belongs in the shared helper, builder or
  double that produced it — once, for every test that will ever use it.
- **Stay close to home.** Commit or checkpoint often enough that an
  inexplicable failure can be answered by reverting a few minutes of work
  and trying again. Code is not sacred because it exists, and the second
  attempt is faster than the first; a long debugging session on a change
  you could have discarded is a choice, not a necessity.
- **An unrelated test failing is information, not noise.** It has just
  told you about a coupling in the system that you did not know was
  there. Find out what it is before making it green.
