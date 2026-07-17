# Patterns: verified typing moves

Each pattern states its scope of applicability and links to evidence. None
is an unconditional rule — apply it when its precondition holds. All
patterns are framework- and architecture-neutral.

## Contents

- [Closed set = enum or `Literal` union](#closed-set--enum-or-literal-union-never-loose-strings)
- [Branded id: `NewType` + validating constructor](#branded-id-newtype--validating-constructor-at-the-boundary)
- [Frozen dataclass, read-only surface](#frozen-dataclass-read-only-surface)
- [Wrap once with `raise ... from` at the source](#wrap-once-with-raise--from-at-the-source)
- [Tagged union + `assert_never` default](#tagged-union--assert_never-default)
- [Enum-keyed mapping with a completeness test](#enum-keyed-mapping-with-a-completeness-test)
- [Minimal `Protocol` as the test seam](#minimal-protocol-as-the-test-seam)
- [TaskGroup owns the fan-out](#taskgroup-owns-the-fan-out)
- [Untrusted values ride out-of-band](#untrusted-values-ride-out-of-band-never-in-the-string)
- [Path containment: resolve, then `is_relative_to`](#path-containment-resolve-then-is_relative_to)
- [Clock as a dependency, aware-UTC everywhere](#clock-as-a-dependency-aware-utc-everywhere)
- [One source of truth per boundary shape](#one-source-of-truth-per-boundary-shape)

## Closed set = enum or `Literal` union (never loose strings)

**Applies when** a value ranges over a fixed set. Use an `enum.StrEnum`
(or a `Literal` union for lightweight boundary shapes) so the checker has a
finite domain to exhaust; comparing loose strings by value scatters the set
and hides typos. Evidence: the `UserStatus` enum in
[../data/fixtures/clean_sample.py](../data/fixtures/clean_sample.py) and
[../references/typing-and-style.md](../references/typing-and-style.md).

## Branded id: `NewType` + validating constructor at the boundary

**Applies when** a value is an identifier. Declare a `NewType` and apply
its constructor (behind a validating `parse_xxx_id` function) exactly where
untyped input enters, so a raw `str` can never be passed where an id is
expected. Evidence: `UserId` / `parse_user_id` in
[../data/fixtures/clean_sample.py](../data/fixtures/clean_sample.py) and
[../references/typing-and-style.md](../references/typing-and-style.md).

## Frozen dataclass, read-only surface

**Applies when** defining a data-carrying type or a public signature.
`@dataclass(frozen=True, slots=True)` for data, `Final` for constants,
`Sequence`/`Mapping`/`AbstractSet` parameters with concrete returns — the
public contract is immutable-by-default. Evidence:
[../references/typing-and-style.md](../references/typing-and-style.md) and
[../references/lint-clean.md](../references/lint-clean.md).

## Wrap once with `raise ... from` at the source

**Applies when** a low-level error must become a higher-level typed error.
Wrap it exactly where it first crosses into your code
(`raise HigherError("...") from err`) and let it bubble untouched —
re-wrapping in intermediate callers duplicates context and mangles the
chain. Evidence:
[../references/errors-config-logging.md](../references/errors-config-logging.md)
and the typed-error example in
[../data/fixtures/clean_sample.py](../data/fixtures/clean_sample.py).

## Tagged union + `assert_never` default

**Applies when** a value ranges over variants or states. Model it as a
union of frozen dataclasses (one class per variant), narrow with `match`,
and close the `case _` with `typing.assert_never` — a new variant then
breaks the type check at every unhandled `match` and still fails loudly on
unsound runtime input. Evidence:
[../references/type-design.md](../references/type-design.md).

## Enum-keyed mapping with a completeness test

**Applies when** parallel data must cover every member of a closed set
(handlers, serializers, per-variant config). Key the mapping by the enum
and pin completeness with a one-line test
(`set(HANDLERS) == set(UserStatus)`) — adding a member then breaks the
build at the map. Evidence:
[../references/generics-and-protocols.md](../references/generics-and-protocols.md).

## Minimal `Protocol` as the test seam

**Applies when** a function needs only part of a large dependency. Declare
the parameter as a minimal `Protocol` with just the members used;
production objects satisfy it structurally, and tests pass a plain stub
object instead of a mock library. Evidence:
[../references/generics-and-protocols.md](../references/generics-and-protocols.md)
and the `UserSource` protocol in
[../data/fixtures/clean_sample.py](../data/fixtures/clean_sample.py).

## TaskGroup owns the fan-out

**Applies when** several awaits are independent. Spawn them inside one
`async with asyncio.TaskGroup()` — the group supervises every task,
cancels the siblings when one fails, and cannot leak a task past its
scope; a failure surfaces as an `ExceptionGroup` handled with `except*`.
Reserve `gather(..., return_exceptions=True)` for "collect every outcome,
never cancel peers". Evidence:
[../references/concurrency.md](../references/concurrency.md).

## Untrusted values ride out-of-band, never in the string

**Applies when** input reaches SQL, a subprocess, or any query-like
string. Pass values through the channel that keeps them data:
placeholders for SQL, an argument list for subprocess (no `shell=True`),
an allowlist for identifiers. Escaping by hand is the fallback of last
resort inside one audited seam. Evidence:
[../references/security.md](../references/security.md) and the `PY-SHELL`
calibration in [../data/fixtures/violations.py](../data/fixtures/violations.py).

## Path containment: resolve, then `is_relative_to`

**Applies when** a filesystem path is built from input. Resolve the base
and the joined result, then require
`target.is_relative_to(base)` — string prefix checks are defeated by
`..`, prefix collisions, and symlinks. Evidence:
[../references/security.md](../references/security.md).

## Clock as a dependency, aware-UTC everywhere

**Applies when** code needs the current time. Construct aware datetimes
(`datetime.now(timezone.utc)`), keep computation in UTC, localize at
presentation — and pass the clock in (a `now` callable or protocol) so
tests inject a fixed time instead of sleeping. Evidence:
[../references/runtime-correctness.md](../references/runtime-correctness.md)
and [../references/testing.md](../references/testing.md).

## One source of truth per boundary shape

**Applies when** external data (API payload, file, queue message) needs
both a static type and runtime validation. Derive one from the other — a
runtime schema whose static type is inferred from it, types generated from
the external spec, or `typing.get_args` recovering a `Literal` union for
the validator — never a hand-maintained type + validator pair, which drift
apart silently. Evidence:
[../references/type-design.md](../references/type-design.md) (trust
boundaries).
