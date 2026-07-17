# Pitfalls: known failure modes

Read this when a checker finding looks wrong or a typing/runtime edge case
bites. Every pitfall lists its evidence; treat anything without evidence as
a hypothesis, not knowledge.

## The checker is lexical, not an AST

**Applies always.** `scripts/check_py_conventions.py` masks comments and
string literals (code inside f-string interpolations `{...}` is still
scanned), so quoted rule text no longer produces findings — but it still
reads the file line by line: a construct split across lines is seen per
line, and semantic questions (is this `Any` reachable? is this `cast`
sound?) are beyond it. It is a backstop; the type checker in strict mode
and the project linter are authoritative. Evidence: the masking tests in
`__test__/skills/test_python_coding.py` and the calibrated fixture
[../data/fixtures/masked_literals.py](../data/fixtures/masked_literals.py).

## `x or default` swallows every falsy value

**Applies when** defaulting an optional. `value or fallback` replaces not
only `None` but also `""`, `0`, `0.0`, `False`, and empty collections —
exactly the values a user may legitimately supply. Write
`value if value is not None else fallback`. The same trap makes `if x:`
the wrong optional check — use `is not None`. Evidence:
[../references/lint-clean.md](../references/lint-clean.md).

## Mutable default arguments are shared across calls

**Applies when** a parameter defaults to `[]`, `{}`, `set()`, or any
mutable object. The default is evaluated once at definition time; every
call that omits the argument mutates the same object. Default to `None`
and normalize in the body, or default to an immutable `()`. Evidence:
[../references/lint-clean.md](../references/lint-clean.md).

## A coroutine you don't await never runs

**Applies when** calling an async function. `foo()` on a coroutine
function only *creates* the coroutine; without an `await` (or a supervised
task) it never executes and its exception is never raised. A dropped
`asyncio.create_task` handle can be garbage-collected mid-flight — hold
the task or use a `TaskGroup`. Evidence:
[../references/lint-clean.md](../references/lint-clean.md) (async is
supervised).

## `assert` disappears under `python -O`

**Applies when** validating anything in shipped code. Assertions are
compiled out with optimization on, so an `assert` guarding real input is a
check that may not run in production — raise a typed error instead. The
checker flags shipped-code asserts as `PY-ASSERT`; in tests they are the
assertion mechanism and are exempt. Evidence:
[../references/errors-config-logging.md](../references/errors-config-logging.md).

## `json.loads` returns `Any` — and `Any` is contagious

**Applies when** ingesting external data. The `Any` result of
`json.loads` (or any untyped def) flows through assignments and calls
without a single checker complaint, unchecking everything downstream.
Give every ingesting function an explicit validated result type and parse
at the boundary; never `cast` the payload into shape. Evidence:
[../references/type-design.md](../references/type-design.md) (trust
boundaries).

## An unchained `raise` inside `except` hides the real cause

**Applies when** converting a caught error into a typed one. `raise
NewError(...)` inside an `except` block attaches the original only as
implicit context ("During handling of the above exception...") — ambiguous
and easily lost in reports. Always `raise NewError(...) from err`; re-raise
the same error with bare `raise`, not `raise err` (which restarts the
traceback). Evidence:
[../references/errors-config-logging.md](../references/errors-config-logging.md).

## `TypedDict` is a plain dict at runtime

**Applies when** relying on a `TypedDict` for shape guarantees.
`isinstance` cannot check it, extra keys pass the checker unseen at
untyped call sites, and nothing validates at runtime — a passing type
check is not proof of shape. Validate where the shape matters; reserve
`TypedDict` for closed key sets on checked paths. Evidence:
[../references/type-design.md](../references/type-design.md) (runtime
consequences).
