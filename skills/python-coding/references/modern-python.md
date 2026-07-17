# Modern Python: what to use at which version

Version-gated adoption guide for Python 3.12 → 3.14. The floor is the
**host project's configured Python version** — never use a feature the
project's runtime does not have, and never keep a legacy form the project's
floor has already obsoleted. When the floor rises, migrate the legacy forms
out instead of mixing styles.

## Contents

- [Baseline (any supported Python ≥ 3.12)](#baseline-any-supported-python--312)
- [3.12: generics syntax and type statements](#312-generics-syntax-and-type-statements)
- [3.13: narrowing, read-only, deprecation](#313-narrowing-read-only-deprecation)
- [3.14: annotations, t-strings, stdlib](#314-annotations-t-strings-stdlib)
- [Banned legacy forms](#banned-legacy-forms)

## Baseline (any supported Python ≥ 3.12)

- `X | None` unions and builtin generics (`list[str]`, `dict[str, int]`);
  the `typing.Optional`/`Union`/`List`/`Dict` spellings are banned.
- `Self` for methods returning their own instance type; `match` with
  `assert_never` exhaustiveness; `ExceptionGroup`/`except*` (3.11);
  `err.add_note()` for attaching context; `asyncio.TaskGroup` and
  `asyncio.timeout` (see [concurrency.md](concurrency.md)).
- `@typing.override` (3.12) on every method that overrides a base-class
  method, so a renamed base method breaks loudly instead of silently
  forking behaviour.
- `datetime.now(timezone.utc)` — `datetime.utcnow()` and
  `utcfromtimestamp()` are deprecated since 3.12 and produce naive
  datetimes; see [runtime-correctness.md](runtime-correctness.md).
- `zoneinfo.ZoneInfo` for timezones (the `pytz` API is obsolete).
- `pathlib.Path` over `os.path` string plumbing for new code.

## 3.12: generics syntax and type statements

- **PEP 695 generics** are the default spelling for new generic code:
  `class Box[T]: ...`, `def first[T](items: Sequence[T]) -> T: ...`, with
  inline bounds `def f[T: Hashable](...)`. Module-level `TypeVar`
  boilerplate remains only where tooling lags — see
  [generics-and-protocols.md](generics-and-protocols.md).
- **`type` statement for aliases**: `type UserMap = dict[UserId, User]` —
  lazily evaluated, forward-reference-friendly. `X: TypeAlias = ...` is
  deprecated (3.12); plain untagged alias assignments are ambiguous to
  readers and checkers.
- `@dataclass(frozen=True, slots=True)` everywhere data is modeled (slots
  became compatible with the common patterns; `kw_only=True` for wide
  constructors).

## 3.13: narrowing, read-only, deprecation

- **`TypeIs` over `TypeGuard`** for ordinary narrowing predicates: `TypeIs`
  narrows in both branches and demands the narrowed type be a subtype of
  the input. Keep `TypeGuard` only for reinterpretation narrowing
  (e.g. `list[object]` → `list[str]`) — see
  [type-design.md](type-design.md).
- **`ReadOnly[...]`** marks TypedDict keys consumers must not mutate
  (checker-only, no runtime effect).
- **`warnings.deprecated`** (`@deprecated("use replace_x")`) on public API
  being retired: checkers flag call sites and the runtime warns.
- TypeVar **defaults** (PEP 696): `class Stack[T = int]: ...` — use when a
  generic has an overwhelmingly common instantiation.
- The **PEP 594 dead batteries are gone** (`cgi`, `telnetlib`, `imghdr`,
  `crypt`, …) — any surviving import of them is dead code walking.

## 3.14: annotations, t-strings, stdlib

- **Annotations are lazy natively** (PEP 649/749): forward references work
  unquoted, so in 3.14-only code do not add
  `from __future__ import annotations` and do not quote type names.
  On a 3.12/3.13 floor keep the future-import uniformly. Two caveats:
  `if TYPE_CHECKING:` imports still work for cycle-breaking, but types
  that dataclass/validator machinery introspects at runtime must stay
  importable at runtime; reflective code reads annotations via
  `annotationlib.get_annotations(obj, format=Format.FORWARDREF)`, never
  raw `__annotations__`.
- **t-strings (PEP 750)**: `t"..."` builds a `string.templatelib.Template`
  keeping static text and interpolations separate — the type-safe seam for
  injection-prone output (SQL, HTML, shell). Use a t-string-aware
  processor where one exists; never write a generic renderer that just
  concatenates the values back (that recreates the injection); f-strings
  remain the default for plain display formatting — see
  [security.md](security.md).
- **`except` tuples stay parenthesized** — `except (A, B):`. 3.14 permits
  the unparenthesized form without `as`, but one consistent shape beats
  two. **Control flow in `finally`** (`return`/`break`/`continue`) is
  banned — it swallows the in-flight exception (SyntaxWarning in 3.14).
- Stdlib upgrades to prefer when available: `uuid.uuid7()` for
  time-sortable ids (`uuid4` for pure randomness); `compression.zstd` for
  new compression needs; `Path.copy()`/`Path.move()` for tree operations;
  tarfile's `filter=` default is finally safe — still pass it explicitly
  (see [security.md](security.md)).
- `zip(..., strict=True)` / `map(..., strict=True)` whenever parallel
  sequences must be equal length — a silent truncation is a data bug.
- The asyncio event-loop **policy system is deprecated**: custom loops are
  wired via `asyncio.run(main(), loop_factory=...)`, and
  `asyncio.get_event_loop()` without a running loop now raises.

## Banned legacy forms

Whatever the floor, these have no place in new code:

| Legacy | Modern |
|--------|--------|
| `typing.Optional[X]`, `Union[X, Y]` | `X \| None`, `X \| Y` |
| `typing.List/Dict/Tuple/Set/Type` | builtin generics |
| `typing.TypeAlias`, `typing.AnyStr`, `typing.ByteString` | `type` statement; `[T: (str, bytes)]`; `bytes \| bytearray \| memoryview` |
| `NamedTuple`/`TypedDict` functional forms | class syntax |
| `datetime.utcnow()`, `utcfromtimestamp()` | `datetime.now(timezone.utc)`, `fromtimestamp(ts, tz=...)` |
| `pytz` | `zoneinfo` |
| `asyncio.get_event_loop()` bootstrapping, `set_event_loop_policy`, `ensure_future`, `loop.run_until_complete` in app code | `asyncio.run`, `TaskGroup`, `loop_factory=` |
| `os.path` string plumbing in new code | `pathlib.Path` |
| `%`-formatting / `.format()` for general strings | f-strings (constant templates stay `%`-style in logging calls; see [errors-config-logging.md](errors-config-logging.md)) |
| Python-2 fossils: `class Foo(object)`, coding cookies, `u''`, `six` | delete on sight |
| PEP 594 removed modules (`cgi`, `telnetlib`, `imghdr`, …) | their documented replacements |
