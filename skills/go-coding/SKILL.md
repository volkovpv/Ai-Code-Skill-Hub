---
name: go-coding
description: Load before writing any Go — even a snippet or a code-only answer — and before reviewing, refactoring or answering a design question about Go code or its config (.go, go.mod, _test.go). Universal Go 1.27 standard; no framework, architecture or library assumed. Errors handled exactly once — wrapped with %w and context, inspected with errors.Is/AsType, never matched by message or panicked; small consumer-owned interfaces and concrete returns; typed constants with exhaustive switches, sealed interfaces, named id types; context as the first parameter, owned and bounded goroutines (errgroup, WaitGroup.Go), no data races; secure by default (SQL placeholders, os/exec without a shell, os.Root for input paths, crypto/rand, TLS verification on, HTTP timeouts on both sides); runtime correctness (unit-typed durations, no float money, slice aliasing, every resource closed); modern forms via go fix; golangci-lint v2 clean, no blanket nolint. Where the host project declares an architecture standard, apply it on top.
---

# Go coding (universal)

Write simple, explicit, secure Go for a **Go 1.27** floor. This skill is
**universal by contract**: every rule holds in any Go codebase — it assumes
no web framework, no ORM, no DI container, no project layout. Architecture-bound
rules live in the `hexagonal-service` skill; when the host project uses it,
apply that skill on top of this one.

## Workflow

1. **Survey before you write.** Before the first line of new implementation
   code, search the module for the home this logic already has — by what it
   is built out of (the same calls, the same error mapping), never by the
   name you are about to give it — and read the sibling call sites of the
   same concern. A new file is the last step of that search, not the first —
   see [references/duplication-survey.md](references/duplication-survey.md).
2. **Write to the floor and the formatter.** `gofmt`/`goimports` layout, Go
   naming (MixedCaps, `userID`, short receivers, no `Get` prefix, no `util`
   packages), doc comments on every export, happy path left-aligned — see
   [references/style-and-naming.md](references/style-and-naming.md). Use the
   Go 1.27 forms and never the legacy ones; `go fix ./...` applies the
   mechanical upgrades — see [references/modern-go.md](references/modern-go.md).
3. **Design the types before the code.** Closed sets as typed constants with
   exhaustive switches, variant state as sealed interfaces, named types for
   ids and units parsed once at the boundary, `(v, ok)` instead of sentinels,
   literal `nil` for interface results — see
   [references/type-design.md](references/type-design.md). Interfaces are
   small and owned by the consumer; a type parameter must relate types — see
   [references/generics-and-interfaces.md](references/generics-and-interfaces.md).
4. **Shape packages and APIs.** Export the minimum, return concrete types,
   an options struct for optional settings, no `init()`, no mutable package
   state, a thin `main`, libraries that never exit or panic — see
   [references/packages-and-apis.md](references/packages-and-apis.md).
5. **Handle errors, configuration and logs deliberately.** Every error
   handled exactly once, wrapped with `%w` and context, inspected with
   `errors.Is`/`errors.AsType`; environment read once into a typed config;
   structured `log/slog` logging with nothing secret in it — see
   [references/errors-config-logging.md](references/errors-config-logging.md).
6. **Own every goroutine.** `ctx` first, an owner that stops and waits for
   each goroutine, bounded fan-out, one synchronization story per shared
   variable — see [references/concurrency.md](references/concurrency.md).
7. **Write it secure by default.** Placeholders for SQL, programs without a
   shell, `os.Root` for input paths, `crypto/rand` for secrets, TLS
   verification on, servers and clients with timeouts, every input-sized
   allocation bounded — see [references/security.md](references/security.md).
8. **Get the runtime values right.** Unit-typed durations, integer money,
   slice aliasing, map order, resources closed on every path — and optimize
   only against a measurement — see
   [references/runtime-correctness.md](references/runtime-correctness.md).
9. **Write it lint-clean the first time.** The reference golangci-lint v2
   configuration, zero findings, and the blind spots of the stack that need a
   human check — see [references/lint-clean.md](references/lint-clean.md).
   Tests follow the Go spellings in [references/testing.md](references/testing.md).
