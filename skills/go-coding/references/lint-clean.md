# Passing a strict lint stack clean

A Go project's quality gate is the compiler plus `go vet` plus a linter
aggregator, and it counts every finding. Write to the configuration below by
default and the gate stays at zero; where the host project's stack differs,
its configuration and output are authoritative — this file is how to be right
the first time, not the rule source.

## Contents

- [The gates](#the-gates)
- [Reference configuration (golangci-lint v2)](#reference-configuration-golangci-lint-v2)
- [errcheck and Close](#errcheck-and-close)
- [What each family expects](#what-each-family-expects)
- [What the stack does not catch](#what-the-stack-does-not-catch)
- [Duplication: what the stack sees and what it does not](#duplication-what-the-stack-sees-and-what-it-does-not)
- [Suppressions](#suppressions)
- [The skill checker](#the-skill-checker)

## The gates

Before handing off, all of these are clean for the packages you touched:

```bash
gofmt -l .                 # prints nothing
go vet ./...               # every registered analyzer
golangci-lint run ./...    # zero issues with the project's config
go test -race ./...        # tests, with the race detector
go fix -diff ./...         # no pending modernizations (exit 0)
govulncheck ./...          # before a release: no reachable vulnerabilities
```

Never weaken a gate to pass: no disabling a linter, raising a threshold,
adding an exclusion rule or a `//nolint` to make a finding disappear. Fix the
code; the one sanctioned suppression shape is in [Suppressions](#suppressions).

## Reference configuration (golangci-lint v2)

Measured: the skill's calibration sample (a service with an enum, a sealed
interface, typed errors, bounded fan-out, SQL, HTTP, `os/exec`, `os.Root` and
secrets code) passes this configuration with zero issues on golangci-lint
2.13 and Go 1.27.1.

```yaml
version: "2"

linters:
  default: standard            # errcheck, govet, ineffassign, staticcheck, unused
  enable:
    - bodyclose
    - containedctx
    - contextcheck
    - dupl
    - durationcheck
    - errchkjson
    - errname
    - errorlint
    - exhaustive
    - fatcontext
    - forbidigo                # fmt.Print*/print/println and the standard log package
    - forcetypeassert
    - gocheckcompilerdirectives
    - gochecknoglobals
    - gochecknoinits
    - gochecksumtype
    - gocognit
    - goconst
    - gocritic
    - godoclint
    - gosec
    - iface
    - makezero
    - mirror
    - misspell
    - mnd
    - modernize
    - musttag
    - nakedret
    - nestif
    - nilerr
    - nilnesserr
    - nilnil
    - noctx
    - nolintlint
    - perfsprint
    - predeclared
    - reassign
    - recvcheck
    - revive
    - rowserrcheck
    - sloglint
    - sqlclosecheck
    - thelper
    - unconvert
    - unparam
    - usestdlibvars
    - usetesting
    - wastedassign
    - wrapcheck
  settings:
    errcheck:
      check-type-assertions: true
      check-blank: false       # `_ = f()` stays the explicit, reviewable discard
    govet:
      enable-all: true         # includes shadow
      disable: [fieldalignment]
    exhaustive:
      check: [switch, map]     # map literals keyed by an enum are completeness-checked too
      default-signifies-exhaustive: false
      ignore-enum-members: "Unspecified$|\\.[a-z]\\w*Count$" # zero value, unexported end marker
    gocognit:
      min-complexity: 15
    nolintlint:
      require-explanation: true
      require-specific: true
    sloglint:
      static-msg: true
    gocritic:
      enabled-tags: [diagnostic, style, performance]
      disabled-checks: [hugeParam, rangeValCopy] # values by default; pointers only on measurement
    forbidigo:
      forbid:
        - pattern: ^(fmt\.Print(|f|ln)|print|println)$
        - pattern: ^log\.(Print|Printf|Println|Fatal|Fatalf|Fatalln|Panic|Panicf|Panicln)$
    usetesting:
      context-background: true   # t.Context() in tests
      context-todo: true
  exclusions:
    generated: strict
    rules:
      - path: _test\.go
        linters: [dupl, goconst, gochecknoglobals, mnd, wrapcheck]

issues:
  uniq-by-line: false          # show every linter's finding, not one per line
  max-issues-per-linter: 0
  max-same-issues: 0

formatters:
  enable: [gofmt, goimports]
```

- `default: standard` is errcheck, govet, ineffassign, staticcheck (which in
  v2 includes the former gosimple and stylecheck) and unused.
- By default golangci-lint shows one finding per line (`uniq-by-line`), so a
  second linter's complaint on the same line appears only after the first is
  fixed — the setting above shows them all at once.
- Test files get only the exclusions listed: tests still print through
  `t.Log`, assert types with comma-ok, build requests with `t.Context()`.
- `hugeParam` and `rangeValCopy` are disabled on purpose: they push values into
  pointers "for speed", which this standard allows only against a measurement.
- Projects that use testify add `testifylint`; projects that must not use a
  package list it under `depguard` — those are project decisions.

## errcheck and Close

golangci-lint v2 has no default exclusions: a bare `defer resp.Body.Close()`
is an errcheck finding. The spellings that pass:

```go
defer func() { _ = resp.Body.Close() }() // read side: an explicit best-effort close
defer func() { err = errors.Join(err, f.Close()) }() // write side: part of the result
```

Enabling the `std-error-handling` exclusion preset instead re-allows the bare
`defer x.Close()` everywhere — including on write paths, where a lost
`Close` error is lost data — so this configuration leaves it off. With
`check-blank: true` even `_ =` is a finding and every close must be handled;
follow whichever the project configured.

## What each family expects

| Family | Write this | Not this |
|---|---|---|
| errcheck, gosec G104 | check or explicitly `_ =` every error | a bare call whose error is dropped |
| errorlint | `errors.Is`, `errors.AsType`, `%w`; to cut a chain, wrap your own sentinel (`fmt.Errorf("stat config: %w", ErrConfigUnavailable)`) | `err == ErrX`, type switch on `err`, `%v` of an error (flagged even when cutting the chain is the intent) |
| wrapcheck | wrap errors from other packages with context | `return err` straight from a dependency |
| forcetypeassert | `v, ok := x.(T)` | `x.(T)` |
| exhaustive, gochecksumtype | every constant / variant, plus `default` | a switch that forgot one |
| contextcheck, containedctx, fatcontext, noctx | ctx as first parameter, `NewRequestWithContext`, `exec.CommandContext` | `context.Background()` below main, ctx in a struct, `http.Get` |
| bodyclose, sqlclosecheck, rowserrcheck | close bodies/rows/statements, check `rows.Err()` | a response or `Rows` left open |
| gosec | placeholders, no shell, `crypto/rand`, TLS verification, server timeouts, `filepath.Clean` on operator-controlled paths (G304), a justified `//nolint:gosec` on a safe argv `exec` (G204) and on each line of a non-security SHA-1 (G505 import, G401 call) | `InsecureSkipVerify`, `math/rand` for anything secret, `http.ListenAndServe` |
| gochecknoinits, gochecknoglobals, reassign | explicit initialization, immutable package values | `init()`, mutable package variables |
| nilerr, nilnil, nilnesserr | return the error you checked; a sentinel instead of `nil, nil` | `if err != nil { return nil }` |
| mnd, goconst | named constants | repeated magic numbers and strings |
| gocognit, nestif, nakedret | small functions, early returns, explicit returns | deep nesting, bare `return` |
| recvcheck, govet copylocks | one receiver kind per type, pointer receivers for types with locks | value receivers copying a mutex |
| govet shadow, predeclared | assign outer variables with `=`; distinct names | `:=` shadowing `err`, a variable named `len` or `url` |
| modernize | the Go 1.27 forms in [modern-go.md](modern-go.md) | `interface{}`, `sort.Slice`, `v := v`, 3-clause integer loops |
| forbidigo, sloglint | an injected `*slog.Logger` with constant messages; `fmt.Fprintln(out, …)` to an injected writer; `t.Log` in tests | `fmt.Print*` or `log.Print*`/`log.Fatal*` anywhere (`package main` included), `slog.Info(fmt.Sprintf(...))` |
| gocritic | `http.NoBody` for a request without a body; named results when two or more share a type | `NewRequestWithContext(ctx, method, url, nil)`, `func f() (string, string, bool)` |
| perfsprint | `errors.New("…")` for a constant message, `strconv.Itoa(n)` for a number | `fmt.Errorf("constant")`, `fmt.Sprintf("%d", n)` |
| revive, godoclint | doc comments on exported identifiers, no stutter | undocumented exports, `orders.OrderService` |
| usetesting, thelper | `t.TempDir`, `t.Setenv`, `t.Context`, `t.Helper()` first in helpers | `os.MkdirTemp`, `os.Setenv` in tests |

Examples in these references inline small numbers (`5 * time.Second`,
`SetLimit(8)`) for readability; under `mnd`, shipped code names them
(`const readHeaderTimeout = 5 * time.Second`) or takes them from
configuration.

## What the stack does not catch

Measured on golangci-lint 2.13 with the configuration above — each of these
passes the whole stack and is still a defect:

| Defect | Why the stack misses it | What catches it |
|---|---|---|
| `err.Error() == "not found"`, `strings.Contains(err.Error(), "timeout")` | errorlint checks `==` on errors, not on their text | checker `GO-ERR-MATCH` |
| SQL built with `fmt.Sprintf` passed **inline** as the query argument, or built into `q` and used in `return db.QueryContext(ctx, q)` | gosec G201/G202 report the build-into-a-variable-then-call shape in an assignment, not these two | checker `GO-SQL-FMT` (not a format string that starts on the next line of a raw string) |
| `panic(err)` for a runtime failure in a library | no linter flags `panic` | checker `GO-PANIC-ERR` |
| `os.Exit` outside `package main` | revive's `deep-exit` is not in its default rules (the forbidigo patterns above catch `log.Fatal`) | checker `GO-EXIT` |
| `errors.As(err, &target)` | golangci-lint's modernize set lacks `errorsastype` (`go fix` has it) | `go fix -diff`, checker `GO-LEGACY-API` |
| `exec.Command("sh", "-c", "tar czf /backup.tgz /data")` — a constant shell line | gosec G204 fires on variable arguments, not on the shell itself | checker `GO-SHELL` |
| a renamed copy in another package, or a short one | see [below](#duplication-what-the-stack-sees-and-what-it-does-not) | the survey before writing |
| a leaked goroutine, a missing `ctx.Done()` case | not statically decidable | review, `synctest`, the `goroutineleak` profile |

## Duplication: what the stack sees and what it does not

`dupl` is the stack's clone detector. It compares syntax-tree shapes and
ignores identifier names and literal values, so it is **rename-blind**: a
copy with every name changed is still the same shape to it. Its reach is
narrow anyway:

- it runs **per package** — measured on golangci-lint 2.13, a 17-line function
  copied and renamed into a sibling package was not reported at any
  threshold down to 20 tokens;
- it reports only above its token threshold, **150 tokens** by default — the
  same copy in two files of one package appeared only once the threshold was
  lowered to 75;
- it is not in the `standard` set; a project that never enabled it has no
  clone detection at all.

A green lint run therefore never clears a duplicate: an ordinary-length
function copied into another package is invisible to every tool here. The
search for an existing home happens before writing — see
[duplication-survey.md](duplication-survey.md).

## Suppressions

- `//nolint:<one-linter> // <reason>`, on the line it covers — exactly one
  linter, never `all`, never file-wide, never without the written reason
  (`nolintlint` with `require-specific` and `require-explanation` enforces
  it). Typical legitimate uses: `gosec` on SHA-1 used as an identifier by an
  external format, `gosec` G404 on `math/rand/v2` jitter.
- Never suppress to meet a deadline; a suppressed finding with a vague reason
  ("false positive", "legacy") is a finding.
- staticcheck-only and gosec-only projects: `//lint:ignore <CHECK> <reason>`
  and `// #nosec <RULE> -- <reason>` are the single-check equivalents.

## The skill checker

`scripts/check_go_conventions.py` is a lexical backstop for the rules above,
with emphasis on the blind spots of the stack. It masks comments, strings,
raw strings and runes, skips files marked `// Code generated … DO NOT EDIT.`
and, in directory walks, `vendor/` and hidden directories. Its codes:
`GO-PRINT`, `GO-ENV`, `GO-SUPPRESS`, `GO-EXIT`, `GO-CTX-ROOT`, `GO-INIT`,
`GO-PANIC-ERR`, `GO-LEGACY-API`, `GO-LEGACY-IMPORT`, `GO-ERR-MATCH`,
`GO-TYPE-ASSERT`, `GO-SQL-FMT`, `GO-SHELL`, `GO-TLS-INSECURE`,
`GO-HTTP-TIMEOUT`, `GO-DURATION`, `GO-EMBED-LOCK`, `GO-PKG-NAME`.

- Contexts relax exactly what the reference configuration also allows: in
  `package main` it drops `GO-EXIT` for `os.Exit` and `GO-CTX-ROOT`; in test
  files (`*_test.go`, `test/`, `tests/`, `testdata/`, `__test__/`,
  `__tests__/`) it drops only environment *reads* of `GO-ENV`; in
  configuration files (`config.go`, `settings.go`, `*_config.go`,
  `*_settings.go`, `config_*.go`, `settings_*.go`, anything under `config/` or
  `settings/`) it drops `GO-ENV`. A file's context comes from its path
  relative to the nearest `go.mod` — a module checked out under `~/tests/`
  is not all test code. Content piped on stdin has no path and no context.
- A checked false positive is held by a per-code pragma with a written
  reason:

  ```go
  isCI := os.Getenv("CI") != "" // skill-check-ignore: GO-ENV -- CI detection in a release tool, not configuration
  ```

  When the same line also needs a linter directive, the `//nolint` comes
  first and the pragma follows in the same comment —
  `//nolint:gochecknoinits // <reason>; skill-check-ignore: GO-INIT -- <reason>`;
  the reverse order hides the directive from golangci-lint. A bare
  `skill-check-ignore`, an unknown code or an empty reason aborts the run
  (exit 2); `GO-SUPPRESS` can never be suppressed.
- It reads lines, not a syntax tree: a construct split across lines is seen
  line by line, and every finding is a prompt to look, not a verdict. The
  compiler, `go vet` and the linter remain authoritative.
