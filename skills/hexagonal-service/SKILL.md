---
name: hexagonal-service
description: Architecture standard for services built as hexagons (ports and adapters) — deliberately language- and framework-agnostic. Layer model domain → application → infrastructure with a composition root, dependency-inward boundaries, ports as interfaces with explicit binding points, one use case per input port, thin adapters, a single-root typed domain error flow (wrap a foreign error exactly once at the driven adapter with its cause, let it bubble untouched, log with the stack and map to transport exactly once in a boundary filter), boundary validation, config as a fail-closed single source of truth, and correlation ids. Use when structuring a module, port, use case, or adapter, when deciding which layer code belongs to, or when reviewing layer boundaries and error flow — in any language and under any framework.
---

# Hexagonal service (ports and adapters)

Keep the domain pure, point every dependency inward, and let errors cross
layers exactly once in each direction. This skill is **language- and
framework-agnostic by contract**: the rules hold for TypeScript, Python, or
any other stack, under any DI container, HTTP engine, ORM, or broker. Pair it
with a language skill (e.g. `typescript-coding`) and, where relevant, a
framework skill (e.g. `typescript-nestjs`) for the concrete mechanics.

## Workflow

1. **Locate the change on the hexagon.** Decide which layer you are touching —
   `domain` (pure core), `application` (use cases/services), `infrastructure`
   (adapters), or the composition root. Dependencies point inward only. See
   [references/architecture.md](references/architecture.md).
2. **Build inside-out.** For a new feature follow the recipe in
   [references/checklist.md](references/checklist.md): domain error → input
   port → application DTO → use case → transport DTO → adapters → error
   mapping → wiring → integration test.
3. **Route every error along the one sanctioned path.** Typed domain errors
   from a single root; foreign errors wrapped exactly once at the driven
   adapter with their cause; mapped to transport exactly once at the boundary
   filter. See [references/error-flow.md](references/error-flow.md) — read it
   before touching any `catch`.
4. **Keep the edges disciplined.** Boundary validation, fail-closed
   configuration, logging through a port, correlation ids, resilience around
   external calls — see
   [references/boundaries-and-io.md](references/boundaries-and-io.md).

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Structuring a module, port, use case, or adapter; layer questions | [references/architecture.md](references/architecture.md) |
| Anything about errors: throwing, catching, wrapping, mapping | [references/error-flow.md](references/error-flow.md) |
| Validation, config, secrets, logging, correlation ids, external calls | [references/boundaries-and-io.md](references/boundaries-and-io.md) |
| Step-by-step recipe for a new feature/endpoint; review checklist | [references/checklist.md](references/checklist.md) |

## Rules

- The `domain` layer imports no framework and no other layer; `application`
  imports no `infrastructure`. Never weaken an import boundary to make a
  build or a gate pass; enforce boundaries with a machine import-graph check.
- A port is an interface plus an explicit binding point; one use case
  implements exactly one input port with a single `execute()`-style entry.
- Adapters stay thin: driving adapters map transport → application → back;
  driven adapters implement output ports and translate infrastructure errors
  into domain errors. Business logic in an adapter is a defect.
- Raw/untyped throws are forbidden in `domain` and `application` — only typed
  domain errors from the single-root registry. A foreign error is wrapped
  **exactly once**, at the driven adapter, with its cause preserved; it
  bubbles untouched and is logged (with stack) and mapped to transport
  **exactly once**, in the boundary filter. Re-wrapping in between is
  forbidden.
- Configuration is a single source of truth validated fail-closed at startup;
  a use case never reads config or environment itself.
- Keep this skill neutral: language mechanics belong to the language skill,
  framework mechanics to the framework skill, project choices to the host
  project. Project instructions always take precedence over this skill.
