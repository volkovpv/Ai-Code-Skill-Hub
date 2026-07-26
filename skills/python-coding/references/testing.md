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
- **A test's case set, its subject, and its dimensions are all chosen from
  the specification, never from the artifact under test.** This is distinct
  from "do not tune a test to the gate" above: nothing here is hardcoded to
  pass, every case is genuinely red before its fix, and a mutation battery
  can still report a healthy score while the property below is violated.
  Three rules, one family:
  - **Provenance of the case set.** Derive cases from the specification's
    class, never copied from — or parametrized over — the artifact under
    test. A healthy mutation score is not evidence of specification
    coverage: when the case set mutates together with the implementation,
    the mutant is killed and the unmet specification stays invisible.
    Minimal reproduction: an implementation exposing `ALLOWED = {a, b, c}`
    for a rule the specification states as an open class; a test
    parametrized over that same `{a, b, c}`; a mutation of the
    implementation set turns the test red (healthy mutation score); one
    specification-class member `d` is silently unhandled and no test
    notices. Stricter variant: if the test *imports* the enumeration rather
    than copying it literally, the mutation does not even fail — mutation
    testing is blind to the pattern in that form.
  - **Subject of the test under layered protection.** When a property is
    protected by more than one layer, a test that reaches it through the
    outer layer proves nothing about the inner one; a defence-in-depth
    claim is unverified until each layer is exercised on a path where it is
    the only protection. Equivalently: every layer needs a test that goes
    red when that layer alone is deleted. Minimal reproduction: a value
    guarded both by an upstream filter and by an unconditional downstream
    overwrite; a test that injects through the filtered channel; deleting
    the downstream overwrite leaves the suite green, because the upstream
    filter already intercepts the forged value before the downstream layer
    is ever reached.
  - **Totality across the dimensions a control discriminates on.** A
    parametrized set that varies one dimension of the input says nothing
    about the others, and its size is not evidence — eleven cases over
    eleven names cover one dimension eleven times. Where the implementation
    carries a dedicated mechanism for another dimension, that mechanism is
    by construction untested until the case set varies that dimension too.
    For each guard, name the dimensions of the input it discriminates on
    and require at least one case per dimension; treat a surviving mutation
    as evidence of a missing dimension, not merely of a missing case.
    Minimal reproduction: a mapping whose keys are normalized by a
    dedicated function before a membership test; a case set that varies
    only the key's text; a mutation that moves the membership test from the
    normalized key to the raw key — green, because no case supplies a key
    whose raw and normalized forms differ.

## Secrets in tests

Use test-only values; never pull real credentials into a test. Where a test
needs a signed token or a key, generate/sign a genuine test-only one rather
than mocking the verification away — the code under test should run its
real checks.
