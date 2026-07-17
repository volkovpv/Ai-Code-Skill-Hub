# Type design

Rules for shaping the types themselves, so that wrong code fails the type
checker instead of failing at runtime — invalid states unrepresentable,
tagged unions, exhaustiveness, parse-don't-cast. Everything here is
framework- and architecture-neutral.

## Contents

- [Make invalid states unrepresentable](#make-invalid-states-unrepresentable)
- [Tagged unions are the default state model](#tagged-unions-are-the-default-state-model)
- [Exhaustiveness: close every match with assert_never](#exhaustiveness-close-every-match-with-assert_never)
- [Wide inputs, narrow outputs](#wide-inputs-narrow-outputs)
- [Nullability at the perimeter](#nullability-at-the-perimeter)
- [Narrowing: isinstance, TypeGuard, and friends](#narrowing-isinstance-typeguard-and-friends)
- [Trust boundaries: parse, don't cast](#trust-boundaries-parse-dont-cast)
- [Runtime consequences of Python typing](#runtime-consequences-of-python-typing)

## Make invalid states unrepresentable

- Model state as a union of the states that can actually occur, never as
  one bag of independently-settable flags:

  ```python
  @dataclass(frozen=True, slots=True)
  class Pending:
      pass

  @dataclass(frozen=True, slots=True)
  class Failed:
      error: Exception

  @dataclass(frozen=True, slots=True)
  class Succeeded:
      data: ResponseBody

  RequestState = Pending | Failed | Succeeded
  ```

  An `is_loading` + optional `error` + optional `data` bag forces every
  consumer to invent behaviour for impossible combinations (loading **and**
  error?).
- If two attributes vary together, define one class per variant and union
  the classes; never make the attributes independently optional — the
  independent form admits mismatched combinations and defeats narrowing.
- Never encode a special case as an in-domain sentinel (`-1`, `0`, `''`).
  Use `T | None` or a tagged union; wrap sentinel-returning APIs
  (e.g. `str.find` returning `-1`) at the boundary. A sentinel is
  assignable wherever the normal value is, so the checker cannot force
  callers to handle it.
- Think twice before making an attribute optional: each `| None` is a place
  the checker can no longer catch a forgotten value, and N optionals are
  2^N combinations. For evolving inputs keep two types — the input shape
  with the optional field and an internal type where it is required — and
  normalize once at the boundary, centralizing the default.

## Tagged unions are the default state model

- Prefer **one frozen dataclass per variant, unioned** (above): the class
  itself is the tag and `match`/`isinstance` narrow on it directly. When
  variants must share a wire shape (e.g. TypedDicts for JSON), give every
  member a `Literal` discriminant field and narrow on it:

  ```python
  class Circle(TypedDict):
      kind: Literal["circle"]
      radius: float

  class Square(TypedDict):
      kind: Literal["square"]
      side: float

  Shape = Circle | Square
  ```

- Narrow with `match` on the class or the discriminant — not with
  attribute-presence probes (`hasattr(shape, "radius")`), which silently
  break when variants structurally overlap or a new variant subsumes an
  old one.
- Constrain free-form `str` / `int` fields to an enum or `Literal` union
  whenever the value set is closed — this is the type-level counterpart of
  the constants-registry rule in
  [typing-and-style.md](typing-and-style.md).

## Exhaustiveness: close every match with assert_never

- End every `match` over a union with a `case _` that passes the narrowed
  value to `typing.assert_never`, and keep it even while unreachable:

  ```python
  match state:
      case Pending():
          ...
      case Failed(error=error):
          ...
      case Succeeded(data=data):
          ...
      case _:
          assert_never(state)
  ```

  Adding a union member then breaks the type check at every unhandled
  `match`, and unsound values arriving from untyped callers still fail
  loudly at runtime.
- `if`/`elif` chains over a union get the same treatment
  (`assert_never(value)` in the final `else`).
- Any function that returns from multiple branches gets an explicit return
  type, so a missed branch fails at the definition, not at distant call
  sites.

## Wide inputs, narrow outputs

- Be liberal in parameter types, strict in return types. Optional
  parameters and unions belong in signatures; always return a
  fully-populated canonical type.
- Declare parameters as the **abstract read-only** collection the function
  actually uses, and return the concrete type: take `Sequence[T]` /
  `Mapping[K, V]` / `AbstractSet[T]` / `Iterable[T]`, return `list[T]` /
  `dict[K, V]` / `tuple[T, ...]`. A `list` parameter both over-demands
  (callers with a tuple must copy) and advertises mutation.
- A function that needs two members of a large dependency takes a
  `Protocol` with those two members — production objects satisfy it
  structurally, and tests pass a plain stub instead of a mock library (see
  [generics-and-protocols.md](generics-and-protocols.md)).
- A function that only iterates takes `Iterable[T]`; if it also needs
  `len()` or indexing, `Sequence[T]`.
- Do not declare adjacent parameters of the same type
  (`def move(x: int, y: int, w: int, h: int)`) — the checker cannot catch
  swapped arguments; make them keyword-only (`*,`) or group them into a
  small frozen dataclass. Exception: genuinely commutative or
  conventionally-ordered pairs.

## Nullability at the perimeter

- Never bake `| None` into a type alias
  (`type User = ... | None`); write the union at the point of use so
  nullability stays visible.
- Values that are null together live in one object that is entirely `None`
  or entirely populated — not in parallel, independently-nullable variables
  the checker cannot correlate.
- Prefer fully non-`None` attributes via a `@classmethod` (or
  `async` factory function) that gathers everything and then constructs,
  over `None`-initialized attributes mutated by an `init()` method — and
  never start async work in `__init__`.

## Narrowing: isinstance, TypeGuard, and friends

- The built-in narrowing tools come first: `isinstance`, `match`,
  `is None` checks, early `return`/`raise`. Restructure code so control
  flow proves the type instead of asserting it: fetch once and test the
  result (`value = mapping.get(key)` then `if value is not None`).
- Extract reusable narrowing into `TypeIs`/`TypeGuard` predicates
  (`def is_shape(v: object) -> TypeIs[Shape]`). Both are **unchecked
  claims**: the checker never verifies that the body establishes the
  predicate (`return True` type-checks). Keep guard bodies minimal and
  exhaustive over the claimed type, keep them next to the type they guard,
  and unit-test them with near-miss values — a wrong guard poisons every
  downstream branch.
- Narrowing traps: a truthiness check (`if x:`) does not distinguish `''`
  and `0` from `None` — narrow optionals with `is not None`; narrowing on
  an attribute (`if obj.field is not None`) does not survive into a nested
  function and may be invalidated by any intervening call — capture the
  attribute into a local first.

## Trust boundaries: parse, don't cast

- A type annotation on unvalidated external data is an unchecked claim:
  `payload: ApiResponse = json.loads(raw)` verifies nothing —
  `json.loads` returns `Any`, which silently poisons everything downstream.
  Treat everything crossing a runtime boundary (network, file, JSON, env,
  queue) as untyped until validated, and give every ingesting function an
  explicit, validated result type so the `Any` cannot leak into the call
  graph.
- `cast()` and `# type: ignore` are never boundary tools: they claim,
  validation proves. Use whatever schema seam the host project provides
  (dataclass-based validators, `pydantic`-style models, generated types) —
  the skill mandates the discipline, not the library.
- Keep **one source of truth** per boundary shape: either a runtime schema
  from which the static type is derived, or an external spec
  (OpenAPI / JSON Schema) with generated types. Never hand-maintain a type
  and a validator in parallel — they drift, and validation then proves the
  wrong shape.
- Never write types for external data from the examples you happened to
  see; import or generate them from the official spec so edge cases and
  nullability are captured. Prefer an honest, imprecise type over a
  precise-looking one that rejects valid data.

## Runtime consequences of Python typing

- **Annotations are not enforcement.** Nothing at runtime stops a caller
  outside the checked codebase from passing the wrong type; where a
  type-level restriction guards real damage (data corruption, security),
  enforce it at runtime too and test that enforcement — see
  [testing.md](testing.md).
- **TypedDict is structural and erased**: at runtime it is a plain `dict`,
  `isinstance` cannot check it, and extra keys may be present — validate
  where extra fields matter; never treat a passing type check as proof of
  shape.
- Collections with dynamic, data-driven string keys are `dict[str, V]` with
  absence in mind (`.get`, `KeyError` handling); reserve `TypedDict` for
  closed key sets. With strict checking, indexing a `dict` raises on
  absence — handle it or use `.get` with an explicit `None` branch, never
  a blind `[]` plus a comment.
- Name-mangled `__private` attributes and underscore conventions are
  advisory, not security: anything is reachable via introspection, and
  `dataclasses.asdict`/`repr` can leak fields. Where secrecy is a runtime
  requirement, keep the secret out of the object's `repr` (e.g.
  `field(repr=False)`) and out of logs — see
  [errors-config-logging.md](errors-config-logging.md).
- Stateless utilities live in modules — plain functions and constants —
  never in classes with only `@staticmethod`s; a class is for state and
  polymorphism, a module already is a namespace.
