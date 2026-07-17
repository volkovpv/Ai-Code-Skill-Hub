---
name: python-coding
description: Universal coding standard and workflow for production Python, free of framework, architecture, or library assumptions. Strict typing (mypy/pyright strict, no Any, no cast escapes), closed sets as enums or Literal unions with match closed by assert_never, NewType-branded ids, frozen dataclasses and read-only parameters, explicit boolean expressions and None-checks over or-defaults, narrow except with `raise ... from` once at the source, no un-awaited coroutines and gather for independent awaits, centralized os.environ access, no print in shipped code, no type/lint suppressions, named constants over magic literals, docstrings that describe intent, test-in-the-same-change discipline. Use whenever writing, reviewing, or refactoring Python (.py) — app code, libraries, scripts, or tests. Combine with the hexagonal-service skill for ports-and-adapters layering.
---

# Python coding (universal)

Write strictly-typed, test-covered Python. This skill is **universal by
contract**: every rule here holds in any Python codebase — it assumes no
framework, no architectural style, no DI container, no specific libraries.
Architecture-bound rules live in the `hexagonal-service` skill; when the
host project uses it, apply that skill on top of this one.

## Workflow

1. **Type strictly, name explicitly.** Apply the type-checker configuration
   and style rules in
   [references/typing-and-style.md](references/typing-and-style.md): full
   annotations on the public surface, closed sets as enums or `Literal`
   unions (never loose strings), `NewType`-branded ids, `Final` constants,
   frozen dataclasses, a single formatter.
2. **Design the types before the code.** Model variant state as a tagged
   union of frozen dataclasses so invalid combinations cannot type-check,
   close every `match` over a union with `assert_never`, keep inputs wide
   (`Sequence`, `Mapping`, `Iterable`, protocols) and outputs narrow,
   validate boundary data instead of casting it — see
   [references/type-design.md](references/type-design.md). Reach for a
   `TypeVar` only when it relates two types, and derive related types from
   one source of truth — see
   [references/generics-and-protocols.md](references/generics-and-protocols.md).
3. **Handle errors and the environment deliberately.** Catch the narrowest
   exception type, never swallow an error, wrap with `raise ... from` at
   most once at the source, centralize `os.environ` access — see
   [references/errors-config-logging.md](references/errors-config-logging.md).
4. **Write it lint-clean the first time.** A strict lint stack (a strict
   type checker plus a broad Ruff-style rule set) rejects far more than the
   runtime and counts warnings too — explicit boolean expressions, no
   `or`-defaults, no un-awaited coroutines, no mutation of parameters, no
   mutable default arguments, named literals, small shallow functions,
   docstrings on the public surface. Follow
   [references/lint-clean.md](references/lint-clean.md) so the project's
   `lint` / `typecheck` come back with zero errors and zero warnings.
5. **Test in the same change.** A code change without its tests is
   incomplete; every bug fix ships a regression test that fails before the
   fix. See [references/testing.md](references/testing.md).
6. **Self-check before handing off.** Run the convention checker over the
   files you touched:

   ```bash
   python scripts/check_py_conventions.py path/to/changed.py
   ```

   It is a heuristic backstop — read every finding in context, then run the
   project's real `lint` / `typecheck` / `test`, which are authoritative.
   A checked false positive may be suppressed only per rule code and only
   with a written reason:

   ```python
   raw = os.environ.get("CI")  # skill-check-ignore: PY-ENV -- CI detection in a build script
   ```

   A bare `skill-check-ignore`, an unknown code, or an empty justification
   aborts the check (exit 2); `PY-SUPPRESS` can never be suppressed.

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Choosing types, checker configuration, constants, or style | [references/typing-and-style.md](references/typing-and-style.md) |
| Modeling states, tagged unions, narrowing, boundary validation, exhaustive `match` | [references/type-design.md](references/type-design.md) |
| Writing a generic or protocol, typing decorators/wrappers, deriving types from a source of truth | [references/generics-and-protocols.md](references/generics-and-protocols.md) |
| Making code pass a strict linter with zero warnings (booleans, async, immutability, complexity, docstrings) | [references/lint-clean.md](references/lint-clean.md) |
| Exceptions, `except` blocks, env access, logging hygiene | [references/errors-config-logging.md](references/errors-config-logging.md) |
| Writing or reviewing tests | [references/testing.md](references/testing.md) |
| Applying a verified pattern | [knowledge/patterns.md](knowledge/patterns.md) |
| A checker finding looks wrong, or a typing/runtime edge case bites | [knowledge/pitfalls.md](knowledge/pitfalls.md) |
| A calibrated input/output pair for the checker | [data/README.md](data/README.md) |
| Diagnosing a known limitation of this skill | [observations/INDEX.md](observations/INDEX.md) |

