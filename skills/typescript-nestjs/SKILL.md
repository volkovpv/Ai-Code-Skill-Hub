---
name: typescript-nestjs
description: NestJS-specific rules and conventions for services that follow the hexagonal (ports-and-adapters) architecture — DI tokens as named unique symbols, use cases as plain classes assembled by factory providers, controllers as pure mappers, a global ValidationPipe with class-validator request DTOs, guards via APP_GUARD with @Public metadata, exception filters that log once and map domain errors to HTTP once (RFC 9457, masked 5xx), fail-closed env validation behind @nestjs/config, and @nestjs/testing with overrideProvider for integration tests. Use when writing, reviewing, or refactoring NestJS code — a module, provider, controller, pipe, guard, interceptor, exception filter, config namespace, or NestJS test. Presumes the hexagonal-service skill for layer rules and the typescript-coding skill for language rules.
---

# TypeScript + NestJS

NestJS mechanics for a hexagonal service. This skill covers only what is
specific to NestJS; the layer model and error flow come from the
`hexagonal-service` skill, and the language discipline from the
`typescript-coding` skill — apply all three together, with project
instructions taking precedence over any of them.

## Workflow

1. **Wire dependencies the NestJS way, without leaking it inward.** Tokens
   are named `unique symbol` constants; use cases stay plain classes wired by
   factory providers. See
   [references/di-and-modules.md](references/di-and-modules.md).
2. **Keep the HTTP boundary declarative and thin.** Controllers map DTOs,
   validation is a global `ValidationPipe`, errors reach the client only
   through the exception-filter chain. See
   [references/http-boundary.md](references/http-boundary.md).
3. **Boot fail-closed.** Validate the environment at startup behind
   `@nestjs/config`; read configuration only through typed accessors. See
   [references/config-and-observability.md](references/config-and-observability.md).
4. **Test through Nest's own seams.** `Test.createTestingModule` +
   `overrideProvider(TOKEN)` against ports, driven through the controller.
   See [references/testing.md](references/testing.md).
5. **Self-check before handing off.** Run the NestJS convention checker over
   the files you touched:

   ```bash
   python scripts/check_nest_conventions.py modules/billing/
   ```

   It is a heuristic backstop (path-based layer detection, lexical masking,
   no AST); read every finding in context, then run the project's real
   `lint` / `typecheck` / `test`. Suppressions follow the same strict
   contract as `typescript-coding`:
   `// skill-check-ignore: NEST-DI-TOKEN -- <non-empty reason>`; a bare
   marker, an unknown code, or an empty justification aborts with exit 2.

## Routing: what to read when

| Situation | Read |
|-----------|------|
| Tokens, providers, module wiring, use-case assembly, file naming | [references/di-and-modules.md](references/di-and-modules.md) |
| Controllers, DTO validation, guards, interceptors, exception filters | [references/http-boundary.md](references/http-boundary.md) |
| ConfigModule, env validation, logging, health/metrics | [references/config-and-observability.md](references/config-and-observability.md) |
| Writing or reviewing NestJS tests | [references/testing.md](references/testing.md) |
| Checker fixtures and calibrated outputs | [data/README.md](data/README.md) |

## Rules

- A DI token is a named `unique symbol` whose description equals its export
  name; `@Inject('string')` and `@Inject(Symbol(...))` are forbidden.
- A use case is a plain class with no DI decorators, assembled in
  `providers/` by a `useFactory` whose `inject` order matches the constructor
  and whose declared return type is the port, not the class.
- A module exports only input-port tokens and domain types through its public
  barrel; importing another module's `*.module.ts` is forbidden.
- `domain/` imports nothing from `@nestjs/*` (or any framework);
  `application/` may use **type-only** imports from the framework base
  package. Raw `throw new Error` in `domain`/`application` is forbidden —
  typed domain errors only (see hexagonal-service error flow).
- Every request DTO is validated by the global `ValidationPipe({ whitelist:
  true, forbidNonWhitelisted: true, transform: true })` (unknown fields
  rejected, not just stripped); controllers hold no business logic; errors are
  logged and mapped to HTTP exactly once, in the exception-filter chain.
- Read env only inside the config layer; boot aborts on invalid env.
- Keep this skill project-neutral: no version pins, no product decisions —
  those belong to the host project.
