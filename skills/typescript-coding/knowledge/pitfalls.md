# Pitfalls: known failure modes

Read this when a checker finding looks wrong or a `strict`-mode edge case
bites. Every pitfall lists its evidence; treat anything without evidence as a
hypothesis, not knowledge.

## The checker is lexical, not an AST

**Applies always.** `scripts/check_conventions.py` masks comments, string
literals, template literals (interpolated `${...}` code is still scanned) and
regex literals, so quoted rule text no longer produces findings — but it still
reads the file line by line: a construct split across lines is seen per line,
and semantic questions (is this `any` reachable? is this cast sound?) are
beyond it. It is a backstop; the compiler in `strict` mode and the project
linter are authoritative. Evidence: the masking tests in
`__test__/skills/test_typescript_coding.py` and the calibrated fixture
[../data/fixtures/masked_literals.ts](../data/fixtures/masked_literals.ts).

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
pass `undefined` explicitly. Evidence:
[../references/typing-and-style.md](../references/typing-and-style.md).
