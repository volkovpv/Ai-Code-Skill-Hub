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
- [OBS-20260826-001](accepted/OBS-20260826-001.md) — the cleanup rule in
  `adapters-and-persistence.md` ("clean persistent state at the start of a
  test") was stated without the ownership precondition its own reasoning
  depends on, even though `schools.md`, in the same skill, already defines
  the Shared/Out-of-process/Unmanaged archetype the rule silently assumed
  away — and the neighbouring rejection of rollback isolation closed the one
  cheap mechanism that would have made the rule safe over such a store,
  without naming a replacement (field report from a consuming project; C3,
  two independent occurrences across two different tasks, plus a
  deterministic, project-independent minimal reproduction; reviewed by
  HC-AGENT-010, 2026-08-26, provisional pending PR merge by the operator).
- [OBS-20261007-001](accepted/OBS-20261007-001.md) — the interaction-precision
  rules argued only one direction (an over-tight match is a false positive);
  they were silent on the opposite one: a negative call assertion ("this call
  never happened") pinned to a full argument list can no longer fail once the
  callee's signature grows, with no compile or run signal, and no rule asked
  to re-observe such assertions (field report from a consuming project; C3,
  one occurrence plus a deterministic, project-independent minimal
  reproduction; reviewed by the consuming project's Reviewer, 2026-10-07,
  provisional pending PR merge by the operator).

## Candidates awaiting review

(none)
