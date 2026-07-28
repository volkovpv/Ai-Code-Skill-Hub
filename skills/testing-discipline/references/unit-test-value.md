# What makes a unit test worth having

Test code is a liability like any other code, so a test has to earn its
place. These are the criteria it is judged by — the same ones whichever
school [schools.md](schools.md) the project declared, and whatever the code
under test is written in.

## The four attributes

| Attribute | The question it answers |
|-----------|-------------------------|
| **Protection against bugs** | if the behaviour breaks, does this test go red? |
| **Resistance to refactoring** | if the implementation changes but the behaviour does not, does this test stay green? |
| **Fast feedback** | how soon does it tell you? |
| **Ease of maintenance** | how hard is it to read, and how hard is it to keep runnable? |

A test's value is the **product** of the four, not their sum: score zero on
any one and the test is worth zero overall, however strong the other three.
A test that cannot fail protects nothing; a test that fails on every
refactoring is noise; a test nobody waits for stops being run; a test
nobody can read stops being maintained.

The first two together are the test's **precision** — signal (bugs found)
over noise (false alarms):

- a **false negative** — behaviour broken, test green — is what protection
  against bugs prevents;
- a **false positive** — behaviour intact, test red — is what resistance to
  refactoring prevents.

False positives cost little early in a project and a great deal later, when
regular refactoring is what keeps the codebase workable. A suite that cries
wolf gets ignored, and the one real failure is ignored along with it.

## Resistance to refactoring is the attribute you do not trade

The first three attributes are mutually exclusive; no test maximizes all
three at once. The extremes make it visible:

| Extreme | Protection | Resistance | Feedback |
|---------|-----------|------------|----------|
| Integration test through every real dependency | excellent | excellent | far too slow |
| Trivial test over a one-line accessor | none | excellent | instant |
| Test asserting the exact statement the subject emitted | good | none | instant |

So the trade is **between protection against bugs and fast feedback** —
that is the axis the test pyramid arranges, with slow, broad tests few at
the top and fast, narrow ones many at the bottom. Resistance to refactoring
is not on that axis: it is close to binary — a test either survives a
behaviour-preserving change or it does not — so it cannot be partially
conceded. Maximize it always.

**Coupling to implementation details is the single cause of false
positives.** The only cure is to assert the outcome the specification
names, approaching the subject the way its client does.

## Observable behaviour versus implementation detail

Code belongs to the **observable behaviour** when it does one of exactly
two things for a client that has a goal:

- exposes an **operation** — a method that computes something and/or
  produces a side effect — that helps the client reach that goal, or
- exposes **state** that helps the client reach that goal.

Everything else is an implementation detail. *Client* is relative to where
the code sits: for a domain object the client is the application service
calling it; for the application service it is the outside caller. Follow
the chain outward and every piece of genuinely observable behaviour traces
back to a requirement — which is why a test that cannot be traced to one is
a strong signal that it is bound to a detail.

- A well-designed surface makes observable behaviour public and every
  implementation detail private. Leaking a detail into the public surface
  is what makes an implementation-coupled test *possible* in the first
  place.
- **Heuristic:** if a client must call more than one operation to reach a
  single goal, the surface is leaking. One goal should take one call; the
  intermediate steps belong inside, where no client can skip them.
- Improving the surface improves the tests for free: with the details
  private, a test has nothing left to bind to except behaviour.
- **Interactions inside the application are implementation details;
  interactions that cross the application boundary are not.** The latter
  are a contract with another system, they must survive refactoring, and
  that is exactly what makes them worth asserting.

## Three styles, in order of preference

| Style | What it asserts | Risk of coupling | Maintenance cost |
|-------|-----------------|------------------|------------------|
| **Output verification** | the value returned for the given input | lowest | lowest |
| **State verification** | the state left behind by the operation | medium | medium |
| **Communication verification** | the calls the subject made to its collaborators | highest | highest |

- **Prefer output verification.** It applies to code with no hidden inputs
  or outputs: no side effects, no reads of ambient state, no exception used
  as a second return channel. Everything such code does is in its
  signature, so the test is "feed inputs, assert the result" and nothing
  else — the shortest possible test with the least to couple to.
- Where output verification does not fit, **prefer state verification.**
  Assert state that is already public for the product's own sake; never
  widen the surface to make an assertion possible — see
  [anti-patterns.md](anti-patterns.md).
- **Communication verification is the last resort.** Under both schools it
  is legitimate without further argument in exactly one place: an
  interaction crossing the application boundary whose effect other systems
  can see.

Moving tests toward output verification is a design activity, not a
test-writing trick. Split the code that **decides** from the code that
**acts on the decision**: the deciding part takes plain inputs and returns
a description of what should happen; the acting part is a thin, branch-free
shell that applies it. The decider is then coverable by output verification
alone and the shell needs only a few integration tests. The cost is real —
the shell must gather inputs up front, which can mean fetching data the
decision may not need — so apply the split where complexity or business
importance justifies it, not everywhere.

### When you do assert an interaction

- **Assert at the last point before the call leaves your process** — the
  outermost adapter you own — not at an intermediate wrapper. That covers
  more code with the same test, and binds the assertion to the message the
  external system actually receives rather than to a call on a class you
  happen to have written.
- **Assert in both directions**: that the expected interaction happened,
  and that no unexpected one did. Compatibility with an external system is
  a two-way obligation.
- **Do not let production code state what "correct" means.** Build the
  expected message from literals owned by the test; a test that composes it
  with the same production helper the subject used asserts only that the
  helper equals itself.
