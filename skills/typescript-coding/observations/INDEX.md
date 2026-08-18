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
- [OBS-20260726-001](accepted/OBS-20260726-001.md) — `references/testing.md`
  §Hygiene had no rule against a test's case set, subject, or dimensional
  coverage being chosen from the artifact under test rather than the
  specification (mirrored from a sibling skill's already-merged fix in the
  same library; source consumer occurrence: news-intel-docs RM-TASK-016;
  reviewed by HC-AGENT-010, 2026-07-26).
- [OBS-20260727-001](accepted/OBS-20260727-001.md) — `references/testing.md`
  said *what* to fake but not how a fake's own return values become known to
  be true of an external system, so a double for a third-party seam could
  stay green while encoding a wrong belief about that system's runtime
  behaviour (mirrored from a sibling skill's already-merged fix in the same
  library; source consumer occurrence: news-intel-docs RM-TASK-017; reviewed
  by HC-AGENT-010, 2026-07-27).
- [OBS-20260728-001](accepted/OBS-20260728-001.md) — the same rule's scope
  sentence named only a fake's *return values*, leaving two adjacent shapes
  unrecognisable: a value the real layer substitutes on the way **out** of a
  call (no return value to inspect at all), and a construction/wiring
  assertion taken at a hand-built collaborator instead of the production
  factory (mirrored from a sibling skill's already-merged fix in the same
  library; source consumer occurrence: news-intel-docs RM-TASK-019; reviewed
  by HC-AGENT-010, 2026-07-28).

- [OBS-20260801-001](accepted/OBS-20260801-001.md) — the JSDoc section said
  which symbols must carry a block and what not to put in it, but never that
  only a two-asterisk `/** */` block is read at all: the same tags in `//`
  line comments, or in a single-star block, are inert and no tool in the
  stack reports it (field report from a consuming project; the claim
  re-executed locally against the compiler in three limbs; reviewed by the
  operator, 2026-08-01).
- [OBS-20260818-001](accepted/OBS-20260818-001.md) — the duplication bullet
  named four SonarJS/ESLint rules and stopped at "factor the shared body
  out", with no statement that all four are same-file, textual-identity
  checks — renaming even one identifier silences them inside a single file,
  and none ever compares two different files, so a fully green lint run is
  not evidence that a repeated implementation is absent (field report from a
  consuming project; C3, SFL-INV-08 met on both limbs; the rule-scope claim
  re-executed live against eslint 10.7.0 + eslint-plugin-sonarjs 4.2.2;
  reviewed by HC-AGENT-010, 2026-08-18, provisional pending PR merge by the
  operator).

## Candidates awaiting review

- `OBS-20260713-001` (`candidates/`, development-only — not shipped in a
  `runtime` install, see the reading rules above) — the convention checker
  over-reports `process.env` access when it has no file path for context
  (reproducible evidence attached; not yet reviewed, not promoted anywhere).
