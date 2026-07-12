# Observations — example-skill

Confirmed observations from real usage of this skill: recurring failures,
success conditions, harness differences, edge cases, measurable results.

Lifecycle (enforced by `skillctl` and validation):

1. `skillctl observation add example-skill --from <file>` creates a
   **candidate** in `candidates/` — never edit `accepted/` directly.
2. A human reviews the candidate and its evidence, then runs
   `skillctl observation approve|reject example-skill <id> --reviewed-by <name>`.
3. Accepted observations may later be **promoted** into `knowledge/` or the
   SKILL.md workflow — as a separate, reviewable change.

Reading rules for agents:

- consult `accepted/` only when diagnosing a known edge case or improving the
  skill — not as part of the normal workflow;
- an observation is evidence, **not** a normative rule; rules live in
  SKILL.md and `knowledge/`;
- candidates and rejected observations are development-only content and are
  not installed in runtime mode.

## Accepted observations

- [OBS-20260712-001](accepted/OBS-20260712-001.md) — deletion-heavy fix
  diffs are classified as `refactor` (promoted to `knowledge/pitfalls.md`).
