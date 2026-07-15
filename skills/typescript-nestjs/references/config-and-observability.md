# Configuration and observability

## Configuration — fail-closed behind @nestjs/config

- All configuration enters through `@nestjs/config` with **namespaced
  `registerAs` factories** (one `<ns>.config.ts` per namespace) and a single
  env **validation schema** applied at bootstrap: an invalid or missing
  variable aborts the boot with a typed error, before any module initializes.
- Access is typed and key-safe: `configService.get<T>(<key from a registry>)`
  with a documented default — never a magic string key, and never a raw
  `process.env` read outside the config layer (the `typescript-coding`
  checker flags this as `TS-ENV`).
- Keep the registries synchronized in one place: env variable names,
  defaults, and config keys each live in their own constants module; adding a
  variable updates the schema, the registries, and the names-only
  `.env.example` in the same change.
- Config values are consumed by driven adapters and `providers/` factories;
  a use case receives limits (timeouts, page sizes) as constructor/method
  parameters, never the `ConfigService` itself.

## Logging

- Log through the project's **own logger port**, implemented once in an
  observability library over a structured logger. Avoid framework-coupling
  wrapper packages that tie the logging pipeline to NestJS internals — the
  port keeps the domain and application layers framework-free.
- Every record carries the trace id (see the boundary interceptor); accept an
  inbound trace id header, generate one at the boundary when absent, echo it
  in the response, and propagate it to outbound calls in headers/metadata —
  never in business payloads.
- Request errors are logged only by the exception-filter chain (once, with
  the stack); `console.*` is forbidden in shipped code.

## Health and metrics

- Liveness/readiness endpoints (`/health`, `/ready`) and metrics come from
  dedicated terminus/metrics modules and stay separate from business routes;
  services without a business HTTP surface expose only these.
- On shutdown, use Nest's shutdown hooks to drain gracefully: stop accepting
  work → finish in-flight requests/messages → close pools and connections →
  flush the log buffer.
