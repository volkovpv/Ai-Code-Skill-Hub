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

- [OBS-20260820-001](accepted/OBS-20260820-001.md) — the completeness-check rule
  covered only a set whose ground truth is already a value in this program (an
  `enum`, a `Literal` union) and was silent on a set owned outside it (a schema's
  foreign keys, another service's enumeration, a protocol's message types), so a
  registry or guard built by reading off the cases the code already handles
  reported full coverage of a set it never read, and a mutation battery — drawn
  from the same code — shared the blind spot rather than covering for it (field
  report from a consuming project; C3, one deterministic project-independent
  minimal reproduction, three consecutive gatekeeper failures on one shape before
  it was named; five passes untransferred for a routing question, resolved by an
  operator routing decision on 2026-08-20 placing the rule in the language
  standards because the failing artifact was production code, not a test;
  reviewed by the operator, 2026-08-20, provisional pending PR merge).

- [OBS-20260820-002](accepted/OBS-20260820-002.md) — the duplication survey's
  decision order listed "an environment-variable key" among the data a caller may
  legitimately differ by, without a condition; read literally it licenses a
  per-caller variable name, and two names for one role leave the shared resolver
  with nothing to be parameterized by, so the resolver is copied too and the copy
  is justified by the rule meant to collapse it (field report from a consuming
  project; C5 at the consumer, whose narrow universal core — separate processes
  read the same role name and each is handed its own value, a second name only
  where one process legitimately holds two principals — transfers on its own
  project-independent reproduction; reviewed by the operator, 2026-08-20,
  provisional pending PR merge).
- [OBS-20260814-001](accepted/OBS-20260814-001.md) — "wrap at most once, preserve the
  cause" and "report with the stack, `__cause__` included" are each correct read alone,
  but compose into a disclosure channel once the wrapped cause is a third-party
  validation/parsing exception that echoes the rejected input in its own `str`/`repr`
  (field report from a consuming project; C3, occurrences: 1, `SFL-INV-08` met via the
  deterministic, project-independent minimal-reproduction limb; reviewed by
  HC-AGENT-010, 2026-08-14, provisional pending PR merge by the operator).
- [OBS-20260818-001](accepted/OBS-20260818-001.md) — two grounds absent from DRY/security
  guidance: the duplication bullet in `lint-clean.md` is not backed by this stack's
  blocking linter at all, and the advisory line-based detector is blind to identifier
  renaming, so a green run does not confirm the rule; and no rule states that a
  defensive/parsing routine over untrusted input must be collapsed to the union of
  every caller's cases rather than duplicated per caller (field report from a
  consuming project; C3, `SFL-INV-08` met on both limbs; the detection-boundary claim
  re-executed live against `pylint` 4.0.6 `duplicate-code`/`R0801`; the original
  filing's overbroad "no implementation-level rule at all" claim was withdrawn on
  re-run and the verdict rests on the two narrower, corrected grounds; reviewed by
  HC-AGENT-010, 2026-08-18, provisional pending PR merge by the operator).
- [OBS-20260819-001](accepted/OBS-20260819-001.md) — `OBS-20260818-001` stated
  the detection boundary and the union-of-callers rule, both about a
  duplicate that already exists, but neither `## Workflow` nor `## Rules`
  ever told an author to search the tree by shape *before* writing a new
  implementation, so following the skill exactly still produced the copies
  the linter cannot see (operator direct-audit transfer, 2026-08-19,
  outside the ordinary `WF-STATE-013` pipeline; symmetric with a sibling
  skill's transfer in the same library on the same date; evidence inherited from
  `OBS-20260818-001`'s own measurement — 11 of 13 repository bodies
  byte-identical, a defensive parser in five independently maintained
  copies; reviewed by the operator, 2026-08-19, provisional pending PR
  merge).
