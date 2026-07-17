# Passing a strict linter clean (zero warnings)

Strict typing keeps the type checker happy; a strict **lint** stack rejects
a much larger surface — and it counts `warn`-level findings, not only
errors. This file is the checklist that keeps both at zero. It targets the
lint setup a production Python project usually runs: a strict type checker
(mypy `--strict` / pyright strict) plus a broad Ruff-style rule set
(pycodestyle/pyflakes, bugbear, comprehensions, simplify, pylint-parity,
naming, docstring, import-order and pytest-style families) — with **all
formatting delegated to a single formatter** (Black or the Ruff formatter).

Nothing here assumes a framework or architecture. Exact thresholds (line
width, complexity ceilings) are the host project's config; the idioms below
are universal — write to them by default and both `error`- and `warn`-level
findings stay at zero. Where the project's stack differs, its `lint` /
`typecheck` output is authoritative; treat this file as how to be right the
first time, not as the rule source.

## Boolean expressions are explicit

The single biggest source of subtle bugs under truthiness.

- **No truthiness on strings, numbers, or optionals.** Test the thing you
  mean:
  - string — `if s != ""`, never `if s`;
  - number — `if n > 0` / `if n != 0`, never `if n`;
  - optional — `if x is not None`, never `if x` (which also drops `0`,
    `""`, `False`, empty collections);
  - collection emptiness, where size is the point — `if len(items) > 0`.
  Truthiness is reserved for values that are actually `bool`.
- **`x if x is not None else fallback`, not `x or fallback`** for
  defaults — `or` also swallows `""`, `0`, `False`. For dict lookups,
  `mapping.get(key, fallback)` already says it precisely.
- **`is` / `is not` for `None`** and sentinel objects; `==` for values;
  never `== None`, never `== True` / `== False` on a bool.
- **No condition the types prove is always true or false**: a guard on a
  non-optional value is dead code — remove it, or fix the type that made
  it redundant.
- **No implicit coercion tricks**: convert explicitly with `str(x)` /
  `int(x)` / `bool(x)`; interpolate non-strings through an f-string, not
  `+`-concatenation with `str()` sprinkled in.

## Async is supervised

- **Every coroutine is awaited or handed to a task the code keeps.** A
  bare `foo()` call on an async function creates a coroutine that never
  runs (the un-awaited-coroutine warning is a defect, not noise); a bare
  `asyncio.create_task(...)` whose result is dropped can be
  garbage-collected mid-flight and its exception lost. Hold the task and
  supervise it — a `TaskGroup` does both.
- **Independent awaits run concurrently** — `asyncio.gather(*aws)` or a
  task group; a sequential `await` inside a loop adds latencies instead of
  taking their maximum. Deliberate rate-limited batching belongs in a
  named helper carrying a justification.
- **No blocking calls in async code** (`time.sleep`, blocking IO, heavy
  CPU) — use the async equivalent or push the work to a thread
  (`asyncio.to_thread`).
- **Don't pass an async function where a sync callable is expected** — the
  callback machinery will silently never run it.
- **Shared state read before an `await` may be stale after it**: another
  task can interleave at every suspension point — re-read after awaiting,
  or guard the read-modify-write with a lock.

## Immutability by default

- **No in-place mutation of shared data**: build a new value —
  comprehensions, `sorted(xs)` over `xs.sort()`, `{**base, "k": v}` /
  `dataclasses.replace(obj, field=v)` over attribute assignment. An
  object may mutate its **own** private state through its methods.
- **Never reassign or mutate a parameter or its contents**:
  defensive-copy an input that flows through stages.
- **Never a mutable default argument** (`def f(items: list[int] = [])`) —
  it is created once and shared across calls. Default to `None` and
  normalize in the body, or default to an immutable `()`.
- **Data classes are frozen** (`@dataclass(frozen=True, slots=True)`)
  unless mutation is the point; module constants are `Final`; attributes
  never rebound after `__init__` are set once and treated as read-only.
