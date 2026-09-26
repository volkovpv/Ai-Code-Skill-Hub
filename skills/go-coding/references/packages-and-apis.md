# Packages, APIs and modules

How to cut packages, what to export, how values get built and wired, and how
the module around them is kept. Layout conventions beyond these (which
directories a service has) belong to the host project.

## Contents

- [Package boundaries and the exported surface](#package-boundaries-and-the-exported-surface)
- [Construction and zero values](#construction-and-zero-values)
- [Optional parameters: an options struct](#optional-parameters-an-options-struct)
- [Dependencies are passed in, wired in main](#dependencies-are-passed-in-wired-in-main)
- [No init, no mutable package state](#no-init-no-mutable-package-state)
- [A thin main](#a-thin-main)
- [Library manners](#library-manners)
- [API shape](#api-shape)
- [Evolving an exported API](#evolving-an-exported-api)
- [Modules and dependencies](#modules-and-dependencies)

## Package boundaries and the exported surface

- Start with one package; split when a cohesive group of types and functions
  has emerged, not "for structure". Dozens of nano-packages and one
  catch-all package are the two failure modes.
- Organize by what the code does for the domain (`orders`, `billing`,
  `pgstore`), not by technical layer across the whole module (`models`,
  `handlers`, `utils`) — layer-wide packages couple everything to everything.
- Export the minimum. An exported identifier is a compatibility promise to
  every importer; unexported is the default.
- `internal/` is the only compiler-enforced privacy boundary above a package:
  put module-private shared code under it and move it out only when an
  outside importer genuinely needs it.
- An import cycle means two packages were split along the wrong line — merge
  them, or move just the shared piece to its own package; never paper over it
  with an interface declared for the sole purpose of breaking the cycle.
- The `golang-standards/project-layout` repository is not an official
  standard; do not cite it as one. Follow the host project's layout; where
  there is none, `cmd/<binary>/` for commands and `internal/` for the rest is
  enough.

## Construction and zero values

- Make the zero value useful when you can — `var b bytes.Buffer`,
  `var mu sync.Mutex`, `var wg sync.WaitGroup` need no constructor, and a nil
  slice is a valid empty slice.
- When a type has invariants or required dependencies, give it unexported
  fields and a constructor so the zero value cannot be misused:

  ```go
  // NewService wires a Service; the clock is injected so tests control time.
  func NewService(store Store, logger *slog.Logger, now func() time.Time) *Service {
  	return &Service{store: store, logger: logger, now: now}
  }
  ```

- Constructors return **concrete types** (`*Service`), not interfaces — the
  caller decides which interface it needs (see
  [generics-and-interfaces.md](generics-and-interfaces.md#interfaces-belong-to-the-consumer)).
  One constructor per concrete type; no factory that picks an implementation
  from its arguments and returns an interface.
- A constructor that can fail returns `(*T, error)`; one that validates input
  data (`ParseOrderID`) is the only place the raw value becomes the domain
  type — see [type-design.md](type-design.md#named-types-for-ids-and-units).

## Optional parameters: an options struct

Mandatory inputs are positional parameters. Optional settings go in an options
struct whose **zero value means "use the default"**, so callers write only
what they change:

```go
// ServerOptions configures NewServer; zero fields take their defaults.
type ServerOptions struct {
	ReadHeaderTimeout time.Duration // default 5s
	MaxBodyBytes      int64         // default 1 MiB
}

func NewServer(addr string, h http.Handler, opts ServerOptions) *http.Server {
	if opts.ReadHeaderTimeout == 0 {
		opts.ReadHeaderTimeout = 5 * time.Second
	}
	// ...
}
```

- When "unset" must differ from a meaningful zero, use a pointer field and
  let callers write `Retries: new(0)` (Go 1.26 `new(expr)`).
- The functional-options pattern (`opts ...Option`) is acceptable where the
  package already uses it or where each option needs its own validation;
  never mix both styles in one package.
- Many parameters are a sign the function does too much; split it before
  reaching for either pattern.

## Dependencies are passed in, wired in main

- Dependencies arrive through constructor parameters typed as small
  interfaces owned by the consumer; `main` (or the composition root the
  project declares) is the only place that knows every concrete type and
  wires them. No service locator, no global registry, no DI framework is
  needed; a code generator such as Wire is optional.
- Pass the clock, randomness source and I/O (`io.Reader`, `io.Writer`,
  `fs.FS`) the same way, so tests can substitute them.

## No init, no mutable package state

- **No `init()`** (checker `GO-INIT`, linter `gochecknoinits`): it runs
  implicitly on import, cannot return an error, runs before every test of the
  package and hides dependencies. Do fallible setup (open a pool, read
  config) in an explicit function that returns an error, called from `main`.
  The rare legitimate `init` computes an immutable package value that cannot
  be written as one assignment; it carries both directives, linter first:
  `func init() { … } //nolint:gochecknoinits // <reason>; skill-check-ignore: GO-INIT -- <reason>`.
- **Register explicitly.** A blank import whose `init` registers a driver,
  codec or handler is a hidden side effect; where you control the package,
  expose `Register(...)` or a constructor and call it from `main`.
- **Package-level variables are immutable in practice.** `gochecknoglobals`
  accepts two kinds without comment — sentinel errors (`var ErrX =
  errors.New(…)`) and compiled regular expressions (`regexp.MustCompile`).
  A lookup table is a function returning it or a field of the struct that
  uses it; a table that must be package-level carries
  `//nolint:gochecknoglobals // immutable after initialization`. Anything that
  changes at runtime lives in a struct created by a constructor. A
  package-level `var now = time.Now` swapped by tests is shared mutable state
  — inject the clock.
- Expensive lazy initialization uses `sync.OnceValue` / `sync.OnceValues`
  (a struct field, or a package variable with the justified nolint above),
  not hand-written `sync.Once` plumbing.

## A thin main

`main` parses flags and configuration, builds dependencies, runs, and turns
the result into an exit code — nothing else. Put the program in a `run`
function that returns an error so it is testable and every `defer` runs:

```go
func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	err := run(ctx, os.Args[1:], os.Stdout)
	stop()
	if err != nil {
		fmt.Fprintln(os.Stderr, "report:", err)
		os.Exit(1)
	}
}
```

- `os.Exit` belongs only in `package main`, after `run` returned (checker
  `GO-EXIT`); `log.Fatal` belongs nowhere — it skips deferred cleanup. The
  root `context.Background()` is created here too (checker `GO-CTX-ROOT`
  relaxes only in `package main`).
- A command writes its output to the `io.Writer` it was handed
  (`fmt.Fprintln(out, …)`), never through `fmt.Print*` or `log.Print*` —
  `GO-PRINT` and forbidigo apply in `package main` too, and the writer is what
  makes `run` testable.

## Library manners

- A library returns errors; it never calls `os.Exit`, `log.Fatal`, or
  `panic` for a runtime failure, and never lets a panic escape its public API
  (recover at the entry point if a dependency can panic, and return an
  error).
- A library never configures global state it does not own: the default
  logger, `http.DefaultServeMux`, global metric registries, GOMAXPROCS,
  environment variables. It accepts what it needs (a `*slog.Logger`, a mux, a
  registry) through its constructor.
- Keep concurrency out of exported APIs: no exported channels or mutexes in
  signatures or struct fields (unless concurrency *is* the package's
  purpose). Callers get synchronous functions; the package owns its
  goroutines — see [concurrency.md](concurrency.md).

## API shape

- Accept the narrowest interface that works: `io.Reader` instead of a file
  name or `*os.File`, `fs.FS` instead of a directory path (testable with
  `testing/fstest.MapFS`), `io.Writer` instead of stdout. Open files at the
  edges of the program.
- Structs, not maps, in signatures — unless the keys genuinely are unknown
  until runtime.
- Prefer functions that return new values over functions that mutate their
  arguments; when a function mutates a slice or map argument, its doc
  comment says so.
- Return `(T, error)`, `(T, bool)` or a named result type — never an in-band
  sentinel such as `-1` or `""` for "absent".
- Pointers in signatures mean mutation or optionality, not speed — see
  [type-design.md](type-design.md#values-by-default-pointers-with-a-reason).

## Evolving an exported API

- Adding a method to an exported interface breaks every implementation.
  Extend by adding a new interface (checked with a type assertion), a new
  concrete wrapper, or a new function instead.
- Rename or move exported identifiers with a forwarding function or a type
  alias (`type Order = orders.Order`, generic aliases since Go 1.24) and a
  `Deprecated:` paragraph; remove the old name only in a new major version
  (`/v2` module path).

## Modules and dependencies

- `go.mod` declares `go 1.27` (the floor of this standard); the `toolchain`
  line or `GOTOOLCHAIN` selects the compiler. Never hand-edit requirements —
  `go get`, `go mod tidy`; commit `go.mod` and `go.sum`.
- Pin development tools with the `tool` directive (`go get -tool
  golang.org/x/tools/cmd/stringer@v0.x.y`, run as `go tool stringer`) — not a
  `tools.go` file with blank imports, not a global `go install @latest`.
- `go.work` is a local convenience and is never committed; no local `replace`
  directives in committed code.
- Prefer the standard library; add a dependency only when it earns its weight
  — copying one small function beats importing a large module for it. Run
  `govulncheck ./...` before a release and act on reachable findings with the
  smallest fixing upgrade.
- `golang.org/x/...` modules (errgroup, x/crypto) are maintained by the Go
  team but carry weaker compatibility guarantees than the standard library.
