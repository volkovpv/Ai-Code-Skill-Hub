# Patterns: verified typing moves

Each pattern states its scope of applicability and links to evidence. None is
an unconditional rule — apply it when its precondition holds. All patterns
are framework- and architecture-neutral.

Some patterns cite `data/fixtures/*` below as calibration evidence. That
directory is Hub-only development content and does **not** ship in a
`runtime` install (see `data/README.md`) — those citations are written as
plain code spans, not clickable links, for that reason.

## Closed set = `as const` object + union (never `enum`)

**Applies when** a value ranges over a fixed set. Use an `as const` object and
derive the union with `(typeof X)[keyof typeof X]`. Unlike a native `enum` it
erases to plain values, needs no runtime import, and narrows structurally.
Evidence: the `USER_STATUS` registry in
`data/fixtures/clean_sample.ts`; the
checker flags `enum` as `TS-ENUM`.

## Branded id + coercer at the boundary

**Applies when** a value is an identifier. Give it a branded type and apply
the coercer (`asXxxId`) exactly where untyped input enters, so a raw `string`
can never be passed where an id is expected. Evidence: `UserId` / `asUserId`
in `data/fixtures/clean_sample.ts` and
[../references/typing-and-style.md](../references/typing-and-style.md).

## Readonly public surface

**Applies when** exporting a type, class, or function result. `readonly`
fields, `readonly T[]`, and explicit return types make the public contract
immutable-by-default and pin what inference would otherwise drift. Evidence:
[../references/typing-and-style.md](../references/typing-and-style.md).

## Wrap once with `cause` at the source

**Applies when** a low-level error must become a higher-level typed error.
Wrap it exactly where it first crosses into your code
(`new HigherError('...', { cause: error })`) and let it bubble untouched —
re-wrapping in intermediate callers destroys the trace. Evidence:
[../references/errors-config-logging.md](../references/errors-config-logging.md)
and the typed-error example in
`data/fixtures/clean_sample.ts`.

## Discriminated union + `assertUnreachable` default

**Applies when** a value ranges over variants or states. Model it as a union
whose members carry a literal discriminant, narrow with `switch` on the
discriminant, and close the `default` with a `never`-typed
`assertUnreachable` helper that throws — a new variant then breaks
compilation at every unhandled switch and still fails loudly on unsound
runtime input. Evidence:
[../references/type-design.md](../references/type-design.md).

## `satisfies` for registries that must keep exact keys

**Applies when** a constant must both conform to a contract and keep its
precise inferred type (config maps, route tables, `as const` registries).
`const X = {...} as const satisfies Contract` checks conformance at the
definition without widening, so `keyof typeof X` keeps the literal keys. An
annotation would widen; a bare `as const` defers errors to use sites.
Evidence: [../references/type-design.md](../references/type-design.md).

## Narrow structural interface as the test seam

**Applies when** a function needs only part of a large dependency. Declare
the parameter as a minimal interface with just the members used; production
objects satisfy it structurally, and tests pass a plain object literal
instead of a mock library. Evidence:
[../references/type-design.md](../references/type-design.md) (wide inputs,
narrow outputs).

## One source of truth per boundary shape

**Applies when** external data (API payload, file, queue message) needs both
a static type and runtime validation. Derive one from the other — a runtime
schema whose static type is inferred from it, or types generated from the
external spec — never a hand-maintained type + validator pair, which drift
apart silently. Evidence:
[../references/type-design.md](../references/type-design.md) (trust
boundaries).
