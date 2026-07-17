# example-skill

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Two things at once:

1. **A working skill**: drafts a [Conventional Commits](https://www.conventionalcommits.org/)
   message from a git diff. The agent feeds `git diff --staged` to the
   bundled `scripts/example.py`, checks the suggestion against the skill's
   reference checklist and verified patterns, and returns a single
   well-formed `type(scope): subject` message.
2. **The reference skill of this library**: it demonstrates the full
   canonical layout — `SKILL.md` routing, `references/`, `scripts/`,
   `assets/`, plus all three optional layers (`knowledge/`, `data/`,
   `observations/`). Use it as the template when authoring your own skill.

## Key features

- **Deterministic helper script.** `scripts/example.py` runs offline, reads
  the diff from stdin, and suggests a commit type, scope, and subject; the
  agent treats it as a starting point, not the final answer.
- **Full layer model in miniature.** Verified `knowledge/` patterns and
  pitfalls, a `data/` contract with fixtures and examples, and reviewed
  `observations/` — the smallest complete example of how this library
  structures accumulated skill knowledge.
- **Honest limits.** The skill never invents changes absent from the diff
  and flags mixed diffs instead of guessing one commit type.

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/example-skill
uv run skillctl install example-skill --target ~/work/my-project --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install example-skill --target ~/work/my-project --agent codex
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in `.agent-skills.lock.yaml`.

## Using it with your project rules

The skill stays generic on purpose; your project rules (for Claude Code:
`.claude/rules/` or `CLAUDE.md`) tune it to the repository:

- **Declare your commit conventions**: allowed types and scopes (e.g. scopes
  = package names in a monorepo), subject language if your history is not in
  English, whether bodies/footers (`BREAKING CHANGE:`, issue refs) are
  required. Project rules always take precedence over the skill.
- **Wire it into your workflow**: if your rules define a commit or PR
  procedure, reference the skill from there ("draft the message with
  example-skill, then apply the scope table below") so both layers stay in
  sync.
- **As a skill-authoring template**: copy the structure (`skillctl new
  <name> --with knowledge,data,observations` scaffolds the same shape) and
  keep your own SKILL.md equally short — deep material belongs in
  `references/` and the layers.
