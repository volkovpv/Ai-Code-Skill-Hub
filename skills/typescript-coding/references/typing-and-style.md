# Typing and style

Strict typing is the contract; the style rules below are what the type checker
and formatter will not write for you. Everything here applies to any
TypeScript codebase — no framework or architecture is assumed.

## tsconfig — strict by construction

Enable `strict: true` and, on top of it, the flags that close the remaining
holes:

- `noImplicitOverride`, `noImplicitReturns`, `noFallthroughCasesInSwitch`;
- `noUnusedLocals`, `noUnusedParameters`;
- `noUncheckedIndexedAccess` — indexed access yields `T | undefined`, so you
  must handle the `undefined` instead of assuming presence;
- `exactOptionalPropertyTypes` — `x?: T` is not `x: T | undefined`; do not
  assign an explicit `undefined` to an optional property.

Target a modern ECMAScript output and `NodeNext` module resolution. Build with
the project's compiler; run scripts with a modern TS runner, not a legacy one.

## Style the linter cannot enforce

- **Member ordering:** fields → constructor → static factories → accessors →
  methods. Declare explicit access modifiers.
- **Explicit return types on every exported function/method.** Let inference
  work inside a function body, but pin the public surface.
- **`import type`** for type-only imports; **`readonly` fields and
  `ReadonlyArray`/`readonly T[]` by default** — reach for mutability
  deliberately.
- In `catch`, the binding is **`unknown`**; narrow before use. Never type a
  caught error as `any`.
- Do not silence the type checker or linter (`@ts-ignore`, `@ts-nocheck`,
  `eslint-disable`) to pass a gate; fix the cause. Format with a single
  formatter and do not fight it with a second one.

## Zero magic — constants registries

- Strings and numbers with meaning (other than `0`/`1`/`-1`/`2`) are named
  constants, grouped in a registry module near the code that owns them —
  never scattered literals.
- A registry is an **`as const` object plus a derived union type** — a native
  `enum` is banned:

  ```ts
  export const USER_STATUS = { Active: 'active', Blocked: 'blocked' } as const;
  export type UserStatus = (typeof USER_STATUS)[keyof typeof USER_STATUS];
  ```

  Unlike a native `enum`, it erases to plain values, needs no runtime import,
  and narrows structurally.

- Tunable thresholds (limits, windows, sizes) belong in configuration, not
  baked into code as literals.

## Identifiers

- **Branded identifiers.** No id is a raw `string`: a branded type plus a
  coercer applied exactly where untyped input enters the program.

  ```ts
  export type UserId = string & { readonly __brand: 'UserId' };
  export const asUserId = (raw: string): UserId => raw as UserId;
  ```

- Identifiers and code are written in English; a name says what the value is,
  not how it is produced.

## Self-check

The checker `scripts/check_conventions.py` flags the mechanical violations of
this file (`enum`, `any`, non-null `!`, suppression comments) and of the other
references. It is a backstop, not the source of truth; the compiler in
`strict` mode is. See [../data/fixtures/clean_sample.ts](../data/fixtures/clean_sample.ts)
for a file that satisfies every rule here.
