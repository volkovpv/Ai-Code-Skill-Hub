# Errors, configuration, logging

Errors are values: every one is handled exactly once, carries the context a
reader needs, and can still be inspected after it was wrapped. Configuration
enters in one place; logs are structured events, never a second error
channel. Where exactly an error is mapped to a transport response in a
layered service is an architecture decision and out of this file's scope.

## Contents

- [Handle every error, exactly once](#handle-every-error-exactly-once)
- [Wrapping: context and cause](#wrapping-context-and-cause)
- [Inspecting errors](#inspecting-errors)
- [Designing error values](#designing-error-values)
- [A wrapped cause that echoes its input is a disclosure channel](#a-wrapped-cause-that-echoes-its-input-is-a-disclosure-channel)
- [Cleanup errors](#cleanup-errors)
- [Panic and recover](#panic-and-recover)
- [Deadlines and retries](#deadlines-and-retries)
- [Configuration and the environment](#configuration-and-the-environment)
- [Logging](#logging)

## Handle every error, exactly once

- Check every returned error (`errcheck`). The four legitimate outcomes:
  return it (with context), handle it (retry, fall back, map to a response),
  convert it into a different error at an API boundary, or discard it
  **explicitly** with a reason:

  ```go
  // Best-effort cache warm-up: a failure only costs a slower first request.
  _ = cache.Warm(ctx)
  ```

- Never discard implicitly (a bare call), never on a write path, never an
  error that decides correctness.
- **Log or return, never both.** Logging is handling: a function that logs an
  error and returns it makes every layer above log it again, and one failure
  becomes five interleaved log lines. Wrap and return; the boundary that
  finally handles the error logs it once, with everything the wrapping
  collected.
- `error` is the last result; on failure the other results are zero values
  and callers must not use them (document the exception, like `io.Reader`
  returning `n > 0` with `io.EOF`).

## Wrapping: context and cause

- Add context when returning, keep the cause with `%w`, context first and the
  error last:

  ```go
  data, err := os.ReadFile(filepath.Clean(path))
  if err != nil {
  	return Config{}, fmt.Errorf("load config: %w", err)
  }
  ```

- The context says what *this* function was doing. Do not repeat what the
  callee already reported — `os.ReadFile`'s error already names the path — and
  do not stutter "failed to …: failed to …"; the chain reads
  `load config: open /etc/app.json: permission denied`.
- `%w` makes the wrapped error part of your API (callers can `errors.Is` it).
  Use it by default inside your module. At an exported boundary where the
  cause is an implementation detail callers must not depend on, cut the chain
  by wrapping your own sentinel instead —
  `fmt.Errorf("stat config: %w", ErrConfigUnavailable)` — rather than `%v`,
  which errorlint reports as a non-wrapping verb.
- Several failures: `errors.Join(errs...)` (nil when all are nil) or several
  `%w` verbs in one `fmt.Errorf`.
- When every return path adds the same context, a deferred wrap on a named
  result avoids repetition:

  ```go
  func (s *Store) Save(ctx context.Context, o Order) (err error) {
  	defer func() {
  		if err != nil {
  			err = fmt.Errorf("save order %s: %w", o.ID, err)
  		}
  	}()
  	// ...
  }
  ```

  `wrapcheck` cannot see a wrap done in a deferred closure and still reports
  each inner `return err` from another package; where the reference linters
  run, wrap at each return instead (a function-wide `//nolint` would be block
  scope, which the suppression rule forbids).

## Inspecting errors

- `errors.Is(err, target)` for a specific value; `errors.AsType[E](err)` for
  a type (Go 1.26; replaces `errors.As` with a target variable):

  ```go
  if errors.Is(err, sql.ErrNoRows) {
  	return Order{}, ErrNotFound
  }
  if verr, ok := errors.AsType[*ValidationError](err); ok {
  	return badRequest(verr.Field)
  }
  ```

- Never `err == ErrX`, never a type assertion or type switch on an error that
  may be wrapped, never `errors.Unwrap` by hand, and never
  `err.Error() == "…"` / `strings.Contains(err.Error(), …)` — message text is
  not a contract (checker `GO-ERR-MATCH`; linter `errorlint` catches the `==`
  form but not message matching). The documented exception: `io.EOF` returned
  directly by a `Read` call may be compared with `==`.
- Timeouts are recognized by value or behaviour, not text:
  `errors.Is(err, context.DeadlineExceeded)`, `errors.Is(err,
  os.ErrDeadlineExceeded)`, or `net.Error`'s `Timeout()` via
  `errors.AsType[net.Error]`.

## Designing error values

- **Sentinel errors** for expected conditions callers branch on and that
  need no extra data: `var ErrNotFound = errors.New("orders: not found")`.
  Never reassign one; never a string-constant error type.
- **Error types** when callers need data (a field, a status code): a struct
  named `…Error` with an `Error()` method and, if it wraps, `Unwrap() error`.
- Both are public API forever once exported; export few, prefer the standard
  library's (`os.ErrNotExist`, `context.Canceled`) when they fit.
- Return the `error` interface, never a concrete error type, and `return nil`
  on success — a nil `*MyError` returned as `error` is not nil (see
  [type-design.md](type-design.md#a-typed-nil-is-not-a-nil-interface)).
- Messages are lowercase, without trailing punctuation or newlines.

## A wrapped cause that echoes its input is a disclosure channel

"Wrap with `%w`, preserve the cause" and "log the full error at the boundary"
are each correct alone. They compose into a leak when the wrapped cause is a
parse or validation error that **echoes the rejected input in its own
message**, and that input is secret or personal data:

```go
key, err := strconv.ParseUint(os.Getenv("API_SIGNING_KEY"), 16, 64)
if err != nil {
	// err.Error() == `strconv.ParseUint: parsing "9f3c…secret…": invalid syntax`
	return Config{}, fmt.Errorf("invalid signing key: %w", err) // the secret rides along
}
```

`strconv.NumError`, `time.Parse` errors and many third-party validation
errors carry the offending text on purpose, for debuggability. A wrapper
whose own message names no value does not stop the chained cause's text from
reaching the log. Where such a cause is first caught for secret or personal
input: return a value-free error instead of wrapping —
`fmt.Errorf("API_SIGNING_KEY: %w", ErrInvalidHex)` with your own sentinel,
or `%v` of a scrubbed description — so no log sink ever receives the raw
value.

## Cleanup errors

- A `Close` on something you wrote to can report the write failure — never
  drop it. Join it into the named error result:

  ```go
  func writeReport(path string, rows []Row) (err error) {
  	f, err := os.Create(filepath.Clean(path))
  	if err != nil {
  		return fmt.Errorf("create report: %w", err)
  	}
  	defer func() { err = errors.Join(err, f.Close()) }()
  	return writeCSV(f, rows)
  }
  ```

- On read paths a failed close loses nothing; the lint-clean spelling of a
  deliberate best-effort close is `defer func() { _ = r.Close() }()` (see
  [lint-clean.md](lint-clean.md#errcheck-and-close)).
- `database/sql`: close `Rows`, then check `rows.Err()` after the loop —
  `Next` returns false on both exhaustion and error.

## Panic and recover

- Return errors for every expected failure — I/O, input, a missing file, a
  failed dependency. **`panic(err)` on an ordinary error is a defect**
  (checker `GO-PANIC-ERR`).
- Panic only for programmer errors and impossible states (an unreachable
  `default` inside the package, a violated invariant) and for `Must`-style
  initialization with constant input (`regexp.MustCompile` on a literal).
- A panic in any goroutine kills the whole process; `recover` works only in a
  deferred function of the panicking goroutine. Recover at goroutine and
  public-API boundaries where a dependency may panic, convert to an error,
  and do not continue as if nothing happened after a resource-exhaustion
  panic.
- Do not rely on `net/http` recovering handler panics as an error strategy.

## Deadlines and retries

- Every call that leaves the process has a deadline: a context with a
  timeout, or a client-level timeout (`http.Client.Timeout`) — an unbounded
  wait is a defect. Details in [concurrency.md](concurrency.md#context).
- Retry only idempotent operations, only on errors that are actually
  transient (timeouts, `503`, connection resets — never a validation error),
  with capped attempts, exponential backoff with jitter, and an overall
  deadline carried by the context.

## Configuration and the environment

- Read the environment **once**, in the configuration package, into a typed
  struct at startup; the rest of the program receives values, never calls
  `os.Getenv` (checker `GO-ENV`, relaxed only in config-layer files):

  ```go
  type Config struct {
  	DatabaseURL string
  	ReadTimeout time.Duration
  }

  func Load() (Config, error) {
  	dsn, ok := os.LookupEnv("DATABASE_URL")
  	if !ok || dsn == "" {
  		return Config{}, fmt.Errorf("DATABASE_URL: %w", ErrMissing)
  	}
  	// ... parse and validate the rest, failing closed
  	return Config{DatabaseURL: dsn, ReadTimeout: 5 * time.Second}, nil
  }
  ```

- Validate early and fail closed: an invalid value stops startup with an
  error naming the variable (and never echoing a secret value — see above).
- Tests set variables with `t.Setenv`, never `os.Setenv`.
- Secrets come from the environment or a secret store; never hardcoded,
  never committed, never logged.

## Logging

- Structured logging through `log/slog` (or the logging seam the project
  provides): a constant message plus attributes, never values interpolated
  into the message:

  ```go
  logger.InfoContext(ctx, "order cancelled",
  	slog.String("order_id", string(id)),
  	slog.Duration("elapsed", time.Since(start)))
  ```

- The logger is injected (`*slog.Logger` in the constructor); libraries never
  configure the global logger, and no code writes diagnostics with
  `fmt.Print*`, `println` or the standard `log` package (checker `GO-PRINT`;
  linter `forbidigo`). `package main` writes its user-facing output to an
  injected `io.Writer` (`fmt.Fprintln(out, …)`); tests use `t.Log`.
- Log each failure once, where it is handled, with the error as an attribute
  (`slog.Any("err", err)`), not `err.Error()` spliced into the message.
- Levels mean what an operator should do: Debug diagnostics, Info state
  changes, Warn unexpected-but-handled, Error a failed operation.
- Log events, not payloads: operation, identifiers, counts, durations — never
  secrets, tokens or whole request bodies. A type that holds a secret
  implements `slog.LogValuer` (and `String`) to redact itself:

  ```go
  type APIKey string

  func (APIKey) LogValue() slog.Value { return slog.StringValue("[redacted]") }

  func (APIKey) String() string { return "[redacted]" }
  ```

- Hot paths use `logger.LogAttrs(ctx, level, msg, attrs...)` with typed
  attributes to avoid allocations; `slog.NewMultiHandler` (Go 1.26) fans out
  to several handlers.
