# Boundaries and I/O: validation, config, logging, external calls

The edges of a service — where input, configuration, secrets, logs, and
external calls live — are where most defects hide. Keep the discipline tight;
all of it is language- and framework-neutral.

## Input validation

- Validate **at the boundary**, declaratively, with closed field sets
  (reject unknown properties). A schema violation is a `400`-class failure; a
  schema-valid but domain-invalid request is a `422`-class failure.
- Keep the transport ↔ domain conversion (naming case, formats) inside the
  driving-layer mapper; the domain never sees transport shapes.

## Configuration and secrets

- **Configuration is a single source of truth, validated fail-closed.** All
  config lives in one config layer; the environment is validated at startup
  and an invalid environment aborts the boot with a typed error. There is
  **zero** raw env access outside the config layer; config values are
  consumed only by driven adapters and the composition root — a use case
  receives limits as parameters.
- **Secrets come only from the deployment environment** — never in code,
  logs, or the repository. Only a names-only example env file is committed.
  Adding a variable updates the validation schema and the example file in the
  same change.

## Observability

- **Log through an injected logger port**, as structured records; direct
  stdout/console writes are forbidden in shipped code. Every record carries a
  correlation/trace id.
- **Logging points:** entry into a public application/infrastructure
  operation → DEBUG; success → INFO; a retry → WARNING (attempt + reason); a
  caught unexpected exception → ERROR with the stack (at the boundary filter
  only — see [error-flow.md](error-flow.md)); a domain validation failure →
  WARNING.
- Do not log secrets, full payloads, or full external-model prompts and
  responses — log metadata (operation, status, duration, counts).
- **Correlation id.** Accept it from the inbound request (or generate one at
  the first boundary that lacks it), echo it in the response, and propagate
  it into every outbound call and message — in headers/metadata, never in the
  business payload.

## External calls

- Any outbound call (HTTP, model API, queue) is made **only from a driven
  adapter**, wrapped in a resilience policy: timeout + retry (exponential
  backoff with jitter) + circuit breaker. One policy instance per external
  service; its parameters come from configuration.
- **Pagination is keyset**, not offset: a `limit` plus an opaque `cursor`
  stable over a total order, returning the page plus a `next_cursor`
  (`null` at the end).
- Consumers of messages are **idempotent by a natural key**; a non-idempotent
  external side effect is guarded by a durable marker.
- On shutdown, drain gracefully: stop accepting work → finish in-flight work →
  close pools/connections → flush the log buffer.
