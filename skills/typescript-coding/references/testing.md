# Testing

A code change without its tests is not done. These rules hold for any test
runner and any project layout; wiring-level conventions (what to mock in a
ports-and-adapters service, DI seams) live in the `hexagonal-service` and
`typescript-nestjs` skills.

## Structure and naming

- **Arrange / Act / Assert** (or Given/When/Then), one scenario per test.
- Group related scenarios (`describe(...)` or the runner's equivalent); test
  names state the behaviour and the condition, e.g.
  `test_rejects_expired_token`, not `test_2` or `works`.
- A unit test touches nothing external — no network, disk, database, or
  wall-clock dependence; anything external is faked behind the seam the code
  already exposes (a parameter, an interface, an injected dependency).
- Mock **interfaces and seams the code exposes**, never someone else's
  internals (private methods, third-party library guts). Patching module
  imports is a last resort, used only when no seam exists, with a justifying
  comment.
- **A fake's own return values, when the property under test belongs to an
  external system, are established by observing that system once, never by
  reading.** The rule above says *what* to fake; this says how the fake's
  contract becomes known to be true. When the subject is a message broker,
  an authentication encoder, a database driver's row shape, or any other
  system this project does not own, no fake, and no re-reading of a project
  norm, an RFC, or vendor documentation, can establish what that system
  actually does — only a live observation against the real system can. Write
  the fake only after a probe against the real system has pinned the
  behaviour, then reuse that pinned observation as a fixture rather than
  re-deriving it from prose on every subsequent change. Treat a second
  rejection of the same reading on the same external-system property as the
  signal to switch evidence class from reading to a live observation, not as
  cause to produce a third reading. Minimal reproduction:
  `new URL("amqp://:p@h:1").username` is `""` — indistinguishable from the
  absent user of `new URL("amqp://h:1")`, whose `username` is also `""` — so
  any client library reading that URL is free to substitute its own default
  identity, a fact no fake at the wrapper's own seam can see, because the
  fake's job is to stand in for the very layer performing the substitution.
  Second reproduction, same family: PostgreSQL names an unaliased expression
  column `?column?`, so `SELECT true, false` yields two identically-named
  fields, and a driver that builds each row as an object keyed by column
  name collapses them into a one-key row (`{ "?column?": false }`) while
  `SELECT true AS a, false AS b` returns both — a two-property object fake
  for that row, the ordinary expectation, is exactly wrong, and only a live
  query against the real database (or the driver's array row mode) exposes
  it.
- Prefer factories/builders over copy-pasted fixture blobs. Use
  property-based tests for pure functions whose invariants you can state.

## Types and tests divide the work

Types and unit tests are complementary verification: the checker eliminates
whole classes of invalid inputs; tests demonstrate behaviour on valid ones.

- **Do not test inputs the type checker already forbids** (calling with
  `null` or a wrong-type argument) — there is no expected behaviour to
  demonstrate, and such tests fight the compiler.
- **Exception — harmful bypasses:** when a type-level restriction guards
  against data corruption or a security breach, enforce it at runtime too,
  and test that enforcement with a line-scoped `@ts-expect-error` carrying a
  justification. This is the one sanctioned use of a type suppression, and
  it lives only in test files.
- **Every user-defined type guard and assertion function gets unit tests**,
  including near-miss values — the compiler never checks that a guard's body
  matches its predicate, and a wrong guard poisons every downstream branch.
- **Nontrivial type utilities get type-level tests** pinned next to them
  (equality-style assertions, negative cases via `@ts-expect-error`); plain
  assignability checks silently accept dropped parameters and extra
  properties — see
  [generics-and-type-level.md](generics-and-type-level.md).

## Hygiene (non-negotiable)

- No focused or skipped tests committed (`.only` / `.skip`), no conditional
  assertions, no empty tests, no duplicate titles.
- Strictness relaxations (`any`, non-null assertions, `console.*`) are
  allowed **only** inside test files.
- **Do not tune a test to the gate:** never hardcode an expected value "so it
  passes", never disable a check, never refresh a snapshot without
  understanding the cause. A red test means dig into the cause.
- **Every bug fix ships a regression test** that reproduces the defect and
  fails before the fix. Unit tests are mandatory for any behaviour change.
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
    Minimal reproduction: `const ALLOWED = ['a', 'b', 'c'] as const;` for a
    rule the specification states as an open class; `it.each(ALLOWED)(...)`
    parametrized over that same array; a mutation of the implementation
    array turns the test red (healthy mutation score); one
    specification-class member `'d'` is silently unhandled and no test
    notices. Stricter variant: if the test *imports* the array rather than
    copying it literally, the mutation does not even fail — mutation
    testing is blind to the pattern in that form.
  - **Subject of the test under layered protection.** When a property is
    protected by more than one layer, a test that reaches it through the
    outer layer proves nothing about the inner one; a defence-in-depth
    claim is unverified until each layer is exercised on a path where it is
    the only protection. Equivalently: every layer needs a test that goes
    red when that layer alone is deleted. Minimal reproduction: a value
    cleared both by an upstream filter keyed on field name and by an
    unconditional downstream overwrite in the serializer; a test that
    injects the value through the filtered channel; deleting the downstream
    overwrite alone leaves the suite green, because the upstream filter
    already intercepts the value before the downstream layer is ever
    reached.
  - **Totality across the dimensions a control discriminates on.** A
    parametrized set that varies one dimension of the input says nothing
    about the others, and its size is not evidence — eleven cases over
    eleven names cover one dimension eleven times. Where the implementation
    carries a dedicated mechanism for another dimension (a
    raw-vs-normalized key form, an exhaustive `switch` arm over a
    discriminated union's discriminant), that mechanism is by construction
    untested until the case set varies that dimension too. For each guard,
    name the dimensions of the input it discriminates on and require at
    least one case per dimension; treat a surviving mutation as evidence of
    a missing dimension, not merely of a missing case. Minimal
    reproduction: a `Map` whose keys are normalized by a dedicated function
    before `.has()`; a case set that varies only the key's text; a mutation
    that checks `.has()` against the raw key instead of the normalized one
    — green, because no case supplies a key whose raw and normalized forms
    differ.

## Secrets in tests

Use test-only values; never pull real credentials into a test. Where a test
needs a signed token or a key, generate/sign a genuine test-only one rather
than mocking the verification away — the code under test should run its real
checks.
