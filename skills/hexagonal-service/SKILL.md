---
name: hexagonal-service
description: Canonical Hexagonal Architecture (ports and adapters) standard — language- and framework-agnostic and project-neutral. Covers the invariant core of the pattern (ports as the app boundary, driving/driven actors, thin adapters, the configurator/composition root, the dependency-inward rule, technology-neutral port contracts, test doubles at every port, a single-root typed domain error flow) and the major approaches to applying it (strict two-layer, layered domain → application → infrastructure, onion/clean refinements, DDD, CQRS). It never picks an adoption strategy — the host project's rules must declare one (module-first, domain-first, layer-first, ports-first, walking skeleton, strangler, …) and always take precedence. Use when structuring a module, port, use case, or adapter, when deciding where code belongs, or when reviewing boundaries and error flow — in any language, under any framework.
---

# Hexagonal service (ports and adapters)

Keep the app pure, point every dependency inward, and let errors cross the
boundary exactly once in each direction. This skill is **neutral by
contract** on three axes:

- **Languages and frameworks** — the rules hold for any stack, DI container,
  HTTP engine, ORM, or broker. Pair it with a language skill (e.g.
  `typescript-coding`) and, where relevant, a framework skill (e.g.
  `typescript-nestjs`) for the concrete mechanics.
- **Approaches** — the pattern itself fixes only the boundary (inside vs
  outside); how the inside is structured (two-layer, layered, onion/clean,
  DDD) is an approach choice. The skill describes them all; see
  [references/approaches.md](references/approaches.md).
- **Projects** — the concrete **adoption strategy** (module-first,
  domain-first, layer-first, ports-first layout; walking-skeleton or
  strangler rollout; port granularity; binding mechanics) is a project
  decision. It must be declared in the rules of the host project where this
  skill is used, and those rules always take precedence over this skill. The
  catalog of known strategies lives in
  [references/strategies.md](references/strategies.md).

## Workflow

1. **Find the project's declared strategy.** Read the host project's rules
   for its hexagonal strategy (layout, port granularity, binding mechanics).
   If none is declared, infer the de-facto layout from the existing code,
   follow it, and propose recording it in the project rules — never invent a
   new layout. See [references/strategies.md](references/strategies.md).
2. **Locate the change on the hexagon.** Decide whether you are touching the
   inside (domain/application core), the outside (driving/driven adapters),
   or the composition root/configurator. Dependencies point inward only. See
   [references/architecture.md](references/architecture.md).
3. **Build inside-out.** For a new feature follow the recipe in
   [references/checklist.md](references/checklist.md): domain error → input
   port → application DTO → use case → transport DTO → adapters → error
   mapping → wiring → integration test.
4. **Route every error along the one sanctioned path.** Typed domain errors
   from a single root; foreign errors wrapped exactly once at the driven
   adapter with their cause; mapped to transport exactly once at the boundary
   filter. See [references/error-flow.md](references/error-flow.md) — read it
   before touching any `catch`.
5. **Keep the edges disciplined.** Boundary validation, fail-closed
   configuration, logging through a port, correlation ids, resilience around
   external calls — see
   [references/boundaries-and-io.md](references/boundaries-and-io.md).

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Pattern canon: ports, actors, adapters, configurator, boundary placement, dependency rule | [references/architecture.md](references/architecture.md) |
| Comparing or choosing an approach: two-layer vs layered, onion/clean, DDD, CQRS, use cases, nesting | [references/approaches.md](references/approaches.md) |
| Adopting the pattern in a project: layout/rollout/migration strategies; what project rules must declare | [references/strategies.md](references/strategies.md) |
| Anything about errors: throwing, catching, wrapping, mapping | [references/error-flow.md](references/error-flow.md) |
| Validation, config, secrets, logging, correlation ids, external calls | [references/boundaries-and-io.md](references/boundaries-and-io.md) |
| Step-by-step recipe for a new feature/endpoint; review checklist | [references/checklist.md](references/checklist.md) |

## Rules

- **Invariant core** (required by the pattern under every approach): every
  interaction between the app and the outside world crosses a port the app
  defines; the app has no source dependency on any actor, adapter, or
  technology; driven actors are configurable at runtime through the
  configurator; port contracts speak business language, never technology.
- Dependencies point inward only. Never weaken an import boundary to make a
  build or a gate pass; enforce boundaries with a machine import-graph check.
- A port is an interface plus an explicit binding point. Port granularity
  (one port per actor intention vs one port per use case) is an approach
  choice recorded in the project rules — apply the declared one consistently.
- Adapters stay thin: driving adapters map transport → application → back;
  driven adapters implement output ports and translate infrastructure errors
  into domain errors. Business logic in an adapter is a defect.
- Raw/untyped throws are forbidden inside the hexagon — only typed domain
  errors from the single-root registry. A foreign error is wrapped **exactly
  once**, at the driven adapter, with its cause preserved; it bubbles
  untouched and is logged (with stack) and mapped to transport **exactly
  once**, in the boundary filter. Re-wrapping in between is forbidden.
- Every port has a test driver or test double; the tests are what make the
  boundary real. Configuration is a single fail-closed source of truth; a
  use case never reads config or environment itself.
- **The strategy belongs to the project, not to this skill.** The skill never
  prescribes a directory layout, module shape, or DI mechanics — the host
  project's rules do. Language mechanics belong to the language skill,
  framework mechanics to the framework skill. Project instructions always
  take precedence over this skill.