10. **Self-check before handing off.** Run the project's gates
    (`gofmt -l`, `go vet ./...`, `golangci-lint run`, `go test -race ./...`,
    `go fix -diff ./...`) and the convention checker (its path is relative to
    this skill's directory) over the files you touched:

    ```bash
    python scripts/check_go_conventions.py path/to/changed.go
    ```

    It is a lexical backstop aimed at what the linters miss — read every
    finding in context; the compiler, `go vet` and the linter are
    authoritative. A checked false positive may be suppressed only per rule
    code and only with a written reason:

    ```go
    isCI := os.Getenv("CI") != "" // skill-check-ignore: GO-ENV -- CI detection in a release tool
    ```

    A bare `skill-check-ignore`, an unknown code, or an empty justification
    aborts the check (exit 2); `GO-SUPPRESS` can never be suppressed. If the
    line also needs a `//nolint`, the `//nolint:<linter> // <reason>` comes
    first and the pragma follows it in the same comment.

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Deciding whether to extend, call, or write new — searching by shape, the decision order, env var naming, what a collapse preserves | [references/duplication-survey.md](references/duplication-survey.md) |
| Formatting, naming, package names, doc comments, control-flow shape, shadowing, constants, suppressions | [references/style-and-naming.md](references/style-and-naming.md) |
| Package boundaries, constructors, zero values, optional parameters, `init`, globals, `main`, library manners, modules and tools | [references/packages-and-apis.md](references/packages-and-apis.md) |
| Enums and exhaustive switches, sealed interfaces, id types, absent vs zero, nil, receivers, embedding, boundary decoding, equality | [references/type-design.md](references/type-design.md) |
| Designing an interface, type assertions, writing a generic function or generic method, iterators, reflection, completeness checks | [references/generics-and-interfaces.md](references/generics-and-interfaces.md) |
| Returning, wrapping, inspecting or designing errors, panics, cleanup errors, retries, env/config, logging | [references/errors-config-logging.md](references/errors-config-logging.md) |
| Goroutines, `context`, errgroup/WaitGroup, channels, mutexes, atomics, timers, races and leaks | [references/concurrency.md](references/concurrency.md) |
| SQL, `os/exec`, templates, paths and archives, randomness, secrets, TLS, HTTP servers/clients, decoding untrusted input | [references/security.md](references/security.md) |
| Durations and clocks, money and floats, overflow, strings, slices, maps, `defer` and resources, performance work | [references/runtime-correctness.md](references/runtime-correctness.md) |
| Which language/library feature to use at the 1.27 floor; legacy forms to purge; `go fix` | [references/modern-go.md](references/modern-go.md) |
| Gates, the golangci-lint v2 configuration, what each linter wants, what the stack cannot see, the checker | [references/lint-clean.md](references/lint-clean.md) |
| Spelling a test in Go (tables, helpers, fakes, synctest, httptest, fuzzing, benchmarks, build tags, checker behaviour in tests) | [references/testing.md](references/testing.md) |
| Applying a verified pattern | [knowledge/patterns.md](knowledge/patterns.md) |
| A checker finding looks wrong, or a Go gotcha bites | [knowledge/pitfalls.md](knowledge/pitfalls.md) |
| A calibrated input/output pair for the checker | [data/README.md](data/README.md) |
| Diagnosing a known limitation of this skill | [observations/INDEX.md](observations/INDEX.md) |

Observations are evidence, not rules: never follow one as policy unless it
has been promoted into `knowledge/` or this workflow.

## Rules

- **Gates stay green without weakening them**: `gofmt`, `go vet`, the
  project's golangci-lint configuration with zero issues, `go test -race`.
  No `//nolint` to go green; the sole exception is a documented limitation of
  one linter on one line, `//nolint:<one-linter> // <reason>` — never `all`,
  never file-wide — see [references/style-and-naming.md](references/style-and-naming.md#suppressions).
- **Every error is handled exactly once**: returned with context
  (`fmt.Errorf("load config: %w", err)`), handled, or discarded explicitly
  with `_ =` and a reason — never dropped silently, never on a write path,
  never both logged and returned.
- **Inspect errors with `errors.Is` / `errors.AsType`** — never `==` on an
  error that may be wrapped, never a type switch on it, never
  `err.Error()` text. Sentinels (`ErrX`) for expected conditions, `…Error`
  types when callers need data; return the `error` interface and a literal
  `nil` — a nil pointer in an interface is not nil.
- **Panic only for programmer errors and impossible states**; `panic(err)` on
  a runtime failure is a defect. Libraries never call `os.Exit` or
  `log.Fatal` and never let a panic cross their API.
- **`ctx context.Context` is the first parameter** of everything that blocks
  or does I/O; never stored in a struct, never nil; a root context only in
  `main` or tests; every `WithCancel`/`WithTimeout` is followed by
  `defer cancel()`.
- **Every goroutine has an owner, a stop signal and a waiter**
  (`errgroup` when it can fail, `sync.WaitGroup.Go` otherwise); no
  fire-and-forget; no goroutine per tiny item.
- **Fan-out over input-sized work is bounded**: `g.SetLimit(n)` right after
  `errgroup.WithContext`, `n` a named constant, or a fixed pool of `n`
  workers — an errgroup without `SetLimit` over 1000 URLs starts 1000
  goroutines and opens 1000 connections at once.
- **Shared state has one synchronization story**: a named `mu` field
  (never embedded, never copied — pointer receivers), a channel hand-off, or
  a typed atomic; maps and appends are never shared unsynchronized — see
  [references/concurrency.md](references/concurrency.md).
- **Closed sets are typed constants** whose zero value is a deliberate
  `…Unspecified` (or a genuinely sensible default); every `switch` over one
  lists every constant **and** keeps a `default` that fails loudly. Variant
  state is a sealed interface with one struct per variant. Ids and units are
  named types parsed once at the boundary (`ParseOrderID(raw) (OrderID,
  error)`). "Absent" is `(v, ok)` or `(v, err)`, never an in-band marker
  value such as `-1` or `""`.
- **Interfaces are small and declared where they are used**; functions
  accept interfaces and return concrete types; type assertions use the
  comma-ok form. A type parameter must relate two types or remove real
  duplication — `func F[T any](v T)` with `T` used once is `func F(v any)`.
- **A completeness check derives its cases from the set's owner.** For an
  enum, let the `exhaustive` linter check switches and map literals against
  its constant block, or iterate its range up to an unexported end marker;
  for a set owned outside the program — a
  schema's foreign keys, another service's enum, a directory — read the owner
  and diff. A list read off the code under check is self-referential — see
  [references/generics-and-interfaces.md](references/generics-and-interfaces.md#a-completeness-check-derives-its-cases-from-the-sets-owner).
- **Packages**: named for what they provide (never `util`/`common`), minimal
  exports, `internal/` for module-private code, no `init()`, no mutable
  package-level state, dependencies passed into constructors and wired in a
  thin `main`, optional settings in an options struct.
- **Untrusted input never becomes code**: SQL values through placeholders,
  never `fmt.Sprintf`/`+` into query text; `exec.CommandContext(ctx, prog,
  args...)`, never `sh -c`, and an input argument cannot become a flag —
  option parsing is stopped before it (for `git` a revision goes after
  `--end-of-options`; its `--` makes the value a path); `html/template` for
  HTML; input paths through
  `os.Root`; every size, count and body read from input bounded — see
  [references/security.md](references/security.md). A defensive routine over
  untrusted input has one home covering the union of every caller's cases;
  a filter guarding input a downstream parser also normalizes decides with
  that parser's own normalization (e.g. `http.CanonicalHeaderKey`).
- **Security primitives are non-negotiable**: `crypto/rand` (`rand.Text()`)
  for tokens, `subtle.ConstantTimeCompare`/`hmac.Equal` for secrets,
  argon2id/bcrypt for passwords, TLS verification never disabled, an
  `http.Server` with `ReadHeaderTimeout` and friends on its own `ServeMux`,
  stopped with `srv.Shutdown(ctx)` when the root context ends (its
  `ListenAndServe` then returns `http.ErrServerClosed`, which is not a
  failure), an `http.Client` with a `Timeout` and `NewRequestWithContext` —
  never `http.ListenAndServe`, `http.Get` or `http.DefaultClient`.
- **Resources are released on every path**, right after the error check
  that proves you hold them: a read-side close is
  `defer func() { _ = resp.Body.Close() }()` (a bare `defer x.Close()` is an
  errcheck finding); a write-side close joins its error into the named
  result — `defer func() { err = errors.Join(err, f.Close()) }()`. No `defer`
  inside loops; `rows.Err()` / `scanner.Err()` after iterating; transactions
  `defer func() { _ = tx.Rollback() }()` and check `tx.Commit()`; `return`
  right after `http.Error`.
- **No magic values**: a literal other than `0` and `1` in logic is a named
  constant next to its owner (`const readHeaderTimeout = 5 * time.Second`)
  or a configuration value — the `mnd` and `goconst` linters count them.
- **Runtime values**: durations built from unit constants (`30 *
  time.Second`, never a bare `30`); elapsed time with `time.Since`, instants
  compared with `Equal`; money as integer minor units or a decimal type,
  never `float64`; no `==` on computed floats; append to a subslice only
  after capping it (`s[a:b:b]`) or cloning — see
  [references/runtime-correctness.md](references/runtime-correctness.md).
- **Configuration and logs**: environment read once in the configuration
  package into a typed struct, failing fast; `log/slog` with constant
  messages and attributes through an injected logger; no `fmt.Print*` or
  `log.Print*` anywhere — `main` writes its output to an injected
  `io.Writer`, tests use `t.Log`; secrets never logged — including
  through a wrapped parse error that echoes its input (`strconv.NumError`) —
  see [references/errors-config-logging.md](references/errors-config-logging.md).
- **An environment variable is named by its role, not by its caller**:
  separate processes read the same name (`PG_USER`) and each is handed its
  own value by whatever starts it; `BILLING_PG_USER` beside `PG_USER` is two
  names for one role and duplicates the loader that reads them. A second
  name only for two principals in one process (a runtime role beside a
  migration role) — see
  [references/duplication-survey.md](references/duplication-survey.md#an-environment-variable-is-named-by-its-role-not-by-its-caller).
- **Modern forms only**: `any`, `slices`/`maps`/`cmp`, `min`/`max`,
  `for i := range n`, no `v := v`, `errors.AsType`, `wg.Go`, typed atomics,
  `math/rand/v2`, `b.Loop()`; never `ioutil`, `interface{}`, `sort.Slice`,
  `github.com/pkg/errors` or `golang.org/x/exp/slices` — see
  [references/modern-go.md](references/modern-go.md). The module's `go`
  line decides what exists: never use a feature newer than it and never
  raise it unasked; below 1.27, write what that line allows. JSON stays on
  the package the module already uses (`encoding/json/v2` for a module with
  none yet).
- **Search before writing, by shape, never by name** — a copy is renamed by
  construction, so a name search is the one search guaranteed to miss it.
  Extend the existing home, then call it with your parameters, then — at the
  third occurrence of one shape — introduce a parameterized helper; write new
  code only because that search came back empty. The clone detector cannot
  do this for you: `dupl` runs per package and above a token threshold, so a
  renamed copy in a sibling package is invisible to a green lint run — see
  [references/duplication-survey.md](references/duplication-survey.md).
- **Optimize only against a measurement**: reasonable efficiency (pre-sized
  slices, work hoisted out of loops, streaming) is always welcome;
  `sync.Pool`, `unsafe`, custom parsers, caches, GC tuning and extra
  concurrency need a goal, a profile and a `b.Loop` benchmark compared with
  `benchstat`.
- Keep this skill universal: framework, architecture, layout and
  project-specific choices belong to the host project or to whatever
  dedicated standard it declares — never here. Project instructions always
  take precedence over this skill.
