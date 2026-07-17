# Concurrency: async, threads, processes

Discipline for concurrent Python: structured async with supervised tasks,
explicit locking that never leans on the GIL, and a deliberate choice of
concurrency model. Framework- and architecture-neutral; the event-loop
runner, driver libraries, and pool wiring belong to the host project.

## Contents

- [Async: structured concurrency](#async-structured-concurrency)
- [Timeouts and cancellation](#timeouts-and-cancellation)
- [The event loop is sacred: no blocking calls](#the-event-loop-is-sacred-no-blocking-calls)
- [Async state and interleaving](#async-state-and-interleaving)
- [Threads: lock like there is no GIL](#threads-lock-like-there-is-no-gil)
- [Choosing the model](#choosing-the-model)

## Async: structured concurrency

- **One entry point: `asyncio.run(main())`.** Inside coroutines use
  `asyncio.get_running_loop()`; `asyncio.get_event_loop()` without a
  running loop is legacy (it raises on 3.14). Libraries never call
  `asyncio.run` themselves — they accept being awaited inside the caller's
  loop.
- **`asyncio.TaskGroup` is the default way to spawn concurrent work**
  (3.11+): it owns its tasks, cancels the siblings when one fails, and
  cannot leak a task past its `async with`. Failures arrive as an
  `ExceptionGroup` — handle with `except*` (see
  [errors-config-logging.md](errors-config-logging.md)).
  `asyncio.gather(*aws, return_exceptions=True)` remains the right tool
  for one case: collect every outcome, never cancel peers. Plain `gather`
  without `return_exceptions` leaves siblings running after a failure —
  don't default to it.
- **Fire-and-forget is a defect.** Every coroutine is awaited, and every
  task has an owner: the event loop holds only weak references, so a
  `create_task` result that nobody keeps can be garbage-collected
  mid-flight and its exception silently lost. A background task the code
  legitimately outlives goes into a task group or a tracked set with a
  done-callback that surfaces its failure.
- **Independent awaits run concurrently** — a task group (or `gather`),
  not a sequential `await` inside a loop that adds latencies instead of
  taking their maximum. Deliberate rate-limited batching belongs in a
  named helper carrying a justification.

## Timeouts and cancellation

- **Every external await has a deadline.** An await on the network without
  a timeout is a hang waiting to happen. Use `async with
  asyncio.timeout(seconds):` (3.11+) around the block — it composes and
  nests; reserve `wait_for` for pre-3.11 code.
- **`CancelledError` must propagate.** It derives from `BaseException`
  precisely so `except Exception` does not eat it; catching it without
  re-raising breaks every timeout and task group above you (both are built
  on cancellation). Cleanup belongs in `try/finally` or `async with`;
  `asyncio.shield` protects only tiny, bounded shutdown-critical sections.
- Retries wrap the timeout, not the other way around: bounded attempts,
  backoff, and a total deadline — see the retry rules in
  [errors-config-logging.md](errors-config-logging.md).

## The event loop is sacred: no blocking calls

- No `time.sleep`, no synchronous network or file IO, no heavy CPU work
  inside a coroutine — one blocking call stalls every task on the loop.
  Use the async equivalent, push blocking library calls through
  `await asyncio.to_thread(...)`, and CPU-bound work to a pool (see
  [Choosing the model](#choosing-the-model)).
- Don't pass an async function where a sync callable is expected — the
  callback machinery silently never runs it.
- During development, run the loop in debug mode
  (`PYTHONASYNCIODEBUG=1`) — it logs slow callbacks and un-awaited
  coroutines.

## Async state and interleaving

- **Every `await` is a preemption point**: shared state read before it may
  be stale after it. Re-read after awaiting, or guard the whole
  read-modify-write with an `asyncio.Lock`.
- Values that must stay consistent across an await travel together in one
  immutable snapshot (a frozen dataclass), not as separate variables that
  can drift.

## Threads: lock like there is no GIL

- **Never justify lock-free code with the GIL.** The GIL never made
  compound operations atomic (`d[k] += 1` and check-then-act always
  raced), and free-threaded CPython (officially supported from 3.14) has
  no GIL at all. The rule that is correct on every build: every
  cross-thread mutation of shared state goes through an explicit
  `threading.Lock`/`RLock`, a `queue.Queue`, or an immutable hand-off.
- Prefer **message passing over shared state**: producers and consumers
  exchange immutable objects through `queue.Queue`; per-thread state lives
  in `threading.local` or `contextvars`, not module globals.
- **Never share an iterator between threads** (items get skipped or
  duplicated); each thread iterates its own.
- Locks are resources: acquire with `with lock:`, keep critical sections
  small, and never call unknown code (callbacks, logging with custom
  handlers) while holding one.
- Mutate global process state (warning filters via
  `warnings.catch_warnings`, locale, cwd, environment) only at startup,
  never from concurrent code — these are process-wide and not
  thread-safe to toggle.

## Choosing the model

| Workload | Use |
|----------|-----|
| Many concurrent I/O-bound operations | `asyncio` |
| Few blocking calls, or libraries without async support | threads (`ThreadPoolExecutor`, `asyncio.to_thread`) |
| CPU-bound work, isolation via message passing | process pool — or `InterpreterPoolExecutor` on 3.14+ |
| CPU-bound work with fine-grained shared memory | free-threaded build + threads, as a deliberate, benchmarked opt-in |

- Pool workers are **top-level, picklable functions taking explicit
  arguments** — never rely on `fork`-inherited globals or lambdas; the
  default start method is no longer `fork` on most platforms (3.14), and
  forking a threaded process was always unsafe.
- Subinterpreters (`concurrent.interpreters`, 3.14+) give in-process
  multi-core parallelism with strong isolation, but are **not a security
  boundary** — never use them to sandbox untrusted code.
- Concurrency is a means: default to simple sequential code, and reach for
  a model only when latency or throughput demands it — then encode the
  choice in one place, not scattered ad-hoc threads.
