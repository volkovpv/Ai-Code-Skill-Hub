# Errors, environment, logging

Universal hygiene for the three places where TypeScript code most often rots:
error paths, environment access, and ad-hoc output. Nothing here assumes a
framework or an architecture; layering rules (where exactly errors are
wrapped and mapped in a ports-and-adapters service) live in the
`hexagonal-service` skill.

## Errors

- **`unknown` in `catch`.** Narrow with `instanceof` / discriminated checks
  before touching the value; never type a caught error as `any`.
- **Never swallow.** An empty `catch` is a defect. Whatever you catch is
  either handled meaningfully, rethrown, or converted into a typed failure —
  and the conversion is logged or surfaced, not silent.
- **Prefer typed error classes over bare `Error`** for failures callers are
  expected to distinguish: a class (or a discriminated union) with a stable
  machine-readable `code` beats string matching on messages.
- **Wrap at most once, at the source, preserving `cause`.** When a low-level
  error must become a higher-level one, wrap it exactly where it first
  crosses into your code and keep the original:

  ```ts
  try {
    await driver.connect(dsn);
  } catch (error: unknown) {
    throw new StorageUnavailableError('connect failed', { cause: error });
  }
  ```

  Re-wrapping the same error again in intermediate callers destroys the stack
  trace and duplicates context — let a wrapped error bubble untouched to the
  place that handles or reports it.
- **Report with the stack.** Wherever the program finally handles an error
  (top-level handler, CLI exit path), log the full chain (`error` + `cause`)
  with the stack — not just `error.message`.

## Environment and configuration

- **Centralize `process.env`.** All environment reads live in the project's
  configuration code (a `config`/`settings` module); the rest of the code
  receives typed values. Scattered `process.env.X ?? 'default'` expressions
  make configuration untraceable and untestable.
- **Validate early, fail closed.** Parse and validate the environment once at
  startup; an invalid value stops the program with a clear typed error rather
  than surfacing later as `undefined` behaviour.
- **Secrets come only from the environment** — never hardcoded, never logged,
  never committed. A test needs a secret? Use an obviously fake value.

## Logging

- **No `console.*` in shipped code.** Use whatever logging seam the project
  provides (a logger object, an injected abstraction, a library); `console`
  writes are invisible to the project's log pipeline and impossible to
  silence or route.
- Tests and one-off local scripts may use `console` freely — the checker
  relaxes this rule for test files.
- Log events, not payload dumps: operation, status, duration, counts — and
  never a secret or a whole request body.
