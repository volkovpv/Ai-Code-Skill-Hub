# Isolation and fakes

Every fake is a claim about something the test does not run. The rules
below are about keeping that claim true — and about noticing the cases
where no fake can make it true at all.

*Which* collaborators are replaced at all is a school decision the host
project declares; this file is about what a fake may stand for and how its
claim is justified once the decision is made. See
[schools.md](schools.md).

## What a unit test may touch

- A unit test touches nothing external — no network, disk, database,
  message broker, or wall-clock dependence. Anything external is faked
  behind the seam the code already exposes (a parameter, an interface, an
  injected dependency).
- A test that needs a real external system is an integration test. Say so,
  put it where the suite expects it, and give it its own lifecycle — do
  not let one quietly grow inside the unit suite.
- An in-process collaborator the project owns and constructs fresh per test
  is never the thing that breaks test isolation; a dependency two tests
  share — a mutable global, a database, a staging environment — always is.
  Whether such a collaborator is nonetheless replaced is the school's call.

## The two kinds of double, and what each may be used for

Whatever a runtime calls them — dummy, stub, fake, spy, mock — every double
falls into one of two kinds, and the distinction decides what a test is
allowed to assert.

| Kind | Stands in for | May the test assert the call? |
|------|---------------|-------------------------------|
| **Stub** (also dummy, fake) | an **incoming** interaction: a call the subject makes to *obtain* data — a query | **No** |
| **Mock** (also spy) | an **outgoing** interaction: a call the subject makes to *change* something — a command | Yes, under the conditions below |

- **Never assert an interaction with a stub.** A call that fetches input is
  a step on the way to the result, not the result; asserting it pins an
  implementation detail and is the most easily spotted form of
  over-specification.
- A double can be both at once — configured to answer one call and asserted
  on a *different* one. That is not a violation; asserting the same call
  that was configured to return data is.
- The kinds map onto the command/query split: a method that produces a side
  effect and returns nothing is a command, a method that returns a value
  and changes nothing is a query. Code that keeps them separate is code
  whose doubles classify themselves.
- An outgoing interaction is worth asserting only when its effect is
  visible outside the application — see
  [unit-test-value.md](unit-test-value.md) for where and how to assert it.
- **Double only types you own.** Wrap a third-party surface in an adapter of
  your own and double the adapter: you cannot vouch for a double of code
  whose behaviour you have not observed, and the adapter also confines the
  blast radius of an upstream API change to one file.

## Control time, never wait for it

- Code that "knows what time it is" takes the clock as a dependency, so a
  test can inject a fixed one. Never make a test sleep to let wall-clock
  time pass.
- **No waiting on wall-clock in any test.** Poll with a deadline, or drive
  the scheduler/event the code actually waits on. "The task has probably
  finished by now" is not a synchronisation primitive.
- Asynchronous tests run the real scheduler of the platform and give every
  awaited assertion a deadline, so a hung await fails the test instead of
  hanging the suite.

## What to fake

- Fake **the seams the code exposes**, never someone else's internals
  (private methods, third-party library guts). A seam the project declares
  is satisfied by a plain stub — a mocking library is a convenience, never
  a requirement.
- Patching a module attribute, an import, or a global — whatever facility
  the language offers — is a last resort, used only when no seam exists,
  with a justifying comment. A patch is a fake bound to a name rather than
  to a contract; it survives no refactor and documents nothing.
- The more a fake knows about the internals of what it replaces, the more
  it tests itself. Prefer the narrowest seam that still expresses the
  dependency.

## Two shapes worth knowing

- **To exercise a path the real dependency almost never takes, sabotage
  one operation rather than reproducing the condition.** A double that
  differs from the real collaborator in exactly one respect — the write
  that fails, the read that returns nothing, the call that times out —
  reaches the error branch without filling a disk or unplugging a cable.
  Error handling that is never executed does not work; this is usually
  the cheapest way to execute it. Keep the deviation to the single
  operation under test, so the double stays readable as "the real thing,
  except this fails".
- **To assert that things happened in a particular order, accumulate a
  record and assert on it once.** A double that appends a marker per call
  turns an ordering claim into a single equality against one value, which
  reads as a sentence and fails with the whole sequence in the message.
  Where the order genuinely does not matter, compare as an unordered
  collection — and say so, rather than pinning an order the specification
  never promised.

