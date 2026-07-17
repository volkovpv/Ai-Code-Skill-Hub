# Generics and protocols

Discipline for writing generic code and structural interfaces: when a type
variable earns its place (the golden rule, no return-only generics), how
protocols replace inheritance and mocks, how to keep related types in one
source of truth, and where to stop. Framework- and architecture-neutral.

## Contents

- [When a TypeVar earns its place](#when-a-typevar-earns-its-place)
- [Bounds, constraints, naming](#bounds-constraints-naming)
- [Protocols: structural seams](#protocols-structural-seams)
- [Overloads vs unions](#overloads-vs-unions)
- [Decorators and wrappers: ParamSpec](#decorators-and-wrappers-paramspec)
- [DRY at the type level](#dry-at-the-type-level)
- [Keep types simple; test the complex ones](#keep-types-simple-test-the-complex-ones)

## When a TypeVar earns its place

- **Golden rule: a type variable must appear at least twice** in the
  signature — it exists to *relate* types: a parameter to the return type,
  two parameters to each other. If it appears once, delete it: use the
  bound directly (`def close(resource: SupportsClose)`), or `object`.
- **Never write a return-only generic** (`def parse[T](raw: str) -> T`) —
  it is a hidden `cast` the caller controls. Return the validated concrete
  type, or `object` plus an explicit, greppable narrowing at the call
  site.
- A parameter that selects a key relates naturally:

  ```python
  def pluck[T, K](records: Sequence[Mapping[K, T]], key: K) -> list[T]:
      return [record[key] for record in records]
  ```

- In a generic function returning `T`, transform the *input* value — never
  fabricate a fresh object and `cast` it to `T`: the caller may
  instantiate `T` with a subtype your object is not.
- Use PEP 695 syntax (`def f[T](...)`, `class Box[T]: ...`) where the
  project's toolchain supports it; otherwise module-level `TypeVar`s. The
  discipline is identical either way.

## Bounds, constraints, naming

- Bound every type variable to its valid domain
  (`[T: Comparable]`, `TypeVar("T", bound=Comparable)`); an unbounded
  variable admits invalid instantiations that surface as wrong types
  downstream instead of errors at the use site.
- Name type variables like parameters: single letters (`T`, `K`, `V`) only
  in tiny scopes; descriptive PascalCase names where there are several or
  the scope is broad.
- Declare type variables at the narrowest scope — on the method, not the
  class, when only the method needs them.
- A generic class whose parameter cannot be inferred from constructor
  arguments must be instantiated with an explicit parameter
  (`Collection[Order]()`), never left to fall back to an implicit `Any`.

## Protocols: structural seams

- A dependency contract is a **`Protocol`**, not an ABC the implementation
  must inherit: production objects satisfy it structurally, and tests pass
  a plain stub object — no mock library, no patching (the Python form of
  the "narrow structural interface as the test seam" pattern).

  ```python
  class UserSource(Protocol):
      def find_by_id(self, user_id: UserId) -> User | None: ...
  ```

- Keep protocols **minimal**: declare only the members the consumer
  actually uses, next to the consumer — not a god-interface next to the
  implementation.
- Add `@runtime_checkable` only when an `isinstance` check is genuinely
  needed; remember it checks member *presence*, not signatures.
- Inheritance is for shared implementation and closed hierarchies;
  protocols are for contracts across a boundary. When in doubt at a seam,
  protocol.

## Overloads vs unions

- When the return type is a *function of the argument type*, use
  `@overload` stacks with a single broad implementation behind them:

  ```python
  @overload
  def double(x: str) -> str: ...
  @overload
  def double(x: int) -> int: ...
  def double(x: str | int) -> str | int:
      return x + x if isinstance(x, str) else x * 2
  ```

  The precise public signatures confine the unchecked spot to one declared
  seam.
- Do not overload what a union return expresses honestly; reach for
  overloads only when callers would otherwise be forced to narrow a return
  value they can already prove.
- Overloads are matched declaration-by-declaration: order them from most
  to least specific, and keep the implementation signature wide enough to
  cover them all.

## Decorators and wrappers: ParamSpec

- A wrapper that forwards an argument list is typed with `ParamSpec` —
  never `(*args: Any, **kwargs: Any)`, which unchecks every call through
  the wrapper:

  ```python
  def timed[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
      @functools.wraps(fn)
      def inner(*args: P.args, **kwargs: P.kwargs) -> R:
          ...
      return inner
  ```

- A wrapper that prepends or appends parameters uses `Concatenate`.
- Always `functools.wraps` the inner function so the runtime identity
  (name, docstring, signature) survives with the types.

## DRY at the type level

- Never write two declarations that must stay in sync by hand — derive one
  from the other: an enum is the single source for its value set (iterate
  `UserStatus` instead of re-listing strings); `typing.get_args` recovers
  a `Literal` union's members for runtime validation so the union and the
  validator cannot drift.
- When parallel *data* must cover every member of a closed set (handlers,
  serializers, per-variant config), key the mapping by the enum and make
  the completeness check explicit and testable:

  ```python
  HANDLERS: Final[Mapping[UserStatus, Handler]] = {...}

  def test_handlers_cover_every_status() -> None:
      assert set(HANDLERS) == set(UserStatus)
  ```

- Several functions sharing a signature get one named alias
  (`type BinaryOp = Callable[[int, int], int]`); a wrapper matching an
  existing function reuses its `ParamSpec` typing (above), never a copied
  signature.
- Do not unify types whose fields are only coincidentally identical, and
  prefer eliminating near-duplicate types over maintaining converters
  between them.

## Keep types simple; test the complex ones

- Escalate deliberately — plain classes → `Literal`/enum unions →
  generics/protocols → overload stacks — and stop at the first level that
  eliminates the error class you care about. Prefer inference-friendly
  signatures over machinery that needs `cast` internally.
- Nontrivial typed utilities get **type-level tests** pinned next to them:
  positive cases via `assert_type`, negative cases via a narrowly-scoped
  suppression that the checker verifies is used (mypy
  `warn_unused_ignores` / pyright `reportUnnecessaryTypeIgnoreComment`
  turn an obsolete ignore into an error) — see
  [testing.md](testing.md).
- If a typed construct needs a page of overloads or defeats inference at
  every call site, it is broken even if it checks — restructure it or
  abandon the type-level approach.
