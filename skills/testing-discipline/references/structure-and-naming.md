# Structure and naming

A test is a written claim about behaviour. Its shape, its name and its
assertions are what make the claim legible to the next reader — including
the reader who sees it fail at three in the morning and has to decide
whether the product or the test is wrong.

## Shape

- **Arrange / Act / Assert** (or Given/When/Then), one scenario per test.
  A test that exercises two scenarios reports one failure for two
  different causes.
- Group related scenarios — a class, a suite block, a module per unit
  under test, whatever the runner offers. The grouping is what tells a
  reader which scenarios are alternatives of one another.
- Keep the arrange step readable: **prefer factories or builders over
  copy-pasted fixture blobs**, so a test states only the fields that
  matter to its scenario and inherits the rest.
- A test's setup belongs to the test. Shared mutable state between tests —
  a module-level accumulator, a database row left behind, an object cached
  across cases — turns an unrelated failure into a mystery.

## Naming

- The name states the **behaviour and the condition**:
  `rejects_expired_token`, `keeps_order_when_scores_tie`. Never `test_2`,
  `works`, or the name of the method being called.
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
  tests.
- No conditional assertions. An assertion inside an `if` that the test
  data may not reach is a test that can pass without checking anything.

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
