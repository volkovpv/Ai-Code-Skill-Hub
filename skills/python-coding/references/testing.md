# Testing

A code change without its tests is not done. These rules hold for any test
runner (the examples use pytest-style phrasing, the discipline fits stdlib
`unittest` equally) and any project layout; wiring-level conventions (what
to fake in a ports-and-adapters service, DI seams) live in the
`hexagonal-service` skill.

## Structure and naming

- **Arrange / Act / Assert** (or Given/When/Then), one scenario per test.
- Group related scenarios (a class or module per unit under test); test
  names state the behaviour and the condition, e.g.
  `test_rejects_expired_token`, not `test_2` or `test_works`.
- A unit test touches nothing external — no network, disk, database, or
  wall-clock dependence; anything external is faked behind the seam the
  code already exposes (a parameter, a `Protocol`, an injected
  dependency). Control time by injecting a clock, not by sleeping.
- Fake **protocols and seams the code exposes**, never someone else's
  internals (private methods, third-party library guts). A `Protocol`
  parameter is satisfied by a plain stub class — no mock library needed;
  `monkeypatch`/`unittest.mock.patch` of module attributes is a last
  resort, used only when no seam exists, with a justifying comment.
- Prefer factories/builders over copy-pasted fixture blobs. Use
  property-based tests (Hypothesis-style) for parsers, serializers, and
  pure functions whose invariants you can state (round-trip, idempotence,
  ordering); keep the failures it finds as pinned regression cases.
- **Assert the exception and its condition, not just "it raised"**: the
  expected exception type plus the relevant attribute or message fragment
  — a test that passes for the wrong error is not a test.
- **Async tests run a real event loop** and every awaited assertion has a
  deadline; never "the task probably finished by now" via `sleep`. No
  waiting on wall-clock in any test — poll with a deadline or inject the
  clock/event.

## Types and tests divide the work

Types and unit tests are complementary verification: the checker eliminates
whole classes of invalid inputs; tests demonstrate behaviour on valid ones.

- **Do not test inputs the type checker already forbids** (calling with
  `None` or a wrong-type argument) — there is no expected behaviour to
  demonstrate. Remember the checker only covers checked callers: at a
  public API boundary that untyped code can reach, validation is a runtime
  feature and **is** tested.
- **Exception — harmful bypasses:** when a type-level restriction guards
  against data corruption or a security breach, enforce it at runtime too,
  and test that enforcement. This runtime check is a feature, not
  redundancy.
- **Every `TypeGuard`/`TypeIs` predicate gets unit tests**, including
  near-miss values — the checker never verifies that a guard's body
  matches its predicate, and a wrong guard poisons every downstream
  branch.
- **Nontrivial typed utilities get type-level tests** pinned next to them:
  positive assertions via `typing.assert_type`, negative cases via a
  narrowly-scoped ignore that the checker itself polices (with mypy
  `warn_unused_ignores` / pyright `reportUnnecessaryTypeIgnoreComment`
  enabled, an obsolete ignore becomes an error) — this is the one
  sanctioned home of a type-level suppression.

## Hygiene (non-negotiable)

- No focused or skipped tests committed: no `@pytest.mark.skip` /
  `skipif` without a written reason and a tracking reference, no
  commented-out tests, no conditional assertions, no empty tests, no
  duplicate test names.
- Strictness relaxations (`Any`, `cast`, `print`, patching) are allowed
  **only** inside test files.
- **Do not tune a test to the gate:** never hardcode an expected value "so
  it passes", never disable a check, never refresh a snapshot/golden file
  without understanding the cause. A red test means dig into the cause.
- **Every bug fix ships a regression test** that reproduces the defect and
  fails before the fix. Unit tests are mandatory for any behaviour change.
- Tests are deterministic: no reliance on dict-iteration accidents,
  wall-clock time, random seeds you did not pin, or test execution order.

## Secrets in tests

Use test-only values; never pull real credentials into a test. Where a test
needs a signed token or a key, generate/sign a genuine test-only one rather
than mocking the verification away — the code under test should run its
real checks.
