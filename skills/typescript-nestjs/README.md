# typescript-nestjs

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Teaches an AI coding agent the **NestJS mechanics of a hexagonal service** —
only what is specific to NestJS. Once installed, the agent applies it when
writing, reviewing, or refactoring NestJS code: modules, providers,
controllers, pipes, guards, interceptors, exception filters, config
namespaces, and NestJS tests.

The rules it enforces:

- DI tokens as named `unique symbol` constants (no string or anonymous
  tokens); use cases as plain classes assembled by factory providers, so the
  framework never leaks into the domain;
- controllers as pure mappers with a global `ValidationPipe` and
  class-validator request DTOs (unknown fields rejected);
- guards via `APP_GUARD` with `@Public` metadata; exception filters that log
  once and map domain errors to HTTP once (RFC 9457, masked 5xx);
- fail-closed env validation behind `@nestjs/config` — boot aborts on
  invalid environment;
- integration tests with `@nestjs/testing` and `overrideProvider` against
  ports, driven through the controller.

## Key features

- **Framework-only scope.** The layer model and error flow come from
  `hexagonal-service`, the language discipline from `typescript-coding`;
  this skill presumes both and adds only the NestJS-specific mechanics.
- **Self-check script.** `scripts/check_nest_conventions.py` is an offline,
  layer-aware heuristic checker the agent runs over changed files;
  suppressions require a rule code and a written reason
  (`// skill-check-ignore: NEST-DI-TOKEN -- <reason>`).
- **Calibrated fixtures.** `data/` holds checker input/output pairs;
  reviewed `observations/` document known limitations.

## How to install

Install the trio together — this skill expects the other two:

```bash
# Claude Code → <project>/.claude/skills/
uv run skillctl install typescript-coding  --target ~/work/my-project --agent claude
uv run skillctl install hexagonal-service  --target ~/work/my-project --agent claude
uv run skillctl install typescript-nestjs  --target ~/work/my-project --agent claude
```

(Use `--agent codex`, `--agent opencode`, etc. for other harnesses; installs
are recorded in the project's `.agent-skills.lock.yaml`.)

## Using it with your project rules

The skill is deliberately project-neutral: no version pins, no product
decisions. Your project rules (for Claude Code: `.claude/rules/` or
`CLAUDE.md`) complete the picture:

- **Declare the hexagonal strategy** required by `hexagonal-service`
  (layout, port granularity, binding mechanics) — this skill's DI and module
  rules plug into whatever layout your rules declare.
- **Pin project specifics** the skill leaves open: NestJS/library versions,
  module and file layout, your config namespaces, auth strategy details,
  health/metrics endpoints, and the exact `lint`/`test` commands to run.
- **Precedence:** project rules override this skill; this skill overrides
  nothing in the other two — the three compose, with the project on top.

## Works well with

- `hexagonal-service` — required conceptually: layers, ports, error flow;
- `typescript-coding` — required conceptually: strict typing and lint-clean
  discipline.
