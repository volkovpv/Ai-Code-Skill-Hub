# Pitfalls: known failure modes

Read this when a checker finding looks wrong or a Go gotcha bites. Every
pitfall lists its evidence; treat anything without evidence as a hypothesis,
not knowledge.

Some pitfalls cite `data/fixtures/*` or measurements taken with Go 1.27.1 and
golangci-lint 2.13 as evidence. The fixtures are Hub-only development content
and do **not** ship in a `runtime` install (see `data/README.md`), so they
are cited as plain code spans.

## Contents

- [The checker is lexical, not a parser](#the-checker-is-lexical-not-a-parser)
- [A nil pointer returned as error is not nil](#a-nil-pointer-returned-as-error-is-not-nil)
- [`:=` in an inner block shadows err](#-in-an-inner-block-shadows-err)
- [`append` on a subslice overwrites the parent](#append-on-a-subslice-overwrites-the-parent)
- [A bare integer duration is nanoseconds](#a-bare-integer-duration-is-nanoseconds)
- [`break` inside `select` does not leave the loop](#break-inside-select-does-not-leave-the-loop)
- [`defer` in a loop holds every resource until return](#defer-in-a-loop-holds-every-resource-until-return)
- [golangci-lint v2 flags a bare `defer x.Close()`](#golangci-lint-v2-flags-a-bare-defer-xclose)
- [A green lint run misses four defect classes](#a-green-lint-run-misses-four-defect-classes)
- [dupl never compares two packages](#dupl-never-compares-two-packages)
- [Disjoint keys do not make a shared map safe](#disjoint-keys-do-not-make-a-shared-map-safe)
- [Embedding promotes methods you did not mean to export](#embedding-promotes-methods-you-did-not-mean-to-export)
- [gosec G404 fires for non-security randomness](#gosec-g404-fires-for-non-security-randomness)
- [Test files relax only environment reads](#test-files-relax-only-environment-reads)

## The checker is lexical, not a parser

**Applies always.** `scripts/check_go_conventions.py` masks comments, strings,
raw strings and runes, so quoted rule text never produces a finding — but it
reads line by line: a call split across lines is seen per line, it cannot know
types (`GO-ERR-MATCH` matches `err == ErrX`, not the type of `err`), and the
config-layer relaxation of `GO-ENV` is decided by the file path. Treat each
finding as a prompt to look. Evidence: the masking and context batteries in
`__test__/skills/test_go_coding.py` and the calibrated fixtures
`data/fixtures/masked_literals.go` and `data/fixtures/app_config.go`.

## A nil pointer returned as error is not nil

**Applies when** a function returns an interface. `var e *MyError; return e`
produces a non-nil `error` holding a nil pointer, so callers see a failure
that never happened. Declare results as `error`, never keep a to-be-returned
error in a variable of the concrete type, `return nil` on success. Evidence:
[../references/type-design.md](../references/type-design.md#a-typed-nil-is-not-a-nil-interface).

## `:=` in an inner block shadows err

**Applies when** assigning outer variables inside `if`/`for`/closures.
`client, err := f()` inside a block declares new variables and leaves the
outer ones untouched; the code compiles as long as the inner ones are used.
Assign with `=`; enable govet `shadow`. Evidence:
[../references/style-and-naming.md](../references/style-and-naming.md#declarations-and-shadowing).

## `append` on a subslice overwrites the parent

**Applies when** a subslice is kept, passed on, or appended to. With spare
capacity, `append(s[:1], x)` writes into `s[1]`. Cap the capacity
(`s[lo:hi:hi]`) or clone before appending. Evidence:
[../references/runtime-correctness.md](../references/runtime-correctness.md#slices).

## A bare integer duration is nanoseconds

**Applies when** passing or assigning a `time.Duration`. `time.Sleep(5)`,
`http.Client{Timeout: 30}`, `context.WithTimeout(ctx, 100)` compile and mean
nanoseconds. Multiply a unit constant. The checker flags these as
`GO-DURATION`; staticcheck catches only the `time.Sleep` case. Evidence: the
`GO-DURATION` battery in `__test__/skills/test_go_coding.py` and
[../references/runtime-correctness.md](../references/runtime-correctness.md#time).

## `break` inside `select` does not leave the loop

**Applies when** a `for` loop contains a `select` or `switch`. An unlabelled
`break` exits only the inner statement, so `case <-ctx.Done(): break` spins
on. Use a labelled `break` or `return`. Evidence:
[../references/concurrency.md](../references/concurrency.md#channels).

## `defer` in a loop holds every resource until return

**Applies when** acquiring resources per iteration. Deferred calls run when
the function returns, so a loop over files keeps them all open. Move the body
into a function that defers. Evidence:
[../references/runtime-correctness.md](../references/runtime-correctness.md#resources-and-defer).

## golangci-lint v2 flags a bare `defer x.Close()`

**Applies when** the project runs golangci-lint v2 without the
`std-error-handling` exclusion preset. errcheck reports `defer
resp.Body.Close()`; the lint-clean spellings are `defer func() { _ =
resp.Body.Close() }()` for reads and a joined error for writes. Evidence:
measured on golangci-lint 2.13 — see
[../references/lint-clean.md](../references/lint-clean.md#errcheck-and-close).

## A green lint run misses four defect classes

**Applies when** reading a clean golangci-lint run as clearance. Measured
with the reference configuration: message matching on `err.Error()`, SQL
built with `fmt.Sprintf` inline as the query argument (or used in a `return
db.QueryContext(ctx, q)`), `panic(err)` in a library, and `os.Exit` outside
`main` all pass. The checker covers them (`GO-ERR-MATCH`, `GO-SQL-FMT`,
`GO-PANIC-ERR`, `GO-EXIT`). Evidence:
[../references/lint-clean.md](../references/lint-clean.md#what-the-stack-does-not-catch).

## dupl never compares two packages

**Applies when** relying on the clone detector. `dupl` ignores identifier
names but runs per package and above 150 tokens by default; a renamed
17-line copy in a sibling package was not reported at any threshold. Search
by shape before writing. Evidence:
[../references/duplication-survey.md](../references/duplication-survey.md#why-the-linter-will-not-do-this-for-you).

## Disjoint keys do not make a shared map safe

**Applies when** several goroutines write one map. Map internals are shared,
so concurrent writes are a data race and a fatal runtime error even when every
goroutine writes different keys. Guard with a mutex or confine the map to one
goroutine. Evidence:
[../references/concurrency.md](../references/concurrency.md#mutexes-and-shared-state).

## Embedding promotes methods you did not mean to export

**Applies when** embedding a type. An embedded `sync.Mutex` lets callers lock
your value (checker `GO-EMBED-LOCK`); an embedded `time.Time` makes the outer
struct a `json.Marshaler` whose output drops every other field. Use named
fields. Evidence:
[../references/type-design.md](../references/type-design.md#embedding-is-composition-not-inheritance).

## gosec G404 fires for non-security randomness

**Applies when** using `math/rand/v2` for jitter or sampling under gosec.
G404 flags every use; hold a genuinely non-security use with
`//nolint:gosec // jitter, not security` and use `crypto/rand` for anything
secret. Evidence: measured on golangci-lint 2.13 — see
[../references/security.md](../references/security.md#randomness-secrets-comparison-passwords).

## Test files relax only environment reads

**Applies when** the checker flags a `_test.go` file. The one relaxation in
tests is reading the environment (to skip integration tests); printing,
unchecked assertions, root contexts, default HTTP clients, environment writes
and every security rule still fire — as forbidigo, errcheck, usetesting,
noctx and gosec do under the reference lint configuration. The test-side
spellings are `t.Log`, comma-ok plus `t.Fatalf`, `t.Context()`,
`srv.Client()`, `t.Setenv`; a TLS peer is `httptest.NewTLSServer` with its
`srv.Client()`, never `InsecureSkipVerify`. Evidence: the context battery in
`__test__/skills/test_go_coding.py` and
[../references/testing.md](../references/testing.md#the-skills-own-checker-in-test-paths).
