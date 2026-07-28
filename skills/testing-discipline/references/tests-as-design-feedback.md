# Reading a test as a report on the design

A test is the first client the code ever has, and it is the only client
that reports back. When a test is hard to write, hard to read, slow or
unreliable, that difficulty is **data about the product**, not an
inconvenience to be worked around in the test file.

This inverts the direction the rest of this skill mostly runs in. The
other files ask *is this test any good?* This one asks the question the
answer usually implies: *what is the code telling me by making this test
hard?*

## The symptoms and what each one says

| Symptom in the test | What it says about the code | The change it asks for |
|---------------------|-----------------------------|------------------------|
| **A long arrange step** — many lines of construction for one small assertion | the subject needs too much of the world before it can do anything | split it; the object is doing several jobs, or it takes collaborators it should be given results from |
| **Arrange duplication with no natural home** — the same setup is needed everywhere but resists being factored out | too many objects, too tightly intertwined; there is no seam because there is no boundary | find the missing concept the shared setup is describing and give it a name |
| **A slow test** | the pieces of the application cannot be exercised apart from the whole | a design problem, addressed with design — not with a longer timeout, a bigger machine, or a decision to run the suite less often |
| **A fragile test** — it breaks for reasons unrelated to what it asserts | one part of the application is affecting another at a distance | either break the connection, or bring the two parts together; they are already coupled, the test only made it visible |
| **The urge to reach private state** — the assertion you want needs a member the client cannot see | the goal you are asserting has no public expression | give it one: the state you want to inspect should be reachable as behaviour. See [anti-patterns.md](anti-patterns.md) |
| **An act step of more than one call** | the subject lets a caller stop halfway through one logical operation | move the second step inside. See [structure-and-naming.md](structure-and-naming.md) |
| **No name fits** — you cannot describe the scenario without "and" | the test covers more than one behaviour, or the operation does | split the test; if it will not split, the operation is the thing that needs splitting |
| **You cannot replace a collaborator without special machinery** — the subject reaches it through a global, a static accessor, an ambient registry, or constructs it itself | the dependency is hidden, not absent | pass it in. See *implicit dependencies* below |
| **A long construction argument list** | several of those arguments together are an unnamed concept | look for arguments that are always used together, or that share a lifetime, and give the group a name; the extraction usually names a missing domain object |
| **A long argument list that will not group** | not all of them are dependencies | separate the dependencies (required, no safe default) from the notifications and adjustments (defaulted, overridden per test) — see [isolation-and-fakes.md](isolation-and-fakes.md) |
| **The test class for one type falls into slices that share nothing** | the type has unrelated responsibilities | split the type along the same lines the tests already split along; the tests have done the analysis for you |
| **Every interaction in the test is required, so none stands out** | the test is pinning things it does not care about, or the unit is too large | separate what must happen from what is merely permitted — see [unit-test-value.md](unit-test-value.md) — and if few things remain required, the unit was the problem |

**Wanting to test a private member is a design problem wearing a testing
problem's clothes.** Every time a variable looks like the only way to
check that code ran correctly, there is an opportunity to improve the
design; taking the shortcut spends it.

## Implicit dependencies are still dependencies

A dependency reached through a global, a static accessor or an ambient
registry has not gone away — it has become inaccessible. The test then
needs machinery to intercept it, and that machinery is the problem.

- **Tools that break such dependencies without touching the code spend
  the feedback.** They are sometimes genuinely necessary, and they always
  cost the signal the test was trying to give you. The design weakness
  stays, other code accumulates around it, and by the time an urgent
  change forces the issue nobody remembers what was intended. Use the
  same techniques to break dependencies in tests that you would use in
  production code.
- **Passing the dependency in makes it visible, which is the point.** The
  objection that this exposes an internal is real and is usually worth
  paying: a subject that cannot be constructed without a clock is a
  subject whose dependence on time is impossible to overlook, and that
  dependence has a way of mattering later.
- **The seam is often not the end of the improvement.** Having injected
  the awkward thing, ask what the subject actually wanted from it. A
  subject that takes a clock and then does date arithmetic on the result
  is doing work that belongs to something else; the question it really
  wants answered ("has this window expired?") names a collaborator, and
  once it exists the subject stops knowing about calendars at all. Each
  step leaves both objects easier to test on their own.

