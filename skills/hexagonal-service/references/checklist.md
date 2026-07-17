# Recipe and review checklist

## Recipe for a new feature or endpoint (inside-out)

Build along the dependency direction, from the domain core outward. Each step
ends with a fast lint + unit run before the next. Where each artifact lives
on disk is set by the project's declared layout strategy
([strategies.md](strategies.md)) — the recipe fixes the order and the
discipline, not the paths.

0. **Project strategy** — confirm the layout, port granularity, and wiring
   mechanics declared in the host project's rules; if none are declared,
   follow the de-facto layout of the existing code.
1. **Domain error** — add the typed error (single root, machine `code`) for
   the new failure mode.
2. **Input port** — declare the input-port interface (one `execute()`-style
   entry, domain-typed signature) and its binding token.
3. **Application DTO** — plain immutable Input/Result types.
4. **Use case** — implement the input port; constructor takes only output
   ports and application services; throws only domain errors.
5. **Output ports** — if new outbound capability is needed, declare the
   output port in domain terms; do not implement it in `application`.
6. **Transport DTO** — request/response types with boundary validation
   (closed field set).
7. **Driving adapter** — controller/handler that maps transport → application
   DTO → input port → response DTO. No business logic.
8. **Driven adapter** — implement each output port; map to domain via a
   mapper; wrap infrastructure errors into domain errors exactly once, with
   the cause; wrap external calls in the resilience policy.
9. **Error mapping** — add the domain-error → transport-status row in the
   boundary filter's table.
10. **Composition root** — register the use-case factory (declared type = the
    port) and bind output ports to implementations; if the strategy defines
    modules, export only input-port bindings and domain types from the
    module's public surface.
11. **Integration test** — through the boundary: happy path → validation →
    business errors → auth.

## Pre-handoff review checklist

- [ ] The change follows the project's declared strategy (layout, port
      granularity, wiring) — no private layout invented.
- [ ] Dependencies point inward; the domain core is framework-free; no
      cross-module import bypasses a module's public surface.
- [ ] One use case = one input port = one entry point; the constructor takes
      only ports/services.
- [ ] Only typed domain errors are thrown in `domain`/`application`; the one
      wrap lives in the driven adapter and preserves the cause; no
      catch-and-rethrow in intermediate layers; no empty catch.
- [ ] The boundary filter logs the error once with the stack and maps it to
      the transport status once; `5xx` responses are masked.
- [ ] Boundary validation distinguishes schema (`400`) from domain (`422`)
      failures.
- [ ] Env is read only in the config layer, validated fail-closed; no secret
      in code, logs, or the repo.
- [ ] Logging goes through the port with a correlation id; external calls sit
      in driven adapters behind a resilience policy.
- [ ] Tests ship in the same change; integration tests drive the boundary,
      not the adapters.
