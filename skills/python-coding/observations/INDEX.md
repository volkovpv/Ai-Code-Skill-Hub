# Observations — python-coding

Confirmed observations from real usage of this skill: recurring failures,
success conditions, harness differences, edge cases, measurable results.

Lifecycle (enforced by `skillctl` and validation):

1. `skillctl observation add python-coding --from <file>` creates a
   **candidate** in `candidates/` — never edit `accepted/` directly.
2. A human reviews the candidate and its evidence, then runs
   `skillctl observation approve|reject python-coding <id> --reviewed-by <name>`.
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

- [OBS-20260814-001](accepted/OBS-20260814-001.md) — "wrap at most once, preserve the
  cause" and "report with the stack, `__cause__` included" are each correct read alone,
  but compose into a disclosure channel once the wrapped cause is a third-party
  validation/parsing exception that echoes the rejected input in its own `str`/`repr`
  (field report from a consuming project; C3, occurrences: 1, `SFL-INV-08` met via the
  deterministic, project-independent minimal-reproduction limb; reviewed by
  HC-AGENT-010, 2026-08-14, provisional pending PR merge by the operator).
