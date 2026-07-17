# Type design

Rules for shaping the types themselves, so that wrong code fails to compile
instead of failing at runtime. Everything here is framework- and
architecture-neutral. Derived from *Effective TypeScript* (2nd ed., Vanderkam)
and *TypeScript Cookbook* (Baumgartner); item/recipe numbers cite the source.

## Contents

- [Make invalid states unrepresentable](#make-invalid-states-unrepresentable)
- [Discriminated unions are the default state model](#discriminated-unions-are-the-default-state-model)
- [Exhaustiveness: close every switch with never](#exhaustiveness-close-every-switch-with-never)
- [Wide inputs, narrow outputs](#wide-inputs-narrow-outputs)
- [Nullability at the perimeter](#nullability-at-the-perimeter)
- [Pin values without widening: annotation, as const, satisfies](#pin-values-without-widening-annotation-as-const-satisfies)
- [Narrowing: guards and assertion functions](#narrowing-guards-and-assertion-functions)
- [Trust boundaries: parse, don't assert](#trust-boundaries-parse-dont-assert)
- [Structural typing consequences](#structural-typing-consequences)

## Make invalid states unrepresentable

- Model state as a union of the states that can actually occur, never as one
  bag of independently-settable flags (ET 29):

  ```ts
  type RequestState =
    | { readonly status: 'pending' }
    | { readonly status: 'error'; readonly error: Error }
    | { readonly status: 'ok'; readonly data: ResponseBody };
  ```

  A `{ isLoading; error?; data? }` bag forces every consumer to invent
  behaviour for impossible combinations (loading **and** error?).
- If two properties vary together, define one interface per variant and union
  the interfaces; never union the property types independently (ET 34) — the
  independent form admits mismatched combinations and defeats narrowing.
- Never encode a special case as an in-domain sentinel (`-1`, `0`, `''`)
  (ET 36). Use `T | null` or a tagged union; wrap sentinel-returning APIs
  (e.g. `indexOf`) at the boundary. A sentinel is assignable wherever the
  normal value is, so the checker cannot force callers to handle it.
- `A | B` is inclusive — when "both" is invalid and a discriminant is
  impossible (a fixed external shape), forbid the foreign properties with
  optional `never` (ET 63; TC 3.8):

  ```ts
  type SingleSelect = SelectBase & { readonly value: string; readonly values?: never };
  type MultiSelect  = SelectBase & { readonly value?: never; readonly values: readonly string[] };
  ```

  The same trick blocks a specific field in a partial update:
  `Partial<Omit<User, 'id'>> & { id?: never }` (ET 77).
- Think twice before making a property optional (ET 37): each `?` is a place
  the checker can no longer catch a forgotten value, and N optionals are 2^N
  combinations. For evolving inputs keep two types — the input type with the
  optional field and an internal type where it is required — and normalize
  once at the boundary, centralizing the default.

## Discriminated unions are the default state model

- Give every union member a literal discriminant (`kind: 'circle'`) and
  narrow with `switch (x.kind)` — not with property-presence (`'r' in shape`)
  checks, which silently break when members structurally overlap or a new
  member subsumes an old one (TC 3.1–3.2).
- Types are erased at runtime: never branch on an interface name or expect
  `instanceof` to work for one (ET 3). The discriminant *is* the runtime
  representation of the type.
- Constrain free-form `string` / `number` fields to literal unions whenever
  the value set is closed (TC 12.2) — this is the type-level counterpart of
  the `as const` registry rule.

## Exhaustiveness: close every switch with never

- End every `switch` over a union with a `default` that passes the narrowed
  value to a `never`-typed helper, and keep it even while unreachable
  (TC 3.3; ET 59):

  ```ts
  function assertUnreachable(value: never): never {
    throw new Error(`Unhandled case: ${String(value)}`);
  }
  // default: return assertUnreachable(state);
  ```

  Adding a union member then breaks compilation at every unhandled switch,
  and unsound values arriving from untyped callers still fail loudly.
- `if`-chains over a union get the same treatment (`value satisfies never` or
  the helper in the final `else`) — lint exhaustiveness rules cover only
  `switch` (ET 59).
- Any function that returns from multiple branches gets an explicit return
  type, so a missed branch fails at the definition, not at distant call
  sites (ET 59).

## Wide inputs, narrow outputs

- Be liberal in parameter types, strict in return types (ET 30). Optional
  properties and unions belong in parameters; always return a fully-populated
  canonical type. When the shapes are related, define the canonical type plus
  a looser `...Options`/`...Like` parameter variant derived from it.
- Declare the parameter as the narrowest structural shape the function
  actually uses, not the concrete caller type (ET 4; TC 2.1). A function that
  needs two members of a large dependency takes an interface with those two
  members — production objects satisfy it structurally, and tests pass a
  plain object literal instead of a mock.
- A function that only iterates an array parameter takes `Iterable<T>`;
  otherwise `readonly T[]` (ET 30).
- Do not declare adjacent parameters of the same type (`(x: number,
  y: number, w: number, h: number)`) — the checker cannot catch swapped
  arguments; group them into small named types or an options object (ET 38).
  Exception: genuinely commutative or conventionally-ordered pairs.
- Callbacks whose result the caller ignores are declared `() => void` —
  substitutability then accepts any function; never read the result of a
  `void`-typed callback (TC 3.6).

## Nullability at the perimeter

- Never bake `| null` into a type alias (`type User = {...} | null`); write
  the union at the point of use so nullability stays visible (ET 32).
- Values that are null together live in one object that is entirely null or
  entirely populated — not in parallel, independently-nullable variables the
  checker cannot correlate (ET 33).
- Prefer fully non-null class fields via a `static async create(...)` factory
  that awaits everything and then constructs, over nullable fields mutated by
  an `init` method — and never start async work in a constructor or silence
  `strictPropertyInitialization` with `!` (ET 33; TC 11.7).

## Pin values without widening: annotation, as const, satisfies

Three checked ways to type a literal — an `as T` assertion on a literal is
never one of them (it skips checking; see typing-and-style.md):

- **Annotation** (`const c: Circle = {...}`) — checks conformance and enables
  excess-property checking, but *widens*: the variable's type becomes the
  annotation, losing literal keys and values.
- **`as const`** — pins exact literal types, makes the value deeply readonly;
  conformance mistakes surface only at use sites.
- **`satisfies T`** — checks conformance early *and* keeps the precise
  inferred type (ET 20; TC 12.3). Use it for registries and config maps where
  callers need the exact keys:

  ```ts
  const ROUTES = {
    home: '/',
    profile: '/users/:userId',
  } as const satisfies Record<string, `/${string}`>;
  // keyof typeof ROUTES stays 'home' | 'profile'
  ```

- Object-literal properties widen (`kind: 'circle'` infers `string`), which
  breaks assignment to a discriminated union — fix with an annotation or
  `as const`, never with a whole-object assertion (TC 3.4).
- Build objects in a single expression with all properties; add conditional
  members with spread (`{ ...base, ...(cond ? { extra } : {}) }`). Never
  build via `{} as T` plus piecemeal assignment — missing properties compile
  silently and drift when the type gains members (ET 21; TC 3.9).

## Narrowing: guards and assertion functions

- Extract reusable narrowing into user-defined type guards
  (`function isFoo(v: unknown): v is Foo`) and, for throw-on-failure
  validation, assertion functions
  (`function assertFoo(v: unknown): asserts v is Foo`) — control flow after
  the call sees the narrowed type without `if`-nesting (TC 3.5, 4.6, 9.3).
- Both are **unchecked claims**: the compiler never verifies that the body
  actually establishes the predicate (`return true` type-checks). Keep guard
  bodies minimal and exhaustive over the claimed type, keep them next to the
  type they guard, and unit-test them with near-miss values (ET 22, 46;
  TC 3.5). A wrong guard poisons every downstream branch — worse than no
  guard.
- Restructure code so control-flow analysis can follow instead of asserting:
  fetch once and test the result (`const v = map.get(k); if (v !== undefined)`),
  narrow with early return/throw, `instanceof`, `Array.isArray`, `in` (ET 22).
- Narrowing traps: `typeof null === 'object'`; a falsy check (`!x`) does not
  exclude `''`/`0` from a string/number union; a refinement on an object
  property does not survive into a callback and may be invalidated by any
  intervening call — capture the property into a `const` first (ET 22, 23, 48).
- Once you alias a property (`const { bbox } = polygon`), do all further
  checks and reads through the alias; mixing alias and property defeats the
  analysis and can diverge after mutation (ET 23).

## Trust boundaries: parse, don't assert

- A type annotation on unvalidated external data is an unchecked claim:
  `const r: ApiResponse = await res.json()` verifies nothing (ET 3; TC 9.2).
  Treat everything crossing a runtime boundary (network, file, JSON, env,
  queue) as `unknown` until validated.
- Keep **one source of truth** for a boundary shape (ET 74; TC 12.5): either
  a runtime schema from which the static type is derived (schema-first, e.g.
  `z.infer`-style), or an external spec (OpenAPI / JSON Schema) with
  generated types. Never hand-maintain a type and a validator in parallel —
  they drift, and validation then proves the wrong shape.
- Give every function that ingests external data an explicit result type so
  a leaked `any` cannot poison the call graph (ET 82); where the platform API
  returns `any` (`JSON.parse`, `res.json()`), a project-local declaration
  override to `unknown` makes the compiler enforce validation project-wide
  (ET 71).
- Never write types for external data from the examples you happened to see;
  import or generate them from the official spec so edge cases and
  nullability are captured (ET 42). Prefer an honest, imprecise type over a
  precise-looking one that rejects valid data (ET 40).

## Structural typing consequences

- Every object type is open: a value may always carry more properties than
  its declared type, and a parameter declared as a class type accepts any
  structurally-matching literal — its constructor may never have run, so
  `instanceof` can be false for a value that type-checked (ET 4; TC 2.9).
- Excess-property checking (typo detection) fires **only** on a fresh object
  literal written directly against a declared type. A literal laundered
  through an untyped variable or an `as` assertion compiles with any extra or
  misspelled key — pass or annotate literals directly, and never treat
  compilation as proof that no extra fields are present; strip or validate at
  runtime where extra fields matter (ET 11; TC 2.1).
- `Object.keys` returns `string[]` by design. To iterate and index a
  parameter object, make the function generic over the concrete subtype and
  use `for-in`, or narrow keys with a guard
  (`const isKey = <T extends object>(o: T, k: PropertyKey): k is keyof T => k in o`).
  Assert `as keyof typeof obj` only on locally-constructed literals whose
  exact keys you control (ET 60; TC 9.1).
- Collections with dynamic, data-driven keys are `Map`/`Set`, not plain
  objects — object keys collide with the prototype chain (`'constructor'`,
  `'__proto__'`) (ET 79). Reserve `Record<K, V>` for closed key sets; if an
  index signature is unavoidable, include absence in the value type
  (`Record<string, V | undefined>`) (TC 3.10).
- TypeScript `private`/`protected` are compile-time only: erased on emit,
  bypassable with a cast, and the fields stay enumerable — a "private" token
  leaks straight through `JSON.stringify`. When privacy must hold at runtime
  (secrets, serialized objects), use ES `#private` fields (TC 11.1; ET 72).
- Stateless utilities live in modules — exported `const`s and functions —
  never in static-only classes or `namespace` blocks (TC 11.5–11.6); the
  linter's `no-extraneous-class` enforces the same.