Observations are evidence, not rules: never follow one as policy unless it
has been promoted into `knowledge/` or this workflow.

## Rules

- The type checker runs in **strict mode** (mypy `--strict` or pyright
  `strict`) over shipped code; never weaken the checker configuration to
  make a run pass. Every public function is fully annotated, including
  `-> None`.
- No `Any` in shipped code — explicit or smuggled through untyped defs;
  type the value or take `object` and narrow. `cast()` is an unchecked
  claim the checker takes on faith — never use it on boundary data, and
  elsewhere only with a comment proving the invariant.
- Model closed sets as an `enum.Enum`/`StrEnum` or a `Literal` union —
  never loose strings compared by value across the codebase. No raw string
  ids — use `NewType` with the constructor applied exactly where untyped
  input enters.
- Model variant state as a tagged union (frozen dataclasses with a
  `Literal` discriminant, or one class per variant) so invalid combinations
  cannot be represented; close every `match` over a union with
  `typing.assert_never`; no in-domain sentinel values (`-1`, `''`) for
  "absent" — see [references/type-design.md](references/type-design.md).
- Data crossing a runtime boundary (network, file, JSON, queue) is untyped
  until validated; keep one source of truth per boundary shape (schema ↔
  type), never a hand-maintained pair. Parse, don't `cast`.
- A `TypeVar` must relate two types or it does not exist (no return-only
  type variables); prefer `Protocol`s as structural seams; derive related
  types from one source of truth — see
  [references/generics-and-protocols.md](references/generics-and-protocols.md).
- Immutable by default: `@dataclass(frozen=True, slots=True)` for data,
  `Final` for constants, `Sequence`/`Mapping`/`AbstractSet` (not
  `list`/`dict`/`set`) for parameters the function only reads; never mutate
  an argument; never a mutable default argument.
- Catch the **narrowest** exception type; a bare `except:` is banned and
  `except Exception` belongs only at a top-level boundary that logs the
  full chain. Never swallow an error; when wrapping, preserve the original
  via `raise NewError(...) from err` and wrap at most once at the source.
- Explicit boolean expressions: `is not None` for optionals, `!= ""` /
  `> 0` for strings and numbers, an explicit emptiness check
  (`len(x) > 0`) where a collection's size is the point; truthiness only on
  actual `bool` values. Defaults with `x if x is not None else fallback`,
  never `x or fallback` — `or` also swallows `""`, `0`, `False`.
- Async discipline: every coroutine is awaited or handed to a task the code
  keeps and supervises — fire-and-forget is a defect; independent awaits
  run concurrently (`asyncio.gather` / a task group), not sequentially in a
  loop.
- Centralize `os.environ` reads in the project's configuration code; never
  hardcode a secret or log one.
- No `print()` in shipped code — use whatever logging seam the project
  provides. No `assert` for runtime validation in shipped code (stripped
  under `-O`); raise a typed error. No `breakpoint()`/`pdb.set_trace()`
  left behind.
- Write to a strict lint stack by default so `lint` returns zero errors
  **and zero warnings**: named literals over magic values, f-strings over
  concatenation, early returns over `else` towers, small shallow functions,
  import groups ordered stdlib → third-party → local, docstrings with a
  prose description on the exported surface — see
  [references/lint-clean.md](references/lint-clean.md).
- A code change without its tests is incomplete; do not suppress the type
  checker or linter (`# type: ignore`, blanket `# noqa`,
  `# pylint: disable`) to go green. Sole exception: a documented upstream
  limitation of a single lint rule, held by a justified line-scoped
  `# noqa: <RULE> -- <reason>` naming exactly one rule — see
  [references/typing-and-style.md](references/typing-and-style.md).
- Keep this skill universal: framework, architecture, and project-specific
  choices belong to the host project or to the dedicated skills
  (`hexagonal-service`) — never here. Project instructions always take
  precedence over this skill.
