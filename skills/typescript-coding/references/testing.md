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
- Prefer factories/builders over copy-pasted fixture blobs. Use
  property-based tests for pure functions whose invariants you can state.

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

## Secrets in tests

Use test-only values; never pull real credentials into a test. Where a test
needs a signed token or a key, generate/sign a genuine test-only one rather
than mocking the verification away — the code under test should run its real
checks.
