# go-coding

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Gives an AI coding agent a **universal Go standard for a Go 1.27 floor** —
deliberately free of any web framework, ORM, DI container, architecture or
project layout. Once installed, the agent applies it whenever it writes,
reviews, or refactors Go: `.go` files, `go.mod`, and `_test.go` tests.

The core discipline it enforces:

- every error handled exactly once — wrapped with `%w` and context, inspected
  with `errors.Is` / `errors.AsType`, never matched by its message, never
  both logged and returned, never `panic(err)`; a literal `nil` for interface
  results;
- type design without sum types: typed constants with exhaustive switches and
  a failing `default`, sealed interfaces for variants, named id types parsed
  once at the boundary, `(v, ok)` instead of sentinels;
- small interfaces owned by the consumer, concrete return types, comma-ok
  assertions, type parameters only where they relate types (including the
  generic methods of Go 1.27);
- `context.Context` first, never stored; every goroutine owned, stoppable and
  waited for (`errgroup`, `sync.WaitGroup.Go`); bounded fan-out; no data
  races;
- secure by default: SQL placeholders, `os/exec` without a shell,
  `html/template`, `os.Root` for paths from input, `crypto/rand`, constant-time
  comparison, TLS verification never disabled, HTTP servers and clients with
  timeouts, bounded input;
- runtime correctness: unit-typed durations, integer money, slice aliasing,
  map order, resources closed on every path (write-side `Close` errors joined
  into the result), optimization only against a benchmark;
- modern Go 1.27 forms with an explicit ban list for the legacy ones
  (`ioutil`, `interface{}`, `sort.Slice`, `github.com/pkg/errors`, `v := v`,
  `b.N` loops, …) and `go fix` to apply them;
- a golangci-lint v2 reference configuration passed with zero findings, and a
  documented list of what that stack cannot see.

## Key features

- **Universal by contract.** Every rule holds in any Go codebase; no framework
  or architecture is assumed. Architecture rules live in the companion
  `hexagonal-service` skill instead.
- **Measured, not assumed.** The reference lint configuration was validated
  with golangci-lint 2.13 on Go 1.27.1 against the skill's calibration sample
  (zero issues). The same measurement records what the stack misses —
  `err.Error()` matching, SQL built from a function parameter, `panic(err)`,
  `os.Exit` in libraries, and renamed duplicates in a sibling package (the
  clone detector runs per package) — and the skill states those blind spots
  instead of trusting a green run.
- **Self-check script.** `scripts/check_go_conventions.py` is an offline,
  stdlib-only lexical checker aimed at those blind spots plus the high-signal
  basics (18 rules: `fmt.Print*`/`log.Print*` output, `os.Exit` below `main`,
  raw environment access, root contexts below `main`, `init`, `panic(err)`, legacy APIs and
  imports, error matching by `==` or text, unchecked type assertions, SQL
  building, shell commands, disabled TLS, HTTP without timeouts, bare-integer
  durations, embedded mutexes, `util`-style package names, unjustified
  `//nolint`). It relaxes exactly the documented rules in `_test.go` files,
  `package main` and config files, skips generated files and `vendor/`, and
  accepts suppressions only with a rule code and a written reason
  (`// skill-check-ignore: GO-INIT -- <reason>`).
- **Layered knowledge.** Beyond `references/` (duplication survey, style and
  naming, packages and APIs, type design, interfaces and generics, errors and
  logging, concurrency, security, runtime correctness, modern Go, lint-clean,
  and a Go test-mechanics spelling map) the skill ships verified `knowledge/`
  patterns and pitfalls, and calibrated `data/` samples for the checker.

## Where the rules come from

The rules were distilled from four books and reconciled against the Go
release notes up to 1.27; where the books disagree, the newer one wins, and
anything a later Go release changed is stated in its 1.27 form:

- Jon Bodner, *Learning Go*, 2nd ed. (2024);
- Bartłomiej Płotka, *Efficient Go* (2022);
- Teiva Harsanyi, *100 Go Mistakes and How to Avoid Them* (2022);
- Alan Donovan and Brian Kernighan, *The Go Programming Language* (2015).

Examples of reconciled points: optional parameters default to an options
struct rather than functional options; sets default to `map[T]bool`; a named
result exists only for a deferred closure, and a bare `return` never; the
loop-variable, `time.After`, `automaxprocs` and `b.N` advice of the older
books is replaced by what Go 1.22–1.27 made true.

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/go-coding
uv run skillctl install go-coding --target ~/work/my-service --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install go-coding --target ~/work/my-service --agent codex
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in `.agent-skills.lock.yaml`. The `.go`
calibration files land under a dot-directory, which the Go tool and
golangci-lint skip, so they never join your build.

## Using it with your project rules

The skill covers the *language*; your project rules (for Claude Code:
`.claude/rules/` or `CLAUDE.md`) cover the *project*. Effective split:

- **Put in project rules:** your actual commands (`make lint`, `go test
  ./...` flags, the golangci-lint config path), the logger and config
  packages to use, the HTTP router or RPC framework, the database driver and
  placeholder style, module layout, and any deliberate deviation (functional
  options instead of options structs, a different JSON package, a mocking
  library). Project instructions always take precedence over the skill.
- **Leave to the skill:** error handling, type design, concurrency, security
  primitives and lint-clean habits — reference the skill instead of restating
  them ("Go style: see the go-coding skill").
- The skill's checker is a backstop, not the authority: the agent still runs
  your real `go vet`, linter and tests, so make sure your rules say how.

## Works well with

- `hexagonal-service` — ports-and-adapters layering (architecture-bound rules
  live there, not here).
