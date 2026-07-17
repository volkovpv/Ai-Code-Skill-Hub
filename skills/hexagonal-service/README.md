# hexagonal-service

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Teaches an AI coding agent the canonical **Hexagonal Architecture**
(ports and adapters) — in any language, under any framework. Once installed,
the agent applies it whenever it structures a module, port, use case, or
adapter, decides where a piece of code belongs, or reviews boundaries and
error handling.

The skill covers:

- the **invariant core** of the pattern: ports as the application boundary,
  driving/driven actors, thin adapters, the configurator, the
  dependency-inward rule, technology-neutral contracts;
- the **major approaches** to structuring the inside: two-layer, layered
  (including the three-hexagon Domain/Application/Framework dialect),
  onion/clean, DDD, CQRS, and how SOLID maps onto the pattern;
- **domain modeling**: entities, value objects, aggregates, specifications;
- a **single sanctioned error flow**: typed domain errors from one root,
  foreign errors wrapped exactly once at the driven adapter, mapped to
  transport exactly once at the boundary;
- a **catalog of adoption strategies** (module-first, domain-first,
  layer-first, ports-first, walking skeleton, strangler, migration paths).

## Key features

### Neutral by contract — on three axes

The skill's fixed core is small and non-negotiable: keep the app pure, point
every dependency inward, and let errors cross the boundary exactly once in
each direction. Everything beyond that core is deliberately left open — the
skill is **neutral by contract** on three axes:

1. **Languages and frameworks.** The rules hold for any stack, DI container,
   HTTP engine, ORM, or message broker — nothing in the skill assumes a
   particular language or framework. The concrete mechanics come from
   companion skills: pair it with a language skill (e.g.
   `typescript-coding`) and, where relevant, a framework skill (e.g.
   `typescript-nestjs`).
2. **Approaches.** The pattern itself fixes only the boundary — what is
   inside the hexagon and what is outside. How the *inside* is structured
   (strict two-layer, layered, onion/clean, DDD) is an approach choice, and
   the skill does not impose one: it describes them all, with their
   trade-offs, in [references/approaches.md](references/approaches.md), and
   applies whichever one your codebase or rules use.
3. **Projects.** The concrete **adoption strategy** — module-first,
   domain-first, layer-first, or ports-first layout; walking-skeleton or
   strangler rollout; port granularity; binding mechanics — is a project
   decision. The skill requires it to be declared in the rules of the host
   project where the skill is used, and those rules always take precedence
   over the skill. The catalog of known strategies to choose from lives in
   [references/strategies.md](references/strategies.md).

In practice this means the skill never fights your stack or your layout: it
enforces the pattern's invariants and defers every open choice — first to
your project rules, then to the conventions already in the code. That is
also why declaring a strategy in your rules matters so much (see
[Using it with your project rules](#using-it-with-your-project-rules)).

### Progressive disclosure

`SKILL.md` is a short router; deep material lives in `references/` and is
read only when the matching task comes up (architecture canon, approaches,
domain modeling, strategies, error flow, boundary I/O, a step-by-step
feature checklist).

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/hexagonal-service
uv run skillctl install hexagonal-service --target ~/work/my-project --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install hexagonal-service --target ~/work/my-project --agent codex

# no uv? plain python works the same
python scripts/skillctl.py install hexagonal-service --target ~/work/my-project --agent claude
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in the project's
`.agent-skills.lock.yaml`.

## Using it with your project rules

This skill is intentionally incomplete without the host project: it refuses
to invent a directory layout, port granularity, or DI mechanics. Declare
those in your project rules (for Claude Code: `.claude/rules/` or
`CLAUDE.md`; for other harnesses: `AGENTS.md` or their rules location), for
example:

```markdown
<!-- .claude/rules/architecture.md -->
# Hexagonal strategy
- Layout: module-first — src/modules/<name>/{domain,application,adapters}
- Port granularity: one port per actor intention
- Binding: composition root in src/main.ts; no framework imports in domain/
```

How the pieces interact:

- **Project rules declare, the skill enforces.** The skill supplies the
  invariants (dependencies point inward, thin adapters, single error path);
  your rules pick one concrete strategy from
  [references/strategies.md](references/strategies.md). That file also lists
  exactly what a project should declare.
- **No declared strategy?** The agent infers the de-facto layout from the
  existing code, follows it, and proposes recording it in your rules — it
  never invents a new layout. Save everyone time and declare it up front.
- **Conflicts resolve toward the project.** Anything your rules say overrides
  this skill.

## Works well with

- `typescript-coding` — language-level discipline (this skill stays
  language-neutral);
- `typescript-nestjs` — NestJS mechanics for a hexagonal service; it presumes
  this skill for the layer model.
