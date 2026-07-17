# Typing and style

Strict typing is the contract; the style rules below are what the type
checker and formatter will not write for you. Everything here applies to any
Python codebase — no framework or architecture is assumed.

## Type checker — strict by construction

Run a static type checker in strict mode over all shipped code and keep it
strict:

- **mypy**: `strict = true` — which implies `disallow_untyped_defs`,
  `disallow_any_generics`, `no_implicit_optional`, `warn_return_any`,
  `warn_unused_ignores`, `strict_equality`, and friends;
- **pyright**: `typeCheckingMode = "strict"`;
- never weaken the configuration (per-module escapes, global
  `ignore_errors`, downgraded severities) to make a run pass — fix the code.

Target a modern Python (≥ 3.12) so `match`, `typing.assert_never`,
`Self`, PEP 604 unions (`X | None`), PEP 695 generics and the `type`
statement are available; which further features each of 3.13/3.14 unlocks
(TypeIs, ReadOnly, native lazy annotations, t-strings) is version-gated in
[modern-python.md](modern-python.md). An un-annotated function is
unchecked territory — the strict flags above ban it; annotate every public
function fully, including `-> None`.

## Style the checker cannot enforce

- **Member ordering:** class attributes → `__init__` → `classmethod`
  factories → properties → methods. One class per concept; no grab-bag
  modules.
- **Full annotations on the public surface.** Inside a function body let
  inference work: do not annotate what the checker already knows
  (`count: int = 0` is noise). Annotate a local only to pin a wider type
  deliberately (e.g. `items: list[int | None] = []`).
- **Parameter defaults live in the signature** (`def f(limit: int = 10)`),
  never as `if limit is None: limit = 10` re-binding in the body — except
  for mutable defaults, where the `None`-sentinel idiom is mandatory
  (see [lint-clean.md](lint-clean.md): mutable default arguments are
  banned).
- **Visibility is explicit by convention:** a leading underscore marks
  module- and class-private names; everything exported is deliberate —
  keep `__all__` in modules that form a package's public API.
- **Overrides are marked** with `@typing.override` (3.12+) so a renamed or
  removed base method breaks at the definition instead of silently forking
  behaviour; public API being retired is marked with
  `@warnings.deprecated` (3.13+) so checkers flag the call sites.
- **Type aliases use the `type` statement** (`type UserMap = dict[UserId,
  User]`), not bare assignment or the deprecated `typing.TypeAlias`.
- In `except` the binding is the narrowest exception type; never a bare
  `except:` — see
  [errors-config-logging.md](errors-config-logging.md).
- Do not silence the type checker or linter (`# type: ignore`, blanket
  `# noqa`, `# pylint: disable`, `# mypy: ignore-errors`) to pass a gate;
  fix the cause. The one sanctioned exception: a documented upstream
  limitation of a single lint rule may be held by a line-scoped
  `# noqa: <RULE> -- <written reason>` naming exactly one rule code —
  never file-wide, never multi-rule, never without the justification.
  Type-level suppressions (`# type: ignore`, `# mypy: ignore-errors`) have
  no such exception in shipped code; their one sanctioned home is negative
  type-level tests — see [testing.md](testing.md). Format with a single
  formatter (Black or the Ruff formatter) and do not fight it with a second
  one.

## Zero magic — constants and closed sets

- Strings and numbers with meaning (other than `0`/`1`/`-1`/`2`) are named
  constants, `Final`, grouped near the code that owns them — never
  scattered literals:

  ```python
  MAX_RETRIES: Final = 3
  DEFAULT_PAGE_SIZE: Final = 50
  ```

- A closed set is an **enum or a `Literal` union** — never loose strings
  compared by value across the codebase:

  ```python
  class UserStatus(enum.StrEnum):
      ACTIVE = "active"
      BLOCKED = "blocked"
  ```

  or, for lightweight boundary shapes:

  ```python
  UserStatus = Literal["active", "blocked"]
  ```

  Both give the checker a finite domain to exhaust in `match` (close it
  with `assert_never` — see [type-design.md](type-design.md)).

- Tunable thresholds (limits, windows, sizes) belong in configuration, not
  baked into code as literals.

## Identifiers

- **Branded identifiers.** No id is a raw `str`: declare a `NewType` and
  apply its constructor exactly where untyped input enters the program —
  the constructor *is* the coercer, and a plain `str` no longer type-checks
  where the id is expected:

  ```python
  UserId = NewType("UserId", str)

  def parse_user_id(raw: str) -> UserId:
      if not _USER_ID_RE.fullmatch(raw):
          raise InvalidUserIdError(raw)
      return UserId(raw)
  ```

- Identifiers and code are written in English; a name says what the value
  is, not how it is produced. Use the domain's established vocabulary —
  never vacuous names (`data`, `info`, `item`) — and encode units in the
  name when the type cannot (`timeout_s`, `temperature_c`). Express "does
  not mutate" as a read-only parameter type (`Sequence`, `Mapping`), never
  as a comment.
- Naming shape: `snake_case` functions, methods, variables, and parameters;
  `PascalCase` classes, enums, `NewType`s, and type aliases; `UPPER_CASE`
  module constants and enum members — PEP 8, applied without exceptions.

## Self-check

The checker `scripts/check_py_conventions.py` flags the mechanical violations
of this file (`Any`, suppression comments, `print`, raw env reads) and of
the other references. It is a backstop, not the source of truth; the type
checker in strict mode is. See
[../data/fixtures/clean_sample.py](../data/fixtures/clean_sample.py) for a
file that satisfies every rule here.
