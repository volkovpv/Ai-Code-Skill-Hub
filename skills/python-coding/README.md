# python-coding

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Gives an AI coding agent a **universal, strictly-typed Python standard** —
deliberately free of any framework, architecture, or library assumptions.
Once installed, the agent applies it whenever it writes, reviews, or
refactors Python (`.py`), whether application code, a library, a script, or
tests.

The core discipline it enforces:

- a strict static type checker (mypy `--strict` / pyright strict) whose
  configuration is never weakened to make a run pass; full annotations on
  the public surface, no `Any`, `cast()` only with a proven invariant;
- closed sets as enums or `Literal` unions, `NewType`-branded identifiers,
  `Final` constants, frozen dataclasses, read-only collection parameters;
- type design: tagged unions with exhaustive `match` closed by
  `assert_never`, invalid states unrepresentable, parse-don't-cast at
  runtime boundaries, `TypeVar`s only where they relate types, `Protocol`s
  as structural test seams;
- narrow `except` clauses, errors never swallowed, wrapping with
  `raise ... from` at most once at the source;
- lint-clean-first-time code: explicit boolean expressions,
  `x if x is not None else d` over `x or d`, no un-awaited coroutines and
  `gather` for independent awaits, no mutation of parameters, no mutable
  default arguments, no type/lint suppressions;
- centralized `os.environ` access, no `print()` in shipped code, no
  `assert` as runtime validation;
- tests land in the same change as the code; every bug fix ships a
  regression test.

## Key features

- **Universal by contract.** Every rule holds in any Python codebase; no
  framework or architecture is assumed. Architecture rules live in the
  companion `hexagonal-service` skill instead.
- **Self-check script.** `scripts/check_py_conventions.py` is an offline
  heuristic checker the agent runs over changed files before handing off;
  suppressions require a rule code and a written reason
  (`# skill-check-ignore: PY-ENV -- <reason>`).
- **Layered knowledge.** Beyond `references/` (typing & style, type design,
  generics & protocols, lint-clean, errors/config/logging, testing) the
  skill ships verified `knowledge/` patterns and pitfalls, and calibrated
  `data/` samples for the checker.

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/python-coding
uv run skillctl install python-coding --target ~/work/my-project --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install python-coding --target ~/work/my-project --agent codex
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in `.agent-skills.lock.yaml`.

## Using it with your project rules

The skill covers the *language*; your project rules (for Claude Code:
`.claude/rules/` or `CLAUDE.md`) cover the *project*. Effective split:

- **Put in project rules:** your actual commands (`lint`, `typecheck`,
  `test`), the logging seam to use instead of `print`, where env/config
  access is centralized, the schema library used at boundaries,
  naming/layout conventions, and any deliberate deviations (e.g. PEP 8
  truthiness for collections instead of explicit emptiness checks).
  Project instructions always take precedence over the skill.
- **Leave to the skill:** the typing discipline, error handling, lint-clean
  and testing rules — no need to restate them in your rules; reference the
  skill instead ("Python style: see the python-coding skill").
- The skill's checker is a backstop, not the authority: the agent still
  runs your project's real `lint`/`typecheck`/`test`, so make sure your
  rules say how.

One deliberate calibration to know about: the skill asks for explicit
boolean expressions (`is not None`, `!= ""`, `len(x) > 0`) where idiomatic
PEP 8 would accept bare truthiness — a strictness choice that keeps intent
visible. If your team prefers `if seq:` for collections, say so in the
project rules — they win.

## Works well with

- `hexagonal-service` — ports-and-adapters layering (architecture-bound
  rules live there, not here).
