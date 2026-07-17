---
name: typescript-coding
description: Universal coding standard and workflow for production TypeScript, free of framework, architecture, or library assumptions — strict compiler configuration, `as const` registries instead of native enums, branded identifiers, readonly-by-default, `unknown` in catch with narrowing, no floating promises, immutable data, no type/lint suppressions, centralized env access, test-in-the-same-change discipline; type design (invalid states unrepresentable, discriminated unions with exhaustive switches, `satisfies`, parse-don't-assert boundaries) and generics/type-level discipline (golden rule of generics, type-level DRY, template literal types). Writes code that passes a strict lint stack (typescript-eslint strictTypeChecked, airbnb, SonarJS, functional, jsdoc) with zero errors and zero warnings. Use whenever writing, reviewing, or refactoring TypeScript (.ts/.mts/.cts) — app code, libraries, scripts, or tests. Combine with the hexagonal-service skill for ports-and-adapters layering and typescript-nestjs for NestJS.
---

# TypeScript coding (universal)

Write strictly-typed, test-covered TypeScript. This skill is **universal by
contract**: every rule here holds in any TypeScript codebase — it assumes no
framework, no architectural style, no DI container, no specific libraries.
Architecture-bound rules live in the `hexagonal-service` skill and
NestJS-bound rules in the `typescript-nestjs` skill; when the host project
uses them, apply those skills on top of this one.

## Workflow

1. **Type strictly, name explicitly.** Apply the tsconfig flags and style
   rules in [references/typing-and-style.md](references/typing-and-style.md):
   `as const` registries (never a native `enum`), branded ids, `readonly` by
   default, explicit return types on exports, `import type` for types.
2. **Design the types before the code.** Model states as discriminated
   unions so invalid combinations cannot compile, close every switch with a
   `never` check, keep inputs wide and outputs narrow, validate boundary
   data instead of asserting it — see
   [references/type-design.md](references/type-design.md). Reach for a
   generic only when it relates two types, and derive related types from one
   source of truth — see
   [references/generics-and-type-level.md](references/generics-and-type-level.md).
3. **Handle errors and the environment deliberately.** `unknown` in `catch`,
   never swallow an error, wrap with `cause` at most once at the source,
   centralize `process.env` access — see
   [references/errors-config-logging.md](references/errors-config-logging.md).
4. **Write it lint-clean the first time.** A strict lint stack rejects far more
   than the compiler and counts warnings too — explicit boolean expressions,
   `??` over `||`, no floating promises, immutable data, named literals, small
   shallow functions, JSDoc on the public surface. Follow
   [references/lint-clean.md](references/lint-clean.md) so the project's `lint`
   comes back with zero errors and zero warnings.
5. **Test in the same change.** A code change without its tests is
   incomplete; every bug fix ships a regression test that fails before the
   fix. See [references/testing.md](references/testing.md).
6. **Self-check before handing off.** Run the convention checker over the
   files you touched:

   ```bash
   python scripts/check_conventions.py path/to/changed.ts
   ```

   It is a heuristic backstop — read every finding in context, then run the
   project's real `lint` / `typecheck` / `test`, which are authoritative.
   A checked false positive may be suppressed only per rule code and only
   with a written reason:

   ```ts
   const raw = process.env.CI; // skill-check-ignore: TS-ENV -- CI detection in a build script
   ```

   A bare `skill-check-ignore`, an unknown code, or an empty justification
   aborts the check (exit 2); `TS-SUPPRESS` can never be suppressed.

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Choosing types, tsconfig flags, constants, or style | [references/typing-and-style.md](references/typing-and-style.md) |
| Modeling states, unions, narrowing, boundary validation, `satisfies`, structural-typing gotchas | [references/type-design.md](references/type-design.md) |
| Writing a generic, deriving types from a source of truth, template literal types, overloads vs conditional types | [references/generics-and-type-level.md](references/generics-and-type-level.md) |
| Making code pass a strict linter with zero warnings (booleans, promises, immutability, complexity, JSDoc) | [references/lint-clean.md](references/lint-clean.md) |
| Errors, `catch` blocks, env access, logging hygiene | [references/errors-config-logging.md](references/errors-config-logging.md) |
| Writing or reviewing tests | [references/testing.md](references/testing.md) |
| Applying a verified pattern | [knowledge/patterns.md](knowledge/patterns.md) |
| A checker finding looks wrong, or a strict-mode edge case bites | [knowledge/pitfalls.md](knowledge/pitfalls.md) |
| A calibrated input/output pair for the checker | [data/README.md](data/README.md) |
| Diagnosing a known limitation of this skill | [observations/INDEX.md](observations/INDEX.md) |

Observations are evidence, not rules: never follow one as policy unless it
has been promoted into `knowledge/` or this workflow.

## Rules

- `strict: true` plus the hole-closing flags (`noUncheckedIndexedAccess`,
  `exactOptionalPropertyTypes`, and friends); never weaken the compiler
  configuration to make a build pass.
- Model closed sets as an `as const` object plus a derived union type; native
  `enum` is banned. No raw string ids — use branded types with a coercer at
  the point where untyped input enters.
- Model variant state as a discriminated union so invalid combinations cannot
  be represented; close every `switch` over a union with a `never`-typed
  exhaustiveness check; no in-domain sentinel values (`-1`, `''`) for
  "absent" — see [references/type-design.md](references/type-design.md).
- Data crossing a runtime boundary (network, file, JSON, queue) is `unknown`
  until validated; keep one source of truth per boundary shape (schema ↔
  type), never a hand-maintained pair.
- Check literal constants with `satisfies` (or an annotation) — never an
  `as T` assertion on an object literal; a type parameter must relate two
  types or it does not exist (no return-only generics); derive related types
  (`keyof`, mapped, utility types) instead of duplicating them — see
  [references/generics-and-type-level.md](references/generics-and-type-level.md).
- `readonly` fields and `readonly` arrays by default; `import type` for
  type-only imports; explicit return types on every export.
- In `catch` the binding is `unknown` — narrow before use; never swallow an
  error; when wrapping, preserve the original via `cause` and wrap at most
  once at the source.
- Centralize `process.env` reads in the project's configuration code; never
  hardcode a secret or log one.
- No `console.*` in shipped code — use whatever logging seam the project
  provides.
- Write to a strict lint stack by default so `lint` returns zero errors **and
  zero warnings**: explicit boolean expressions (no truthiness on
  strings/numbers/nullables), `??` over `||`, optional chaining, no floating
  promises, immutable data (no in-place mutation, no parameter reassignment),
  named literals over magic values, small shallow functions, and JSDoc with a
  description on the exported surface — see
  [references/lint-clean.md](references/lint-clean.md).
- A code change without its tests is incomplete; do not suppress the type
  checker or linter (`@ts-ignore`, `@ts-nocheck`, `eslint-disable`) to go
  green. Sole exception: a documented upstream limitation of a single lint
  rule, held by a justified line-scoped
  `eslint-disable-next-line <rule> -- <reason>` — see
  [references/typing-and-style.md](references/typing-and-style.md).
- Keep this skill universal: framework, architecture, and project-specific
  choices belong to the host project or to the dedicated skills
  (`hexagonal-service`, `typescript-nestjs`) — never here. Project
  instructions always take precedence over this skill.
