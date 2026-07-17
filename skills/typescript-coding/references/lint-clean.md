# Passing a strict linter clean (zero warnings)

Strict typing keeps the compiler happy; a strict **lint** stack rejects a much
larger surface — and it counts `warn`-level findings, not only errors. This
file is the checklist that keeps both at zero. It targets the lint setup a
production TypeScript project usually runs: ESLint with typescript-eslint
`strictTypeChecked` + `stylisticTypeChecked`, the airbnb base and TypeScript
rule sets, SonarJS, `eslint-plugin-functional`, `eslint-plugin-jsdoc`, and a
jest preset for tests — with **all formatting delegated to a single formatter**
(Prettier) via `eslint-config-prettier`.

Nothing here assumes a framework or architecture. Exact thresholds (line
width, complexity ceilings, the naming regex) are the host project's config;
the idioms below are universal — write to them by default and both `error`-
and `warn`-level findings stay at zero. Where the project's stack differs,
its `lint` / `typecheck` output is authoritative; treat this file as how to be
right the first time, not as the rule source.

## Boolean expressions are explicit

The single biggest source of findings under a type-aware stack.

- **No truthiness on strings, numbers, or nullables** (`strict-boolean-expressions`).
  Test the thing you mean:
  - string — `if (s !== '')`, never `if (s)`;
  - number — `if (n > 0)` / `if (n !== 0)`, never `if (n)`;
  - nullable — `if (x != null)` or `if (x !== undefined)`, never `if (x)`;
  - array non-empty — `if (arr.length > 0)`.
  A plain nullable **object** may be tested directly (`if (entity)`), because
  an object has no falsy value other than `null`/`undefined`.
- **`??` not `||` for defaults** (`prefer-nullish-coalescing`): `a ?? fallback`,
  not `a || fallback` — `||` also swallows `''`, `0`, `false`.
- **`a?.b` not `a && a.b`** (`prefer-optional-chain`).
- **No condition the types prove is always true or false**
  (`no-unnecessary-condition`): a guard on a non-nullable value is dead code —
  remove it, or fix the type that made it redundant.
- **`===` / `!==` always** (`eqeqeq`); `== null` is the one allowed loose form,
  as the nullish check above.
- **No implicit coercion** (`no-implicit-coercion`, `restrict-plus-operands`,
  `restrict-template-expressions`): convert explicitly with `String(x)` /
  `Number(x)`, and check explicitly instead of relying on `+x` or `'' + x`.
  `!!x` for a boolean is fine. A `number` interpolates in a template literal;
  an object needs an explicit `String()` or a named field (`no-base-to-string`).

## Promises and async

- **Every promise is awaited or explicitly discarded with `void`**
  (`no-floating-promises`) — a fire-and-forget call that is neither is a finding.
- **No async function where a void-returning callback is expected**
  (`no-misused-promises`): don't pass `async () => …` as an event handler or
  array callback that ignores the return.
- **A function that returns a promise is declared `async`**
  (`promise-function-async`).
- **`return await` inside `try`/`catch`**, a bare `return promise` elsewhere
  (`return-await`).
- **Independent awaits run in parallel** with `Promise.all`; a sequential
  `await` inside a loop is flagged (`no-await-in-loop`). Deliberate
  rate-limited batching belongs in a named helper carrying a justification.
- **Throw and reject only `Error` instances** (`only-throw-error`,
  `prefer-promise-reject-errors`); the catch-callback binding is `unknown`
  (`use-unknown-in-catch-callback-variable`) — see
  [errors-config-logging.md](errors-config-logging.md).

## Immutability by default

- **No in-place mutation of data** (`functional/immutable-data`): no
  `arr.push()` / `splice()`, no `obj.prop = x`, no `arr[i] = x` on shared
  values. Build a new value — spread, `map`, `filter`, `{ ...obj, k: v }`. A
  class instance may mutate its **own** fields through its methods (via `this`).
- **Never reassign or mutate a parameter or its properties**
  (`no-param-reassign`): defensive-copy an input that flows through stages.
- **`const` unless genuinely reassigned** (`prefer-const`, `functional/no-let`):
  reach for `let` only for loop counters, accumulators, or retry state.
- **Private fields never reassigned after construction are `readonly`**
  (`prefer-readonly`).
- **Type and interface members are `readonly`** unless the type is explicitly a
  mutable one (`functional/type-declaration-immutability`); prefer `readonly`
  parameters and `ReadonlyArray` / `readonly T[]` on the public surface
  (`prefer-readonly-parameter-types`).

