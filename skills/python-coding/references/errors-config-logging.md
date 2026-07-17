# Errors, environment, logging

Universal hygiene for the three places where Python code most often rots:
error paths, environment access, and ad-hoc output — narrow catch, never
swallow, wrap once with the cause preserved. Nothing here assumes a
framework or an architecture; layering rules (where exactly errors are
wrapped and mapped in a ports-and-adapters service) live in the
`hexagonal-service` skill.

## Contents

- [Errors](#errors)
- [Exception groups, notes, retries](#exception-groups-notes-retries)
- [Environment and configuration](#environment-and-configuration)
- [Logging](#logging)

## Errors

- **Catch the narrowest exception type.** `except ValueError:` beats
  `except Exception:`; a bare `except:` (which also traps
  `KeyboardInterrupt` and `SystemExit`) is banned. `except Exception`
  belongs only at a top-level boundary (request handler, worker loop, CLI
  exit path) that logs the full chain and converts to the transport's
  failure shape.
- **Never swallow.** `except SomeError: pass` is a defect. Whatever you
  catch is either handled meaningfully, re-raised, or converted into a
  typed failure — and the conversion is logged or surfaced, not silent.
  `contextlib.suppress` is the same swallow in nicer clothes: acceptable
  only where losing the error is provably the intended behaviour, with a
  comment saying why.
- **Prefer typed error classes over bare `Exception`** for failures
  callers are expected to distinguish: a small hierarchy rooted in one
  project base class, each with a stable machine-readable `code`, beats
  string matching on messages. Raise instances, not strings; never raise
  or subclass `BaseException` directly.
- **Wrap at most once, at the source, preserving the cause.** When a
  low-level error must become a higher-level one, wrap it exactly where it
  first crosses into your code and keep the original chained:

  ```python
  try:
      connection = driver.connect(dsn)
  except OSError as err:
      raise StorageUnavailableError("connect failed") from err
  ```

  Re-wrapping the same error again in intermediate callers destroys the
  traceback's shape and duplicates context — let a wrapped error bubble
  untouched to the place that handles or reports it. Inside an `except`
  block, `raise NewError(...) from err` is mandatory (an unchained raise
  there silently replaces the real cause with an implicit context).
- **Re-raise with `raise`, not `raise err`** — the bare form preserves the
  original traceback. `raise ... from None` (deliberately severing the
  chain) is reserved for hiding an implementation detail from a public
  API, with a comment saying so — never a habit.
- **Always parenthesize exception tuples** — `except (TimeoutError,
  ConnectionError) as err:` — one consistent shape (3.14 permits an
  unparenthesized form without `as`; don't mix styles).
- **Exceptions are not cross-layer control flow** for expected outcomes —
  model an expected alternative as a return type (a tagged union, `T |
  None`). Locally, EAFP is fine and often required:
  `try: ... except KeyError` beats a check-then-act that races.
- **Report with the stack.** Wherever the program finally handles an error
  (top-level handler, CLI exit path), log the full chain — `__cause__`
  included — with the traceback (`logger.exception(...)`), not just
  `str(err)`.
- **`assert` is not error handling.** Assertions vanish under `python -O`;
  in shipped code raise a typed error. `assert` belongs in tests and in
  checker-visible narrowing of genuinely impossible states.
- **`finally` never returns, breaks, continues, or raises on its own** —
  it silently eats the in-flight exception (a `SyntaxWarning` since 3.14);
  `finally` is for cleanup only (prefer `with`).

## Exception groups, notes, retries

- **`ExceptionGroup` / `except*` (3.11+) belong to genuinely concurrent
  failures** — a `TaskGroup`, a fan-out — where several errors are true
  peers. Do not convert ordinary single-error flows into groups, and know
  that raising a group from an existing API is a breaking change for its
  callers. Code that awaits a `TaskGroup` must be written for
  `ExceptionGroup`: handle with `except*` (or split), not a bare
  `except Exception` that misses it.
- **Attach context with `err.add_note(...)` (3.11+)** — the item id, the
  attempt number, the file being processed — before re-raising, instead of
  string-munging the message or wrapping in a shallow custom exception
  that adds no meaning.
- **Retry discipline**: retry only idempotent operations, only on error
  types that are actually transient (never on a `ValueError`-class bug),
  with capped attempts, exponential backoff with jitter, and a total
  deadline. **Every external call carries an explicit timeout** — an
  unbounded wait is a defect, not a default. In async code the timeout is
  `asyncio.timeout` around the block — see
  [concurrency.md](concurrency.md).

## Environment and configuration

- **Centralize `os.environ`.** All environment reads live in the project's
  configuration code (a `config`/`settings` module); the rest of the code
  receives typed values. Scattered `os.environ.get("X", "default")`
  expressions make configuration untraceable and untestable.
- **Validate early, fail closed.** Parse and validate the environment once
  at startup into a frozen, fully-typed config object; an invalid value
  stops the program with a clear typed error rather than surfacing later
  as a `KeyError` or a mis-typed string deep in a request.
- **Secrets come only from the environment** — never hardcoded, never
  logged, never committed. A test needs a secret? Use an obviously fake
  value.

## Logging

- **No `print()` in shipped code.** Use whatever logging seam the project
  provides (the stdlib `logging` module behind a project logger, an
  injected abstraction, a structured-logging library); `print` writes are
  invisible to the project's log pipeline and impossible to silence or
  route.
- Tests and one-off local scripts may use `print` freely — the checker
  relaxes this rule for test files.
- **Libraries never configure logging**: a library module does
  `logger = logging.getLogger(__name__)` and emits; handler, level, and
  format configuration (`basicConfig`, `dictConfig`) belongs solely to the
  application entry point. A library that must silence "no handler"
  warnings attaches `NullHandler` and nothing else.
- **Log the exception where it is finally handled — once.** Use
  `logger.exception(...)` inside the `except` block (or `exc_info=True`);
  `logger.error(str(err))` discards the type and traceback. No
  log-and-re-raise at every layer: one failure produces one error record
  at the boundary, not a storm of duplicates.
- **Levels have meaning**: DEBUG diagnostics, INFO state changes, WARNING
  unexpected-but-handled, ERROR a failed operation, CRITICAL
  service-unusable. Choose by what an operator should do, not by how the
  author feels.
- Log events, not payload dumps: operation, status, duration, counts — and
  never a secret or a whole request body. Keep secrets out of `repr` too
  (`field(repr=False)` on dataclass secret fields) — see
  [security.md](security.md).
- **Keep the message template constant and pass data as arguments**
  (`logger.info("processed %d items", n)`): arguments are not rendered
  when the level is off, aggregation tools can group by template, and
  untrusted input never becomes part of a format string. In structured
  logging the same rule reads: constant event name, values as fields.
