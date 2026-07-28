---
name: typescript-nestjs
description: NestJS-specific rules and conventions for services that follow the hexagonal (ports-and-adapters) architecture — DI tokens as named unique symbols, use cases as plain classes assembled by factory providers, controllers as pure mappers, a global ValidationPipe with class-validator request DTOs, guards via APP_GUARD with @Public metadata, exception filters that log once and map domain errors to HTTP once (RFC 9457, masked 5xx), fail-closed env validation behind @nestjs/config, and @nestjs/testing with overrideProvider for integration tests. Use when writing, reviewing, or refactoring NestJS code — a module, provider, controller, pipe, guard, interceptor, exception filter, config namespace, or NestJS test. Where the host project also declares an architecture or a language standard, apply that on top of this skill.
---

# TypeScript + NestJS

NestJS mechanics for a service built along ports and adapters. This skill
covers only what is specific to NestJS, and it **stands on its own**: every
rule below is stated in full here, in terms of the layers a
ports-and-adapters codebase already carries (`domain`, `application`,
driving and driven adapters). Where the host project also declares an
architecture or a language standard, apply that on top of this skill;
project instructions take precedence over both.

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
   `lint` / `typecheck` / `test`. A checked false positive may be suppressed
   only per rule code and only with a written reason:

   ```ts
   @Inject('LEGACY_TOKEN') // skill-check-ignore: NEST-DI-TOKEN -- third-party module exports a string token
   ```

   A bare `skill-check-ignore`, an unknown code, or an empty justification
   aborts the check (exit 2).

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
  typed domain errors only; a foreign error is wrapped into one exactly once,
  in the driven adapter that received it, with the original kept as `cause`.
- Every request DTO is validated by the global `ValidationPipe({ whitelist:
  true, forbidNonWhitelisted: true, transform: true })` (unknown fields
  rejected, not just stripped); controllers hold no business logic; errors are
  logged and mapped to HTTP exactly once, in the exception-filter chain.
- Read env only inside the config layer; boot aborts on invalid env.
- Keep this skill project-neutral: no version pins, no product decisions —
  those belong to the host project.
