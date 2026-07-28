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

**Wanting to test a private member is a design problem wearing a testing
problem's clothes.** Every time a variable looks like the only way to
check that code ran correctly, there is an opportunity to improve the
design; taking the shortcut spends it.

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
