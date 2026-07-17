# typescript-coding

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Gives an AI coding agent a **universal, strictly-typed TypeScript standard**
— deliberately free of any framework, architecture, or library assumptions.
Once installed, the agent applies it whenever it writes, reviews, or
refactors TypeScript (`.ts`/`.mts`/`.cts`), whether application code, a
library, a script, or tests.

The core discipline it enforces:

- `strict: true` plus the hole-closing compiler flags; the configuration is
  never weakened to make a build pass;
- `as const` registries instead of native `enum`s, branded identifiers,
  `readonly` by default, explicit return types on exports;
- `unknown` in `catch` with narrowing, errors never swallowed, wrapping with
  `cause` at most once at the source;
- lint-clean-first-time code aimed at a strict stack (typescript-eslint
  strictTypeChecked, airbnb, SonarJS, functional, jsdoc): explicit boolean
  expressions, `??` over `||`, no floating promises, immutable data, no
  type/lint suppressions;
- centralized `process.env` access, no `console.*` in shipped code;
- tests land in the same change as the code; every bug fix ships a
  regression test.

## Key features

- **Universal by contract.** Every rule holds in any TypeScript codebase; no
  framework or architecture is assumed. Framework/architecture rules live in
  the companion skills instead.
- **Self-check script.** `scripts/check_conventions.py` is an offline
  heuristic checker the agent runs over changed files before handing off;
  suppressions require a rule code and a written reason
  (`// skill-check-ignore: TS-ENV -- <reason>`).
- **Layered knowledge.** Beyond `references/` (typing & style, lint-clean,
  errors/config/logging, testing) the skill ships verified `knowledge/`
  patterns and pitfalls, calibrated `data/` samples for the checker, and
  reviewed `observations/`.

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/typescript-coding
uv run skillctl install typescript-coding --target ~/work/my-project --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install typescript-coding --target ~/work/my-project --agent codex
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in `.agent-skills.lock.yaml`.

## Using it with your project rules

The skill covers the *language*; your project rules (for Claude Code:
`.claude/rules/` or `CLAUDE.md`) cover the *project*. Effective split:

- **Put in project rules:** your actual commands (`npm run lint`,
  `typecheck`, `test`), the logging seam to use instead of `console.*`,
  where env/config access is centralized, naming/layout conventions, and any
  deliberate deviations (e.g. a relaxed rule in test files). Project
  instructions always take precedence over the skill.
- **Leave to the skill:** the typing discipline, error handling, lint-clean
  and testing rules — no need to restate them in your rules; reference the
  skill instead ("TypeScript style: see the typescript-coding skill").
- The skill's checker is a backstop, not the authority: the agent still runs
  your project's real `lint`/`typecheck`/`test`, so make sure your rules say
  how.

## Works well with

- `hexagonal-service` — ports-and-adapters layering (architecture-bound
  rules live there, not here);
- `typescript-nestjs` — NestJS specifics on top of both.
