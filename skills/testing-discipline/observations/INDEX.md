# Observations — testing-discipline

Confirmed observations from real usage of this skill: recurring failures,
success conditions, harness differences, edge cases, measurable results.

Lifecycle (enforced by `skillctl` and validation):

1. `skillctl observation add testing-discipline --from <file>` creates a
   **candidate** in `candidates/` — never edit `accepted/` directly.
2. A human reviews the candidate and its evidence, then runs
   `skillctl observation approve|reject testing-discipline <id> --reviewed-by <name>`.
3. Accepted observations may later be **promoted** into `knowledge/` or the
   SKILL.md workflow — as a separate, reviewable change.

Reading rules for agents:

- consult `accepted/` only when diagnosing a known edge case or improving the
  skill — not as part of the normal workflow;
- an observation is evidence, **not** a normative rule; rules live in
  SKILL.md and `references/`;
- candidates and rejected observations are development-only content and are
  not installed in runtime mode.

## Accepted observations

- [OBS-20260808-001](accepted/OBS-20260808-001.md) — rule 12 ("exercise the
  production wiring") and the hygiene coverage guidance both approached a
  pure wiring/DI line's evidence direction and neither stated it: such a line
  has no return value of its own, so coverage from a pre-existing, unrelated
  test is not evidence that it is protected (field report from a consuming
  project; C3, five occurrences across five consecutive tasks in two
  distinct modules, plus a deterministic, project-independent minimal
  reproduction; reviewed by HC-AGENT-010, 2026-08-08, provisional pending PR
  merge by the operator).

## Candidates awaiting review

(none)