- **Read-only ABCs on the public surface**: parameters take `Sequence` /
  `Mapping` / `AbstractSet`, returns are concrete (`list`, `dict`,
  `tuple`) — see [type-design.md](type-design.md).

## Types precise, no redundancy

- **No `Any`, and no leaks of it**: an untyped def, a bare `dict`
  parameter, or a `json.loads` result silently poisons everything it
  touches. Parse and narrow at the boundary
  ([type-design.md](type-design.md)).
- **`cast()` only with a proven invariant** — never on boundary data,
  never to shut the checker up; no `# type: ignore` in shipped code.
- **Don't annotate what the checker infers** (`n: int = 1` is noise);
  annotate the public surface fully.
- **Modern forms**: `X | None` over `Optional[X]`, `list[int]` over
  `List[int]`, `collections.abc` over `typing` aliases.

## Naming and class shape

- **snake_case** functions, methods, variables, parameters; **PascalCase**
  classes and type aliases; **UPPER_CASE** module constants and enum
  members; leading underscore for private names.
- Members are ordered: class attributes → `__init__` → `classmethod`
  factories → properties → methods.
- **No static-only classes as namespaces** — a module of functions and
  constants does that job; no `@staticmethod` that never touches the
  class (make it a module function).
- **`obj.key` shape beats `getattr(obj, "key")`** for a statically known
  attribute; dynamic attribute access is a smell outside serialization
  code.

## No magic, low duplication, low complexity

- **Name every meaningful literal** — numbers other than `0`/`1`/`-1`/`2`
  and any string that repeats — as a `Final` constant near its owner (see
  [typing-and-style.md](typing-and-style.md)). Tunables live in
  configuration.
- **Keep functions small and shallow.** The stack caps cyclomatic and
  cognitive complexity, nesting depth, and file/function length (the
  reference calibration: complexity ≤ 15, nesting ≤ 4, function ≤ 120
  lines, file ≤ 500 — the host project's config wins). Extract a helper
  rather than grow one function.
- **No duplicated or identical branches, conditions, or functions** —
  factor the shared body out.
- **Prefer the idiom the linter wants:** f-strings over `+`/`%`/
  `.format`; comprehensions over `map`/`filter`-with-lambda and
  accumulate-in-a-loop; `enumerate`/`zip` over manual index bookkeeping;
  unpacking over index access; `with` for every resource; early return
  over `else` after `return`/`raise`; no lonely `if` inside `else` (use
  `elif`); no nested ternary.

## Docstrings on the public surface

- **Exported modules, classes, and functions** carry a docstring with a
  prose **description** of intent and behaviour — what it does and why it
  exists, not a restating of the name.
- **Do not restate types in docstrings**: the signature is the single
  source of truth — describe meaning, constraints, units, error behaviour.
  Parameter/return sections are optional, but if written must be valid and
  correctly named.

## Imports and modules

- **One group order** — `__future__`, stdlib, third-party, first-party,
  local — with a blank line between groups and after the import block;
  imports at the top of the file; no duplicate, wildcard
  (`from x import *`), or relative-beyond-package imports; no import that
  exists only for a side effect without a comment saying so.
- Module-level code executes on import: keep it to definitions and cheap
  constants; anything with effects lives behind
  `if __name__ == "__main__":` or an explicit entry point.

## Formatting

A single formatter owns whitespace, quotes, line width, and trailing
commas. Never fight the formatter by hand or add a second one — run it
**before** the linter. A style finding surfacing from the linter usually
means the formatter has simply not run yet.

## Self-check

The bundled `scripts/check_py_conventions.py` catches only the mechanical,
lexical subset of the above (`Any`, `print`, raw env reads, bare `except`,
`assert` in shipped code, suppressions, debugger calls). The type-aware
rules — boolean strictness, un-awaited coroutines, mutation, dead
conditions — are invisible to a lexical scanner. The project's real `lint`
and `typecheck` are the authority; run them, and read every finding in
context.
