# Structure and naming

A test is a written claim about behaviour. Its shape, its name and its
assertions are what make the claim legible to the next reader — including
the reader who sees it fail at three in the morning and has to decide
whether the product or the test is wrong.

## Shape

- **Arrange / Act / Assert** (or Given/When/Then), one scenario per test.
  A test that exercises two scenarios reports one failure for two
  different causes.
- **One act step per test.** A second act — act, assert, act again — means
  the test covers two units of behaviour; split it. The one exception is a
  slow integration test walking a state machine, where each act doubles as
  the arrange of the next and splitting would pay the setup cost twice.
- **No branching in a test.** A conditional means the test is describing
  more than one scenario, and unlike multiple act steps this has no
  exception: a branch buys nothing and costs the reader the certainty of
  knowing which path ran.
- **An act step longer than one call is a statement about the subject, not
  about the test.** If a client must call two operations in the right order
  to complete one logical operation, the subject lets a caller stop
  halfway; move the second step inside. (Utility and infrastructure code is
  the usual legitimate exception — check it before accepting it.)
- Group related scenarios — a class, a suite block, a module per unit
  under test, whatever the runner offers. The grouping is what tells a
  reader which scenarios are alternatives of one another.
- Keep the arrange step readable: **prefer factories or builders over
  copy-pasted fixture blobs**, so a test states only the fields that
  matter to its scenario and inherits the rest. Which of the two, and the
  traps in each, are in
  [test-data-builders.md](test-data-builders.md).
- **Mark the subject.** Give the object under test a name that says it is
  the subject rather than one of its dependencies, so a reader of a busy
  arrange step never has to work out which is which.
- A test's setup belongs to the test. Shared mutable state between tests —
  a module-level accumulator, a database row left behind, an object cached
  across cases — turns an unrelated failure into a mystery.
- **Write it backwards when the shape is unclear: assertion first.** Start
  from the assertion that will hold when the work is done, then add
  whatever the assertion refers to, then whatever *that* refers to, until
  the arrange step is complete. Writing a test asks you to decide where
  the behaviour belongs, what to call it, what the right answer is and how
  to check it, all at once; starting from the assertion separates the last
  two out and answers them first.

## Naming

- The name states the **behaviour and the condition**:
  `rejects_expired_token`, `keeps_order_when_scores_tie`. Never `test_2`,
  `works`, or the name of the method being called.
- **Name it as you would describe the scenario to a non-programmer who
  knows the domain.** A name a domain expert can read is also the fastest
  name for a programmer to read, and it is the check that the test is
  addressed to behaviour rather than to code.
- **No rigid template.** A fixed
  `method_scenario_expectation` mould forces the name toward the
  implementation and cannot hold a description of non-trivial behaviour.
  Plain words, separated so they stay readable at length.
- **Do not put the name of the method under test in the test's name.** The
  method is the entry point to the behaviour, not the behaviour; renaming
  it should not oblige you to rename the test. (Utility code, whose
  behaviour barely exceeds the method itself, is the exception.)
- **State a fact, not a wish**: `delivery_with_a_past_date_is_invalid`, not
  `..._should_be_invalid`. A passing test asserts that something is true of
  the system today.
- The name is part of the failure report. If the runner's output does not
  say what was expected of the system, the name is not doing its job.
- No duplicate test names inside a group: two identical names make one of
  them invisible in the report.

## Assertions

- **Assert the exception and its condition, not just "it raised"**: the
  expected error type plus the relevant attribute or message fragment. A
  test that passes for the wrong error is not a test.
- Assert on the observable outcome the specification names, not on
  incidental structure a refactor will change (call counts of an internal
  helper, the order of an unordered collection, whitespace of a formatted
  string that nobody specified).
- One logical assertion per scenario. Several physical assertions that
  describe one outcome are fine; several unrelated outcomes are several
  tests. "Exactly one assertion per test" comes from the mistaken idea
  that a unit is a unit of code — one unit of behaviour may legitimately
  have several outcomes.
- An assert block that keeps growing is usually a missing abstraction, not
  a thorough test: comparing an object field by field where the object
  could be compared by value is the common case.
- No conditional assertions. An assertion inside an `if` that the test
  data may not reach is a test that can pass without checking anything.
- **Name the expected value; do not settle for a property of it.**
  Asserting that a result is non-zero, non-empty or merely of the right
  kind passes for a large family of wrong answers. If the answer should be
  50, say 50. Where a whole class of values really is acceptable, that
  class is what the specification says and what the assertion should
  express — not the first predicate that happens to hold.
