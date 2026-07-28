# testing-discipline

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Gives an AI coding agent a **universal test-writing standard** — one that
holds in any language, with any test runner, on any platform. Once
installed, the agent applies it whenever it writes, reviews, or reworks
tests, whatever the code under test is written in.

The core discipline it enforces:

- tests land in the same change as the code, and every bug fix ships a
  regression test that fails before the fix;
- Arrange/Act/Assert, one scenario per test, names that state the
  behaviour and the condition, assertions that pin the expected error
  *and* its condition;
- unit tests touch nothing external; time is injected rather than slept
  through, and every awaited assertion carries a deadline;
- fakes are bound to the seams the code exposes, never to someone else's
  internals; patching is a justified last resort;
- a fake standing in for a system the project does not own has its
  contract pinned by a **live observation** of that system — never by
  re-reading a project norm, an RFC, or vendor documentation;
- properties that live in the product's own construction, or on the way
  *out* of a call, are exercised through the production factory or entry
  point, never through an instance the test assembled itself;
- case sets, subjects and dimensions come from the specification, never
  from the artifact under test: a healthy mutation score is not evidence
  of specification coverage, and a surviving mutation is evidence of a
  missing dimension;
- suite hygiene: no committed focus/skip markers, no test tuned to the
  gate, deterministic runs, test-only secrets.

## Key features

- **Universal by contract.** No language, runner, framework, mocking
  library or architecture is assumed. How a rule is *spelled* belongs to
  the host project and to the language standards; which rules apply
  belongs here.
- **Evidence-backed rules.** The load-bearing rules (external-system fake
  provenance, outbound substitution, wiring-level construction, case-set
  provenance) each ship a minimal, deterministic reproduction — they were
  written because a green suite hid a real defect, not because they sound
  prudent.
- **Progressive disclosure.** `SKILL.md` stays short and routes to four
  reference files: structure and naming, isolation and fakes, suite
  hygiene and case provenance, and the division of labour between static
  checks and tests.

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/testing-discipline
uv run skillctl install testing-discipline --target ~/work/my-project --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install testing-discipline --target ~/work/my-project --agent codex
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in `.agent-skills.lock.yaml`.

## Using it with your project rules

The skill covers *what makes a test worth having*; your project rules
cover the mechanics of your suite. Effective split:

- **Put in project rules:** the runner and its invocation, where tests
  live and how they are named for discovery, which fixtures/factories the
  project ships, how integration tests get their environment, the
  coverage or mutation thresholds the build enforces, and any deliberate
  deviations. Project instructions always take precedence over the skill.
- **Leave to the skill:** what a test must establish, what may be faked
  and how a fake's contract is justified, where cases come from, and the
  hygiene rules — no need to restate them in your rules; reference the
  skill instead ("test discipline: see the testing-discipline skill").

## Works well with

- `hexagonal-service` — which collaborator is faked at which seam in a
  ports-and-adapters codebase (wiring-level conventions live there, not
  here).
