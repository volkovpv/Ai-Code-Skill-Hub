# Modern Go: the 1.27 floor and the legacy forms it retires

The floor is **Go 1.27**: the host module declares `go 1.27` (or newer) in
`go.mod` and builds with a 1.27.x toolchain. Everything below is available
and is the default spelling; the legacy column is banned in new code and is
migrated out in the code you change (not across untouched files in the same
change). The module's `go` line decides what exists: never use a feature it
does not have, and never raise it unless asked — since 1.27 `go test` runs the
`stdversion` vet check and reports standard-library symbols newer than that
line. On an older line, write what it allows and hold a checker finding that
suggests a newer form with a pragma naming the line
(`skill-check-ignore: GO-LEGACY-API -- module is on go 1.25`).

## Contents

- [Run the modernizers](#run-the-modernizers)
- [Language features you can rely on](#language-features-you-can-rely-on)
- [Standard library defaults](#standard-library-defaults)
- [Tooling defaults](#tooling-defaults)
- [Out of scope unless the project opts in](#out-of-scope-unless-the-project-opts-in)
- [Banned legacy forms](#banned-legacy-forms)

## Run the modernizers

`go fix ./...` (rewritten in 1.26 as the home of the modernizers) applies
every mechanical upgrade in the table at the end of this file; `go fix -diff
./...` prints the pending rewrites and exits non-zero when there are any, so
it works as a check. Run it on the files you touched before handing off,
then review the diff — a modernizer is a suggestion with a proof of
equivalence, not a license to reformat unrelated code.

## Language features you can rely on

| Since | Feature | Use it for |
|---|---|---|
| 1.18 | generics, `any`, `comparable` | type parameters that relate types — see [generics-and-interfaces.md](generics-and-interfaces.md) |
| 1.21 | `min`, `max`, `clear` builtins | never hand-write an `if a < b` min or a delete-every-key loop |
| 1.22 | per-iteration loop variables | closures and goroutines may capture `v` from `for _, v := range` directly — the `v := v` copy is dead code |
| 1.22 | `for i := range n` | counting loops over an integer |
| 1.23 | range-over-func iterators (`iter.Seq`, `iter.Seq2`) | streaming a sequence without materializing a slice; `for k, v := range seq` |
| 1.24 | generic type aliases | `type Set[T comparable] = map[T]struct{}` style aliases |
| 1.26 | `new(expr)` | a pointer to a computed value: `Age: new(yearsSince(born))` — replaces `ptr[T]` helpers |
| 1.26 | self-referential generic constraints | `type Adder[A Adder[A]] interface{ Add(A) A }` |
| 1.27 | **generic methods** | a method may declare its own type parameters (`func (r *Rand) N[I intType](n I) I`); interface methods may not, and a generic method never satisfies an interface method |
| 1.27 | struct literal keys may name a promoted field | `Config{Port: 8080}` sets a field promoted through embedded non-pointer structs directly (`Server.Port` is not a key; a field promoted through an embedded pointer cannot be set this way) |

## Standard library defaults

| Need | Default (package, since) |
|---|---|
| Sorting, searching, cloning, comparing slices | `slices` (1.21): `Sort`, `SortFunc`, `SortStableFunc`, `BinarySearch`, `Contains`, `Index`, `Clone`, `Compact`, `Equal`; iterator helpers `Collect`, `Sorted`, `Backward`, `All`, `Values` (1.23) |
| Map helpers | `maps` (1.21): `Clone`, `Copy`, `Equal`; iterators `Keys`, `Values`, `All`, `Collect` (1.23); sorted keys: `slices.Sorted(maps.Keys(m))` |
| Ordering | `cmp.Compare`, `cmp.Or` (first non-zero value), `cmp.Ordered` constraint |
| Structured logging | `log/slog` (1.21); `slog.NewMultiHandler` (1.26) fans out to several handlers |
| Errors | `errors.Is`, `errors.AsType[E]` (1.26, replaces `errors.As` with a target variable), `errors.Join` (1.20), `fmt.Errorf` with one or more `%w` |
| One-time initialization | `sync.OnceValue`, `sync.OnceValues`, `sync.OnceFunc` (1.21) |
| Waiting for goroutines | `sync.WaitGroup.Go` (1.25) replaces `Add(1)` + `go` + `defer Done()`; `golang.org/x/sync/errgroup` when the goroutines return errors (still outside the standard library) |
| Typed atomics | `atomic.Int64`, `atomic.Bool`, `atomic.Pointer[T]` (1.19) — never the `atomic.AddInt64(&n, …)` function family on a plain integer |
| Randomness | `math/rand/v2` (1.22, auto-seeded) for simulations and jitter; `crypto/rand` for anything secret — `rand.Text()` (1.24) for tokens |
| Identifiers | `uuid` (1.27): `uuid.New()` (random), `uuid.NewV7()` (time-ordered), `uuid.Parse` |
| JSON | the package the module already uses; `encoding/json/v2` (1.27) for a module with none yet or a deliberate migration — stricter defaults (rejects duplicate names, invalid UTF-8, trailing data); `encoding/json` v1 stays supported and is now backed by v2; do not mix the two in one module |
| Filesystem confinement | `os.Root`, `os.OpenInRoot` (1.24, methods widened in 1.25) — see [security.md](security.md) |
| Test context and clocks | `t.Context()` (1.24), `testing/synctest` (1.25) with `synctest.Sleep` (1.27), `t.ArtifactDir()` (1.26) — see [testing.md](testing.md) |
| Benchmarks | `for b.Loop() { … }` (1.24) — never `for i := 0; i < b.N; i++` |
| Reflection | `reflect.TypeFor[T]()` (1.22); `reflect.TypeAssert[T](v)` (1.25); iterator methods `Type.Fields`, `Value.Fields` (1.26) |
| Strings | `strings.Cut`, `CutPrefix`, `CutSuffix`, `CutLast` (1.27), `strings.Lines`, `SplitSeq`, `FieldsSeq` (1.24) |
| Weak references and cleanups | `weak.Pointer`, `runtime.AddCleanup` (1.24) — never `runtime.SetFinalizer` in new code |
| Canonicalization | `unique.Make` (1.23) for interning comparable values |
| HTTP routing | `http.ServeMux` method and wildcard patterns (1.22): `mux.HandleFunc("GET /orders/{id}", h)` with `r.PathValue("id")` |
| CSRF protection | `http.CrossOriginProtection` (1.25) |
| Leak diagnosis | the `goroutineleak` profile (1.27) in `runtime/pprof` and `/debug/pprof/goroutineleak` |

## Tooling defaults

- `gofmt` (or `goimports`) output is the only accepted formatting.
- `go vet ./...` runs every registered analyzer (1.27 includes `copylocks`,
  `lostcancel`, `loopclosure`, `printf`, `httpresponse`, `waitgroup`,
  `hostport`, `stdversion`, `tests`, …); its findings are defects.
- Development tools are pinned with the `tool` directive in `go.mod` (1.24)
  and run as `go tool <name>` — not a `tools.go` file with blank imports.
- `govulncheck ./...` checks reachable known vulnerabilities before a release.
- `go mod tidy` keeps `go.mod`/`go.sum` exact; for `go 1.27+` modules it also
  merges duplicate `require` blocks into one direct and one indirect block.
- The runtime is container-aware: GOMAXPROCS follows the cgroup CPU limit
  (1.25); never hard-code it at startup to "fix" containers.

## Out of scope unless the project opts in

`GOEXPERIMENT`-gated packages (`simd`, `simd/archsimd`, `runtime/secret`) are
not stable API. Use them only where the host project has deliberately enabled
the experiment and measured the need.

## Banned legacy forms

| Legacy | Go 1.27 form | Retired by |
|---|---|---|
| `interface{}` | `any` | 1.18 (`go fix`: any) |
| `io/ioutil` | `io.ReadAll`, `os.ReadFile`, `os.WriteFile`, `os.MkdirTemp`, `os.CreateTemp`, `os.ReadDir` | 1.16 |
| `math/rand` (v1), `rand.Seed` | `math/rand/v2` (auto-seeded); `crypto/rand` for secrets | 1.22 |
| `golang.org/x/exp/slices`, `golang.org/x/exp/maps`, `golang.org/x/exp/constraints`, `golang.org/x/exp/slog`, `golang.org/x/exp/rand` | `slices`, `maps`, `cmp.Ordered`, `log/slog`, `math/rand/v2` | 1.21–1.22 |
| `github.com/pkg/errors` | `fmt.Errorf("…: %w", err)`, `errors.Is`, `errors.AsType`, `errors.Join` | 1.13–1.26 |
| `golang.org/x/net/context` | `context` | 1.7 |
| `sort.Slice`, `sort.Strings`, `sort.Ints` | `slices.Sort`, `slices.SortFunc` | 1.21 (`go fix` slicessort rewrites simple `sort.Slice` only; checker `GO-LEGACY-API` flags all three) |
| hand-written `min`/`max` `if` blocks | `min(a, b)`, `max(a, b)` | 1.21 (`go fix`: minmax) |
| loop copying map keys/values into a slice | `slices.Collect(maps.Keys(m))`, `slices.Sorted(maps.Keys(m))` | 1.23 (`go fix`: mapsloop) |
| `v := v` inside a loop body | nothing — loop variables are per-iteration | 1.22 (`go fix`: forvar) |
| `for i := 0; i < n; i++` counting loop | `for i := range n` | 1.22 (`go fix`: rangeint) |
| `var t *T; errors.As(err, &t)` | `t, ok := errors.AsType[*T](err)` | 1.26 (`go fix`: errorsastype) |
| `wg.Add(1); go func() { defer wg.Done(); … }()` | `wg.Go(func() { … })` | 1.25 (`go fix`: waitgroupgo) |
| `atomic.AddInt64(&n, 1)` on a plain `int64` | `var n atomic.Int64; n.Add(1)` | 1.19 (`go fix`: atomictypes) |
| `reflect.TypeOf((*T)(nil)).Elem()` | `reflect.TypeFor[T]()` | 1.22 (`go fix`: reflecttypefor) |
| `func ptr[T any](v T) *T { return &v }` helpers | `new(v)` | 1.26 (`go fix`: newexpr) |
| `Config{Server: Server{Port: 8080}}` for an embedded non-pointer struct | `Config{Port: 8080}` | 1.27 (`go fix`: embedlit) |
| `strings.Index` + slicing, `HasPrefix` + `TrimPrefix` | `strings.Cut`, `strings.CutPrefix`, `strings.CutLast` | 1.18–1.27 (`go fix`: stringscut, stringscutprefix) |
| `for _, s := range strings.Split(x, ",")` | `for s := range strings.SplitSeq(x, ",")` | 1.24 (`go fix`: stringsseq) |
| `strings.Title` | `golang.org/x/text/cases` | deprecated 1.18 |
| `for i := 0; i < b.N; i++` in benchmarks | `for b.Loop()` | 1.24 (neither `go fix` nor the default modernize set rewrites it; checker `GO-LEGACY-API` flags `b.N`) |
| `ctx, cancel := context.WithCancel(context.Background())` in tests | `ctx := t.Context()` | 1.24 (`go fix`: testingcontext) |
| `json:",omitempty"` on struct-typed or `time.Time` fields | `json:",omitzero"` | 1.24 (`go fix`: omitzero) |
| `// +build` lines | `//go:build` only | 1.17 (`go fix`: plusbuild) |
| `tools.go` with blank imports | `tool` directive in `go.mod` | 1.24 |
| `runtime.SetFinalizer` | `runtime.AddCleanup` | 1.24 |
| `go.uber.org/automaxprocs`, `GOMAXPROCS` set at startup for containers | nothing — the default follows the cgroup CPU limit | 1.25 |
| `httputil.ReverseProxy.Director` | `ReverseProxy.Rewrite` | deprecated 1.26 |
| `time.After` inside a `for`/`select` loop | one `time.NewTimer` (or `Ticker`) reused with `Reset` — unstopped timers are collectable since 1.23, but each iteration still allocates a fresh one | 1.23 |
