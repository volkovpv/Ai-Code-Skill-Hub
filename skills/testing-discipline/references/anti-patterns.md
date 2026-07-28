# Unit-testing anti-patterns

Each of these is a popular answer to a real problem. Each buys a short-term
convenience by binding the suite to something that is not behaviour, and
the bill arrives as false positives later.

## Testing a private method directly

Do not widen a member's visibility so a test can reach it. Private members
stand for implementation details; asserting them costs resistance to
refactoring, the one attribute that cannot be partially conceded. Test a
private method **indirectly, through the observable behaviour that uses
it.**

If that leaves it insufficiently covered while the observable behaviour
around it is well covered, the code is saying one of two things:

- **it is dead code** — nothing reaches it any more; delete it;
- **an abstraction is missing** — it is complex enough to be its own unit;
  extract it into a separate, collaborator-free unit with its own public
  surface and test that directly.

**The rare exception** is a member that is private *and* part of the
observable behaviour — typically a constructor that exists as a contract
with a mapping, serialization or factory facility that builds objects
reflectively. Its being private does not make the contract less real.
Widening it is not coupling to a detail, provided it keeps enforcing its
preconditions; the alternative is to construct the object the same
reflective way the facility does.

## Exposing private state to enable an assertion

A test interacts with the subject exactly as production code does, with no
special privileges. Making a field readable so a test can check it binds
the suite to something production does not depend on.

Assert instead the behaviour that the state produces — the discount a
promoted customer now receives, not the status field the promotion set. If
production code later starts reading that state, it becomes part of the
observable behaviour and may be asserted then, for that reason.

## Leaking the algorithm into the test

A test that recomputes the expected value with the same algorithm as the
production code asserts only that the algorithm equals itself. It has
almost no resistance to refactoring and cannot tell a real defect from a
false alarm: when it goes red the tempting fix is to copy the new
implementation into the test, and it usually wins.

**Hardcode the expected results**, obtained from something other than the
code under test — the specification, a domain expert, a worked example, or,
when refactoring a legacy implementation, results captured from the old one
beforehand. This is the assertion-side view of the case-set provenance rule
in [hygiene.md](hygiene.md).

**Where the boundary runs.** Writing the specification's own arithmetic
into the assertion — the rule spelled out over literals the test owns, so
a reader can check it without leaving the file — is the opposite of this
anti-pattern and is encouraged; see
[structure-and-naming.md](structure-and-naming.md). What makes an
expression a leak is not that it computes, but *whose* computation it
reuses: the moment the test calls the production routine, imports the
production constant, or re-implements the subject's own steps, the
assertion has lost its independent source. The test:

- may restate the rule the specification gives, in the test's own terms;
- may not obtain the answer from the thing it is judging.

## Code pollution — production code that exists only for tests

A flag on a production type that switches its behaviour off "when running
under test" mixes test code into the product, raises the product's
maintenance cost, and creates a branch that can be enabled by accident in
production.

Extract the test-only behaviour into a separate implementation behind a
declared seam and let the product ship only the real one. The seam itself
is a mild pollution — it exists partly for testing — but it is the cheap
kind: a contract holds no logic, so it cannot carry a defect, and it cannot
be switched on by mistake.

## Doubling a concrete type to keep part of it

Replacing a type partially — doubling it but letting the members you did
not override run the real code — is always a signal that the type carries
two responsibilities: the computation worth keeping and the collaboration
worth replacing.

**Split it** instead: an adapter that talks to the external dependency, and
a collaborator-free unit that computes. The double then stands for a whole
seam, and nothing about it is partial.

## Time as ambient context

Reaching for the current time through a global or static accessor — and a
test-time hook that redirects it — pollutes production code and introduces
a shared mutable dependency between tests, which quietly moves them out of
the unit category and makes their order matter.

**Inject time explicitly.** Prefer injecting it as a **value** — the
instant the operation happens — over injecting it as a service: values are
easier to pass around in production code and easier to fix in a test. Where
the wiring makes that impractical, inject the service at the entry point of
the operation and pass the value it produced down the rest of the call
chain. This is the same requirement as *control time, never wait for it* in
[isolation-and-fakes.md](isolation-and-fakes.md).

## Sharing the arrange step through a per-test setup hook

Hoisting the arrange step into a hook that runs before every test in the
group shortens the file and costs two things: the tests become coupled to
one another, so changing the setup for one changes it for all; and a reader
must look in two places to learn what a test does.

**Prefer factory methods** that each test calls with the parameters that
matter to it — reusable, and the test keeps its whole story in one place.
The exception is setup that genuinely every test needs, typically the
connection an integration suite opens; put that in a shared base fixture
rather than repeating it per group.