## Support reporting is a feature; diagnostic tracing is scaffolding

Two things are usually written through the same facility and are not the
same thing:

| | **Support reporting** | **Diagnostic tracing** |
|---|---|---|
| Audience | operators, support staff, auditors — and the tools they built | the programmer writing the code, now |
| In production | on, and depended upon | off |
| Driven by | somebody's requirement | curiosity |
| Therefore | **test-driven, like any other output** | not test-driven; free to be inconsistent |

- Once support reporting is understood as an output of the application,
  its awkwardness in tests resolves itself: it goes through a
  notification seam you own — reported as objects, in domain terms — and
  the test substitutes a double for it like any other notification. The
  alternative, asserting formatted text produced by a global facility,
  requires managing shared state across tests, cleaning it up, and
  matching strings.
- Writing a test per report is what stops the reporting from being noise:
  it forces the question of who the message is for and what they will do
  with it, and it protects the tools other people wrote to parse it.
- **"I would have to pass a reporter everywhere"** is itself the signal.
  Either much of that reporting is really diagnostic tracing, or the
  domain code has enough duplication that the few places worth reporting
  from have not emerged yet.
- A system that logs so much that the logs are unusable would have been
  better off logging nothing.

## The rule, and its escape valve

**Change the design first, and the test second.** A test bent around a
design defect keeps the defect and adds a second place it has to be
maintained.

The escape valve is real and should be used honestly: **if the design
idea does not come, it does not come.** Assert the state, leave the note,
and come back on a better day — with the cost recorded rather than
hidden. What is not acceptable is doing that silently and calling the
result a passing test.

Two more limits worth stating plainly:

- **Not every part of a system earns this treatment.** The parts you
  touch constantly should be solid enough to change daily; toward the
  periphery, where nothing changes, spottier tests and an uglier design
  cost little. "Finished" is not the goal, and uniform polish is not
  either.
- **A painful test is a symptom, not a diagnosis.** It says *something
  here is wrong*, and it is frequently right about that and wrong about
  what. Use it to start looking, not to justify the first restructuring
  that comes to mind.

## Why writing the test first is a design activity

The loop in [tdd-cycle.md](tdd-cycle.md) is usually explained as a way to
catch defects early. That is the smaller half of it.

- **It is the shortest feedback loop available on an interface
  decision.** The gap between "perhaps the API should look like this" and
  the first honest attempt to use it is seconds, instead of the weeks it
  takes for someone else to feel the consequence.
- **It is scope control.** The test states what "done" means before the
  work starts, which is what stops the work from expanding into
  everything the code could conceivably need.
- **Isolating tests from one another is a design force, not just a
  hygiene rule.** Making each test set up its own world is work, and the
  only way to make that work cheap is to break the problem into small,
  orthogonal, loosely coupled pieces. High cohesion and loose coupling
  are easy to admire and hard to reach on purpose; requiring isolated
  tests is one of the few pressures that reaches them reliably. The same
  force explains why shared mutable state is so expensive: a dependency
  reached through a global cannot be varied per test, and the design
  usually improves more by passing it explicitly than the change costs.
- **Reusable structure emerges from removing duplication, not from
  predicting variation.** The first feature goes in simply; the second, a
  variation, puts the common part in one place and the differences in
  another; by the third the common part is reusable as it stands. What
  you end up with is open to exactly the kinds of variation that actually
  occurred — which is worth more than a generalization designed for
  variation that never arrives. When an unforeseen variation does arrive,
  the tests are what make rapid restructuring safe.

## What this does not license

- It is not an argument for testing everything, or for treating a test
  that is merely *tedious* as proof of a design defect. Judge the test
  itself by the four attributes in
  [unit-test-value.md](unit-test-value.md) first.
- It is not a reason to widen a surface. A member made public so a test
  can reach it is a design made worse to make a test easier — the exact
  inversion of this file.
- It does not replace the judgement about *what deserves a unit test at
  all*; complexity and collaborator count still decide that, and code in
  the wrong quadrant is refactored rather than covered as it stands.