- **…and say nothing about what the scenario does not drive.** The rule
  above governs the outcome under test; its other half governs
  everything else in the same result. Do not assert values the test's
  inputs did not determine, do not re-assert behaviour another test
  already pins, and do not compare a whole structure when one field is
  the point — each of those is a way for an unrelated change to turn this
  test red. The pair reads as one rule: **exact about the claim, silent
  about the rest.** An assertion over text is the common case — pin the
  information that must be present rather than the exact rendering,
  unless the rendering is itself what is specified. When pinning text
  precisely turns out to be hard, that is often a missing structured type
  whose conversion to text could be tested on its own.

## The data a test carries

The values in a test are read by people. Choose them for what they reveal.

- **Make the relationship between input and expected value visible.**
  Where the expected value is derived from the inputs by a rule the
  specification states, write the derivation out in the test rather than
  its result: a commission rule stated as *rate 2, commission 1.5%* reads
  as `100 / 2 * (1 - 0.015)`, and a reader can check the claim against the
  rule without leaving the test. Collapsing it to `49.25` hides exactly
  the thing under test. This is the one place where in-line numeric
  literals beat named constants — within one short test the relationship
  between the numbers *is* the documentation. Where a symbolic constant
  for the same quantity already exists, use it.
- **This is not recomputing the expected value with the code under
  test.** The derivation above is written from the specification, out of
  literals the test owns; the moment it reaches for the production
  routine, the helper or the constant that the subject itself uses, it
  stops being a claim and starts asserting that the code equals itself —
  see [anti-patterns.md](anti-patterns.md).
- **Never let one constant mean two things in the same test.** If a
  function takes two arguments, do not pass it 2 and 2: an implementation
  that swaps, duplicates or ignores an argument passes. Different roles
  get different values, and a value that differs from another should
  differ for a reason a reader can name.
- **Use the smallest data that forces the same decisions.** A list of
  three items that exercises the same branches as a list of ten is the
  better input; extra volume adds reading cost and no coverage. Handling
  multiple inputs is still a behaviour that gets its own cases — small
  data is not an excuse for thin coverage.
- **Realistic data is for the cases that require it**: replaying captured
  traces of real events, running a new implementation against a previous
  one in parallel, or refactoring a computation that must produce
  bit-identical answers. Elsewhere it obscures why an expected value is
  what it is.
- **Write the information, not its representation.** Where a value stands
  for a *concept* — "no customer was found", "the field was not supplied",
  "this argument is irrelevant here" — give the concept a name the test
  owns and use the name. A test that writes the bare representation
  instead says nothing about why that value is there, and binds itself to
  a decision made elsewhere: when the concept is later represented
  differently, every such test has to be found and edited, and any that
  the type system does not catch keep compiling while meaning something
  else. Named once, the change is one line.
- **Give a value content that states its role wherever the type allows
  it**, and choose values that could not have come from the real system
  where it does not. Both are diagnostic decisions as much as readability
  ones — see [test-diagnostics.md](test-diagnostics.md).

## Grouping similar cases

- Where several scenarios differ only in their data, **group them as one
  parametrized test** with one case per fact instead of copying the body.
  The cost is a more generic name and a less obvious link between input and
  expectation — so it is a trade, not a default.
- **Split the positive scenario out** when the parameters alone do not make
  clear which case is expected to succeed. A named positive test plus a
  parametrized negative one usually reads better than one table carrying an
  `expected` column.
- When the behaviour is complex enough that a reader cannot tell from the
  case list what is being claimed, stop parametrizing and write the cases
  out as named tests.
- Whatever the grouping, the cases themselves come from the specification —
  never from the artifact under test; see [hygiene.md](hygiene.md).

## Example-based and property-based cases

- Example-based tests are the default: they pin the behaviour the
  specification names, including its boundaries and its failure modes.
- Reach for **property-based tests** where you can state an invariant
  rather than an example — round-trip (parse then serialize), idempotence,
  ordering, conservation of a total. Parsers, serializers, encoders and
  pure functions are the natural home.
- A property-based failure is a discovery, not a nuisance: **pin the
  failing input it finds as an ordinary regression case**, so the next run
  does not have to rediscover it.
- Neither style replaces the other. A property says "this holds for
  everything"; an example says "and here is exactly what that looks like".
