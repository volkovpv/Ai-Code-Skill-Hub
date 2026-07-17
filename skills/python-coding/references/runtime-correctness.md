# Runtime correctness: time, numbers, resources, performance

Rules for the values and resources that break at runtime, not at the type
checker: clocks, money, floats, file handles, and the handful of
performance idioms that are really correctness rules. Framework- and
architecture-neutral.

## Contents

- [Time and clocks](#time-and-clocks)
- [Money and floats](#money-and-floats)
- [Resource lifecycle](#resource-lifecycle)
- [Performance rules that are correctness rules](#performance-rules-that-are-correctness-rules)

## Time and clocks

- **Aware datetimes only.** A naive `datetime` compares and converts
  wrongly the moment a second timezone appears. Construct with an explicit
  timezone — `datetime.now(timezone.utc)` — and never `utcnow()` /
  `utcfromtimestamp()` (deprecated since 3.12, naive by construction; the
  checker flags them as `PY-UTCNOW`).
- **Store and compute in UTC; localize only at presentation** with
  `zoneinfo.ZoneInfo`. A timezone name in data is configuration, not a
  hardcoded string per call site.
- **Elapsed time uses a monotonic clock** — `time.monotonic()` or
  `time.perf_counter()`; subtracting wall-clock timestamps breaks under
  NTP steps and DST. Wall-clock is for timestamps, monotonic for
  durations.
- Code that "knows what time it is" takes the clock as a dependency (a
  `now: Callable[[], datetime]` parameter or clock protocol) so tests can
  inject a fixed time — see [testing.md](testing.md).

## Money and floats

- **Money is `decimal.Decimal` or integer minor units (cents) — never
  binary `float`.** Construct `Decimal` from `str` or `int`, never from
  `float` (`Decimal(0.1)` imports the binary error). Rounding is explicit:
  pick the rounding mode the domain requires and name it once.
- **Never `==` on floats**: use `math.isclose(a, b, rel_tol=...,
  abs_tol=...)` — and remember `abs_tol` is required for comparisons
  against zero.
- Serialization boundaries preserve exactness: money as a string or
  integer minor units in JSON, never a JSON float.

## Resource lifecycle

- **Every acquired resource is released by a context manager** — files,
  sockets, connections, locks, subprocesses (`Popen` is one). Relying on
  garbage collection to close is nondeterministic and already wrong on
  free-threaded builds and alternative interpreters.
- **`__del__` is never the release path.** It may run late, never, or
  during interpreter shutdown with modules half-collected, and its
  exceptions are swallowed. At most it is a leak detector that warns.
- A class that owns a resource exposes `__enter__/__exit__` (or the async
  variants), not a bare `open()`/`close()` pair; if `close()` exists it is
  idempotent.
- **`contextlib` over hand-rolled `try/finally` pyramids**:
  `ExitStack`/`AsyncExitStack` for N resources or conditional acquisition
  (`stack.pop_all()` for the commit/rollback pattern), `closing()` for
  close-only objects, `@contextmanager` for a simple paired setup/teardown.
  `contextlib.suppress(SpecificError)` is still a swallow — see
  [errors-config-logging.md](errors-config-logging.md).
- **A suspended generator's `finally` runs only at GC**: a generator that
  holds a resource must be driven to completion or closed deterministically
  (`contextlib.closing`), not abandoned mid-iteration.

## Performance rules that are correctness rules

These are the idioms whose absence eventually breaks production, not
micro-optimizations:

- **String building in a loop is `"".join(parts)`** (or an `io.StringIO`),
  never `s += piece` — the quadratic form is an accident waiting for a
  large input.
- **Stream large data with generators and iterators**; materialize a
  `list` only for `len()`, indexing, or multiple passes. Iterate files
  line by line, not `read()` into memory.
- **Membership tests inside loops use `set`/`dict`**, not `list` (O(1) vs
  O(n)); head-removals use `collections.deque`, not `list.pop(0)`.
- **`functools.lru_cache`/`cache` on an instance method is banned** — the
  function-level cache keeps every `self` alive forever. Use
  `functools.cached_property`, a module-level cached function over
  hashable arguments, or an explicit instance-local cache. Prefer a
  bounded `lru_cache(maxsize=N)` when keys come from input, and never
  cache functions of mutable or time-dependent state.
- `slots=True` (already the default via
  `@dataclass(frozen=True, slots=True)`) for classes instantiated in
  volume.
- **Beyond these idioms, measure before optimizing** — a profiler trace
  justifies a perf-motivated restructuring; folklore does not. Premature
  caching in particular is a correctness hazard (staleness, leaks), not a
  free win.
