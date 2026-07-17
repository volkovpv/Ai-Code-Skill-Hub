# Generics and type-level programming

Discipline for writing generic code and derived types: when a type parameter
earns its place, how to keep related types in one source of truth, and where
to stop. Framework- and architecture-neutral. Derived from *Effective
TypeScript* (2nd ed., Vanderkam) and *TypeScript Cookbook* (Baumgartner);
item/recipe numbers cite the source.

## Contents

- [When a generic earns its place](#when-a-generic-earns-its-place)
- [Constraints, defaults, naming](#constraints-defaults-naming)
- [Conditional return types vs overloads](#conditional-return-types-vs-overloads)
- [Tuples and variadic signatures](#tuples-and-variadic-signatures)
- [DRY at the type level](#dry-at-the-type-level)
- [Template literal types](#template-literal-types)
- [Keep types simple; test the complex ones](#keep-types-simple-test-the-complex-ones)

## When a generic earns its place

- **Golden rule: a type parameter must appear at least twice** (its
  declaration aside) — it exists to *relate* types: a parameter to the return
  type, two parameters to each other (ET 51). If it appears once, delete it:
  use `unknown`, or inline the constraint (`key: keyof T` instead of a
  once-used `K extends keyof T`).
- **Never write a return-only generic** (`parse<T>(s: string): T`) — it is a
  hidden type assertion the caller controls. Return `unknown` and force an
  explicit, greppable narrowing at the call site (ET 51; TC 4.3).
- A parameter that names a property is `keyof T`; when the result depends on
  which key was passed, add `K extends keyof T` and return `T[K]` so the
  exact value type flows through (ET 35):

  ```ts
  function pluck<T, K extends keyof T>(records: readonly T[], key: K): T[K][] {
    return records.map((r) => r[key]);
  }
  ```

- Express dependencies between parameters with chained constraints
  (`<List extends URLList, K extends keyof List>`) so typos fail at the call
  site and narrowing is preserved (TC 4.2).
- In a generic function returning `T`, clone and modify the input
  (`{ ...input, field }`) — never fabricate a fresh literal and assert it
  `as T`: the caller may instantiate `T` with a subtype carrying extra
  properties your literal does not have (TC 4.4).
- When one type parameter must be given explicitly and another inferred,
  split the binding sites (inference is all-or-nothing): a curried function
  or a generic class method carries the inferred parameter separately (ET 28).
- When literal values inside an argument must survive (routes, config
  arrays), declare the parameter `const` — `function router<const T extends
  Route>(routes: T[])` — instead of relying on callers writing `as const`
  (TC 4.9).
- Writing through `obj[key]` with a broad `keyof T` key fails (the write
  position intersects all property types); lock the key in a generic —
  `function set<K extends keyof T>(key: K, value: T[K])` — never assert
  (TC 12.6).

## Constraints, defaults, naming

- Constrain every type parameter with `extends` to its valid domain
  (`<T extends object, K extends keyof T>`); an unconstrained parameter
  admits invalid instantiations that surface as wrong types downstream
  instead of errors at the use site (ET 50).
- Name type parameters like function parameters: single letters (`T`, `K`)
  only in tiny scopes; descriptive PascalCase names (`Route`, `From`,
  `Union`) wherever there are several or the scope is broad — the same
  applies to `infer` variables (TC 12.8; ET 50).
- A generic class whose `T` cannot be inferred from constructor arguments
  defaults it to `never` (`class Collection<T = never>`), so an un-annotated
  instantiation fails at first use instead of silently becoming `unknown`
  (TC 11.4).
- Declare type parameters at the narrowest scope — on the method, not the
  class, when only the method needs them (ET 51).

## Conditional return types vs overloads

- When the return type is a *function of the argument type*, prefer a
  generic with a conditional return type over an overload stack — overloads
  are matched one-by-one and reject union-typed arguments; conditional types
  distribute and cover them (ET 52; TC 5.1):

  ```ts
  function double<T extends string | number>(x: T): T extends string ? string : number;
  function double(x: string | number): string | number {
    return typeof x === 'string' ? x + x : Number(x) * 2;
  }
  ```

  The single broad implementation signature behind the precise public one
  confines the unchecked spot to one declared seam.
- Overloads remain the right tool when the *argument lists themselves*
  differ (query vs query+callback) or when exact argument pairings must be
  rejected — one overload per valid combination, with the body
  runtime-checking which variant it received (TC 2.6, 12.7).
- Decide, for every conditional type, whether it should distribute over
  unions. Only a bare `T extends ...` distributes; wrap both sides in
  one-tuples (`[T] extends [X]`) to switch distribution off. Traps:
  `boolean` is `true | false` and distributes; a distributive conditional
  over `never` is always `never` (ET 53).

## Tuples and variadic signatures

- A fixed-length heterogeneous result is a tuple, not an array: annotate the
  return type or use `as const` — otherwise every destructured element gets
  the full union type (TC 10.3, 2.4).
- Label tuple elements (`[name: string, age: number]`) — labels are free
  documentation in hovers and completions (TC 7.5).
- Wrappers that reorder, extend, or forward argument lists are typed with
  variadic tuples — `(...args: [...Args, Extra]) => R` — not `any[]` and not
  an overload wall (TC 7.1–7.2; ET 62). Model type-dependent arity with a
  rest parameter whose tuple type is computed:

  ```ts
  function buildURL<P extends keyof RouteParams>(
    route: P,
    ...args: RouteParams[P] extends null ? [] : [params: RouteParams[P]]
  ): string { /* ... */ }
  ```

## DRY at the type level

- Never write two declarations that must stay in sync by hand — derive one
  from the other (ET 15; TC 12.1): `typeof value` when a runtime constant is
  the source of truth, `keyof`, indexed access (`Action['type']` for a union
  of tags), `Pick` / `Partial` / `Omit` / `Record` / `Exclude` / `Extract`,
  `Parameters<typeof fn>` / `ReturnType<typeof fn>` for function contracts
  (TC 7.7).
- A lookup keyed by a union's discriminant is a mapped type over the
  discriminant, refined with `Extract` — it updates itself when a variant is
  added (TC 4.5):

  ```ts
  type GroupedToys = { [K in Toy['kind']]?: Extract<Toy, { kind: K }>[] };
  ```

- When parallel *data* must cover every property of a type (flags,
  serializers, per-field config), type it `Record<keyof T, V>` with a literal
  initializer — adding or renaming a property on `T` then breaks the build at
  the map (ET 61).
- Several functions sharing a signature get one named function type
  (`const add: BinaryFn = (a, b) => a + b`); a wrapper matching an existing
  function is typed `typeof fn` (ET 12).
- Compose utility types into small named helpers with constrained, defaulted
  key parameters (`type SetOptional<T, K extends keyof T = keyof T> = ...`)
  instead of repeating raw mapped types inline (TC 8.1).
- Caveats: `Partial` / `Required` / `Readonly` — like object spread — are
  shallow; a deep variant needs a recursive type *and* a deep runtime merge
  (TC 8.2). `keyof (A | B)` yields only the shared keys — often `never`
  (TC 8.7). Do not unify types whose fields are only coincidentally identical
  (ET 15), and prefer eliminating near-duplicate types over maintaining
  converters between them (ET 39).

## Template literal types

- When a string has internal structure (prefix, delimiter, pattern), encode
  it — `` `on${string}` ``, `` `H${1 | 2 | 3}` ``, key remapping with
  `` as `on${Capitalize<K>}Changed` `` — instead of accepting `string` and
  validating by hand; pattern violations become compile errors (ET 54;
  TC 6.1–6.3).
- Parse structured strings with `infer` in a conditional type; keep deep
  recursion in tail position by threading an accumulator parameter, which
  raises the recursion limit and speeds checking (ET 57; TC 5.5).
- Do not encode large value ranges as unions — a four-digit-year template
  union has 1,000 members and every operation checks them all. Prefer
  `string`/`number` plus a branded type with a validating coercer (ET 78).
- Stop before the pattern becomes inaccurate: an honest `string` beats a
  clever template type that rejects valid data (ET 40, 54).

## Keep types simple; test the complex ones

- Escalate deliberately — plain shapes → literal unions → generics →
  template-literal/conditional types — and stop at the first level that
  eliminates the error class you care about (TC 12.11). Prefer
  inference-friendly signatures over conditional-type machinery that needs
  `as` internally and destroys autocomplete (TC 7.5).
- When precise types would need a type-level parser for an external DSL,
  generate the types with an ordinary program from the real source of truth
  and keep them fresh in CI, rather than writing a type-level interpreter
  (ET 58).
- Nontrivial type utilities get **type-level tests** pinned next to them,
  using an established helper (`expectTypeOf`-style equality assertions, or
  an `Expect<Equal<X, Y>>` pattern), plus negative cases via narrowly-scoped
  `@ts-expect-error` (ET 55; TC 12.4). Plain assignability checks are the
  wrong tool: they silently accept dropped parameters and extra properties.
- A recursive type that errors ("instantiation is excessively deep") is
  broken even if its output looks right — restructure it (accumulator,
  simpler formulation) or abandon the type-level approach (TC 5.5/6.5).
