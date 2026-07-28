# Test mechanics in TypeScript

A spelling map, not a rule list: it says **how** a test rule is expressed
in TypeScript, not which rules apply or why. The runner is the project's
choice — Jest, Vitest, `node:test` and the rest all satisfy everything
below.

| What the test needs | TypeScript spelling |
|---------------------|---------------------|
| A stand-in for a seam the project owns | a plain object literal or small class implementing the declared interface — no mocking library needed |
| Patching, where no seam exists (last resort) | module patching (`jest.mock` / `vi.mock` / a loader hook), with a comment justifying why no seam was available |
| A fixed clock | inject a `Clock` interface or a `now: () => Date` parameter; fake timers only where the runner owns the scheduler, never a real `setTimeout` wait |
| An asynchronous test | `await` the assertion and return the promise to the runner; give every wait an explicit deadline instead of assuming completion, and let no promise float |
| A skip that must ship | `describe.skip` / `it.skip` with the reason written next to it plus a tracking reference; `.only` is never committed |
| Relaxations confined to test files | `any`, non-null assertions (`!`) and `console.*` are permitted in spec files only |
| Unit-testing a narrowing predicate | one test per user-defined type guard (`x is T`) and assertion function (`asserts x is T`), including near-miss values it must reject |
| A positive type-level assertion | an equality-style type assertion (`Expect<Equal<Actual, Expected>>`) pinned next to the utility — plain assignability silently accepts dropped parameters and extra properties, see [generics-and-type-level.md](generics-and-type-level.md) |
| A negative type-level assertion | a line-scoped `@ts-expect-error` carrying a justification — the one sanctioned type suppression, and only in test files |
| Runtime enforcement of a harmful bypass | validate and throw at runtime, then drive the check from a test through a `@ts-expect-error` line (types are erased; they enforce nothing at runtime) |
| Generated cases | a property-based runner (fast-check or equivalent) for parsers, serializers and pure functions with a statable invariant; pin every counterexample it reports as an ordinary regression test |
| Names the runner discovers | `*.spec.ts` / `*.test.ts`, `describe(<unit>)` grouping, `it('<behaviour> when <condition>')` |

## The skill's own checker in test paths

`scripts/check_conventions.py` recognizes test paths (`*.spec.ts`,
`*.test.ts`, `*_test.ts`, `test_*.ts`, `*.integration-spec.ts`, and anything under
`test/`, `tests/`, `__test__/` or `__tests__/`) and drops exactly three
rules there — `TS-CONSOLE`, `TS-ANY`, `TS-NONNULL`, the relaxations listed
above. Every other rule keeps firing in test files, `TS-SUPPRESS`
included; `@ts-expect-error` is deliberately not in its pattern, because
it fails the build once the error it covers disappears — which is exactly
what makes it the sanctioned form — see [lint-clean.md](lint-clean.md).
