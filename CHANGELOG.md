# Changelog

Versions follow SemVer. The first entry of this file always matches the current
version in `pyproject.toml` — enforced by the `scripts/check_version_drift.py`
gate. Entry header format: `## [X.Y.Z] — YYYY-MM-DD`; the entry body becomes
the GitHub release notes (extracted by `.github/workflows/release.yml`).

## [3.12.0] — 2026-08-19

`typescript-coding` `1.11.0 → 1.12.0`, `python-coding` `1.9.0 → 1.10.0`

### The gap

An operator-triggered SFL transfer (`OBS-20260819-001` in both skills, C3-universal;
not routed through the ordinary `WF-STATE-013` pipeline — the occasion was a direct
operator audit of a consuming project's build). `OBS-20260818-001` (`3.10.0`/`3.11.0`,
PR #24) had already added the *negative* half of the duplication story to both
skills: what the after-the-fact detection tooling does and does not catch. Neither
skill's `## Workflow` ever gained the *positive* half — a step telling an author to
search the tree, by shape, **before** writing a new implementation. Measured on one
live TypeScript service tree (293 files, rename-tolerant structural fingerprint): a
prior de-duplication task had already extracted three shared pieces of logic into a
common module and still left the scaffold standing in ten independently maintained
configuration modules, two of them token-identical after renaming even after that
extraction; five access-guard files differed only in class name; the correct
collapsed shape already existed one directory away, unused as an example. The Python
plane's own already-recorded measurement (`OBS-20260818-001`) shows the same
underlying cause: 11 of 13 repository bodies byte-identical, a defensive parser in
five independently maintained copies.

### What changed

- **`SKILL.md`** (both skills) — a new `## Workflow` step 1, "Survey before you
  write," ahead of the typing step; a new `## Rules` bullet stating the decision
  order (extend → call → parameterized factory at the third occurrence → new file
  only once the search comes back empty); a new `## Routing` table row.
- **`references/duplication-survey.md`** (both skills, new file) — the search
  procedure (by shape, never by name), the decision order, and the two invariants a
  safe collapse must preserve (per-caller fail-closed test coverage; the union, never
  a pick, of every caller's cases for a routine defending untrusted input — for
  `python-coding` this cross-links the union rule `OBS-20260818-001` already put in
  `references/security.md` rather than restating it).
- **`references/lint-clean.md`** (both skills) — the existing duplication bullet
  gained one cross-link sentence to the new survey file: it is the after-the-fact
  check, the survey file is what runs before.
- **`__test__/evals/typescript-coding/cases.json`** and
  **`__test__/evals/python-coding/cases.json`** — two new cases each (23 total for
  `typescript-coding`, 32 for `python-coding`): one `behavior` case (extend/call the
  existing home instead of writing a renamed duplicate), one `negative` guard (the
  survey step must not be read as blocking a genuinely new capability once the search
  comes back empty).

### How the change was made

Test first: `TestDuplicationSurveyGuidance` in both skills' test modules pins the new
`## Workflow` step, the `## Rules` bullet, the routing-table row, every section of the
new reference file, and the cross-link sentence in `lint-clean.md` — 18 of 20
assertions red before the delta (verified by temporarily reverting the content files
while keeping the tests), green after. Negative guards confirm `OBS-20260818-001`'s
own delta in both skills survives untouched, and that the new file cross-links rather
than restates the pre-existing union-of-callers rule in `python-coding`'s
`security.md`. A further guard pins that the evidence section carries the measured
facts and carries no project name, framework name, or path from the reporting
project's repository — the two skills stay universal.

Deliberately out of scope: the bundled convention checkers
(`scripts/check_conventions.py`, `scripts/check_py_conventions.py`) already have no
structural, cross-file duplicate-detection capability (`OBS-20260818-001`); this delta
does not add one — it addresses the moment before a duplicate is written, which no
static checker can reach.

`uv run skillctl validate && uv run skillctl test`: `997/997` passed, exit 0.

## [3.11.0] — 2026-08-18

`python-coding` `1.8.0 → 1.9.0`

### The gap

A field report from a consuming project (`OBS-20260818-001`, C3, several independently
occurring clusters across unrelated tasks, `SFL-INV-08` met on both limbs). The original
filing claimed the skill states no implementation-level duplication rule at all; that
claim was **false as stated** — `references/lint-clean.md` already carries "no
duplicated or identical branches, conditions, or functions — factor the shared body
out," unscoped. Had that been the whole gap it would be C2 (a project tightening an
already-correct rule), not C3. Two things remain genuinely absent, independent of any
project's rules: (a) nothing states that this stack's blocking linter (`ruff`) carries
no rule of this class at any configuration, and that the advisory line-based detector
that does exist for it (`pylint`'s `duplicate-code`/`R0801`) is blind to identifier
renaming — re-executed live, a cross-module copy with five identifiers renamed scores
`10.00/10`, zero findings, while the verbatim control fires as expected; (b) no rule
states that a defensive/parsing routine standing over untrusted input (e.g. model
output) must be collapsed to the union of every caller's cases rather than duplicated
per caller, each covering only what its own author tested against.

### What changed

- **`references/lint-clean.md`** — the duplication bullet gained a clause naming the
  detection boundary: not backed by the blocking linter, and the advisory detector is
  blind to renaming, so a green run does not confirm the rule.
- **`references/security.md`** — a new section, "A defensive routine over untrusted
  input has one home, the union of every caller's cases," added to the Contents ToC.
- **`SKILL.md`** — the lint-clean and untrusted-input `Rules` bullets each gained one
  pointer clause to the corresponding new guidance.
- **`__test__/evals/python-coding/cases.json`** — four new cases (26 → 30): two
  `behavior` cases (a renamed duplicate still needs extraction despite clean blocking
  lint; a defensive parser over untrusted input needs one shared, union-covering home),
  two `negative` false-positive guards (an exact cross-module copy is still credited as
  caught by the duplicate-code detector; a single-caller validator is not flagged as
  needing to anticipate callers that do not exist).
- The skill's `stable` gate-bar comment in `skills.yaml` now flags the case count as
  unmeasured against the declared bar since this addition.

### How the change was made

Test first: a regression pinning the new clause text in `references/lint-clean.md` and
the new section in `references/security.md`, plus both `SKILL.md` pointer clauses (5 of
7 assertions red before the delta, green after), plus a stdlib-only reproduction of the
union-rule failure mode (two independently-maintained copies of a parser, each patched
only for its own caller's historical case) confirmed genuinely failing on the
unpatched-copy leg before the delta and unaffected by it after. Minimal delta: one
extended bullet in `lint-clean.md`, one new section in `security.md`, two pointer
clauses in `SKILL.md`. Negative/false-positive-guard assertions confirm the adjacent
pre-existing rules in both reference files are untouched and not duplicated.

Deliberately out of scope: teaching the bundled convention checker
(`scripts/check_py_conventions.py`) to detect cross-file or renamed duplication itself
— a structural, cross-file comparison its current per-file design does not do.


## [3.10.0] — 2026-08-18

`typescript-coding` `1.10.0 → 1.11.0`

### The gap

A field report from a consuming project (`OBS-20260818-001`, C3, several independently
occurring clusters across unrelated tasks weeks apart, `SFL-INV-08` met on both limbs):
the "No duplicated or identical branches, conditions, or functions" bullet names four
SonarJS/ESLint rules and stops at "factor the shared body out", with no statement of
what those rules actually cover. Re-executed against `eslint` 10.7.0 +
`eslint-plugin-sonarjs` 4.2.2 on a four-file scratch tree outside this library: all four
rules are same-file, textual-identity checks — renaming so much as one identifier
silences them even inside a single file, and none of the family ever compares two
different files. A project whose only duplication discipline is this skill's guidance
can run its lint stack fully green while an identical implementation, renamed and/or
moved to another file, sits undetected — the gap is the false assurance, not merely the
missing rule.

### What changed

- **`references/lint-clean.md`** — the duplication bullet gained a scope statement
  naming what the four cited rules do and do not catch, plus the obligation the census
  shows actually matters: an identical implementation has exactly one home regardless of
  which file it lives in.
- **`SKILL.md`** — the corresponding `Rules` bullet gained one pointer clause to the new
  scope note.
- **`__test__/evals/typescript-coding/cases.json`** — two new cases (19 → 21): one
  `behavior` case pinning that a renamed, cross-file duplicate still needs extraction
  despite a green lint run; one `negative` false-positive guard confirming an exact,
  unrenamed, same-file duplicate is still credited as caught by the linter itself.
- The skill's `stable` gate-bar comment in `skills.yaml` now flags the case count as
  unmeasured against the declared bar since this addition, rather than silently carrying
  a stale count.

Deliberately out of scope: teaching the bundled convention checker
(`scripts/check_conventions.py`) to detect cross-file or renamed duplication itself —
that is a structural, cross-file comparison the checker's current lexical/AST-per-file
design does not do, and reworking it is not a delta-sized change.

## [3.9.0] — 2026-08-14

`python-coding` `1.7.0 → 1.8.0`

### The gap

A field report from a consuming project (`OBS-20260814-001`, C3, occurrences: 1,
`SFL-INV-08` met via the deterministic, project-independent minimal-reproduction limb):
"wrap at most once, preserve the cause" and "report with the stack, `__cause__`
included" are each correct read alone, but compose into a disclosure channel the moment
the wrapped cause is a third-party validation/parsing exception that echoes the rejected
input in its own `str`/`repr` for debuggability — a careful author can satisfy both
rules individually, including keeping the wrapper's own message deliberately name-only
and value-free, and still leak the value through the chained cause's own text once the
full chain reaches a log sink. Neither rule named the interaction.

### What changed

- **`references/errors-config-logging.md`** — a new clause under "Report with the
  stack" naming the composition explicitly and offering two remedies: do not log
  `__cause__` at that boundary and log only the wrapper's own scrubbed message, or
  re-render the cause through the project's own log-scrubber before it reaches any sink
  governed by "report with the stack."
- **`SKILL.md`** — the exception-handling Rules bullet gained one clause pointing to the
  new guidance.
- **`__test__/evals/python-coding/cases.json`** — two new cases (24 → 26): one
  `behavior` case pinning that a chained validation error must not reach a log sink
  unscrubbed, one `negative` false-positive guard confirming an ordinary internal
  exception's chained-and-logged cause is not flagged as a leak.
- The skill's `stable` gate-bar comment in `skills.yaml` now flags the case count as
  unmeasured against the declared bar since this addition, rather than silently
  carrying a stale count.

## [3.8.0] — 2026-08-08

`testing-discipline` `1.6.0 → 1.7.0`

### The gap

A field report from a consuming project (`OBS-20260808-001`, C3, five occurrences across
five consecutive tasks in two distinct modules, plus a deterministic, project-independent
minimal reproduction): a line whose entire content is a wiring/DI decision — a factory
call, the registration of its result — has no return value of its own, so line/branch
coverage reports it as protected the moment *any* test executes it, including a
pre-existing test that boots the real startup path for an unrelated reason and reaches
the line only as a side effect. Deleting the line reddened no test. Rule 12 ("exercise the
production wiring, not a hand-built copy of it") and the hygiene coverage guidance ("use
coverage to find untested areas, not as a target") both approach this from adjacent
angles and neither told an author how to detect it — the test satisfied rule 12's letter
while proving nothing about the new line.

### What changed

- **`references/isolation-and-fakes.md`** — a new section, "A pure wiring/DI line has no
  return value for coverage to protect": coverage produced by an unrelated test is not
  evidence for such a line; the regression check is a targeted mutation of the line,
  verified by a fake/spy at the collaborator's own construction seam, asserting the call,
  its argument, and — where the mounted resource owns teardown — that the teardown was
  registered.
- **`SKILL.md`** — rule 12 gained one clause naming the same distinction, and the `Rules`
  section gained one bullet stating it in imperative form.
- **`__test__/evals/testing-discipline/cases.json`** — two new cases (40 → 42): one
  `behavior` case pinning that a wiring line covered only by an unrelated test is not
  sufficient, one `negative` false-positive guard confirming a wiring line with its own
  targeted spy test is *not* flagged.
- The skill's `stable` gate-bar comment in `skills.yaml` now flags this content as
  unmeasured against the declared bar (`scripts/run_skill_evals.py --tier gate --repeat 3`
  pending) rather than silently carrying a stale case count.

## [3.7.0] — 2026-08-05

Model vendors become first-class: a registry, one adapter per vendor in every
skill, and an eval gate that names the environment it is green on.

`example-skill` `0.2.1 → 0.3.0` · `hexagonal-service` `2.2.0 → 2.3.0` ·
`python-coding` `1.6.0 → 1.7.0` · `testing-discipline` `1.5.0 → 1.6.0` ·
`typescript-coding` `1.9.0 → 1.10.0` · `typescript-nestjs` `1.2.0 → 1.3.0`

### The gap

A green eval gate recorded the model and the effort level it ran at, but not
the vendor those belonged to — so "green" pointed at an environment that was
only half named. Worse, the list of allowed effort levels was frozen in
`scripts/run_skill_evals.py`, which made it a statement about one supplier
written as if it were universal, and left no way to notice that a declared
model rejects the effort parameter altogether.

### What changed

- **`vendors.yaml`** — a new root registry of vendors, their models and the
  effort levels each model accepts, with the state of each vendor's
  documentation sync. It is library data: never installed into a consumer, and
  changing it does not require a project version bump.
- **`skillctl vendor`** — `list`, `show`, `add-model`, `refresh`, `apply`,
  `check`. The library still makes no network call: `refresh` prints the sync
  plan and `apply` records the answer someone with network access brings back.
  There are two sanctioned reasons to go to a vendor's documentation — a newly
  registered model, or an explicit operator request — and `refresh` fails
  without a reason from that closed set and a named reviewer.
- **`skillctl vendor check`** (also a CI step) fails on a pending sync for a
  vendor marked `in_use: true`, on a sync older than the newest model
  registered for it, and on any adapter or eval tier naming a vendor or model
  the registry does not know. Vendors declared as groundwork are reported as
  pending and block nothing.
- **Adapters** — every skill now carries one `agents/<vendor>.yaml` per
  declared vendor, checked in both directions by `skillctl validate`. An
  adapter holds interface wiring only (`display_name`, `short_description`,
  `default_prompt`); a rule inside one is now a validation error, since it
  would bind a single vendor. There is deliberately no `vendors/` directory
  inside a skill.
- **Eval manifests** — each tier declares `vendor` alongside `model` and
  `effort`, all three required and all three resolved against the registry. An
  unknown vendor, an unknown model, a model belonging to another vendor, or a
  level that *model* does not accept is a manifest error rather than a silent
  fallback, and `--model`/`--effort` overrides are held to the same registry.
  The `RUN` header now names the vendor, and the effort environment variable
  scrubbed from the harness comes from the vendor entry.
- **First sync of all five vendors** — recorded on 2026-08-05 against each
  vendor's own documentation. Four of the five carried a wrong fact:

  | Vendor | What the sync corrected |
  |---|---|
  | anthropic | `claude-haiku-4-5` takes no effort level at all — the cheap `debug` tier of all six manifests had been declaring exactly that pair, and now runs on a model that accepts the dial |
  | openai | the default is `medium`, not `none` |
  | google | the default is per model, not per vendor; `gemini-3.1-flash-lite` defaults to `minimal`. Three newer general-purpose models registered |
  | deepseek | the field is nested — `thinking.reasoning_effort`, not top-level; `low` does exist (`medium` does not); `deepseek-chat` and `deepseek-reasoner` were retired on 2026-07-24 |
  | xai | confirmed unchanged (`reasoning.effort`, `low…xhigh`, default `high`; `xhigh` on the multi-agent model sets the agent count, not the depth) |

  `gpt-5.2` is the one row left `verified: false`: its level set is confirmed
  (no `max`), its own default is not documented anywhere reachable.
- **Feedback-loop rules** (`AGENTS.md`) — an observation records the vendor,
  model and effort it was seen on; proved for one vendor is not proved for
  another; a new model triggers a documentation sync and a re-measurement, not
  a rule rewrite; a behavioural difference between vendors is an observation,
  never a per-vendor branch in `SKILL.md`.
- The language gate additionally exempts the untracked `_promts/` working area,
  alongside `_audit/` and `_temp/`.

## [3.6.0] — 2026-08-01

`typescript-coding` `1.8.0 → 1.9.0` — JSDoc has exactly one parsed form, and
the skill now says so.

### The gap

The skill's JSDoc section stated which symbols must carry a block and what
must not be restated inside it, but never what makes a comment a block at all.
A field report from a consuming project found the consequence: a `@typedef`
written with `//` line comments is inert — the compiler, the language service,
the declaration emit and `eslint-plugin-jsdoc` all skip it, and none of them
reports the mistake, so the type check the author believed they had written
never ran. The reporting side classified it as a real defect rather than a
style deviation, which is what it is: an inert `@typedef` or `@type` takes a
check away with it.

Re-executed against the compiler before the rule was written (TypeScript
6.0.3, Node 26): under `checkJs`, `// @typedef …` + `// @type {User}` above
`const u = { id: 1 };` compiles without the `TS2322` the same two tags in a
`/** */` block report; the single-star `/* */` form yields no diagnostic at
all; and under `--declaration` a `//` description above an export is dropped
from the emitted `.d.ts` while a `/** */` one is carried into it.

### The delta

- `references/lint-clean.md` — one rule bullet in "JSDoc on the public
  surface": JSDoc is a block-comment format (`/**` … `*/`), the two other
  forms are silently inert rather than mis-styled, comment form is decided per
  directive (`// @ts-expect-error` genuinely does work as a line comment), and
  an annotation is confirmed by its effect, never by its presence.
- `knowledge/pitfalls.md` — the failure mode with its re-executable
  reproduction and the reason nothing in the stack catches it; the file
  crossed 100 lines and gained the required table of contents. Routed from
  `knowledge/INDEX.md`.
- Observation `OBS-20260801-001` accepted, with the compiler run, the
  pre-change inspection and the regression as evidence.
- Regression `TestJsdocCommentFormGuidance` in
  `__test__/skills/test_typescript_coding.py` (5 of 6 assertions red against
  the pre-change text) pins the rule's load-bearing clauses, the pitfall's
  evidence, the one-home rule for the reproduction, a negative guard that both
  pre-existing JSDoc rules survive, and that the new table of contents lists
  every pitfall. Two eval cases added — one behavioural, one negative guarding
  against turning line-comment directives into JSDoc blocks.
- `docs/history.{eng,rus}.md` — one new entry, "A comment that looked like an
  annotation".

Deliberately out of scope: teaching the bundled convention checker to flag the
inert form. It is lexically detectable, but the checker masks comment
delimiters before any rule runs, so it would mean reworking that masker — a
change to an analyzer under mutation scope, to be raised on its own evidence.

## [3.5.1] — 2026-07-29

No skill rule changed in this release. What changed is how much of those rules
the gate actually covers, and what the word "stable" next to them is backed by.

### Gate coverage for the four skills that had stopped growing

Their case sets had not moved since the skills were first published, while the
skills themselves had: `hexagonal-service` went 1.0 → 2.2.0 (gaining
`approaches.md`, `domain-modeling.md` and `strategies.md`) on the same 7 cases,
`typescript-coding` collected five accepted observations on the same 7,
`typescript-nestjs` kept its original 6, and `python-coding` handed its test
cases to `testing-discipline` in 3.4.0 without replacing them. Whole reference
files — adoption strategies, domain modeling, generics, security, concurrency,
runtime correctness, config and observability — had no case at all.

47 cases were added, one per rule left uncovered: `hexagonal-service` 7 → 22,
`python-coding` 10 → 24, `typescript-coding` 7 → 17, `typescript-nestjs`
6 → 14.

### The bar they are stable on is measured, not asserted

`skills.yaml` said only that they "passed the eval-gate" — no date, no tier, no
repeat count, no score; the tier mechanism (3.5.0) landed after those
promotions, so the green they stood on named no model/effort pair at all. All
four are now measured with `--tier gate --repeat 3` (`claude-sonnet-5`, effort
`medium`) on the same bar as `testing-discipline`: **every case passes at least
2 of 3 attempts** — 226 of 231 attempts, five cases at 2/3. The per-skill
scores and the cases sitting at 2/3 are recorded in `skills.yaml` next to each
entry rather than left to memory.

### Three `conflict-*` cases were flaky by construction

Each pointed at a `CLAUDE.md` or ADR file that the harness's temporary project
never creates, so a run could go looking for it, fail to find it and refuse the
premise, or stop to ask for permission to write files — measuring the harness,
not the skill. They now state the team decision as given, forbid the file
lookup, and ask for code in the answer; all three moved to 3/3.

Five oracles were corrected the same way, after reading what the harness
actually answered: `secrets.compare_digest` is the same function as
`hmac.compare_digest`, a containment check may be spelled with `commonpath` or
`.parents`, a `catch (cause)` binding is already `unknown` under strict mode
without saying so, and two patterns demanded vocabulary a correct answer need
not use.

## [3.5.0] — 2026-07-29

### `testing-discipline` is stable

The skill was draft "until the eval-gate runs against a real harness". It has
now run four times against a live one, and the bar it is promoted on is
recorded in `skills.yaml` next to the entry rather than left to memory: **every
one of the 40 cases passes at least 2 of 3 attempts on the gate tier
(`claude-sonnet-5`, effort `medium`)** — measured 118/120, with two cases at
2/3.

The bar is per-case majority, not a clean sweep. A single `--repeat 1` run is
what it replaces: across this release's runs the one-shot result moved between
35/40 and 36/40 with a *different* set of failures each time, so it measured
the model's variance rather than the skill. The two cases that sit at 2/3
(`async-test-must-not-run-ahead-of-the-system`,
`persistence-test-cleans-at-the-start-and-commits`) fail on wording their
passing attempts quote from the skill verbatim — variance, not a missing rule.

### Four rules made reachable from `SKILL.md`

A live gate run of `testing-discipline` (`claude-sonnet-5`, effort `medium`)
failed two cases whose rules were already written down — in
`references/hygiene.md`, which a short question never opens. Both are now
stated in `SKILL.md` itself, which is always loaded:

- **An unfinished test stays in the working copy.** A test red only because
  its behaviour is not written yet is not carried by a skip; the documented-
  skip exception is for a test held red by something outside the current
  change, and renaming the silence to an expected-failure or pending marker —
  with or without a tracking reference — is the same commit.
- **A red test after a refactor is a finding.** A refactor that changes no
  behaviour cannot turn a test red, so when one does the question is whether
  the change was more than a refactor or introduced a defect; that is settled
  before any expected value or snapshot moves. Where the behaviour did change
  on purpose, the new expectation comes from the specification that sanctioned
  it, never read back from what the code now produces.

- **Persistent state is cleaned at the start of a test, not at the end** — and
  a test is not isolated by rolling its transaction back, since commit is
  where pending changes flush, constraints are checked, generated values are
  assigned and triggers fire. Found the same way at `--repeat 3`: the attempt
  that opened `references/adapters-and-persistence.md` answered correctly, the
  two that did not put the cleanup in teardown.

- **A wait whose condition already held at the starting state never waited for
  anything** — a quantity back to the value it began at, a collection back to
  empty. `references/async-and-concurrency.md` already carried this scenario as
  its minimal reproduction; without the tell in `SKILL.md` an agent diagnosed
  the same test as merely tautological and missed the asynchronous point.

The frontmatter `description` now names persistence (`persistence cleans on the
way in and commits`), since it is the only text read before the skill is loaded
and a question phrased in database terms was not reaching the skill at all.
Room was made by dropping `the two levels kept apart`, which the preceding
sentence about the school already states, and `determinism`.

The refusal now leads the tuning rule (`A red test is answered with a
diagnosis, never with a refreshed expectation`), because an agent that met the
"behaviour changed on purpose" branch first answered "yes, that's the normal
move" and never reached the rest. `agents/openai.yaml` carries the clauses too.
Skill version 1.4.0 → 1.5.0.

### Eval oracles widened to the vocabulary answers actually use

Seven `testing-discipline` oracles rejected correct answers over wording:
break-and-restore phrased as breaking the *logic* or *commenting out* the
calculation; un-pinning a query count phrased as *drop or loosen* or
*implementation detail*; declining to impose the cycle phrased as *not wrong*
or *a sequencing choice*; a circular test called *tautological* or answered
with *hand-computed* fixtures; a regression test verified against the
*pre-fix* code; visibility answered with the *public API's observable effect*;
an expected value the answer said to *hardcode* — both where it explained that
importing the constants makes the test *re-execute* the formula, and where the
oracle asked for a *literal* while the skill's own rule is spelled "hardcode
the expected results".

The forbidden patterns carried a real defect, in both directions. They scan
only the sentence *prefix* for what would make the phrase conditional or
negated, so `Once that's in place, you're done` read as a flat claim, and
`Write the class first and you'll end up naming the interface after the
implementation, not after what your object needs` read as advice to write the
class first. The shared prefix exclusion now covers conditional openers
(`once|if|when|after|until|provided`) alongside the negations it already knew,
and every pattern gained a trailing guard for a negation that arrives after the
phrase — closing both blind spots in all twenty-one patterns rather than the
two that happened to fire.

`cycle-is-not-imposed-on-a-project-that-has-not-declared-it` asked for a review
of "this one test" that the harness never put in the temporary project, so the
answer was "paste the test" and the process question went unanswered; the test
is now inline in the prompt.

Every widening was replayed over the 240 harness answers saved by four runs:
the correct answers pass, and every substantively wrong answer in that archive
is still rejected.

## [3.4.4] — 2026-07-29

### Reasoning effort is part of the eval environment, not the operator's shell

- The `models` block added in 3.4.3 becomes `tiers`, carrying both dials that
  decide an answer:

  ```json
{
  "tiers": {
    "gate":  { "model": "claude-sonnet-5",           "effort": "medium" },
    "debug": { "model": "claude-haiku-4-5-20251001", "effort": "low" }
  }
}
  ```

  `scripts/run_skill_evals.py` gains `--effort` and an `{effort}` placeholder
  next to `--model`/`{model}`, and the run header names both.
- The gap this closes: effort changes the answer as much as the model does, and
  it was arriving from the operator's own environment — `CLAUDE_EFFORT` in the
  launching shell, inherited by every harness subprocess, plus `effortLevel` in
  their personal `settings.json`. Every gate run so far was therefore a claim
  about "that model **at high effort**", recorded nowhere. The runner now strips
  `CLAUDE_EFFORT` from the harness environment: the manifest decides, or nothing
  does.
- Effort is validated against `low|medium|high|xhigh|max` at manifest load,
  because `claude --effort` does not reject an unknown level — it warns and
  silently falls back to its own default, which would produce a run whose header
  lies about its environment.
- Which effort to declare is an audience decision. Where it is unknown, the
  lower bound is the safer claim: a skill that passes at low effort will almost
  certainly pass at high, and not the other way round. Every manifest here
  declares `medium` for the gate and `low` for debug.
- Validation covers unknown tiers, unknown dials, non-string values and bad
  effort levels; `__test__/test_evals.py` reaches 21 tests, including one that
  sets `CLAUDE_EFFORT` in the parent and asserts the harness sees it unset, and
  one that reads the saved answer to confirm the declared pair reached the
  harness rather than only the log. `README.md`, `CLAUDE.md` and
  `__test__/README.md` document both dials.

## [3.4.3] — 2026-07-29

### Eval runs name their model instead of inheriting whatever the CLI defaults to

- Every `__test__/evals/<skill>/cases.json` now declares `models: {gate, debug}`
  and `scripts/run_skill_evals.py` takes `--tier {gate,debug}` (default `gate`)
  plus a `{model}` placeholder for `--command`.
  - `gate` — the model the skill's users actually run (`claude-sonnet-5` for
    every manifest here). A green gate is green *for that model* and claims
    nothing about any other, so this is the only tier that may move a skill
    `draft → stable`.
  - `debug` — a cheap, fast model (`claude-haiku-4-5-20251001`) for shaking
    manifest defects out between live runs. Its failures may be the model's
    limits rather than the skill's, so it promotes nothing; it exists because
    three rounds of manifest defects cost an hour of live run each. A weaker
    model also makes the skill's effect more visible, so cases the model
    already passes unaided stand out.
- `--model` overrides the declared tier for a one-off experiment.
- Fail-closed in both directions: a resolved model with no `{model}` in the
  command is refused (the harness would silently use its own default while the
  log named a different model), and a `{model}` placeholder with no resolved
  model is refused too. A manifest without a `models` block stays valid and
  runs on the harness default — recorded as such.
- Every run now opens with a header naming its environment —
  `RUN <skill> platform=… tier=… model=… repeat=… cases=… command=…` — so a
  green result records where it is green. `--validate-only` lists the declared
  tiers alongside the case count.
- `__test__/test_evals.py` grows to 19 tests covering tier selection, the
  override, both fail-closed directions, the no-models fallback, tier and
  model-name validation, and that every catalog manifest declares both tiers.
  `README.md`, `CLAUDE.md` and `__test__/README.md` document the two tiers and
  the rule that only a `gate` run can promote.

## [3.4.2] — 2026-07-29

### `_temp/` joins `_audit/` as a language-policy exemption

- `scripts/check_language.py` exempts `_temp/` from the English-only rule.
  Both exempt prefixes are untracked working areas (`.gitignore` lists
  `_audit/*` and `_temp/*`): they hold review reports and scratch notes
  written for whoever runs the tool, not repository content that a reader of
  the library will ever see. Until now a note written in the reader's own
  language there failed `skillctl test` — the scanner walks the working tree,
  not the index, so being untracked did not exempt it.
- The exemption is a directory prefix, not a name match: `_temp/notes.md` is
  allowed while `_template.md` and `_temporary/notes.md` stay English-only.
  `__test__/test_language_policy.py` pins both directions.
- The rule text is updated everywhere it is stated: `AGENTS.md` (authoritative),
  `CLAUDE.md`, `README.md` and the scanner's own docstring and failure message.

### `testing-discipline` eval manifest: second audit pass

- A full `--repeat 3` gate (120 live invocations) came back **114/120**. The
  shape of the failures is the finding: six failures in six *different* cases,
  every one of them 2/3. A skill that did not know a rule would not state it in
  the other two attempts — so all six were again defects of the instrument, and
  the skill is untouched by this entry.
- Four required regexes were pinned to one lexical realisation of their rule
  and now accept it however it is phrased:
  - `bug-fix-…-fails-first` demanded the bigram `(fail|red) (before|first)`;
    the answer expressed the same ordering as "revert your one-line fix and run
    it". The pattern now also accepts reverting/undoing/removing the fix.
  - `expected-value-derivation-…` missed on the plural (`\bimport\b` against
    "not in **imports**"), on the gerund (`recomputes?` against
    "**recomputing**") and on a 96-character gap under an 80-character limit.
  - `async-test-must-not-run-ahead-…` demanded the words "intermediate" or
    "equals 10"; the answer proposed the equivalent remedy — make the expected
    end state unreachable from the start state. The pattern now states the
    principle, not one recipe for it.
  - `query-call-count-…` required the query word and the permission phrase on
    one line in one order; they were 256 characters apart in the other order.
- The endorsement template gained two guards, applied across all 21 bans:
  - *use–mention*: a phrase in quotes is being named, not advised — the failing
    answer wrote `"Tidy it later" is how that happens` while condemning it;
  - *qualified verdict*: where the skill itself makes a verdict contingent on
    the declared school or on scope, a verdict that carries its condition in
    the same sentence is the required answer ("the reviewer is right **if**
    your project declares London"). Applied only to the three verdict-shaped
    bans; on bans that are unconditionally true it would only weaken them.
- Verified offline in both directions before any re-run: all **120** saved
  harness answers are accepted (including the six the gate rejected), and 27
  sentence pairs assert that each changed expectation still catches the wrong
  answer and spares the right one. `__test__/README.md` documents both guards
  and the "no single recipe" rule.

## [3.4.1] — 2026-07-28

### Eval manifests can forbid a pattern, not just a substring

- `scripts/run_skill_evals.py` accepts an optional `stdout_not_matches` list
  in a case's `expect`: regexes the harness output must **not** match,
  searched with `re.MULTILINE`, validated and compiled at manifest-load time
  alongside `stdout_matches`. The four existing oracles are unchanged, so
  every manifest stays valid as written.
- The gap this closes: `stdout_not_contains` bans a phrase wherever it
  occurs, which is wrong for any case whose correct answer is conditional.
  Ran against the live Claude Code CLI, the `testing-discipline` case
  `unit-integration-line-is-taken-from-the-declared-school` failed 5 of 6
  attempts on the banned phrase `the reviewer is right` — every failure
  inside a clause like "under London the reviewer is right about the label",
  which is precisely the school-conditional answer the case requires. The
  one passing attempt differed only in wording, not in behaviour, so the
  case was scoring synonyms rather than the skill.
- That case now states its requirement positively (the verdict must be tied
  to a declared school) and uses an anchored `stdout_not_matches` to reject
  an unconditional verdict — including the hybrid answer that names the
  schools and *then* hands down a flat one, which neither the old ban nor a
  positive pattern alone could catch. Verified against nine real harness
  outputs (zero false rejections) and re-run live: 3/3 pass, against 1/5
  before the fix.
- `__test__/test_evals.py` pins the new field (a flat claim fails while the
  same words inside a conditional clause pass, invalid regexes and
  non-list values are rejected at validation); `__test__/README.md`
  documents the oracle and when to reach for it.

### A failing case keeps its answer (`--save-output`)

- `scripts/run_skill_evals.py --save-output DIR` writes every harness stdout
  to `DIR/<skill>--<case>--<attempt>.txt`. A verdict names the oracle that
  missed but not what the harness actually said, and the temporary project
  is deleted with the attempt — so until now the only way to read a failure
  was to run the case again. Diagnosing three failures in one gate run cost
  two extra live runs; this removes that.
- The output path is built with `skill_library.security.safe_join`, and a
  case `id` must now match `[A-Za-z0-9][A-Za-z0-9._-]*` because it names a
  file. No manifest in the repository violates the rule; the runner rejects
  an id that would escape the directory at validation time, before anything
  runs.

### The whole class of form-pinned expectations, not just the one that fired

- A full `--repeat 3` gate over `testing-discipline` (120 live invocations)
  came back **117/120**. All three failures were manifest defects, not skill
  defects: re-run with the answers captured, the skill stated the required
  rule every time.
  - `bug-fix-ships-a-regression-test-that-fails-first` required the bigram
    `(fail|red) (before|without)`. The failing answer wrote "a regression
    test that **fails** before the fix" — the requirement verbatim, rejected
    over one inflected letter. The two passing attempts matched only because
    they happened to also write the uninflected "red before".
  - `expected-value-derivation-is-visible-but-not-borrowed-from-production`
    required a negative verb near "import". The failing answer put the
    prohibition in a heading ("Why not import the constants") and a gerund
    ("Importing … recomputes the expected value with the algorithm under
    test") — right answer, wrong part of speech. The same case also banned
    the substring `import COMMISSION_RATE`, which the correct advice "do not
    import COMMISSION_RATE" contains; it had not fired yet only because the
    model wrote the identifier in backticks.
  - `declared-school-is-followed-not-overridden` banned `use the real
    PriceCalculator` — the exact words the correct answer must write after
    "don't". It passed three re-runs only because the identifier came back
    backticked.
- So the audit covered all 40 cases rather than the three that fired.
  Seventeen cases had bans phrased as advice, which a correct answer has to
  contradict verbatim; each is now an endorsement pattern that matches only
  where the phrase is put forward as a recommendation — sentence-initial,
  with no negation between the sentence start and the phrase — and tolerates
  backticked identifiers. Bans that a correct answer cannot utter (`yes,
  this test is sufficient`, `this is a good test`) were left as substrings.
- Every conversion is checked in both directions: 23 sentence pairs assert
  that the negated form survives and the endorsement is still caught, and
  all 18 real harness answers saved so far pass, including the two that the
  gate rejected.
- `testing-discipline` stays `draft` and its version is unchanged — no skill
  content changed here, only the instrument measuring it. The gate must be
  re-run green before the status can move.

## [3.4.0] — 2026-07-28

### Every skill now stands alone (`typescript-nestjs` 1.1.1 → 1.2.0, `typescript-coding` 1.7.0 → 1.8.0, `python-coding` 1.5.0 → 1.6.0, `hexagonal-service` 2.1.1 → 2.2.0, `testing-discipline` 1.3.0 → 1.4.0)

Skills are installed one at a time, but four of the five had grown text
that only works when a *second* skill is installed too — and one of them
pointed at the wrong owner entirely.

**`typescript-nestjs` was not usable on its own.** Its `description` said
it "presumes" two other skills; its body said to "apply all three
together"; `references/testing.md` sourced universal test hygiene from a
skill that does not contain any (that content moved out three releases
ago, in 3.0.0); two files sent the reader to another skill's error-flow
reference for a rule they never stated themselves; a config rule quoted
another checker's rule code; and the suppression contract was defined by
reference instead of written down. A consumer who installed only this
skill got a standard with holes in it. Every one of those is now stated in
full, in NestJS's own terms — the wrap-once/log-once/map-once invariant,
the config rule, the suppression contract with its own worked example.

**The rest was unconditional naming.** `typescript-coding`,
`python-coding`, `hexagonal-service` and `testing-discipline` each
asserted that some rule "lives in" a named sibling — in `SKILL.md`, in the
OpenAI adapter prompts, in a reference file, in a checker comment, in a
dataset contract. All of it is now either scoped out ("out of this
skill's scope") or made conditional in the one shape an agent can act on:
*where the host project also declares an architecture standard, apply it
on top*. `hexagonal-service`, which claims language neutrality, no longer
names two TypeScript skills as its examples and none for other languages.

The distinction the whole change turns on: **duplication is the price of
independence and is fine; a reference is not.** Two skills stating the
same rule about wrapping an error is correct. One skill telling the reader
to go find that rule somewhere else is a dependency.

- **Removed from `typescript-nestjs`:** three restatements of universal
  test rules and a hardcoded school predicate ("mock ports" in every unit
  test). Which collaborators a unit test replaces is the project's
  declaration, not a framework's; the file now says so and keeps only what
  is genuinely NestJS — `Test.createTestingModule`, `overrideProvider` at
  the token, `app.close()` teardown, the spec-file names.
- **New gate `__test__/skills/test_skill_boundaries.py`** — a sibling may
  be named only inside a sentence carrying a conditional marker; another
  skill's rule codes, file paths and pinned versions are refused
  everywhere. The skill-root `README.md` is exempt because it is never
  installed. The existing anti-duplication battery in
  `test_testing_discipline.py` now covers `typescript-nestjs` as well —
  the omission through which the restatements above arrived.
- **Recorded in `AGENTS.md`:** skills stand alone; what a *new*
  observation may say about a sibling (neutrally — never its path,
  version, PR number or commit). Observation records accepted before this
  rule are history and are left as they are.

## [3.3.0] — 2026-07-28

### `testing-discipline` 1.2.0 → 1.3.0: scoped to unit and integration tests, and the London school gets its own half

Two changes with one shape: **the skill now states what it does not
cover, and covers what it claims to.**

**The scope is unit and integration tests, and the limit is enforced.**
The skill had been accumulating levels — a third, system-wide one arrived
with its own outer loop, its own suites and its own deployment advice.
Those rules have different subjects, lifecycles and owners, and an agent
reading them under one name applies unit-test reasoning (isolate, double
the collaborators, run in milliseconds) to a question where every one of
those moves is wrong. The scope is now part of the contract: it is stated
in the `description` a caller reads before loading the skill, restated as
a **rule** that says to decline out-of-scope questions rather than
improvise from these ones, and pinned by a scanner that fails the build if
a third level reappears anywhere in the skill.

**Both schools now have an operational half.** The skill declared itself
neutral between the two unit-testing schools and was not: every
operational file — the cycle, the value model, the anti-patterns — was
calibrated against the classical school's primary sources, while London
appeared only as a catalog entry naming the school's cost ("replacing
every collaboration binds the tests to *how* the unit reaches its result")
with nothing to pay it down. The half that was missing and is
unit-level — where the doubled collaborators come from, and how tightly an
interaction may be pinned — is now carried, calibrated against Freeman and
Pryce's *Growing Object-Oriented Software, Guided by Tests*.

The two changes meet in one place: **the line between a unit test and an
integration test is what the schools disagree about**, so with only two
levels left the skill has a single axis instead of three parallel ones.

- **New `references/interface-discovery.md`** — London's own technique,
  applied where the project declares that school. **The collaborator does
  not exist yet**, and the double is what brings it into existence: name
  the service in the client's terms (*"if this worked, who would know?"*),
  **pull interfaces into existence from the client rather than pushing
  them out from an implementation**, keep the discovered surface narrow,
  and merge roles that turn out to mean the same thing. It ships with the
  cost it incurs and the rules elsewhere in the skill that pay it down —
  a project that declares London and skips those has bought the cost
  without the benefit.
- **Removed `references/outside-in-cycle.md`** — feature-level
  acceptance-driven development, walking skeletons, deployment risk and
  the progress-versus-regression suite split. All of it is about a level
  this skill no longer claims. Its one unit-level part became the file
  above.
- **Removed `references/types-and-tests.md`** — the division of labour
  between a static type checker and a test suite is about tooling rather
  than about a unit or integration test. Its operative parts (a test per
  narrowing predicate including the near-miss values it must reject,
  runtime enforcement of a harmful type-level bypass driven from a test,
  type-level assertions pinned next to the utility) are already spelled
  out in the language standards, which is where a project meets a type
  checker at all. This is the one deliberate exception to "the universal
  test rules have a single home".
- **`references/test-levels.md` rewritten around two levels.** The
  interesting half is new: there is **no level boundary this skill can
  hand you**, because London draws it structurally (a real collaborator
  makes it an integration test) and the classical school draws it
  behaviourally (a shared dependency, slowness, or more than one unit of
  behaviour does). The project declares which line it draws — and what
  does *not* vary by school is that once drawn, the line is enforced: a
  unit test that acquires a real connection, file or clock has changed
  level and is moved.
- **`references/tdd-cycle.md` narrowed to the test.** The evidence rule,
  the four-step loop and the refactor step stay; choosing the next item
  off a written list, sizing a step, the four gears to green and ending a
  session were project workflow rather than rules about a unit or
  integration test, and are gone. What the cycle owes the rest of the
  discipline — a learning test before first use of an unfamiliar facility,
  and the smallest reproduction for every defect — stays.
- **`references/test-diagnostics.md`** — **the cycle has four steps, not
  three**: fail, *report*, pass, refactor. The report step runs before any
  production code exists, because a failure nobody can read is a test that
  gets deleted the first time it fires under deadline. Plus self-describing
  values, obviously canned values, tracer objects, and checking
  interactions before value assertions so the report names the cause
  rather than the consequence.
- **`references/test-data-builders.md`** — when a factory method is
  enough and when it is not, safe (not realistic) defaults, and two traps
  the one-line "prefer builders" advice could not carry: a reused
  chainable builder **silently leaks one object's override into the next**
  once two uses diverge, and a shared helper that takes *values* grows one
  overload per variation — pass the builder through instead.
- **`references/async-and-concurrency.md`** — separating what an object
  computes from how it schedules; wait for success and time out for
  failure; sampling versus listening and the **lost update** a poll can
  miss; the stress-test procedure that requires watching the test fail
  dependably first; flickering treated as breakage. Its load-bearing rule
  ships a reproduction: a **runaway test** that waits for a state the
  system was already in passes before the system has started, and stays
  green when the work never happens at all.
- **`references/adapters-and-persistence.md`** — clean persistent state at
  the *start* of a test (so a failure leaves evidence and the next test
  still isolates); write transaction boundaries into the test rather than
  isolating by rollback, which never exercises the commit where
  constraints fire; round-trip every reflective mapping; and do not
  exercise generic mapping code with production domain types — the second
  cost is **silent rot**, where the domain type loses the field the test
  thought it was covering and nothing fails.

Existing files gained the rules that make the above coherent:

- `unit-test-value.md` — **specify precisely what should happen and no
  more**: allow queries, expect commands; keep required interactions few;
  match arguments only as tightly as the scenario constrains them; pin
  call order only where the order is the contract; ignoring an irrelevant
  peer is a power tool, and a *chain* of ignored peers is a design smell.
- `isolation-and-fakes.md` — **peers, not internals** as the substitution
  boundary, the three kinds of peer (a **dependency** required at
  construction with no safe default, against **notifications** and
  **adjustments** that carry defaults), and the case against doubling a
  concrete type at all: the relationship stays unnamed and the subject is
  bound to more of that type than it uses.
- `tests-as-design-feedback.md` — five more symptoms (a hidden dependency,
  a long construction argument list, an argument list that will not group,
  a test class that falls into unrelated slices, a test in which every
  interaction is required), plus **support reporting is a feature and is
  test-driven; diagnostic tracing is scaffolding and is not**.
- `structure-and-naming.md` — write the *information*, not its
  representation; and the other half of "name the expected value": **exact
  about the claim, silent about the rest**.
- `hygiene.md` — a flickering test is broken, not mostly working; a test
  that is red because the behaviour is not built yet **stays in the
  working copy** until it passes, and **no red suite is ever shared** —
  which is the resolution both the cycle and the no-committed-skips rule
  were pointing at.
- `schools.md`, `anti-patterns.md` — the report step, the routes into the
  new files, and the round-trip-mapping exception to "never reach into
  private state", argued and bounded.

Three collisions with the pre-existing rules are written down rather than
left for a reader to trip over: an unfinished red test against
no-committed-skips; naming the expected value against not over-asserting;
and reflective round-tripping against the private-state prohibition.
`SKILL.md`, the `README.md` and the OpenAI adapter were updated to match.
`__test__/skills/test_testing_discipline.py` (142 tests) grew a scope
class that fails if a third level reappears anywhere in the skill —
including a guard on the scanner itself — and the eval set traded its two
acceptance-loop cases for four: an unfinished test kept local, an
out-of-scope system-wide request declined by naming the limit, the
unit/integration line taken from the declared school, and a London
collaborator discovered from its client.

## [3.2.0] — 2026-07-28

### `testing-discipline` 1.1.0 → 1.2.0: the process axis, from the classical school's primary source

Every rule the skill carried judged a test that already existed — its
shape, what it may touch, what it may assert. Nothing said *when* a test
comes into being relative to the code, how the next one is chosen, how to
get from red to green, or what to do when writing the test is painful. An
agent could therefore produce a flawless test that had never once been
observed to fail, and the skill had no objection. This release adds that
axis, calibrated against Kent Beck's *Test-Driven Development By Example*
— the classical (Detroit) school's own primary source — and reconciles it
with the rules already in place.

- **New `references/tdd-cycle.md`.** Its first section holds in any
  project whatever its process: **a test that has never been observed to
  fail for its own reason is not yet evidence of anything** — free when
  the test is written first, one deliberate break-and-restore of the
  behaviour otherwise; *which* failure you got matters (a blown-up arrange
  step demonstrates nothing about the assertion); and an unexpected green
  is investigated, never enjoyed. The rest describes the cycle itself and
  is applied **only where the host project declares that it practises
  it**, exactly as the school is declared: the two generating rules
  (failing test first, remove duplication), the five-step loop, never more
  than one red test at once, the written test list worked one item at a
  time, choosing the next test for what it teaches against what you are
  confident you can pass, a degenerate first case, replacing an oversized
  test with a smaller one, the four gears to green (obvious implementation
  → one-to-many → triangulate → fake it) with the rule for changing gear,
  step size named as the variable being controlled rather than a virtue,
  the refactor step including duplication *between the test and the code*,
  session boundaries, and the limits — security, concurrency, performance,
  a design decided in advance, and seamless legacy code.
- **New `references/tests-as-design-feedback.md`.** The inversion the rest
  of the skill implies but never stated: a long arrange step, setup that
  resists being shared, a slow test, a fragile test, the urge to reach
  private state, a two-call act step or a name that will not fit are each
  a report on the *product*. Each maps to what it says about the code and
  the change it asks for, under one rule — **change the design first and
  the test second** — with an explicit escape valve for when the design
  idea does not come, plus the reasons the loop works (shortest feedback
  on an interface decision, scope control, isolation as a design force,
  reusable structure emerging from removed duplication) and what none of
  it licenses.
- **Four coexistence boundaries written down**, because each pair reads as
  a contradiction otherwise and each is now pinned by a test: a
  deliberately constant *production* implementation is a step in the cycle,
  not a test tuned to the gate; writing the specification's own derivation
  into an assertion over the test's literals is the opposite of leaking the
  algorithm into the test (the question is *whose* computation is reused);
  a red test left as a bookmark lives in the working copy and never on a
  shared branch; and the classical school's direction is corrected —
  "inside-out" is a contrast with London's outside-in, not the school's
  account of itself, which rejects the vertical metaphor in favour of
  **known-to-unknown**.
- **`references/structure-and-naming.md`** gains assertion-first as a
  writing order and a new *data a test carries* section: make the
  derivation from input to expected value visible rather than collapsing
  it to a magic result, never let one constant mean two things in one
  case, prefer the smallest data that forces the same decisions, and
  reserve realistic data for replay, parallel-run and bit-exact
  refactoring. Assertions must name the expected value rather than a
  property many wrong answers share.
- **`references/hygiene.md`** gains the evidence rule as a hygiene item
  and **when a test may be deleted** — only when redundant on *both*
  confidence and communication, judged against the specification rather
  than a coverage report, shipped with the change that made it redundant.
- **`references/unit-test-value.md`** gains *what is on the hook and how
  deep to go*: the conditionals, loops, operations and dispatch **you**
  wrote; not a dependency's own behaviour, except to learn a facility
  before first use or to pin a defect you must work around; and depth
  calibrated by the cost of being wrong rather than by a case count.
- **`references/isolation-and-fakes.md`** gains the lifecycle of the live
  observation the fake-provenance rule already demanded — write it before
  the first use of an unfamiliar facility, re-run it on every upgrade
  before anything else, and express the contract as cases the fake and the
  real dependency can both answer — plus two shapes worth knowing:
  sabotaging a single operation to reach an error path, and accumulating a
  record to assert on ordering once.
- `SKILL.md` grows two workflow steps and two routing rows; `README.md`
  documents that test-driven development is the project's declaration too;
  the OpenAI adapter carries the cycle and its conditionality.

## [3.1.0] — 2026-07-28

### `testing-discipline` 1.0.0 → 1.1.0: unit-testing rules and the two schools

- **The unit-testing school is now an explicit project declaration.** Which
  collaborators are replaced by a test double does not follow from "write
  good tests" — it follows from what a project means by *isolation*, and
  there are two coherent answers in wide use. The skill previously assumed
  one of them in passing ("isolation is about the *test*, not about
  purity") without ever saying so, which is wrong for half the codebases
  that install it. `references/schools.md` now carries both schools —
  **London (mockist)**: isolate the unit, a unit is a class, double every
  mutable collaborator; **classical (Detroit)**: isolate the tests, a unit
  is a unit of behaviour, double only shared dependencies — plus the
  dependency vocabulary the choice is made in (shared/private,
  in-/out-of-process, managed/unmanaged, value/collaborator), the rules
  that hold either way, the resolution order for an undeclared project
  (follow the suite → propose → record; never guess, never mix), and the
  list of what the host project's rules must declare. The skill never
  picks; the project's rules do and always take precedence.
- **New `references/unit-test-value.md`** — how a test is judged, which
  every other rule serves: the four attributes (protection against bugs,
  resistance to refactoring, feedback speed, maintenance cost) multiplied
  rather than added; resistance to refactoring as the one attribute never
  traded, with coupling to implementation details named as the single cause
  of false positives; observable behaviour versus implementation detail and
  the one-call-per-goal heuristic; the three verification styles ranked
  (output → state → interaction) with the rules for asserting an
  interaction at the last seam before the call leaves the process, in both
  directions; and which code deserves a unit test at all (domain and
  algorithms thoroughly, trivial code never, orchestrators briefly through
  integration tests, over-complicated code refactored first).
- **New `references/anti-patterns.md`** — testing a private method
  directly, exposing private state to enable an assertion, leaking the
  algorithm into the test, code pollution (production code that exists only
  for tests), doubling a concrete type to keep part of it, time as ambient
  context, and sharing the arrange step through a per-test setup hook.
- `references/isolation-and-fakes.md` gains the stub/mock distinction —
  a double standing in for an incoming interaction is never asserted on;
  only an outgoing one may be — the *double only types you own* rule, and a
  school-aware preamble in place of the sentence that quietly assumed the
  classical reading. `references/structure-and-naming.md` gains one act
  step per test, no branching in a test, the act-length signal about the
  subject's surface, the naming rules (no rigid template, no method name in
  the test name, state a fact rather than a wish) and guidance on grouping
  similar cases.
- `SKILL.md` routes the school decision first, before anything is faked,
  and adds the value/anti-pattern rows to its routing table; the
  description, the OpenAI adapter and the user-facing `README.md` all state
  that the school is declared by the project. `__test__` pins the new rules
  and the neutrality contract (47 tests in the skill's module); six eval
  cases cover the school declaration, a declared school being followed,
  asserting on a stub, recomputing the expected value with the algorithm
  under test, widening visibility for an assertion, and a declared school
  not being second-guessed.

## [3.0.0] — 2026-07-28

### New skill: `testing-discipline` 1.0.0 (major: a skill was created)

- The rules for writing and reviewing tests now live in one place, free of
  any language, runner, framework or platform assumption. Until this
  release the same rule set was carried twice — once per language standard
  — and each of the last three test-rule fixes had to be applied to one
  standard and then mirrored into the other in a separate release
  (`2.5.0`/`2.6.0`, `2.7.0`/`2.8.0`, `2.9.0`/`2.10.0`), even though every
  one of them shipped its own universality check. Two copies of one rule
  can drift, and a third language would have needed a third copy.
- `SKILL.md` carries the workflow and the rule list and routes to four
  references: `structure-and-naming.md` (Arrange/Act/Assert, one scenario
  per test, names that state behaviour and condition, asserting the error
  *and* its condition, factories over fixture blobs, example-based versus
  property-based cases); `isolation-and-fakes.md` (nothing external in a
  unit test, injected clocks and deadlines instead of waiting, faking the
  seams the code exposes and never someone else's internals, the
  external-system fake-provenance rule with its two reproductions, the
  outbound-substitution shape, and the production-wiring rule);
  `hygiene.md` (no committed focus/skip, no test tuned to the gate,
  regression test per bug fix, determinism, the case-set/subject/dimension
  family with its three reproductions, test-only secrets); and
  `types-and-tests.md` (what a static checker already covers and what it
  cannot verify).
- Status is `draft` until the eval-gate
  (`scripts/run_skill_evals.py` over `__test__/evals/testing-discipline/cases.json`,
  15 cases: 2 trigger, 6 behavior, 5 negative, plus a trigger case in a
  language the skill names nowhere) runs against a real harness. Ships an
  OpenAI adapter and a user-facing `README.md`; no scripts and no optional
  layers — a language-neutral checker for prose test rules would be
  guesswork.

### `python-coding` 1.4.0 → 1.5.0 (minor: an existing skill's rules changed)

- `references/testing.md` is now a **spelling map**: which Python
  construct expresses a test rule (a `Protocol`-satisfying stub,
  `monkeypatch`/`unittest.mock.patch` as the justified last resort,
  injected clocks, a real event loop with `asyncio.timeout` deadlines,
  `pytest.mark.skip` with a reason, the `Any`/`cast`/`print` relaxations
  scoped to test files, `TypeGuard`/`TypeIs` unit tests,
  `typing.assert_type` and the `warn_unused_ignores`-policed negative
  type-level assertion, Hypothesis), plus the checker's behaviour in test
  paths. The rules themselves — and the observation-backed guidance
  transferred in `2.5.0`, `2.7.0` and `2.9.0` — moved to
  `testing-discipline` unchanged in substance.
- `SKILL.md` drops the "test in the same change" workflow step and the
  test clause of the suppression rule; the routing row now points at the
  spelling map. The `description` and the OpenAI adapter prompt no longer
  claim test rules.

### `typescript-coding` 1.6.0 → 1.7.0 (minor: an existing skill's rules changed)

- Same split, TypeScript side: `references/testing.md` becomes a spelling
  map (object-literal stubs, module patching as the justified last resort,
  injected clocks, awaited assertions with deadlines and no floating
  promises, `it.skip` with a reason and never `.only`, the
  `any`/non-null/`console` relaxations scoped to spec files, type-guard
  and assertion-function tests, equality-style type-level assertions and
  the `@ts-expect-error` negative case, fast-check), plus the checker's
  behaviour in test paths. The rules transferred in `2.6.0`, `2.8.0` and
  `2.10.0` moved to `testing-discipline`.
- `SKILL.md` drops the "test in the same change" workflow step and the
  test clause of the suppression rule; `description` and the OpenAI
  adapter prompt updated accordingly.

### Tests and documentation

- The three observation-backed regression classes that pinned the moved
  rules (case-set provenance/subject/dimension, external-system fake
  provenance, outbound mutation + wiring level) are relocated into
  `__test__/skills/test_testing_discipline.py` against the new skill's
  files, alongside structural, neutrality and adapter pins. Both language
  test modules gain a guard that their `references/testing.md` stays a
  spelling map and re-states none of the relocated rule text; the new
  module carries the same guard for both skills.
- The ten test-rule eval cases duplicated across the two language
  manifests collapse into `__test__/evals/testing-discipline/cases.json`;
  the language manifests keep their language-specific cases.
- Root `README.md` lists the new skill; `docs/history.{eng,rus}.md` gain
  the bilingual entry for the split.

## [2.10.0] — 2026-07-28

### `typescript-coding` 1.5.0 → 1.6.0 (minor: an existing skill's rules changed)

- Fixed OBS-20260728-001 (mirrored from `python-coding` OBS-20260728-001,
  commit 33d6380, itself a field report from a consuming project,
  reviewer-confirmed class C3, `occurrences: 6` across two consecutive
  tasks, at least three of them after the sibling fix for the adjacent
  external-system-fake class was already pinned and active; universality
  threshold met on both limbs, both claimed minimal reproductions
  independently re-executed by that reviewer, re-confirmed unchanged at a
  second review pass): `references/testing.md` already said a fake's own
  return values, for a property belonging to an external system, must be
  pinned by a live observation rather than by reading — but its scope
  sentence named only "return values", an output-side property, and stayed
  silent on two adjacent shapes. (1) Outbound-mutation: a value a
  third-party client substitutes on the way OUT of a call (a header, id, or
  default the caller does not fully control) has no return value to inspect
  at all, so a fake bound at exactly the layer performing that substitution
  cannot show whether it happened, and a reader keying on "return values"
  would not recognise the shape as covered. (2) Wiring-level: a test that
  constructs its own copy of a third-party collaborator to assert *how* it
  is built (which constructor or options-object arguments, which
  interceptors) proves the property achievable, never that the product's
  own production factory achieves it — a materially different code path
  that, left uncovered, can carry a defect the sibling test suite stays
  fully green on. The same language-independent gap already fixed in
  `python-coding`, ported here in TypeScript idiom. Widened the existing
  guidance's scope sentence and added both sub-shapes as their own guidance
  block, each with a deterministic, project-independent minimal
  reproduction (an outbound header/id substitution the caller does not
  control, performed by an SDK's own interceptor; a `createClient(...)`
  factory whose `interceptors` / `hooks` option has zero test coverage
  because every test builds its own client).
- Added a regression in `__test__/skills/test_typescript_coding.py`
  (`TestOutboundMutationAndWiringLevelFakeGuidance`): pins the two new
  rules' load-bearing clauses, both minimal reproductions, and negative
  guards that the pre-existing OBS-20260727-001 rule with its two
  reproductions and the distinct "mock interfaces and seams the code
  exposes, never someone else's internals" rule survive untouched.
  Confirmed genuinely red before the delta (6 of 8 tests failing against
  the pre-change text; the 2 negative guards passed throughout) and green
  after.
- Added four eval cases to `__test__/evals/typescript-coding/cases.json`
  (two `behavior`, two `negative` — one pair per sub-shape) guarding
  against over-applying either rule onto a project-owned interface with no
  outbound call, or onto a test that already exercises the real production
  factory. Schema-validated (`run_skill_evals.py --validate-only`); the
  LLM-backed execution is the Hub's opt-in eval runner, not part of this
  local run.
- Transferred the observation via `skillctl observation add/approve` (Hub id
  OBS-20260728-001 in `skills/typescript-coding/observations/accepted/`),
  citing the mirrored `python-coding` observation, the consumer observation
  id and the reviewer verdict as evidence; `observations/INDEX.md` updated.
- `docs/history.{eng,rus}.md`: the existing "What a stub still can't see"
  entry gains this release on its **Releases** line and a short TypeScript
  restating of both shapes — one story, one entry, per the history-docs
  discipline.

`uv run skillctl validate` && `uv run skillctl test`: 719/719 passed, no
regressions. Non-main branch; no push to `main`, no tag, no release — PR
only.

## [2.9.0] — 2026-07-28

### `python-coding` 1.3.0 → 1.4.0 (minor: an existing skill's rules changed)

- Fixed OBS-20260728-001 (field report from a consuming project, reviewer-
  confirmed class C3, `occurrences: 6` across two consecutive tasks, at
  least three of them after the sibling fix `OBS-20260727-001`/PR #13 for
  the adjacent external-system-fake class was already pinned and active;
  universality threshold met on both limbs, both claimed minimal
  reproductions independently re-executed by that reviewer, re-confirmed
  unchanged at a second review pass): `references/testing.md` already said
  a fake's own return values, for a property belonging to an external
  system, must be pinned by a live observation rather than by reading —
  but its scope sentence named only "return values", an output-side
  property, and stayed silent on two adjacent shapes. (1) Outbound-mutation:
  a value a third-party client substitutes on the way OUT of a call (a
  header, id, or default the caller does not fully control) has no return
  value to inspect at all, so a fake bound at exactly the layer performing
  that substitution cannot show whether it happened, and a reader keying on
  "return values" would not recognise the shape as covered. (2)
  Wiring-level: a test that constructs its own copy of a third-party
  collaborator to assert *how* it is built (which constructor arguments,
  which interceptors) proves the property achievable, never that the
  product's own production factory achieves it — a materially different
  code path that, left uncovered, can carry a defect the sibling test
  suite stays fully green on. Widened the existing guidance's scope
  sentence and added both sub-shapes as their own guidance block, each with
  a deterministic, project-independent minimal reproduction (an outbound
  header/id substitution the caller does not control; a factory whose
  interceptor argument has zero test coverage because every test builds
  its own client). Added one `behavior` and one `negative` eval case per
  sub-shape guarding against over-application onto a project-owned seam
  with no outbound call, and onto a test that already exercises the real
  production factory.

## [2.8.0] — 2026-07-27

### `typescript-coding` 1.4.0 → 1.5.0 (minor: an existing skill's rules changed)

- Fixed OBS-20260727-001 (mirrored from `python-coding` OBS-20260727-001 /
  PR #13, commit 8e6177e, itself a field report from a consuming project,
  reviewer-confirmed class C3, `occurrences: 3`, universality threshold met
  on both limbs, both claimed minimal reproductions independently
  re-executed by that reviewer): `references/testing.md` already said *what*
  to fake ("mock interfaces and seams the code exposes, never someone else's
  internals") but was silent on *how the fake's own return values are known
  to be true of the real system* before the fake is written — the same
  language-independent gap already fixed in `python-coding`, ported here in
  TypeScript idiom. In the three source occurrences — a broker rewriting the
  delivery key at every dead-letter hop, an authentication encoder
  substituting a default identity for an absent **or empty** username, and a
  database driver collapsing two un-aliased columns into a single row key —
  a unit-test fake for a third-party seam stayed green while encoding a
  wrong belief about that system's runtime behaviour, and only a live probe
  against the real system, never a re-reading of project norms or vendor
  prose, ever caught it. Added one guidance block adjacent to the existing
  mock-the-seam rule: the reference behaviour a fake encodes for an
  **external** system is established once, by observing the real system, and
  pinned as a fixture; a second rejection of the same reading on the same
  external-system property is the trigger to switch evidence class from
  reading to a live observation, not to produce a third reading. Ships two
  deterministic, project-independent minimal reproductions in TypeScript
  idiom — `new URL("amqp://:p@h:1").username` is `""`, indistinguishable
  from the absent user of `new URL("amqp://h:1")` (re-executed on Node
  v26.4.0); and PostgreSQL's `?column?` naming of unaliased expression
  columns, which makes `SELECT true, false` collapse into a one-key row
  under an object-row driver while `SELECT true AS a, false AS b` returns
  both (the PostgreSQL-side fact carried over from the reporting reviewer's
  own execution against a live instance). The third occurrence (a live
  two-hop broker dead-letter cycle) is not reducible to a snippet, which the
  new guidance states explicitly.
- Added a regression in `__test__/skills/test_typescript_coding.py`
  (`TestExternalReferenceBehaviourGuidance`): pins the rule's two
  load-bearing clauses, both illustrative reproductions, a negative guard
  that the pre-existing, distinct "mock interfaces and seams the code
  exposes, never someone else's internals" rule survives untouched, and a
  duplication guard. Confirmed genuinely red before the delta (4 of 5
  assertions failing against the pre-change text) and green after.
- Added two eval cases to `__test__/evals/typescript-coding/cases.json` (one
  `behavior`, one `negative`) exercising the rule and guarding against
  over-applying it to a fake of an interface this project itself owns and
  defines. Schema-validated (`run_skill_evals.py --validate-only`); the
  LLM-backed execution is the Hub's opt-in eval runner, not part of this
  local run.
- `docs/history.{eng,rus}.md`: the existing "Where a stub gets its truth
  from" entry gains this release on its **Releases** line — one story, one
  entry, per the history-docs discipline.

`uv run skillctl validate` && `uv run skillctl test`: 703/703 passed, no
regressions. Non-main branch; no push to `main`, no tag, no release — PR
only.

## [2.7.0] — 2026-07-27

### `python-coding` 1.2.0 → 1.3.0 (minor: an existing skill's rules changed)

- Fixed OBS-20260727-001 (field report from a consuming project, reviewer-
  confirmed class C3, `occurrences: 3`, universality threshold met on both
  limbs, both claimed minimal reproductions independently re-executed by
  that reviewer): `references/testing.md` already
  said *what* to fake ("fake protocols and seams the code exposes, never
  someone else's internals") but was silent on *how the fake's own return
  values are known to be true of the real system* before the fake is
  written. Across three independent occurrences in a single build —
  RabbitMQ's dead-letter key rewriting via `aio-pika`, the `aiormq`
  SASL-PLAIN identity substitution for an absent/empty user, and
  `psycopg`'s `dict_row` column collapse — a unit-test fake for a
  third-party seam stayed green while encoding a wrong belief about that
  system's runtime behaviour, and only a live probe against the real
  system, never a re-reading of project norms or vendor prose, ever caught
  it. Added one guidance block adjacent to the existing fake-the-seam
  rules: the reference behaviour a fake encodes for an **external** system
  is established once, by observing the real system, and pinned as a
  fixture; a second rejection of the same reading on the same
  external-system property is the trigger to switch evidence class from
  reading to a live observation, not to produce a third reading. Ships two
  deterministic, project-independent minimal reproductions (a `yarl.URL`
  empty-user-vs-absent-user case; a `psycopg` `dict_row`
  unaliased-column-collapse case, both reproduced from the reporting
  reviewer's own executed verification) — the third occurrence (a live
  two-hop broker DLX cycle) is not reducible to a snippet, which the new
  guidance states explicitly.
- Added a regression in `__test__/skills/test_python_coding.py`
  (`TestExternalReferenceBehaviourGuidance`): pins the rule's two
  load-bearing clauses, both illustrative reproductions, a negative guard
  that the pre-existing, distinct "fake protocols and seams the code
  exposes, never someone else's internals" rule survives untouched, and a
  duplication guard. Confirmed genuinely red before the delta (4/5
  assertions failing against the pre-change text) and green after.
- Added two eval cases to `__test__/evals/python-coding/cases.json` (one
  `behavior`, one `negative`) exercising the new rule and a false-positive
  guard against over-applying it to a fake of a seam this project itself
  owns and defines.

### Documentation and policy

- New human-readable history pair `docs/history.eng.md` /
  `docs/history.rus.md` — the narrative counterpart of this file. This file
  says *what changed in which release*; the pair says *what was going wrong,
  why it was wrong and what the fix does*, with AS IS / TO BE diagrams, a
  runnable minimal example and tables instead of paragraphs. Linked from
  `README.md`; the policy is recorded in `AGENTS.md` ("History docs
  discipline"): the pair is bilingual and symmetric, entries run newest-first
  like this file, one fix is written once with every carrying release on a
  single line, and neither the pair nor this file may attribute a defect to a
  named consuming project.
- Two entries so far. **2.5.0 + 2.6.0, written as one entry** across both
  skills that carry the same fix — where a test gets its cases from
  (provenance, subject under layered protection, totality across dimensions).
  **2.7.0** — where a stub gets its truth from (an external system's behaviour
  is observed, never read).
- Applied that last rule to this file: five entries (2.7.0, 2.6.0, 2.5.0,
  2.4.0, 2.3.0) named a consuming project and cited its internal record paths
  and identifiers. Only the attribution was removed — every technical claim,
  verdict class and occurrence count is unchanged; the neutral form is "a
  field report from a consuming project".
- `scripts/check_language.py`: `docs/history.rus.md` joins the Russian
  allowlist (the second and last carve-out, after the root `README.md` and
  `__test__/README.md`); its English twin stays under the English-only rule.
  Verified load-bearing — removing the entry turns the gate red on 98 lines.
- New `__test__/test_history_docs.py` pins the whole policy: the pair exists
  and is symmetric, each half carries diagrams, tables and a runnable example,
  `README.md` links both, and neither the pair nor this file matches any
  defect-attribution shape. The attribution check is written by shape, never
  as a denylist of project names — naming them would reintroduce exactly what
  the rule forbids — and carries a guard-the-guard case proving it can fail.

## [2.6.0] — 2026-07-26

### `typescript-coding` 1.3.0 → 1.4.0 (minor: an existing skill's rules changed)

- Fixed OBS-20260726-001 (mirrored from `python-coding` OBS-20260726-001 /
  PR #11, commit 67fffe3, itself a field report from a consuming project,
  reviewer-confirmed class C3, `occurrences: 9`, universality threshold met
  on both limbs): `references/testing.md` §Hygiene carried a rule
  against hardcoding an expected value "so it passes", but no rule against
  the distinct pattern of a test's *case set*, its *subject*, or its
  *dimensional coverage* being chosen from the artifact under test rather
  than the specification — the same language-independent gap already fixed
  in `python-coding`, ported here in TypeScript idiom. Added one guidance
  block, three rules (identical in substance to `python-coding` 1.2.0):
  1. **Provenance of the case set** — derive cases from the specification's
     class, never copy or parametrize over the implementation's own
     `as const` array; a healthy mutation score is not evidence of
     specification coverage.
  2. **Subject of the test under layered protection** — a defence-in-depth
     claim is unverified until each layer is exercised on a path where it
     is the only protection.
  3. **Totality across the dimensions a control discriminates on** — name
     the dimensions a guard discriminates on and require at least one case
     per dimension; a surviving mutation is evidence of a missing
     dimension, not merely a missing case.

  Each rule ships its own deterministic, project-independent minimal
  reproduction snippet in TypeScript idiom (an `as const` registry vs.
  mutation case for rule 1; an upstream-filter-vs-downstream-serializer-
  overwrite case for rule 2; a normalized-vs-raw `Map`-key membership case
  for rule 3, with an exhaustive discriminated-union `switch` noted as the
  same pattern on a second dimension).
- Added a regression in `__test__/skills/test_typescript_coding.py`
  (`TestCaseProvenanceSubjectAndDimensionGuidance`): pins the presence of
  each rule's load-bearing clause and its illustrative reproduction, a
  negative guard that the pre-existing, distinct "do not tune a test to the
  gate" rule survives untouched, and a duplication guard. Confirmed
  genuinely red before the delta (5 failing assertions against the
  pre-change text) and green after (679/679 for the library).
- Added four eval cases to `__test__/evals/typescript-coding/cases.json`
  (three `behavior`, one `negative`) exercising each rule and a
  false-positive guard against over-applying rule 3 to a genuinely
  single-dimension input. Schema-validated
  (`run_skill_evals.py --validate-only`); the LLM-backed execution is the
  Hub's opt-in eval runner, not part of this local run.

`uv run skillctl validate typescript-coding` && `uv run skillctl test`:
679/679 passed, no regressions. Non-main branch; no push to `main`, no tag,
no release — PR only.

## [2.5.0] — 2026-07-26

### `python-coding` 1.1.0 → 1.2.0 (minor: an existing skill's rules changed)

- Fixed OBS-20260726-001 (field report from a consuming project, reviewer-
  confirmed class C3, `occurrences: 9`, universality threshold met on both
  limbs): `references/testing.md` §Hygiene carried a rule
  against hardcoding an expected value "so it passes", but no rule against
  the distinct pattern of a test's *case set*, its *subject*, or its
  *dimensional coverage* being chosen from the artifact under test rather
  than the specification — silence that let the class recur nine times
  across a single build, every instance found by a live probe or a
  mutation battery, never by the suite that was supposed to guard the
  property. Added one guidance block, three rules:
  1. **Provenance of the case set** — derive cases from the specification's
     class, never copy or parametrize over the implementation's own
     enumeration; a healthy mutation score is not evidence of specification
     coverage.
  2. **Subject of the test under layered protection** — a defence-in-depth
     claim is unverified until each layer is exercised on a path where it
     is the only protection.
  3. **Totality across the dimensions a control discriminates on** — name
     the dimensions a guard discriminates on and require at least one case
     per dimension; a surviving mutation is evidence of a missing
     dimension, not merely a missing case.

  Each rule ships its own deterministic, project-independent minimal
  reproduction snippet (an `ALLOWED = {...}` enum-vs-mutation case for rule
  1; an upstream-filter-vs-downstream-overwrite case for rule 2; a
  normalized-vs-raw-key mapping case for rule 3), reproduced from the
  reporting reviewer's own executed verification (rule 3: `303 passed`
  before the remedy, `11 failed` after a single case varying the key's form
  was added).
- Added a regression in `__test__/skills/test_python_coding.py`
  (`TestCaseProvenanceSubjectAndDimensionGuidance`): pins the presence of
  each rule's load-bearing clause and its illustrative reproduction, a
  negative guard that the pre-existing, distinct "do not tune a test to the
  gate" rule survives untouched, and a duplication guard. Confirmed
  genuinely red before the delta (5 failing assertions against the
  pre-change text) and green after (119/119 for `python-coding`, 673/673
  for the library).
- Added four eval cases to `__test__/evals/python-coding/cases.json` (three
  `behavior`, one `negative`) exercising each rule and a false-positive
  guard against over-applying rule 3 to a genuinely single-dimension input.

## [2.4.0] — 2026-07-24

### `python-coding` 1.0.0 → 1.1.0 (minor: an existing skill's layers changed)

- Fixed OBS-20260724-001 (field report from a consuming project,
  reviewer-confirmed class C3): shipped prose in
  `knowledge/patterns.md`, `knowledge/pitfalls.md` and
  `references/typing-and-style.md` linked into `data/fixtures/*`, which a
  `runtime` install strips (`RUNTIME_EXCLUDED_PREFIXES`) — 7 dangling
  references across 3 files. The citations are now plain code spans (not
  markdown links) with an explicit "Hub-only, not shipped in `runtime`
  installs" note, and `data/README.md`'s Purpose bullet states the same
  install-mode split the Layout section already described.
- Added a regression in `__test__/skills/test_python_coding.py`
  (`TestRuntimeInstallLinkResolution`): every markdown link in a `runtime`-
  installed copy of the skill must resolve on disk, with a negative guard
  that a `full` install (which does ship `data/fixtures/`) keeps the very
  same links resolving too.

## [2.3.0] — 2026-07-24

### `typescript-coding` 1.2.0 → 1.3.0 (minor: an existing skill's layers changed)

- Fixed OBS-20260724-001 (field report from a consuming project,
  reviewer-confirmed class C3): shipped prose in
  `knowledge/patterns.md`, `knowledge/pitfalls.md` and
  `references/typing-and-style.md` linked into `data/fixtures/*`, which a
  `runtime` install strips (`RUNTIME_EXCLUDED_PREFIXES`) — 4 dangling
  references across 3 files. `observations/INDEX.md` additionally stated the
  candidates-are-not-shipped rule and then linked
  `candidates/OBS-20260713-001.md`, contradicting it two lines later; that
  link is now plain, non-shipped-annotated text. `data/README.md`'s Purpose
  bullet now states the same install-mode split its Layout section already
  described.
- Also fixed, per the Reviewer's transfer note: the shipped
  `observations/accepted/OBS-20260715-001.md` cited
  `data/fixtures/justified_rule_disable.ts` as its own reproduction evidence
  without disclosing it is unreachable in a `runtime` install; the evidence
  entry and reproduction text now say so explicitly and point a `runtime`
  consumer at the equivalent test instead.
- Added a regression in `__test__/skills/test_typescript_coding.py`
  (`TestRuntimeInstallLinkResolution`): every markdown link in a `runtime`-
  installed copy of the skill must resolve on disk; a negative guard checks
  a `full` install (which does ship `data/fixtures/` and
  `observations/candidates/`) keeps the same links resolving, and a third
  test pins the accepted-observation evidence annotation.

## [2.2.0] — 2026-07-17

### `python-coding` 1.0.0, promoted to `stable` (minor: an existing skill's catalog contract changed)

- The eval-gate that held the skill at `draft` has been passed for real: `scripts/run_skill_evals.py --platform claude --repeat 3 --command 'claude -p {prompt}'` against the live Claude Code CLI — **30/30 PASS** across the 10 trigger/behavior/negative cases (each case installed fresh into a temporary project per attempt).
- `skills.yaml`: `python-coding` `0.2.0 draft` → `1.0.0 stable`; the skill is now installable for consumers (`draft` means "not for installation").
- Eval oracle hardening found by the gate itself: the `subprocess-never-shell-true` case forbade the bare substring `shell=True`, which a fully compliant answer can legitimately *mention* in prose ("never use shell=True"); the forbidden markers are now the code forms `, shell=True` and `os.system(`, so only actually recommending the unsafe call fails the case.

## [2.1.0] — 2026-07-17

### `python-coding` 0.2.0 (minor: the rules of an existing skill changed)

The skill is strengthened into a **secure-by-default, modern (3.12–3.14) Python standard** — still framework-, architecture- and library-neutral by contract.

- Four new `references/`: **security** (parameterized SQL and argument-list subprocess, no `eval`/`exec` on data, no pickle/`yaml.load` on untrusted input, path containment via `resolve()` + `is_relative_to`, `mkstemp`-family temp files, tarfile `filter=`, `secrets` + `hmac.compare_digest`, memory-hard password hashing, TLS verification never disabled, ReDoS awareness, secrets hygiene); **concurrency** (structured concurrency with `asyncio.TaskGroup` and `asyncio.timeout`, no fire-and-forget, `CancelledError` propagation, no blocking calls on the loop, thread locking that never leans on the GIL, model choice incl. 3.14 subinterpreters and free-threading); **runtime-correctness** (aware-UTC datetimes, monotonic clocks for durations, `Decimal` money, context-managed resources with `__del__` banned, `lru_cache`-on-method leak, join-over-`+=`); **modern-python** (version-gated adoption for 3.12/3.13/3.14: PEP 695 generics and `type` aliases, `TypeIs`, `ReadOnly`, `@override`, native lazy annotations, t-strings, plus an explicit banned-legacy table).
- Existing references upgraded: exception groups/`except*` and `add_note`, retry/timeout discipline, library-logging rules (`NullHandler`, log-once-per-failure, constant message templates) in errors-config-logging; `TypeIs`-over-`TypeGuard` and `NotRequired`/`ReadOnly` in type-design; PEP 696 defaults in generics; async section of lint-clean routed to concurrency; property-based/async-test/exception-assert rules in testing. The superseded `gather`-by-default guidance is replaced by `TaskGroup`-first.
- `scripts/check_py_conventions.py` gains seven high-signal security rules — `PY-EVAL`, `PY-SHELL`, `PY-PICKLE`, `PY-YAML-LOAD`, `PY-MKTEMP`, `PY-UTCNOW`, `PY-TLS-NOVERIFY` — with no test-file relaxation; fixtures, the calibrated example pair, per-rule tests and eval cases updated accordingly.

## [2.0.0] — 2026-07-17

### New skill: `python-coding` 0.1.0 (major: a skill was created)

A **universal, strictly-typed Python coding standard**: framework-, architecture- and library-neutral by contract; catalogued as `status: draft` until the eval-gate is run against a real harness (`__test__/evals/python-coding/cases.json` ships with trigger/behavior/negative cases).

- The rule surface: a strict type checker (mypy `--strict`/pyright strict) whose configuration is never weakened; no `Any` and no unproven `cast()`; closed sets as `enum.StrEnum`/`Literal` unions; `NewType`-branded ids with a validating constructor at the boundary; tagged unions with `match` closed by `assert_never`; frozen dataclasses, `Final`, `Sequence`/`Mapping` parameters (immutable by default); explicit booleans and `x if x is not None else d` over `x or d`; supervised coroutines with `gather` for independent awaits; narrowest `except` with `raise ... from` once at the source; centralized `os.environ`; no `print`; docstrings describing intent without restating types; a single formatter (Black/Ruff); mutable default arguments banned; `assert` banned as shipped-code validation (stripped under `-O`); no `breakpoint()`/`set_trace()` left behind; parse-don't-cast boundary validation with one source of truth per shape; tests in the same change.
- Six `references/` (typing-and-style, type-design, generics-and-protocols, lint-clean, errors-config-logging, testing), `knowledge/` patterns + pitfalls with evidence links, calibrated `data/` fixtures/examples, and an `agents/openai.yaml` adapter — the library's standard layered anatomy.
- New analyzer `scripts/check_py_conventions.py`: a Python-source lexical masking scanner (comments, string literals incl. triple-quoted; f-string interpolation code is still scanned) with the same strict fail-closed `skill-check-ignore: <CODE> -- <reason>` suppression contract as the library's other analyzers. Rules: `PY-PRINT`, `PY-ENV`, `PY-ANY`, `PY-SUPPRESS` (a single-rule, line-scoped, justified `# noqa: <RULE> -- <reason>` is the one sanctioned escape; `type: ignore` has none), `PY-BARE-EXCEPT`, `PY-ASSERT`, `PY-DEBUG`; test/config path contexts relax exactly the rules the references relax. Named `check_py_conventions.py` (not `check_conventions.py`) so every mutation-scope module keeps a unique short name for `scripts/mutation.py`.
- Test suite `__test__/skills/test_python_coding.py` (fixture contract, exact scanner views, masking, suppression bypass battery, path contexts, determinism, IO edge cases, in-process driver); the analyzer joins the coverage sources and the mutmut `only_mutate` scope in `pyproject.toml`; root `README.md`, `AGENTS.md` and `CLAUDE.md` updated.

## [1.5.0] — 2026-07-17

### `typescript-coding` 1.1.1 → 1.2.0 — type-design and generics rules from the source literature

The skill's rules are strengthened from two books — Dan Vanderkam, *Effective TypeScript* (2nd ed., 83 items) and Stefan Baumgartner, *TypeScript Cookbook* — while staying universal (no framework/architecture assumptions) and consistent with a strict reference ESLint stack (typescript-eslint strictTypeChecked, airbnb, SonarJS, functional, jsdoc, Prettier-owned formatting).

- New `references/type-design.md`: invalid states unrepresentable (tagged unions over flag bags, no in-domain sentinels, optional-`never` exclusivity), discriminated unions as the default state model, exhaustive `switch`es closed with a `never` check, wide inputs / narrow outputs, nullability at the perimeter, `satisfies` vs annotation vs `as const`, type-guard/assertion-function soundness discipline, parse-don't-assert trust boundaries with one source of truth per shape, and structural-typing consequences (open types, excess-property freshness, `Object.keys`, `Map` for dynamic keys, ES `#private` for runtime privacy).
- New `references/generics-and-type-level.md`: the golden rule of generics (a type parameter must relate two types; no return-only generics), constraints/defaults/naming, conditional return types vs overloads, variadic and labeled tuples, type-level DRY (`keyof`, mapped types, `Record<keyof T, V>`, utility-type composition, shallowness caveats), template literal types with tail-recursive parsing, and "keep types simple; type-level-test the complex ones".
- `typing-and-style.md`: no annotations on inferable locals, parameter defaults in the signature, domain vocabulary and units in names; `@ts-expect-error` clarified as banned in shipped code with its one sanctioned home in negative type-level tests.
- `testing.md`: types-vs-tests division of labour (don't test type-forbidden inputs; test harmful bypasses via `@ts-expect-error` + runtime enforcement; unit-test every type guard with near-miss values; type-level tests for nontrivial utilities).
- `knowledge/`: +4 patterns (discriminated union + `assertUnreachable`, `satisfies` registries, narrow structural test seams, one source of truth per boundary shape) and +5 pitfalls (excess-property freshness, `Object.keys` is `string[]`, `filter(Boolean)` doesn't narrow, shallow `Readonly`/`Partial`/spread, TS `private` is compile-time only), all with evidence links.
- SKILL.md: new workflow step "Design the types before the code", routing rows for both new references, and four new hard rules; skill README updated accordingly.

The one deliberate deviation from the books: constructor parameter properties stay encouraged (the reference ESLint stack mandates them); the books' advice against TS-only runtime features is adopted only for `namespace`/`enum`/triple-slash references. The convention checker (`scripts/check_conventions.py`) is unchanged.

## [1.4.1] — 2026-07-17

This release rebuilds the `hexagonal-service` skill from the source literature and adds user-facing documentation to every skill in the library. It aggregates the unpublished versions 1.3.0 and 1.4.0 (their full entries are below); the previous published release was 1.2.0.

### `hexagonal-service` 1.0.0 → 2.1.1 — from a hardwired layout to a neutral canon

**2.0.0 — neutral ports-and-adapters canon** (derived from Cockburn & Garrido de Paz, *Hexagonal Architecture Explained*). The skill no longer mandates one directory layout. It is now **neutral by contract on three axes** — languages/frameworks, approaches, and projects: the concrete adoption strategy must be declared in the host project's rules, which always take precedence.

- `references/architecture.md` rewritten as the pattern canon: the invariant core (ports as the app boundary, no source dependencies on actors, runtime-swappable driven actors, technology-neutral contracts, the test wall), the configurator's wiring styles, port design and granularity.
- New `references/approaches.md`: ways to structure the inside (two-layer, layered, onion/clean) and relations to use cases, DDD, CQRS.
- New `references/strategies.md`: a catalog of adoption strategies (module-first / layer-first / domain-first / ports-first layouts; walking-skeleton and strangler rollouts; migration paths) plus the exact list of what project rules must declare.

**2.1.0 — rules strengthened** (derived from Vieira, *Designing Hexagonal Architecture with Java*, 2nd ed., folded in as a complement to the Cockburn/Garrido canon).

- New `references/domain-modeling.md`: rich entities, value objects, aggregates with one repository-port per root, specifications, policies, domain services, and the business-knowledge practices (ubiquitous language, subdomains, Event Storming, written-first use cases).
- Architecture canon extended: Vieira ↔ Cockburn terminology table, extended actor catalog, many-adapters-per-port, "output port is not a repository".
- Approaches extended: the Domain/Application/Framework three-hexagon dialect, SOLID-to-hexagon mapping, adapter categories, a sharper "when not to use it".
- Strategies extended: staged hexagon build, layered → hexagonal migration recipe, and new project-declared knobs (DTO policy, DI annotations in the application layer).

### Per-skill documentation (1.4.1)

Every published skill now ships a skill-root `README.md` — English, user-facing docs: what the skill does, key features, how to install it, and how to combine it with the host project's rules (e.g. `.claude/rules`). Linked from the root `README.md`.

- Skill versions: `example-skill` **0.2.0 → 0.2.1**, `typescript-coding` **1.1.0 → 1.1.1**, `hexagonal-service` **2.1.0 → 2.1.1**, `typescript-nestjs` **1.1.0 → 1.1.1** (patch each: documentation only, no rule changes).
- The validator now allows a skill-root `README.md` (alongside `data/README.md`; other auxiliary docs such as `CHANGELOG.md` stay forbidden); the installer excludes it from `runtime`-mode installs — the agent reads `SKILL.md`, `full` mode still ships it. Tests pin the allowance, the still-forbidden `CHANGELOG.md`, and the runtime-mode exclusion; AGENTS.md/CLAUDE.md updated to the new policy.

**Full Changelog**: https://github.com/volkovpv/Ai-Code-Skill-Hub/compare/v1.2.0...v1.4.1

## [1.4.0] — 2026-07-17

- `hexagonal-service` **2.0.0 → 2.1.0** (minor: rules strengthened — derived from studying Vieira, *Designing Hexagonal Architecture with Java*, 2nd ed., folded in as a complement to the Cockburn/Garrido canon without changing the invariant core). New `references/domain-modeling.md` catalogs the domain building blocks (rich entities vs the anemic model, value objects, domain-generated identity, aggregates with one repository-port per root and writes only through the root, specifications, policies, domain services, the value-objects → entities → specifications → services build order) and the business-knowledge practices (ubiquitous language, subdomains, bounded contexts as module-scale SRP, Event Storming, written-first use cases whose scenarios become the port tests). `references/architecture.md` gains a Vieira ↔ Cockburn terminology table (the use-case/input-port name inversion), an extended actor catalog (health probes, hexagon-to-hexagon calls, brokers as driven actors even for inbound messages), the many-adapters-per-port rule, the "output port is not a repository" framing, and the input-port-contract-hides-data-needs rule. `references/approaches.md` gains the Domain/Application/Framework three-hexagon dialect of the layered approach, a deeper layered-vs-hexagonal comparison (judge claims by the driven side), a SOLID-to-hexagon mapping, adapter categories (driven categories carry the translation tax), and a sharper "when not to use it" section. `references/strategies.md` gains the staged hexagon build rollout (domain → application → framework, green-tested per stage), the layered → hexagonal migration recipe, module-system boundary enforcement with a bootstrap/aggregator module for the layer-first layout, and two new project-declared knobs: the DTO policy and whether DI container annotations are allowed in the application layer — both defaulting to the strict rules (full DTO chain; plain classes wired externally), with the domain framework-free under every strategy. Checklist, `SKILL.md`, catalog summary, and the OpenAI adapter updated; per-skill tests extended to pin the new content.

## [1.3.0] — 2026-07-17

- `hexagonal-service` **1.0.0 → 2.0.0** (major reframe of the skill's contract: from one hardwired layout to a neutral canon; derived from studying Cockburn & Garrido de Paz, *Hexagonal Architecture Explained*). The skill is now explicitly neutral on three axes — languages/frameworks, approaches, and **projects**: the concrete adoption strategy must be declared in the host project's rules, which always take precedence. `references/architecture.md` is rewritten as the pattern canon (the invariant core the pattern actually requires — ports as the app boundary, no source dependencies on actors, runtime-swappable driven actors, technology-neutral contracts, the test wall — plus elements, the configurator's three wiring styles, port design and granularity, symmetry/asymmetry). New `references/approaches.md` maps the ways to structure the inside (strict two-layer, layered domain → application → infrastructure, onion/clean refinements) and relations to neighbors (use cases, DDD/bounded contexts/ACL, CQRS, Component + Strategy, why the pattern does not nest). New `references/strategies.md` catalogs adoption strategies a project picks from — layout (module-first, layer-first, domain-first, ports-first, hexagon-per-service), rollout (walking skeleton test-to-test → real-to-real, inside-out), migration (test-wall-first, seam extraction, strangler fig) — with a resolution order and the list of what project rules must declare. The former module-first layout is kept as an illustration under that strategy, no longer as the skill's mandate. Error-flow and boundaries-and-io discipline unchanged; `SKILL.md`, the catalog summary, and the OpenAI adapter updated to the new contract.

## [1.2.0] — 2026-07-17

- `typescript-coding` **1.0.1 → 1.1.0** (minor: rules strengthened — derived from studying a real consumer's ESLint + tsconfig). The skill now steers code to pass a strict, type-aware lint stack (typescript-eslint `strictTypeChecked` + `stylisticTypeChecked`, airbnb base/TypeScript, SonarJS, `eslint-plugin-functional`, `eslint-plugin-jsdoc`, with formatting delegated to Prettier) with **zero errors and zero warnings**, not only a clean compile. New universal reference `references/lint-clean.md` organizes the generalizable rule surface the compiler does not cover — explicit boolean expressions (`strict-boolean-expressions`), `??` over `||` and optional chaining, no floating/misused promises and `Promise.all` over serial `await`, immutable data (`functional/immutable-data`, `no-param-reassign`, `prefer-readonly`), precise types (no `any`/unsafe leaks, `as`-only assertions, `no-inferrable-types`, banned type names), naming and class shape (accessibility, member order, parameter properties), named literals and low complexity (`no-magic-numbers`, `sonarjs/*`, complexity/length caps), JSDoc on the public surface, import ordering, and single-formatter hygiene. Wired into `SKILL.md` (new workflow step, routing row, rules bullet, description) and a new high-yield `knowledge/pitfalls.md` entry on truthy checks and `||` defaults. Kept vendor-neutral: framework-specific calibrations (NestJS DI tokens, Fastify boundaries) remain out of this skill and route to `typescript-nestjs`. Thresholds are described as host-project config, not hardcoded. The heuristic `check_conventions.py` is unchanged — the added rules are type-aware and out of a lexical scanner's reach; the reference points at the project's real `lint`/`typecheck` as authoritative.

## [1.1.0] — 2026-07-17

- `typescript-nestjs` **1.0.0 → 1.1.0** (minor: new rule, OBS-20260717-001 — transferred from a real consumer run). New checker rule `NEST-HTTP-STATUS-LITERAL`: a raw numeric HTTP-status literal (e.g. `404`, `204`) is now flagged wherever it stands in for the canonical `HttpStatus.*` registry (`@nestjs/common`) — a thrown `HttpException`'s status argument, an `@HttpCode(...)` decorator argument, a `Map`/array-literal status-map entry key, and a `.toBe(...)`/`.toEqual(...)` test assertion in a test-path file. The standard HTTP status-code set disambiguates a genuine status literal from an unrelated 3-digit magic number; negative tests pin identifier-based `HttpStatus.*` forms, non-status numbers, and number/number pairs as clean, plus the existing literal-in-comment/-string masking. Mirrored as an explicit example in `references/http-boundary.md`. New calibrated fixture `data/fixtures/raw_http_status_literal.ts`; concrete trigger observed in a consumer project (`STATUS_TO_PROBLEM_CODE` built as `new Map<number, ProblemCode>([[400, ...], ...])` with `HttpStatus` imported and left unused, plus `expect(...).toBe(404)`-style test assertions).

## [1.0.1] — 2026-07-15

- `typescript-coding` **1.0.0 → 1.0.1** (patch: false-positive fix, OBS-20260715-001, first accepted observation — transferred from a real consumer run). `TS-SUPPRESS` no longer fires on a *justified, single-rule, line-scoped* eslint disable — `// eslint-disable-next-line <one rule> -- <written reason>` (or the `eslint-disable-line` variant) — the sanctioned way to hold a documented upstream limitation of a lint rule (concrete trigger: `@typescript-eslint/promise-function-async` with `allowAny: false` reporting synchronous `unknown`-returning helpers). Everything wider still fires and is pinned by a negative-guard battery: file/block-scoped `eslint-disable` (with or without a rule and reason), multi-rule and unjustified/rule-less line disables, `@ts-ignore`/`@ts-nocheck` (even with a reason), and a type suppression sharing the line with a justified disable; directive text inside a string stays data, and `TS-SUPPRESS` itself remains unsuppressable via `skill-check-ignore`. Prose rule mirrored in `references/typing-and-style.md` and `SKILL.md`; new calibrated fixture `data/fixtures/justified_rule_disable.ts`.
- Mutation-testing infrastructure repair: the stats phase of every `mutmut run` failed before trying a single mutant (reproduced on clean `main`), because `test_real_library_passes` also runs from mutmut's copied tree, where the trampoline-rewritten skill analyzer scripts legitimately exceed `max_tracked_file_bytes`. The test now ignores only that known artifact inside the `mutants/` copy and still asserts a clean real library everywhere else.
- New local mutation wrapper `scripts/mutation.py` (stdlib-only, not used by CI): caps `mutmut`'s parallelism to `CPU − 2` (mutmut otherwise forks one worker per core and saturates the machine — there is no config knob, only the `--max-children` CLI flag) and, given a changed source file or its short name, runs `mutmut run` for just that file's mutants. The mutant glob is derived exactly as mutmut derives it (suffix dropped, `os.sep` → `.`, leading `src.` stripped) and the mutatable-file set is read from `[tool.mutmut].only_mutate`, so no module list is hand-maintained; a source outside the scope is a no-op (exit 0). Editing-agent guidance in `AGENTS.md`/`CLAUDE.md` now mandates the scoped run over a local full-scope pass; covered by `__test__/test_mutation_wrapper.py`.

## [1.0.0] — 2026-07-14

- Three new skills (major: skills were added), split by concern per the audit:
  - `typescript-coding` — a **universal** TypeScript coding standard, explicitly free of framework, architecture, and library assumptions: strict tsconfig flags, `as const` registries (no native `enum`), branded ids, readonly-by-default, `unknown` in catch with cause-preserving single wraps, centralized env access, test-in-the-same-change discipline. Ships three `references/`, `knowledge/` patterns + pitfalls, calibrated `.ts` fixtures/examples, and one **candidate** observation (unreviewed by design — promotion is a separate reviewed change).
  - `hexagonal-service` — a **language- and framework-agnostic** ports-and-adapters architecture standard: layer model with a composition root, dependency-inward boundaries, one use case per input port, thin adapters, and the single sanctioned error flow (typed domain errors from one root; a foreign error is wrapped exactly once at the driven adapter with its `cause`, bubbles untouched, and is logged with the stack and mapped to transport exactly once in the boundary filter; re-wrapping in intermediate layers is forbidden), plus boundary validation (400 vs 422), RFC 9457 envelopes with masked 5xx, fail-closed config, correlation ids, resilience policies, and an inside-out recipe/review checklist.
  - `typescript-nestjs` — NestJS specifics on top of the two above: named `unique symbol` DI tokens, plain use-case classes assembled by `useFactory` providers, controllers as mappers behind a global `ValidationPipe`, `APP_GUARD` + `@Public`, exception filters that log once and map domain errors to HTTP once, fail-closed env validation behind `@nestjs/config`, and `@nestjs/testing`/`overrideProvider` conventions.
- Rewrote `check_conventions.py` (typescript-coding) around a lexical masking scanner: string literals, template literals (interpolated `${...}` code is still scanned), regex literals, and comments can no longer produce false positives on quoted rule text; `TS-SUPPRESS` scans only comment text. The suppression contract is strict and fail-closed: only `skill-check-ignore: <CODE> -- <non-empty justification>` (specific known codes, mandatory reason) suppresses; a bare marker, unknown code, empty justification, or any malformed pragma aborts with exit 2, and `TS-SUPPRESS` itself can never be suppressed. Architecture-bound rules (`TS-RAW-THROW`, `TS-DI-TOKEN`) moved out of the universal checker.
- New layer-aware checker `check_nest_conventions.py` (typescript-nestjs): `NEST-DI-TOKEN` (string/inline-`Symbol()` `@Inject`), `NEST-RAW-THROW` (raw throws in `domain`/`application` only), `NEST-DOMAIN-IMPORT` (framework imports in the domain core), `NEST-APP-IMPORT` (runtime `@nestjs/*` imports in application; `import type` allowed) — same masking scanner and strict suppression contract, path-based layer detection.
- Analyzer test suites rebuilt and extended (`__test__/skills/`, 120+ tests): the checkers are imported in-process, so line+branch coverage and mutation testing now include `skills/*/scripts/` (see the coverage sources in `pyproject.toml` and the extended mutmut scope gated by `mutation.yml`), with a shared exact-output scanner-conformance battery pinning both checker copies; coverage spans `.ts/.mts/.cts`, literals/comments/regex masking, every suppression bypass, test/config/layer path contexts, directory scanning, output determinism, IO errors, and encoding edge cases.
- Eval manifests for all three skills (`__test__/evals/<skill>/cases.json`, schema v1) with positive/trigger, behavior, boundary, negative, and project-instructions-conflict cases; CI validates every manifest offline. The eval-gate was run against a real harness and passed for all three (7/7, 7/7, 6/6), so each is catalogued as `status: stable` at skill version `1.0.0`.
- Validator: `agents/*.yaml` adapters must now parse in the in-house YAML subset and be a mapping (fail-closed); each skill ships an `agents/openai.yaml` with a `default_prompt` stating its activation scope, boundaries, and project-instructions precedence, pinned by per-skill tests.
- Language policy gate: new `scripts/check_language.py` (CI step + `__test__/test_language_policy.py`) forbids Cyrillic text outside the root `README.md`, `__test__/README.md`, and `_audit/`; Unicode test data uses explicit `non-english-ok: <reason>` waivers. Russian comments in `ORIGIN.yaml` files, `.gitignore`, and workflow files were translated; the validator's TOC-heading check is English-only now.

## [0.0.5] — 2026-07-13

- Security: closed a path-traversal hole in the observation review path (audit C-1). `skillctl observation approve/reject` now validates the observation id against `OBS-YYYYMMDD-NNN`, derives the destination from the on-disk file name (never the untrusted frontmatter `id`), and routes the write through `security.safe_join`, so a candidate carrying a forged `id` can no longer write outside the skill directory. The candidate gate is now the containing directory, not the (forgeable) frontmatter `status`.
- Robustness against untrusted/nonstandard inputs: observation approval and validation reject evidence that is only blank strings (`[""]`, audit M-8); a single malformed observation file no longer blocks `add`/`list`/`review` (M-9); `installer.status()` skips non-mapping lock entries instead of crashing (M-3); `install` gives a clear error and is recoverable with `--force` when a plain file sits where the skill directory should go (M-4); `skillctl new` refuses a name already registered in `skills.yaml` and `load_catalog` rejects duplicate entries (M-7); the YAML parser keeps zero-padded integers (`007`) as strings per YAML 1.2 (M-17).
- EOL determinism (audit H-2, M-1): a `.gitattributes` (`* text=auto eol=lf`) now pins LF across every platform, so the sha256 hashes the installer records in `.agent-skills.lock.yaml` stay stable regardless of a contributor's `core.autocrlf` and cannot spuriously flag an installed file as "locally modified". `scripts/bump_version.py` preserves each file's original line endings (`newline=""`) instead of silently rewriting CRLF to LF.
- Release gate rename-awareness (audit H-1): `scripts/check_release_gate.py` classifies changes via `git diff --name-status -M` instead of `--name-only`, which collapsed a rename to its new path only. Moving used code out of a released location (e.g. `src/foo.py` → `_attic/foo.py`) or deleting it is now correctly counted as a used-code change — a rename is release-relevant if either endpoint is used code — so such a change can no longer masquerade as infra-only and skip the release.
- Graceful handling of non-UTF-8/broken inputs (audit H-3): a binary or mis-encoded file in the skill tree no longer crashes `skillctl list`/`validate`/`knowledge list` with a bare `UnicodeDecodeError`. `yamlio.load_file` raises `YamlError`, `discovery.load_skill` raises `DiscoveryError`, and the validator records a fail-closed problem instead of aborting; `main()` also gained a top-level safety net (`OSError`/`UnicodeDecodeError`/`DiscoveryError`/`SecurityError` → `error: …`, exit 1) so no command can emit a raw traceback.
- Atomic version bump (audit H-4, L-9): `scripts/bump_version.py` now computes every file's new text in a pre-flight pass and touches disk only once all substitutions have matched, writing each file through a temp file + `os.replace` and rolling the already-written files back to their original bytes on any mid-commit IO error. A bump that fails on a regenerated/incomplete `uv.lock` no longer leaves `pyproject.toml` and `__init__.py` stamped ahead of the CHANGELOG. A non-`X.Y.Z` current version (e.g. a `rc` tag) now yields a diagnosable error instead of a bare `ValueError`, and the docstring examples are version-neutral.
- Validator type robustness (audit H-6, M-2): a wrong-typed structural field in `skills.yaml` no longer crashes `skillctl validate` with a bare `ValueError`. `CatalogEntry.from_dict` rejects a list `capabilities:`/`content_policy:` and a scalar `platforms:` (which `list("linux")` would silently split into characters) with a clear, skill-attributed message that `load_catalog` surfaces as a fail-closed `DiscoveryError`/problem; a non-numeric `content_policy.max_tracked_file_bytes` degrades to the standard range problem instead of a traceback.
- Secret-scan negative coverage (audit H-5): all seven heuristics in the content-policy secret scan (private key, AWS `AKIA`, GitHub `ghp_`/`github_pat_`, Slack `xox…`, `sk-`, and the generic hardcoded-credential pattern) now each have a positive test (an obviously-fake marker is caught) and a negative test (a non-secret look-alike is not flagged), plus a structural test asserting every scanner pattern has a paired case — so a mutation or typo in any single regex now fails a test instead of passing silently. Test-only change; also adds an explicit UDP `sendmsg` deny test for the network blocker (audit L-16).

## [0.0.1] — 2026-07-13

- Hardened skill testing: stable gates, placeholder and network bans in Python tests, transactional installer rollback, coverage/mutation gates and executable eval manifests.
- The project moved to Python ≥ 3.12 (`requires-python`, `uv.lock`, CI, documentation).
- Audit follow-ups: `skillctl test <skill>` looks up tests by exact module name (`test_<name>.py`) — prefix collisions between skills are ruled out; the YAML parser rejects empty flow-list items (`[a,,b]`); the link-install message no longer reports a bogus copied-file count; the test network blocker additionally denies UDP `sendto`/`sendmsg`; killer tests were added after triaging surviving mutants (previous-scope score 76.6% → 81.2%); the mutation-testing scope was extended to `yamlio.py` and `validator.py` (2034 mutants, score 78.6% against the 75 gate).

## [0.0.0] — 2026-07-12

Baseline: no published releases yet. Version `0.0.0` is never published —
releases start with the first version bump.
