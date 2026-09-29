# Concurrency

Goroutines are cheap to start and expensive to lose track of. Every goroutine
has an owner that knows how it stops and waits for it; every blocking
operation can be cancelled; every piece of shared memory has exactly one
synchronization story.

## Contents

- [Concurrency only when it pays](#concurrency-only-when-it-pays)
- [Every goroutine has an owner](#every-goroutine-has-an-owner)
- [Context](#context)
- [Waiting for goroutines: errgroup and WaitGroup.Go](#waiting-for-goroutines-errgroup-and-waitgroupgo)
- [Bounded fan-out](#bounded-fan-out)
- [Channels](#channels)
- [Mutexes and shared state](#mutexes-and-shared-state)
- [Timers and tickers](#timers-and-tickers)
- [Races, leaks and how to find them](#races-leaks-and-how-to-find-them)

## Concurrency only when it pays

- Start sequential. Add concurrency for independent operations that wait —
  network calls, disk, other services — or when the problem is naturally
  concurrent (one goroutine per connection). Fast in-memory work usually gets
  slower when split: a goroutine per small item costs more in scheduling and
  channel traffic than the work itself.
- For CPU-bound parallelism, measure the sequential version first and split
  into a few large shards, not one goroutine per element.
- Keep business functions synchronous and unaware of goroutines; do the
  concurrency bookkeeping in the caller that launches them. Exported APIs do
  not take or return channels or mutexes unless concurrency is the package's
  purpose.

## Every goroutine has an owner

Before writing `go`, answer three questions: **who owns it, what makes it
stop, and who waits for it to finish.** A goroutine blocked forever is never
collected — its stack and everything it references leak, and a leak on a
cancellation path grows with every cancelled request.

```go
// Start polls until ctx is cancelled; Wait returns after the goroutine exits.
func (p *Poller) Start(ctx context.Context) {
	p.wg.Go(func() {
		ticker := time.NewTicker(p.interval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				p.poll(ctx)
			}
		}
	})
}

func (p *Poller) Wait() { p.wg.Wait() }
```

- No fire-and-forget: `go f()` with no owner and no stop condition is a
  defect. A component that runs goroutines exposes a blocking `Close`/`Wait`
  (or runs them inside a function that returns only when they are done).
- A worker whose result may no longer be wanted must still be able to finish:
  either the receiver always receives, or the worker's send `select`s on
  `ctx.Done()`. Returning early from `select { case <-ctx.Done(): }` while a
  worker blocks on an unbuffered send leaks that worker.
- `main` returning kills every goroutine without cleanup — shutdown is
  designed, not assumed: cancel the root context, then wait.

## Context

- `ctx context.Context` is the **first parameter** of every function that
  blocks, does I/O, or starts work callers may want to cancel — named `ctx`,
  passed down explicitly.
- **Never store a context in a struct** (`containedctx`), never pass `nil`,
  and create a root context (`context.Background()`) only in `main`, at the
  top of a test, or where a framework hands you none — never
  `context.TODO()` in shipped code (checker `GO-CTX-ROOT`, relaxed in
  `package main` and tests; in tests prefer `t.Context()`).
- Every `WithCancel`/`WithTimeout`/`WithDeadline` is followed by
  `defer cancel()` (govet `lostcancel`). Use the `…Cause` variants and
  `context.Cause(ctx)` to record why.
- Work that must outlive the request (publishing after the response was
  written) runs on `context.WithoutCancel(ctx)` plus its own timeout — it keeps
  the values (trace IDs), drops the cancellation. Never `context.Background()`
  there: it drops the values too.
- Honour cancellation in your own code: every `select` has a
  `case <-ctx.Done()`, and long CPU loops check `ctx.Err()` periodically.
- Context values carry request-scoped metadata only (trace IDs,
  authenticated principal) behind an unexported key type and typed
  accessors; business parameters are explicit arguments:

  ```go
  type principalKey struct{}

  func WithPrincipal(ctx context.Context, p Principal) context.Context {
  	return context.WithValue(ctx, principalKey{}, p)
  }

  func PrincipalFrom(ctx context.Context) (Principal, bool) {
  	p, ok := ctx.Value(principalKey{}).(Principal)
  	return p, ok
  }
  ```

## Waiting for goroutines: errgroup and WaitGroup.Go

- Goroutines that can fail, where the first error should cancel the rest:
  `golang.org/x/sync/errgroup` with `WithContext`; the work must honour the
  derived context or cancellation changes nothing:

  ```go
  g, ctx := errgroup.WithContext(ctx)
  g.SetLimit(8)
  results := make([]Page, len(urls))
  for i, u := range urls {
  	g.Go(func() error {
  		page, err := fetch(ctx, client, u)
  		results[i] = page // distinct index per goroutine: no race
  		return err
  	})
  }
  if err := g.Wait(); err != nil {
  	return nil, fmt.Errorf("fetch pages: %w", err)
  }
  ```

- Goroutines that do not return errors: `sync.WaitGroup.Go` (Go 1.25), never
  `wg.Add(1)` inside the goroutine (it races with `Wait`; govet `waitgroup`).
- Loop variables are per-iteration since Go 1.22: capture `i` and `u`
  directly; a `u := u` copy is dead code.
- The derived errgroup context is cancelled when `Wait` returns — do not use
  it afterwards.

## Bounded fan-out

- Never let input size decide how many goroutines run: bound with
  `errgroup.SetLimit`, a fixed worker pool, or a buffered channel used as a
  semaphore — acquired *before* the `go` statement, so a thousand inputs never
  mean a thousand parked goroutines. Without `x/sync`: acquire the slot, then
  `wg.Go`, record each goroutine's error at its own index, and
  `errors.Join` them after `wg.Wait()`.
- CPU-bound work: about `runtime.GOMAXPROCS(0)` workers. I/O-bound work: what
  the downstream system can absorb — the limit protects it too.
- Under overload, reject (HTTP 429) rather than queue without bound.
- GOMAXPROCS already follows the container's CPU limit (Go 1.25); do not set
  it at startup or import `go.uber.org/automaxprocs` (checker
  `GO-LEGACY-IMPORT`).

## Channels

- Channels coordinate goroutines and transfer ownership of data; a mutex
  protects shared state. Pick by that, not by slogan.
- **The sender closes**, and only when a receiver waits for the close
  (`for v := range ch`); with several senders, a single goroutine closes after
  `wg.Wait()`. Sending on or closing a closed channel panics. Receive with
  comma-ok (`v, ok := <-ch`) where the channel may be closed.
- Unbuffered by default. A buffer needs a stated reason: one slot per
  launched goroutine so none blocks, a deliberate cap on queued work, or a
  measured throughput need — and the size says which (`make(chan Result,
  workers)`).
- Use directional types in signatures (`<-chan T`, `chan<- T`).
- `chan struct{}` for signals; `close` it to broadcast to every receiver.
- In a `for`–`select` loop: an exit case is mandatory, a `default` case turns
  it into a busy loop, and a nil channel variable disables its case (set a
  drained input to `nil`). `select` picks among ready cases at random — never
  rely on case order for priority.
- `break` inside `select` or `switch` leaves only that statement; leave the
  loop with a labelled `break`:

  ```go
  loop:
  	for {
  		select {
  		case <-ctx.Done():
  			break loop
  		case m := <-msgs:
  			handle(m)
  		}
  	}
  ```

## Mutexes and shared state

- Every variable touched by more than one goroutine, with at least one
  writer, is synchronized — there is no benign data race, and "each goroutine
  writes different keys" does not make a map safe (concurrent map writes are a
  fatal runtime error).
- The mutex is a named unexported field next to the data it guards
  (`mu sync.Mutex`), never embedded, never copied — pointer receivers
  throughout (govet `copylocks`):

  ```go
  type Counter struct {
  	mu     sync.Mutex
  	counts map[string]int
  }

  func (c *Counter) Inc(key string) {
  	c.mu.Lock()
  	defer c.mu.Unlock()
  	c.counts[key]++
  }
  ```

- `defer mu.Unlock()` right after `Lock`. Locks are not reentrant: never
  re-lock in a callee, never call unknown code (callbacks, `%v` formatting of
  a value whose `String` method locks) while holding one.
- Reading a shared map or slice after `Unlock` races with writers —
  assignment copies the header, not the contents. Keep the whole read inside
  the critical section, or copy (`maps.Clone`, `slices.Clone`) under the lock
  and work on the copy.
- `append` to a slice shared between goroutines is a race whenever capacity
  remains; each goroutine appends to its own slice or writes its own index.
- `sync.RWMutex` when reads vastly outnumber writes; typed atomics
  (`atomic.Int64`, `atomic.Bool`, `atomic.Pointer[T]`) for single-word
  counters and flags — never the `atomic.AddInt64(&n, …)` function family on
  a plain integer (checker `GO-LEGACY-API`). `sync.Map` only for
  write-once/read-many or disjoint-key workloads. `sync.Cond` rarely — a
  closed channel plus a context usually says the same thing more clearly.
- One-time lazy initialization: `sync.OnceValue` / `sync.OnceFunc`.

## Timers and tickers

- `time.After` inside a loop allocates a new timer every iteration; reuse one
  `time.NewTimer` (`Reset` per iteration) or a `time.NewTicker`, and `Stop` it
  with `defer`. Since Go 1.23 an unreferenced timer is collectable and timer
  channels are unbuffered (no stale tick after `Reset`/`Stop`), so the old
  "leaks until it fires" warning no longer applies — the allocation does.
- Durations passed to timers are built from unit constants
  (`30 * time.Second`); a bare integer is nanoseconds (checker `GO-DURATION`).

## Races, leaks and how to find them

- Run tests with `go test -race` in CI; the detector finds races only on paths
  the tests execute, so exercise the concurrent paths. Never "fix" a race
  with `time.Sleep`.
- Test concurrency deterministically with `testing/synctest` (fake clock,
  `synctest.Wait` until every goroutine in the bubble is blocked;
  `synctest.Sleep` since Go 1.27) — see [testing.md](testing.md).
- Leaks in a running program: the `goroutineleak` profile (`runtime/pprof`,
  `/debug/pprof/goroutineleak`, Go 1.27) reports goroutines blocked forever on
  unreachable channels or locks; a steadily rising goroutine count is the
  production signal.
