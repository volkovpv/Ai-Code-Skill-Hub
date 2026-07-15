# The HTTP boundary

Controllers, pipes, guards, interceptors, and exception filters are the
driving edge of the hexagon. They translate; they never decide.

## Controllers are mappers

- A controller method does exactly: request DTO → application Input (plus
  auth subject and trace id from parameter decorators) → `execute()` on the
  injected input port → response DTO via a static response mapper.
- Business logic, persistence access, or error mapping inside a controller is
  a defect.
- `@HttpCode` is explicit for every non-default status; route paths, API
  summaries, and status codes come from constant registries, not string
  literals scattered through decorators.

## Validation

- One **global** `ValidationPipe({ whitelist: true, forbidNonWhitelisted:
  true, transform: true })` — unknown fields are rejected (a bare
  `whitelist: true` only *strips* them; `forbidNonWhitelisted` turns the extra
  field into a `400`), payloads arrive typed.
- Request DTOs carry `class-validator` decorators (with `class-transformer`
  where conversion is needed); response DTOs are `public readonly` fields
  (plus OpenAPI decorators where the project documents its API).
- Field-name convention translation (e.g. `snake_case` wire ↔ `camelCase`
  code) is encapsulated in the driving-layer mapper, never in the domain.
- A schema violation → `400`; a schema-valid but domain-invalid request →
  `422` (raised by the use case as a domain error, mapped by the filter).

## Guards and cross-cutting order

- Authentication is on by default: register the guard as `APP_GUARD`; public
  endpoints opt out explicitly with a `@Public()` decorator whose metadata
  key is a `unique symbol`.
- Parameter decorators (`@Auth()`, `@TraceId()`) deliver cross-cutting values
  to controllers — controllers never dig into the raw request.
- Know the real execution order: **middleware → guard → interceptor → pipe →
  handler → interceptor → exception filter**. Guards run *before*
  interceptors, so a request an auth guard rejects never reaches a post-guard
  logging interceptor — establish the trace id in middleware (ahead of the
  guards), not in an interceptor, if auth failures must carry it. The
  exception filter still catches guard rejections, so every failure —
  authenticated or not — leaves through the error envelope and is logged
  there exactly once.

## Exception filters — log once, map once

- A **module filter** owns a `Map<ErrorName, HttpStatus>` translating that
  module's domain errors to statuses; a **global filter** builds the error
  envelope (RFC 9457 Problem Details with a stable machine `code` and the
  trace id) and masks every `5xx` — internals, stacks, and raw upstream
  payloads never reach the client.
- The filter chain is the **only** place a request error is logged (ERROR,
  with the full stack and cause chain, plus the trace id) and the only place
  a domain error meets HTTP. Use cases and adapters let errors bubble — see
  the hexagonal-service error-flow reference.
