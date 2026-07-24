# Observations — typescript-coding

Confirmed observations from real usage of this skill: recurring failures,
success conditions, harness differences, edge cases, measurable results.

Lifecycle (enforced by `skillctl` and validation):

1. `skillctl observation add typescript-coding --from <file>` creates a
   **candidate** in `candidates/` — never edit `accepted/` directly.
2. A human reviews the candidate and its evidence, then runs
   `skillctl observation approve|reject typescript-coding <id> --reviewed-by <name>`.
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

- [OBS-20260715-001](accepted/OBS-20260715-001.md) — `TS-SUPPRESS` leaves no
  green path for a justified single-rule line-scoped `eslint-disable` working
  around a documented upstream lint-rule limitation (transferred from the
  news-intel consumer; deterministic fixture attached; reviewed by the
  operator, 2026-07-15).
- [OBS-20260724-001](accepted/OBS-20260724-001.md) — shipped prose linked into
  `data/fixtures/*` and this very index linked into `candidates/`, both
  stripped by a `runtime` install (transferred from the news-intel consumer;
  reviewed by the operator, 2026-07-24).

## Candidates awaiting review

- `OBS-20260713-001` (`candidates/`, development-only — not shipped in a
  `runtime` install, see the reading rules above) — the convention checker
  over-reports `process.env` access when it has no file path for context
  (reproducible evidence attached; not yet reviewed, not promoted anywhere).
