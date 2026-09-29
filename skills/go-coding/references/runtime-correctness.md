# Runtime correctness and performance

The mistakes the compiler accepts and a quick test rarely shows: durations
that are nanoseconds, money in floats, slices that share memory, resources
that are never released — and the discipline for making code faster only
where a measurement says so.

## Contents

- [Time](#time)
- [Numbers](#numbers)
- [Strings and bytes](#strings-and-bytes)
- [Slices](#slices)
- [Maps](#maps)
- [Resources and defer](#resources-and-defer)
- [Control-flow traps](#control-flow-traps)
- [Performance: measure before you optimize](#performance-measure-before-you-optimize)

## Time

- Durations are `time.Duration` built from unit constants:
  `30 * time.Second`, `250 * time.Millisecond`. A bare integer is
  **nanoseconds** — `time.Sleep(5)`, `time.NewTicker(1000)`,
  `http.Client{Timeout: 30}` are bugs (checker `GO-DURATION`, staticcheck
  SA1004 for `Sleep`). Configuration that arrives as seconds is converted once
  (`time.Duration(n) * time.Second`) or parsed with `time.ParseDuration`.
- Elapsed time is `time.Since(start)` with `start := time.Now()` — the
  monotonic reading makes it immune to wall-clock jumps. Never subtract wall
  times rebuilt from strings or other sources.
- Compare instants with `t.Equal(u)`, `Before`, `After` — never `==`, which
  also compares the location and the monotonic reading (a time that went
  through JSON or a database is never `==` to the original).
- Store and compute in UTC; convert with `In(loc)` only for presentation;
  load zones with `time.LoadLocation`. Format and parse with the layout
  constants (`time.RFC3339`, `time.DateOnly`) rather than hand-typed
  reference layouts.
- Code that needs "now" takes a clock (`now func() time.Time` in the
  constructor) so tests control time; `testing/synctest` fakes the clock for
  code that sleeps or uses timers — see [testing.md](testing.md).
- `time.Time{}` / `IsZero()` means "unset" only where zero can never be real.

## Numbers

- **Money is an integer number of minor units (`int64` cents) or a decimal
  type — never `float64`.** Name the unit in the type (`type Cents int64`).
  Rounding is explicit and done once, with the mode the domain requires.
- Floats are approximations: never `==`/`!=` on computed floats; compare
  within a tolerance, and test special values with `math.IsNaN` /
  `math.IsInf`. Float division by zero yields ±Inf or NaN silently; integer
  division by zero panics — check the divisor when it can be zero.
- Integer arithmetic wraps silently at run time. Where values come from input
  or can grow (counters, sizes, sums of amounts), check before adding,
  multiplying or narrowing:

  ```go
  func addCents(a, b Cents) (Cents, error) {
  	if (b > 0 && a > math.MaxInt64-b) || (b < 0 && a < math.MinInt64-b) {
  		return 0, ErrOverflow
  	}
  	return a + b, nil
  }
  ```

- `int` by default; sized and unsigned types only to match a format or
  protocol. `string(i)` converts a code point, not a number — use
  `strconv.Itoa` (govet `stringintconv`).

## Strings and bytes

- A string is immutable bytes: `len(s)` counts bytes, `s[i]` is a byte, and
  `for i, r := range s` yields runes with their byte offsets. Index and slice
  strings by byte only when the content is known to be ASCII;
  `utf8.RuneCountInString` counts characters.
- Build strings in loops with `strings.Builder` (call `Grow` when the size is
  known) or `strings.Join` — `+=` in a loop copies the whole string every
  iteration.
- `strings.TrimSuffix` / `TrimPrefix` remove one exact affix;
  `TrimRight` / `TrimLeft` strip any run of characters from a *cutset* —
  `TrimRight("report.go.go", ".go")` is `"report"`. Prefer `strings.Cut`,
  `CutPrefix`, `CutSuffix`, `CutLast` (Go 1.27), which also report whether the
  separator was there.
- A substring or subslice keeps the whole original alive; to retain a small
  piece of a large input (a key, an ID) copy it with `strings.Clone` /
  `bytes.Clone`.
- Keep I/O data as `[]byte` and use the `bytes` counterparts instead of
  round-tripping through `string`.
- `strings.Split("", ",")` returns `[""]` — one empty element, not an empty
  slice; check for the empty input first (or iterate `strings.SplitSeq` and
  skip empty fields) when "no values" must mean zero elements.
- `r.Read(buf)` may return fewer bytes than `len(buf)` without an error;
  read an exact amount with `io.ReadFull`, and process `buf[:n]` before
  looking at the error.

## Slices

- A slice is (pointer, length, capacity) over a shared array. `append` writes
  into spare capacity **in place** — appending to a subslice can overwrite
  its parent:

  ```go
  s := []int{1, 2, 3}
  head := s[:1]
  head = append(head, 99) // s is now [1 99 3]
  ```

  Pass or keep `s[lo:hi:hi]` (capacity capped, so `append` reallocates) or a
  copy (`slices.Clone`) when the receiver may append.
- Always `s = append(s, v)`; a function that appends returns the new slice.
- The `range` value is a copy: mutate elements through the index
  (`items[i].Price = p`), not through `v`.
- `copy(dst, src)` copies `min(len(dst), len(src))` elements — size `dst`
  first, or use `slices.Clone`.
- Pre-allocate when the length is known: `make([]T, 0, n)` plus `append`
  (or `make([]T, n)` plus index assignment when every slot is written).
- Empty is `len(s) == 0`. Return a nil slice for "no results". With
  `encoding/json` (v1) a nil slice marshals as `null` and an empty one as
  `[]`; `encoding/json/v2` marshals both as `[]` by default — choose
  deliberately where a client distinguishes them.
- Removing elements: `slices.Delete`, `slices.DeleteFunc`, `slices.Compact`
  clear the vacated tail so pointers there do not keep objects alive; when
  shrinking by hand, `clear(s[n:])` before `s = s[:n]`.
- Compare with `slices.Equal`; search sorted data with `slices.BinarySearch`;
  sort with `slices.Sort` / `slices.SortFunc` and `cmp.Compare` / `cmp.Or`
  for multi-key orders.

## Maps

- Writing to a nil map panics; create with `make` (with a size hint when the
  count is known) or a literal.
- `v, ok := m[k]` whenever absent must differ from the zero value.
- Iteration order is random on purpose: never depend on it; iterate
  `slices.Sorted(maps.Keys(m))` for deterministic output.
- Maps never shrink: a map that spiked keeps its memory after deletes;
  rebuild it (copy the survivors into a new map) if that matters. `clear(m)`
  empties it but keeps the space.
- Sets are `map[T]bool` for readability; `map[T]struct{}` when the set is
  large or on a hot path.
- Maps are not safe for concurrent writes — see
  [concurrency.md](concurrency.md#mutexes-and-shared-state).

## Resources and defer

- Release every resource you acquire, with `defer` immediately after the
  error check that proves you have it: files, `resp.Body` (even when you do
  not read it), `*sql.Rows`, `*sql.Stmt`, `*sql.Tx` (rollback), cancel
  functions, tickers, `os.Root`, locks.
- Write paths join the `Close` error into the result; read paths close
  best-effort — see [errors-config-logging.md](errors-config-logging.md#cleanup-errors).
- `database/sql`: `sql.Open` does not connect — `PingContext` before
  declaring readiness; size the pool (`SetMaxOpenConns`,
  `SetConnMaxLifetime`); scan nullable columns into `sql.Null[T]`; check
  `rows.Err()` after the loop.
- Transactions: `tx, err := db.BeginTx(ctx, nil)`, then immediately
  `defer func() { _ = tx.Rollback() }()` (a no-op after a successful commit),
  run every statement on `tx`, never on `db`, and return the error of
  `tx.Commit()` — a commit can fail.
- `bufio.Scanner`: check `scanner.Err()` after the loop (`Scan` returns false
  on errors too), and know that a token longer than 64 KiB stops it with
  `bufio.ErrTooLong` — raise the limit with `scanner.Buffer(buf, max)` when
  lines can be long.
- **No `defer` inside a loop**: deferred calls run when the *function*
  returns, so a loop that opens a file per iteration holds them all. Move the
  body into a function that defers.
- Arguments of a deferred call are evaluated at the `defer` statement; to use
  final values, defer a closure.
- After writing an error response in an HTTP handler (`http.Error`),
  `return` — the handler otherwise keeps running and writes more.
- Go 1.27 drains a bounded amount of an unread HTTP/1 response body on
  `Close` for connection reuse; closing is still mandatory.

## Control-flow traps

- `break` inside `switch` or `select` leaves only that statement; use a
  labelled `break` to leave the enclosing loop.
- Named results start at their zero values, so returning one that no path
  assigned compiles and returns nil:

  ```go
  func coords(ctx context.Context) (lat, lng float64, err error) {
  	if ctx.Err() != nil {
  		return 0, 0, err // the named err was never assigned: returns nil
  	}
  	// ...
  }
  ```

  Write `if err := ctx.Err(); err != nil { return 0, 0, err }`. Name results
  only when several share a type or a deferred closure must modify them, and
  never use a bare `return` in a function that returns values (the compiler
  already rejects one whose named result is shadowed).
- The range expression is evaluated once before the loop: appending to the
  slice inside the loop does not extend the iteration.

## Performance: measure before you optimize

- Two kinds of optimization. **Reasonable** ones cost no readability and are
  always welcome: pre-allocating known sizes, hoisting invariant work out of
  loops (compile a `regexp` once, call a getter once), `strings.Builder` for
  loops, streaming instead of reading everything, not leaking. **Deliberate**
  ones trade readability or another resource for speed — `sync.Pool`,
  `unsafe` conversions, custom parsers, manual inlining, caches, GC tuning,
  extra concurrency — and need all of: a written goal they serve, a profile
  showing the code is the bottleneck, and a before/after benchmark.
- Benchmarks use `for b.Loop()` (Go 1.24) with setup before the loop and
  `b.ReportAllocs()`; compare versions with `benchstat` over repeated runs
  (`-count=10`), never a single run. Memory and GC changes are confirmed at a
  larger scale than one micro-benchmark.
- Profile before guessing: `go test -cpuprofile/-memprofile`, `pprof`, the
  execution tracer; `go build -gcflags=-m` shows what escapes to the heap.
- Values over pointers for small data, contiguous slices over linked
  structures, fewer allocations over GC tuning. Leave `GOGC` alone unless a
  measurement says otherwise; in memory-limited containers set `GOMEMLIMIT`
  (≈ 90 % of the limit) instead of heap ballast; never call `runtime.GC()`.
- `sync.Pool` only for frequently allocated, resettable objects whose
  allocation cost a profile shows — store pointers, `Reset` before use, and
  `Put` only after the last use. A reusable buffer owned by one worker is
  usually simpler and as fast.
- Profile-guided optimization: commit a representative CPU profile as
  `default.pgo` in the main package when a CPU-heavy service needs the last
  few percent.
- Re-run the relevant benchmarks after a toolchain upgrade — inlining,
  escape analysis and the GC change between releases.