## How a fake's contract becomes known to be true

**A fake's own return values, when the property under test belongs to an
external system, are established by observing that system once, never by
reading.** The rule above says *what* to fake; this says how the fake's
contract becomes known to be true. When the subject is a message broker,
an authentication encoder, a database driver's row shape, or any other
system this project does not own, no fake, and no re-reading of a project
norm, an RFC, or vendor documentation, can establish what that system
actually does — only a live observation against the real system can.
Write the fake only after a probe against the real system has pinned the
behaviour, then reuse that pinned observation as a fixture rather than
re-deriving it from prose on every subsequent change. Treat a second
rejection of the same reading on the same external-system property as the
signal to switch evidence class from reading to a live observation, not as
cause to produce a third reading.

- **Minimal reproduction — an identity that vanishes.** A URL parser that
  reports an empty user and an absent user identically: `amqp://:p@h:1`
  carries an empty user with a password, `amqp://h:1` carries no user at
  all, and both surface the same empty-or-null user to the reader. Any
  client library reading that URL is therefore free to substitute its own
  default identity — a fact no fake at the wrapper's own seam can see,
  because the fake's job is to stand in for the very layer performing the
  substitution.
- **Second reproduction, same family — a row that collapses.** A SQL
  engine names an unaliased expression column `?column?`, so
  `SELECT true, false` yields two identically-named fields; a driver that
  builds each row as a mapping keyed by column name collapses them into a
  one-key row, while `SELECT true AS a, false AS b` returns both. The
  ordinary two-field row fake is exactly wrong for that driver mode, and
  only a live query against the real database (or the driver's positional
  row mode) exposes it.

### The observation is a test, and it has a lifecycle

The probe that pins the contract is not a throwaway script. Give it the
shape it already has — a test against the real facility — and it pays
twice.

- **Write it before the first use of an unfamiliar external facility**,
  not after the integration misbehaves. Its job is to state what you
  believe the facility does and find out immediately whether that is
  true; if your understanding is right it passes first time, which costs
  minutes and settles the question.
- **Re-run it on every upgrade of that dependency, before anything else.**
  A failure there means the application cannot work either, and it names
  the cause precisely; a green run means the rest of the suite is
  measuring your code rather than someone else's release notes.
- **The fake and the real thing should answer to the same tests.** The
  standing risk of any double is that it stops resembling what it
  replaces. Writing the contract as a set of cases that can be executed
  against both — the double in the fast suite, the real dependency
  wherever it is reachable — is what converts that risk into a failing
  test instead of a production surprise.
- These tests live where the suite keeps things that touch the outside
  world, not in the unit suite, and they carry their own lifecycle: they
  are allowed to be slow and to require an environment, and they are
  never the reason a unit test reaches the network.

## Properties that live on the way out of a call

**Third reproduction, the outbound-mutation shape:** any third-party
client whose outgoing call sets its own request-id, retry token, or
default identity header regardless of what the caller passes — an SDK
whose own interceptor regenerates a client-supplied trace or correlation
id before the request leaves the process — mutates an argument the caller
does not fully control on the way OUT of the call; there is no return
value to inspect and the fake stands in for the very code that would
decide the outcome, so a reader who checks only "the fake's return values
are true of the real system" and stops there would still miss it. The
belief that needs a live observation here is that the caller's argument
reaches the wire unmodified, not that the fake computed the right output
for a given input.

## Properties that live in the construction itself

**A test that constructs the collaborator itself establishes nothing about
the construction the product performs.** When the property under test is
*how* a third-party client gets built — which constructor or options
arguments are passed, which interceptors, hooks, or middleware are wired —
the seam exercised must be the actual production factory, provider, or
entry point that performs that construction, never a hand-assembled
instance built inside the test. A test that instantiates the client
itself, wires its own interceptor list onto it, and then asserts a
property of that hand-built object proves only that the property is
achievable, never that the product's own wiring achieves it.

- **Minimal reproduction.** A client factory is the sole place the
  interceptor/hook list is assembled for production use; if every test
  builds its own client with its own interceptor list, removing that
  argument from the factory call can leave the suite fully green while the
  running product wires no interceptors at all — a mutation any coverage
  tool would flag as "removed, no test failed," which is exactly the
  signal to route the test through the factory instead of adding another
  hand-built-client test.
