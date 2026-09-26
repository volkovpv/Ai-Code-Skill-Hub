# Patterns: verified Go moves

Each pattern states its scope of applicability and links to evidence. None is
an unconditional rule — apply it when its precondition holds. All patterns are
framework- and architecture-neutral.

Several patterns cite `data/fixtures/*` as calibration evidence. That
directory is Hub-only development content and does **not** ship in a
`runtime` install (see `data/README.md`) — those citations are plain code
spans, not links, for that reason. The fixture `data/fixtures/clean_sample.go`
compiles on Go 1.27.1 and passes `go vet` and the reference golangci-lint
configuration with zero issues.

## Contents

- [Enum: typed constants, an end marker, exhaustive switches](#enum-typed-constants-an-end-marker-exhaustive-switches)
- [Variants: a sealed interface](#variants-a-sealed-interface)
- [Id type parsed once at the boundary](#id-type-parsed-once-at-the-boundary)
- [Wrap with context, inspect with errors.Is / AsType](#wrap-with-context-inspect-with-errorsis--astype)
- [Write-path Close joined into the result](#write-path-close-joined-into-the-result)
- [Consumer-owned interface as the test seam](#consumer-owned-interface-as-the-test-seam)
- [Options struct with zero-value defaults](#options-struct-with-zero-value-defaults)
- [An owned goroutine](#an-owned-goroutine)
- [Bounded fan-out with index-owned results](#bounded-fan-out-with-index-owned-results)
- [Input paths through os.Root](#input-paths-through-osroot)
- [HTTP with timeouts on both sides](#http-with-timeouts-on-both-sides)
- [Configuration loaded once](#configuration-loaded-once)
- [A thin main around run](#a-thin-main-around-run)

## Enum: typed constants, an end marker, exhaustive switches

**Applies when** a value ranges over a fixed set. A named type with typed
constants, a zero value named `…Unspecified`, an unexported `…Count` end
marker inside the `iota` block for iteration, and switches that list every
constant plus a failing `default` (the `exhaustive` linter with
`check: [switch, map]`, `default-signifies-exhaustive: false` and
`ignore-enum-members: "Unspecified$|\.[a-z]\w*Count$"`). Evidence: the `Status` type
and its `Statuses` iterator in `data/fixtures/clean_sample.go` (zero findings
under that configuration) and
[../references/type-design.md](../references/type-design.md#closed-sets-typed-constants).

## Variants: a sealed interface

**Applies when** a value is one of several shapes with different fields. An
interface with an unexported marker method and one struct per variant; a type
switch with a `default` that returns an error. Evidence: `Event` /
`Describe` in `data/fixtures/clean_sample.go` and
[../references/type-design.md](../references/type-design.md#variant-state-a-sealed-interface).

## Id type parsed once at the boundary

**Applies when** a value is an identifier or carries a unit. `type OrderID
string` plus `ParseOrderID(raw string) (OrderID, error)` called exactly where
untyped input enters; a struct wrapper with an unexported field where even
conversions must be prevented. Evidence: `OrderID` / `ParseOrderID` in
`data/fixtures/clean_sample.go` and
[../references/type-design.md](../references/type-design.md#named-types-for-ids-and-units).

## Wrap with context, inspect with errors.Is / AsType

**Applies when** an error crosses a function boundary. Return
`fmt.Errorf("<what this function was doing>: %w", err)`, log only where it is
handled, and inspect with `errors.Is` / `errors.AsType[*T]` — never `==` or
message text. Evidence: `Service.Status`, `LoadStatus` and `AsValidation` in
`data/fixtures/clean_sample.go`, and
[../references/errors-config-logging.md](../references/errors-config-logging.md#inspecting-errors).

## Write-path Close joined into the result

**Applies when** a function writes to a file or another closer whose `Close`
can fail. Named `err` result and `defer func() { err = errors.Join(err,
f.Close()) }()`; read paths close best-effort with `_ =`. Evidence:
[../references/errors-config-logging.md](../references/errors-config-logging.md#cleanup-errors)
and the errcheck measurement in
[../references/lint-clean.md](../references/lint-clean.md#errcheck-and-close).

## Consumer-owned interface as the test seam

**Applies when** a function needs part of a dependency's behaviour. Declare
the interface in the consuming package with only the methods it calls; tests
pass a small hand-written struct. Evidence: the `Store` interface consumed by
`Service` in `data/fixtures/clean_sample.go`, and
[../references/generics-and-interfaces.md](../references/generics-and-interfaces.md#interfaces-belong-to-the-consumer).

## Options struct with zero-value defaults

**Applies when** a constructor has optional settings. Mandatory inputs are
parameters; optional ones live in an options struct whose zero fields mean
"use the default"; pointer fields plus `new(expr)` where unset must differ
from zero. Evidence:
[../references/packages-and-apis.md](../references/packages-and-apis.md#optional-parameters-an-options-struct).

## An owned goroutine

**Applies when** work runs in the background. Started through
`sync.WaitGroup.Go` (or an errgroup) by a component that exposes a waiting
method, stopped by `ctx.Done()`, with its ticker stopped by `defer`.
Evidence: [../references/concurrency.md](../references/concurrency.md#every-goroutine-has-an-owner).

## Bounded fan-out with index-owned results

**Applies when** many independent calls run concurrently. With
`golang.org/x/sync/errgroup`: `SetLimit(n)` and the first error cancels the
rest. With the standard library only: take a slot from a buffered channel
*before* `wg.Go`, so no more than `n` goroutines ever exist, collect errors
per index and `errors.Join` them. Either way a result slice pre-sized so each
goroutine writes only its own index — no mutex, no race. Evidence:
`Service.LoadAll` in `data/fixtures/clean_sample.go` and
[../references/concurrency.md](../references/concurrency.md#waiting-for-goroutines-errgroup-and-waitgroupgo).

## Input paths through os.Root

**Applies when** a file name comes from input. `os.OpenRoot(dir)` then
`root.Open(name)` / `root.ReadFile(name)` — traversal and escaping symlinks
are refused by the standard library, no string checks. Evidence:
`ReadAttachment` in `data/fixtures/clean_sample.go` and
[../references/security.md](../references/security.md#files-and-paths).

## HTTP with timeouts on both sides

**Applies when** code serves or calls HTTP. An `http.Server` with
`ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout` on its own
`ServeMux`; one shared `http.Client` with a `Timeout`, requests built with
`NewRequestWithContext`, bodies closed and size-limited. Evidence:
`NewHTTPClient` / `FetchReceipt` in `data/fixtures/clean_sample.go` and
[../references/security.md](../references/security.md#http-servers-and-clients).

## Configuration loaded once

**Applies when** the program reads its environment. One `Load() (Config,
error)` in the configuration package, validating every variable and failing
closed; the rest of the code receives the typed struct. Evidence:
`data/fixtures/app_config.go` (the checker's config-layer context) and
[../references/errors-config-logging.md](../references/errors-config-logging.md#configuration-and-the-environment).

## A thin main around run

**Applies when** writing a command. `main` builds the root context
(`signal.NotifyContext`), calls `run(ctx, args, out) error` — which writes its
output to `out`, never through `fmt.Print*` — and turns the error into an exit
code, the only place `os.Exit` appears. Evidence:
`data/fixtures/cmd_main.go` (the checker's `package main` context) and
[../references/packages-and-apis.md](../references/packages-and-apis.md#a-thin-main).
