# Pitfalls: known failure modes

Read this when a checker finding looks wrong or a `strict`-mode edge case
bites. Every pitfall lists its evidence; treat anything without evidence as a
hypothesis, not knowledge.

A pitfall below cites `data/fixtures/*` as calibration evidence. That
directory is Hub-only development content and does **not** ship in a
`runtime` install (see `data/README.md`) — the citation is a plain code
span, not a clickable link, for that reason.

## The checker is lexical, not an AST

**Applies always.** `scripts/check_conventions.py` masks comments, string
literals, template literals (interpolated `${...}` code is still scanned) and
regex literals, so quoted rule text no longer produces findings — but it still
reads the file line by line: a construct split across lines is seen per line,
and semantic questions (is this `any` reachable? is this cast sound?) are
beyond it. It is a backstop; the compiler in `strict` mode and the project
linter are authoritative. Evidence: the masking tests in
`__test__/skills/test_typescript_coding.py` and the calibrated fixture
`data/fixtures/masked_literals.ts`.

## Truthy checks and `||` defaults fail a strict lint stack

**Applies when** the project runs a type-aware lint stack (typescript-eslint
`strictTypeChecked` and friends). The compiler accepts `if (str)` and
`x || fallback`, but the linter does not: `strict-boolean-expressions` rejects
truthiness on a string, number, or nullable, and `prefer-nullish-coalescing`
rejects `||` for a default. Write the explicit form (`if (str !== '')`,
`x ?? fallback`) from the start — these two rules, plus `no-floating-promises`
and `functional/immutable-data`, produce the bulk of surprise findings on
otherwise type-correct code. Evidence:
[../references/lint-clean.md](../references/lint-clean.md).

## `noUncheckedIndexedAccess` makes indexing return `T | undefined`

**Applies when** you index an array or record. With this flag, `arr[i]` is
`T | undefined`; do not reach for a non-null assertion (`arr[i]!`) to silence
it — narrow with a guard or a default. The non-null assertion is exactly what
the checker flags as `TS-NONNULL`. Evidence:
[../references/typing-and-style.md](../references/typing-and-style.md).

## `exactOptionalPropertyTypes` distinguishes "absent" from "undefined"

**Applies when** a type has an optional property. `x?: T` no longer accepts an
explicit `undefined` value — assigning `{ x: undefined }` is an error. Omit the
key to mean "absent"; type it `x?: T | undefined` only if you truly need to
pass `undefined` explicitly. When reading, default with `x ?? fallback`, not
an `in` check — `in` is true for a key explicitly set to `undefined`.
Evidence: [../references/typing-and-style.md](../references/typing-and-style.md).

## Excess-property checking fires only on fresh literals

**Applies when** relying on the compiler to catch a misspelled or extra key.
The check runs only where an object literal is written directly against a
declared type; the same object passed through an untyped variable or an `as`
assertion is accepted, because structural subtyping allows extra members.
Pass or annotate literals directly, and never treat compilation as proof
that no extra fields are present. Evidence:
[../references/type-design.md](../references/type-design.md) (structural
typing consequences).

## `Object.keys` returns `string[]` — by design

**Applies when** iterating an object received as a parameter. Structural
typing means the value may carry keys beyond its declared type, so a
`keyof T` element type would be unsound. Iterate via a generic + `for-in`,
or an `isKey` guard; assert `as keyof typeof obj` only on locally-built
literals. Evidence:
[../references/type-design.md](../references/type-design.md).

## `.filter(Boolean)` does not narrow away null

**Applies when** cleaning nullish values out of an array. `filter(Boolean)`
removes them at runtime but the element type stays `T | null | undefined`.
Filter with an explicit guard predicate — `arr.filter((v): v is T => v != null)`.
Evidence: [../references/type-design.md](../references/type-design.md)
(narrowing).

## `Readonly`, `Partial`, `Required` — and spread — are shallow

**Applies when** deriving types for nested data. The built-in modifiers touch
only the first level, and `Readonly<T>` constrains properties, not mutating
methods. A deep-partial parameter combined with a shallow `{...defaults,
...overrides}` merge silently drops nested defaults — pair a deep type with a
deep merge, or keep both shallow. Evidence:
[../references/generics-and-type-level.md](../references/generics-and-type-level.md).

## TS `private` does not survive to runtime

**Applies when** a field must actually be hidden (secrets, tokens,
serialized objects). `private`/`protected` are erased on emit and the field
stays enumerable — `JSON.stringify` leaks it. Use an ES `#private` field
where privacy is a runtime requirement; keep TS modifiers for compile-time
encapsulation and parameter properties. Evidence:
[../references/type-design.md](../references/type-design.md) (structural
typing consequences).
