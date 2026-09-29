# Test mechanics in Go

A spelling map, not a rule list: it says **how** a test rule is expressed in
Go, not which rules apply or why. The standard `testing` package is enough for
everything below; assertion and mocking libraries are the project's choice.

| What the test needs | Go spelling |
|---------------------|-------------|
| Several cases of one behaviour | a table: a slice of anonymous structs with a `name` field, each run with `t.Run(tc.name, func(t *testing.T) { ... })`; loop variables are per-iteration, so no `tc := tc` |
| A helper that fails the test | take `t *testing.T` (or `testing.TB`), call `t.Helper()` first, fail with `t.Fatalf` |
| Cleanup owned by a helper | `t.Cleanup(func() { ... })` — runs last-in, first-out after the test |
| A context | `t.Context()` (cancelled when the test ends), never `context.Background()` |
| Output from a test | `t.Log` / `t.Logf` — shown for failing tests or with `-v`; never `fmt.Print*` |
| Asserting a dynamic type | the comma-ok form, then `t.Fatalf("got %T, want *Order", v)` on a mismatch — never a bare `v.(T)` |
| Scratch files and directories | `t.TempDir()`; files a test wants to keep for inspection: `t.ArtifactDir()` |
| An environment variable or working directory | `t.Setenv`, `t.Chdir` (both restore automatically; not usable with `t.Parallel`) |
| Parallel execution | `t.Parallel()` as the first statement of independent tests and subtests |
| A stand-in for a dependency the project owns | a small struct implementing the consumer-owned interface; for a large interface, a struct with function fields per method, set per table case — no mocking library needed |
| A fixed or controlled clock | inject `now func() time.Time`, or run the test body inside `synctest.Test(t, func(t *testing.T) { ... })` from `testing/synctest`, where `time.Now`, timers and `time.Sleep` use a fake clock |
| Waiting for concurrent work | `synctest.Wait()` (returns when every goroutine in the bubble is durably blocked) and `synctest.Sleep(d)` (Go 1.27); channels the fake signals on otherwise — never `time.Sleep` on the real clock |
| An HTTP handler | `httptest.NewRequest` + `httptest.NewRecorder`, then inspect `rec.Result()` |
| An HTTP dependency | `srv := httptest.NewTestServer(t, handler)` (Go 1.27): an in-memory network, its own cleanup, and a failed test on a handler panic; reach it only through `srv.Client()` (its URL is not a real host), with requests built by `http.NewRequestWithContext(t.Context(), ...)`; `httptest.NewServer` only when the code under test needs a real loopback socket |
| A TLS peer | `httptest.NewTLSServer` and its `srv.Client()`, which already trusts the test certificate — never `InsecureSkipVerify` |
| Readers and writers that misbehave | `testing/iotest`: `ErrReader`, `HalfReader`, `OneByteReader`, `TimeoutReader`, `TestReader` |
| Fixture files | a `testdata/` directory next to the test (ignored by the build), opened by relative path |
| Golden files | expected output under `testdata/*.golden`, rewritten only when a `-update` flag the test defines is set |
| Comparing structs, slices, maps | `slices.Equal`, `maps.Equal`, or `cmp.Diff` from `github.com/google/go-cmp` for a readable diff — not `reflect.DeepEqual` |
| Checking an error | `errors.Is(err, ErrNotFound)`, `errors.AsType[*ValidationError](err)` — not the message text |
| Black-box tests of the exported API | a `package foo_test` file in the same directory; white-box tests stay in `package foo` |
| Documentation that is also a test | `func ExampleParseOrderID()` with a trailing `// Output:` comment |
| Generated cases | a fuzz target `func FuzzParseOrderID(f *testing.F)`: seeds with `f.Add(...)`, properties checked in `f.Fuzz(func(t *testing.T, raw string) { ... })`; run with `go test -fuzz=FuzzParseOrderID`; failing inputs saved under `testdata/fuzz/` are committed as regression cases |
| A benchmark | `func BenchmarkX(b *testing.B)` with setup before `for b.Loop() { ... }` and `b.ReportAllocs()`; compare runs with `benchstat` |
| Data races | `go test -race ./...` in CI |
| Hidden order dependence | `go test -shuffle=on`; replay a failure with the printed seed |
| Bypassing the result cache | `go test -count=1` |
| Tests that need real infrastructure | files starting with `//go:build integration`, run with `go test -tags integration ./...`, or a `t.Skip` with instructions when `os.LookupEnv("…")` finds the variable absent |
| A skip that must ship | `t.Skip("reason and tracking reference")` — never a silent early `return` |
| A goroutine-leak check | run the code inside `synctest.Test` (a bubble whose goroutines never finish fails the test), or `go.uber.org/goleak` where the project uses it |
| Package-wide setup | `func TestMain(m *testing.M) { ...; m.Run() }` — no `os.Exit` needed since Go 1.15 |

## The skill's own checker in test paths

`scripts/check_go_conventions.py` recognizes test paths (`*_test.go`, and
anything under `test/`, `tests/`, `testdata/`, `__test__/` or `__tests__/`
relative to the module root) and relaxes exactly one thing there:
environment reads (`GO-ENV` for `os.Getenv` / `os.LookupEnv`), because a test
may decide to skip on a variable. Every other rule keeps firing in test files,
exactly as the reference lint configuration does (forbidigo, errcheck with
type-assertion checks, usetesting and noctx all run on tests):

- `GO-PRINT` — write test output with `t.Log`;
- `GO-TYPE-ASSERT` — comma-ok, then `t.Fatalf`;
- `GO-CTX-ROOT` — `t.Context()`;
- `GO-HTTP-TIMEOUT` — `srv.Client()` with `NewRequestWithContext`;
- `GO-ENV` for writes — `t.Setenv`;
- `GO-EXIT` — `TestMain` needs no `os.Exit`;
- the security rules — a shell-built command in a test helper is still one.

Directory walks skip `testdata/`: fixtures there may break rules on purpose.