## Types precise, no redundancy

- **No `any`, and none of its unsafe leaks** (`no-unsafe-assignment` / `-call`
  / `-member-access` / `-return` / `-argument`): parse and narrow `unknown`
  before use.
- **Assert with `as`, never angle brackets, never on an object literal**
  (`consistent-type-assertions`) — type the variable instead; and never an
  unnecessary, unsafe, or non-null (`!`) assertion.
- **Don't annotate what the compiler infers** (`no-inferrable-types`):
  `const n = 1`, not `const n: number = 1`.
- **`T[]` / `readonly T[]` for simple element types** (`array-type`);
  **`Record<K, V>` over an index signature** (`consistent-indexed-object-style`).
- **Banned type names** (`no-restricted-types`): use `object` /
  `Record<string, unknown>` / a precise shape rather than `{}` or `Object`;
  the primitives `string` / `number` / `boolean` / `symbol` / `bigint`; and an
  explicit call signature rather than the bare `Function`.
- **`import type` / `export type` for type-only** references
  (`consistent-type-imports`, `consistent-type-exports`); no native `enum` and
  no `export =` (`no-restricted-syntax`).

## Naming and class shape

- **camelCase** values, parameters, and functions; **PascalCase** types and
  classes; **UPPER_CASE** module constants and closed-set members
  (`naming-convention`).
- **Every class member declares `public` / `private` / `protected`**
  (`explicit-member-accessibility`); members are ordered fields → constructor →
  static methods → accessors → instance methods (`member-ordering`).
- **Prefer constructor parameter properties** over hand-assigned fields
  (`parameter-properties`); **don't use a class purely as a namespace**
  (`no-extraneous-class`) — a module of exported functions and constants does
  that job.
- **`obj.key` not `obj['key']`** for a statically known key (`dot-notation`).

## No magic, low duplication, low complexity

- **Name every meaningful literal** — numbers other than `0`/`1`/`-1`/`2`
  (`no-magic-numbers`) and any string that repeats (`sonarjs/no-duplicate-string`)
  — in an `as const` registry near its owner (see
  [typing-and-style.md](typing-and-style.md)). Tunables live in configuration.
- **Keep functions small and shallow.** The stack caps cyclomatic and
  cognitive complexity, nesting depth, callback nesting, and file/function
  length (`complexity`, `sonarjs/cognitive-complexity`, `max-depth`,
  `max-nested-callbacks`, `max-lines`, `max-lines-per-function`). Extract a
  helper rather than grow one function.
- **No duplicated or identical branches, conditions, or functions**
  (`sonarjs/no-all-duplicated-branches`, `no-duplicated-branches`,
  `no-identical-conditions`, `no-identical-functions`) — factor the shared
  body out.
- **Prefer the idiom the linter wants:** template strings over `+`
  (`prefer-template`), object spread over `Object.assign` (`prefer-object-spread`),
  `find` / `includes` / `startsWith` / `for-of` over manual equivalents, no
  nested ternary, no `else` after `return`, no lonely `if`, no useless rename /
  concat / computed key.

## JSDoc on the public surface

- **Exported classes, functions, interfaces, and type aliases** — plus public
  methods and getters — carry a JSDoc block with a prose **description**
  (`jsdoc/require-jsdoc`, `require-description`).
- **Do not restate types in JSDoc** (`jsdoc/no-types`): TypeScript is the
  single source of truth — describe intent, not the signature. `@param` /
  `@returns` are optional, but if written must be valid and correctly named.

## Imports and modules

- **One group order** — builtin, external, internal, parent, sibling, index —
  with a blank line between groups and after the import block (`import/order`,
  `import/newline-after-import`, `import/first`); no duplicate imports
  (`import/no-duplicates`), no useless path segments.

## Formatting

A single formatter owns whitespace, quotes, semicolons, line width, and
trailing commas; `eslint-config-prettier` switches off every stylistic ESLint
rule so the two never disagree. Never fight the formatter by hand or add a
second one — run it **before** the linter. A stylistic "error" surfacing from
ESLint means the formatter has simply not run yet.

## Self-check

The bundled `scripts/check_conventions.py` catches only the mechanical, lexical
subset of the above (`enum`, `any`, non-null `!`, `console`, raw `process.env`,
suppressions, focused tests). The type-aware rules — boolean strictness,
floating promises, immutability, unnecessary conditions — are invisible to a
lexical scanner. The project's real `lint` and `typecheck` are the authority;
run them, and read every finding in context.