- **Prefer a hand-written double that records what it received** and
  exposes named assertion helpers over a chain of framework expectations:
  it is reusable across tests, it reads as a sentence, and it keeps the
  contract in test code.
- Not every unmanaged dependency needs the same fidelity. Where only the
  existence and the content of a message matter and not its exact shape —
  diagnostic logging is the usual case — asserting at a higher-level,
  domain-shaped seam is enough.

### Specify precisely what should happen, and no more

Every interaction a test pins is a constraint on the implementation. The
constraints you *meant* to state are the contract; the ones you stated by
accident are what turns a behaviour-preserving change into a red suite.
This applies under both schools, and it is what makes a London-school
suite survivable at all — see [schools.md](schools.md).

- **Allow queries; expect commands.** A call that only asks a question
  changes nothing, so how many times it happens is not part of the
  contract: permit it any number of times, including none. A call that
  changes something outside the subject is a different matter — the
  system's state depends on how often it happens, so require it exactly
  as often as the contract says. Pinning a query's call count means the
  test breaks when a cache is introduced or an algorithm reorganised,
  which changed no behaviour anyone can observe. (Where the *subject* is
  a cache, the call count is the behaviour, and then you do pin it.)
- **Write few expectations.** When everything in a test is required,
  nothing in it is emphasised, and a reader cannot tell what is under
  test from what is scaffolding. More than a handful of required
  interactions usually means the unit is too large or the test is pinning
  interactions it does not care about.
- **Match arguments only as precisely as the scenario constrains them.**
  Where the scenario turns on one field of an argument, constrain that
  field and leave the rest free; where a message must merely carry
  certain information, assert that the information is present rather than
  pinning the exact rendering. An argument matched exactly when the test
  only cared about part of it is a false positive waiting for the next
  unrelated change.
- **Constrain call order only where the order is part of the contract.**
  Most orderings are incidental, and pinning them locks down the
  implementation for nothing. Where order genuinely matters — a result
  may not arrive after the "finished" signal — express the constraint
  that actually holds rather than a full sequence: "not after the
  terminal event" leaves the results free to arrive in any order, while a
  strict sequence forbids a reordering nobody promised was forbidden. One
  practical form is to have the double append a marker per call and
  assert once against the accumulated record, which fails with the whole
  sequence in the message.
- **Ignoring a collaborator wholesale is a power tool.** Declaring that a
  peer is irrelevant to this scenario keeps the test focused, and it does
  not contradict *assert in both directions* above: that rule governs the
  dependency the test is about, this one governs the ones it is not. Two
  cautions — the ignored behaviour must be covered by some other test,
  and a *chain* of ignored objects is a design smell rather than a
  convenience, saying that the subject is reaching through one
  collaborator to get at another.

## What deserves a unit test at all

Classify production code on two axes: how complex or domain-important it
is, and how many collaborators it has.

| | Few collaborators | Many collaborators |
|---|---|---|
| **Complex / domain-important** | domain model, algorithms → **unit-test thoroughly** | over-complicated code → **refactor; do not test as it stands** |
| **Simple / incidental** | trivial code → **do not test** | orchestrators, controllers → **cover briefly, with integration tests** |

- The upper-left quadrant is where unit tests pay: high protection, low
  maintenance cost, few or no collaborators to arrange.
- Trivial code — a one-line accessor, an empty constructor — yields tests
  whose value rounds to zero. Coverage is not a reason to write them.
- Over-complicated code, an orchestrator that also decides, is the
  problematic quadrant: expensive to unit-test and too risky to leave
  uncovered. Split it into a collaborator-free decider and a thin
  orchestrator, and the two halves land in quadrants that are each easy to
  cover. Rule of thumb: **the more important or complex the code, the fewer
  collaborators it should have.**
- Treat the subject as a **black box**: derive cases from the
  specification, not from the source. A white-box view has one good use —
  reading coverage to find *untested* areas — after which those areas are
  tested as a black box again. A coverage percentage is a diagnostic, never
  a target.
- **Better no test than a bad one.** A test that cannot be traced to a
  requirement, or that would survive any behaviour change, is a liability;
  rewrite it or delete it.
- Failing fast is sometimes the alternative to a test: an edge case that
  makes the application stop immediately, visibly, and without corrupting
  data does not also need a test of its own.

### What is on the hook, and how deep to go

What earns tests, when you need a shorter answer than the quadrants: the
**conditionals, loops, operations and polymorphic dispatch that you
wrote** — and only those you wrote.

- **Do not test other people's code.** A suite that re-verifies a
  dependency's own behaviour pays maintenance for a guarantee it does not
  own. Two exceptions: you have reason to distrust it, and you are about
  to depend on a facility for the first time — the latter is a learning
  test against the real thing, which is evidence rather than coverage; see
  [isolation-and-fakes.md](isolation-and-fakes.md).
- Where a dependency's *defect* forces logic of your own, that logic is
  yours and is tested as such. Pinning the upstream misbehaviour with a
  test that will go red when it is finally fixed is a cheap way to be told
  when the workaround can go.
- **Depth is calibrated by the cost of being wrong.** How many cases a
  behaviour deserves is a question about acceptable time between failures,
  not about a number of tests: for a rarely reached input whose failure is
  visible and cheap, an extra case buys nothing measurable; for code whose
  failure is expensive or irreversible, combinations you consider unlikely
  are exactly the ones worth writing. Confidence, not case count, is the
  quantity being bought — where knowledge of the implementation already
  supplies it, the test is not needed.
