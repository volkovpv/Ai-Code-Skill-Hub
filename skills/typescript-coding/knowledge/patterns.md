# Patterns: verified typing moves

Each pattern states its scope of applicability and links to evidence. None is
an unconditional rule — apply it when its precondition holds. All patterns
are framework- and architecture-neutral.

## Closed set = `as const` object + union (never `enum`)

**Applies when** a value ranges over a fixed set. Use an `as const` object and
derive the union with `(typeof X)[keyof typeof X]`. Unlike a native `enum` it
erases to plain values, needs no runtime import, and narrows structurally.
Evidence: the `USER_STATUS` registry in
[../data/fixtures/clean_sample.ts](../data/fixtures/clean_sample.ts); the
checker flags `enum` as `TS-ENUM`.

## Branded id + coercer at the boundary

**Applies when** a value is an identifier. Give it a branded type and apply
the coercer (`asXxxId`) exactly where untyped input enters, so a raw `string`
can never be passed where an id is expected. Evidence: `UserId` / `asUserId`
in [../data/fixtures/clean_sample.ts](../data/fixtures/clean_sample.ts) and
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
[../data/fixtures/clean_sample.ts](../data/fixtures/clean_sample.ts).
