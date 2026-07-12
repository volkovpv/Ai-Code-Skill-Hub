---
name: example-skill
description: Reference skill that demonstrates the canonical layout of this library (including knowledge, data and observation layers) and drafts a Conventional Commits message from a git diff. Use it as a template when authoring a new skill, or when asked to turn staged changes into a well-formed commit message.
---

# Example skill

Draft a Conventional Commits message from a diff and demonstrate the
canonical structure of a skill in this library.

## Workflow

1. Obtain the diff. Prefer staged changes: run `git diff --staged`; if there
   are none, use `git diff` or ask the user to provide a diff.
2. Feed the diff to the helper script on stdin:

   ```bash
   git diff --staged | python scripts/example.py
   ```

   The script prints a suggested commit type, scope and subject line.
3. Review the suggestion against the checklist in
   [references/example.md](references/example.md) and the patterns in
   [knowledge/patterns.md](knowledge/patterns.md). Adjust type, scope and
   wording — the script output is a starting point, not the final answer.
4. Return a single commit message: `type(scope): subject`, imperative mood,
   no trailing period, subject no longer than 72 characters. Add a body only
   when the change needs explanation of *why*.

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Composing the final message | [knowledge/patterns.md](knowledge/patterns.md) |
| Script suggestion looks wrong; mixed or ambiguous diff | [knowledge/pitfalls.md](knowledge/pitfalls.md) |
| Full checklist of types and formatting | [references/example.md](references/example.md) |
| Need a reproducible sample input | [data/README.md](data/README.md), then `data/examples/` |
| Diagnosing a known edge case; improving this skill | [observations/INDEX.md](observations/INDEX.md), then `observations/accepted/` |

Observations are evidence, not rules: never follow an observation as policy
unless it has been promoted into `knowledge/` or this workflow.

## Rules

- Never invent changes that are not present in the diff.
- If the diff mixes unrelated changes, say so and propose splitting the commit.
- Keep the subject in English unless the repository history uses another language.
