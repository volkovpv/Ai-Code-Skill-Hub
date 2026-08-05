# AGENTS.md — rules for developers and coding harnesses working on this library

## Structure invariants

- Canonical skills live only in `skills/`; the directory name is fixed.
- All tests live only in `__test__/`; the directory name is fixed (not `tests`).
- `templates/skill/` is a scaffold, not a published skill — never validate or
  install it directly.
- Keep canonical skills vendor-neutral. Anything specific to one harness or one
  model vendor goes into the skill's `agents/` adapter files or into installer
  code, never into `SKILL.md`.
- A **vendor** is a model supplier (`vendors.yaml`); a **platform** is a harness
  (`platforms` in `skills.yaml`). They are separate axes — never conflate them.
  Every skill carries exactly one `agents/<vendor>.yaml` per declared vendor,
  and an adapter holds interface wiring only (`interface.display_name`,
  `interface.short_description`, `interface.default_prompt`). A rule in an
  adapter would bind one vendor and not the others, which is the split
  `SKILL.md` exists to prevent.
- There is no `vendors/` directory inside a skill and there will not be one. A
  skill's directories divide content by the *status* of the knowledge (rule,
  verified generalization, observation, data); a vendor is the *scope* of a
  record — an attribute value, not a status. A directory per attribute value
  gives a second, crossing division: a rule with one vendor-specific exception
  loses its single address, and the same logic would next demand directories
  per language and per framework. Installation copies directories whole, so
  `vendors/` would also ship every vendor's corpus to every consumer.
- Do not put product- or project-specific decisions into universal skills.
- **Skills are installed one at a time and must stand alone.** No skill may
  depend on another being present: a rule is never stated only by pointing at
  a sibling, and a sibling's rule codes, file paths, section names or pinned
  versions are never quoted. The same rule restated in two skills is the
  accepted price of that independence — what is forbidden is the reference,
  not the duplicate; copies that contradict each other are the real defect.
  A sibling may be *named* only in the conditional form ("where the host
  project also declares an architecture standard, apply it on top"), which an
  agent can act on when both skills happen to be attached and ignore when
  they are not. Gated by `__test__/skills/test_skill_boundaries.py`; the
  skill-root `README.md` is exempt because it is never installed.
- Do not duplicate content between `SKILL.md` and `references/`: `SKILL.md`
  stays short and imperative, details live in `references/` and are loaded on
  demand.
- Do not add `CHANGELOG.md` and similar auxiliary documents inside a skill.
  The only exceptions are the skill-root `README.md` (English, user-facing
  docs for library consumers; excluded from runtime installs — the agent
  reads `SKILL.md`) and `data/README.md` — the dataset contract.
- Optional layers `knowledge/`, `data/`, `observations/` are capabilities, not
  requirements: a skill with only `SKILL.md` + `references/` + `scripts/` +
  `assets/` stays valid. Do not create empty layers "for structure".
- Do not create a `history/` directory inside a skill — Git history is the
  history. This is about the skill layers; it does not touch the repository-level
  narrative pair `docs/history.eng.md` / `docs/history.rus.md`, which is governed
  by "History docs discipline" below.

## Knowledge and observation discipline

- Preserve progressive disclosure: `description` → `SKILL.md` body → deeper
  files strictly on demand. Never make `SKILL.md` require pre-reading the
  whole knowledge/data corpus; route to specific files with explicit triggers.
- Never turn an unverified observation into a rule. New observations go to
  `observations/candidates/` via `skillctl observation add`; promotion to
  `accepted/` happens only through `skillctl observation approve` with a
  human reviewer. Promotion of an accepted observation into `knowledge/` or
  the SKILL.md workflow is a separate, reviewable change.
- Every observation needs reproducible evidence (test, fixture, commit,
  scenario). Subjective impressions without evidence must not be recorded as
  knowledge.
- **A new observation names no sibling skill's internals.** A record that
  mirrors a fix already made elsewhere in this library says so neutrally —
  "a sibling skill in the same library" — never with that skill's path,
  version, PR number or commit, for the same reason a consuming project is
  never named in `CHANGELOG.md`. Accepted records predating this rule are
  history and stay as they are; the gate covers `observations/INDEX.md`, not
  the records themselves.
- `knowledge/` holds only verified, generalizable statements with an explicit
  applicability scope, each linked to its evidence.
- Agents must not edit `observations/accepted/` or auto-modify `SKILL.md`
  based on observations **on `main`**. The one sanctioned automated path is
  a consumer-side feedback agent: it MAY author the observation candidate,
  its promotion, the tests-first regression + delta and the version bump
  **on a non-`main` branch and open a PR**, provided the observation carries
  a reviewer verdict from the consuming project and reproducible evidence.
  Nothing on that branch is accepted or released until a human reviews and
  merges the PR; `--reviewed-by` names the human merger — the merge confers
  the approval. Agents never push to `main`, never tag and never publish
  releases (release publication stays the `main`-push automation triggered by
  the human merge).

## Vendor discipline

`vendors.yaml` is the registry of model vendors, their models and the effort
levels each model accepts. It is cached knowledge about somebody else's product,
so it has exactly one refresh path and exactly two reasons to use it.

- **The library never goes to the network.** `skillctl vendor refresh` prints
  the sync plan — which pages to open, which fields to extract, where to put the
  answer — and `skillctl vendor apply` records what came back. The trip itself
  is made by a human or an agent that has network access.
- **Two, and only two, reasons to go to a vendor's documentation:** a new model
  version enters the registry (`skillctl vendor add-model` raises
  `docs_refresh_required`), or the operator asks explicitly
  (`--reason operator-request`). Ordinary skill edits, installs, gate runs,
  reviews, releases and CI never consult a vendor and never touch `vendors.yaml`.
  `vendor refresh` without a `--reason` from the closed set and without
  `--reviewed-by` fails.
- **`in_use` is a declaration, not a guess.** `skillctl vendor check` holds a
  vendor to a completed sync only when it is marked `in_use: true` — the vendor
  the library actually measures against. The rest are declared groundwork: an
  unfinished sync for them is reported, never a failure. Referential integrity (an
  adapter or an eval tier naming a vendor or model the registry does not know)
  is enforced for every vendor.
- `vendors.yaml` is library data, not skill content: it is never installed into a
  consumer and — unlike `skills/`, `src/`, `scripts/` and `templates/` — a change
  to it does not require a project version bump. A sync is not a release.

### How the feedback loop uses all this

1. **An observation records its environment.** A record in `observations/` names
   the vendor, the model and the effort level it was seen on, next to the
   skill's version and commit. Without them "a defect of the skill" is not
   checkable: nobody knows which edition failed in which environment.
2. **Proved for one vendor is not proved for another.** A green eval gate
   belongs to the declared vendor + model + effort triple. Carrying a rule over
   to another vendor is a separate measurement and a separate record, never an
   inference.
3. **A new model is a reason to sync the documentation, not to rewrite rules.**
   The sequence is `vendor add-model` → `vendor refresh --reason new-model` →
   `vendor apply`, and then the gate is re-measured. The skill's text does not
   change: the sync updates the registry, not the rules.
4. **A behavioural difference between vendors is an observation, not an edit.**
   If one vendor's model reliably fails to apply a rule another vendor's model
   applies, that becomes an observation candidate in the skill concerned, scoped
   to "vendor + model family + effort level". Promotion into `knowledge/` is an
   ordinary reviewed change. Neither `SKILL.md` nor `references/` gains a
   per-vendor branch.
5. **Outside the two reasons, nobody goes to a vendor.** Not triage, not a rule
   edit, not a release.

## History docs discipline

`docs/history.eng.md` and `docs/history.rus.md` are the human-readable
counterpart of `CHANGELOG.md`. `CHANGELOG.md` answers *what changed in which
release* and drives the release notes; the history pair answers *what was going
wrong, why it was wrong, and what the fix does*. Both files are mandatory
reading surface for a person, not for an agent at runtime, and neither is
installed into a consumer.

- **The pair is bilingual and symmetric.** Every entry exists in both files, in
  the same order, with the same **Releases** line. Adding an entry to one file
  and not the other is an incomplete change. `docs/history.rus.md` is the second
  and last carve-out from the English-only policy (alongside the root
  `README.md` and `__test__/README.md`) and is allowlisted in
  `scripts/check_language.py`; `docs/history.eng.md` is English like everything
  else.
- **Show, do not list.** An entry must make the defect visible: an AS IS
  diagram of how it went wrong, a TO BE diagram of how it goes now, a minimal
  example a reader can run, and tables instead of paragraphs wherever a table
  fits. Plain language throughout — no internal jargon, no identifier soup. A
  bare bullet list of changed files belongs in `CHANGELOG.md`, not here.
- **One story, one entry — group the releases.** When the same fix lands in
  several skills across several releases, it is written once and every carrying
  version is named on a single **Releases** line. Never duplicate the same
  explanation per skill or per version.
- **Never name a consuming project — in `docs/history.*.md` or in
  `CHANGELOG.md`.** A defect discovered while a skill was in use is described by
  its technical content only. The consuming project's name, its repository, its
  file paths and its internal record identifiers must not appear in either
  document; the neutral form is "a field report from a consuming project", with
  the reviewer verdict class and the occurrence count carried as data. The
  traceability link is kept on the consumer's side, where it belongs.
- **Entries are newest-first — a new one goes above the others**, the same
  order as `CHANGELOG.md`. The pair does not claim to cover releases older than
  its last entry — `CHANGELOG.md` remains complete.
- `docs/` is gate infrastructure, not used code: a docs-only change must NOT
  bump the project version (`scripts/check_release_gate.py`).

## Change discipline (layers)

- Any change to the knowledge/data/observation policy requires updating the
  tests in `__test__/` that pin the policy.
- Changing skill content (including layers) means bumping its `version` in
  `skills.yaml`; keep `capabilities` flags in sync with actual directories.

## Change discipline

- Any behaviour change requires adding or updating tests in `__test__/`.
- Before declaring work done, actually run and show the output of:
  ```bash
  uv run skillctl validate
  uv run skillctl test
  ```
  (`uv` is the project's default package manager; `python scripts/skillctl.py …`
  is the equivalent zero-tooling fallback used by CI.)
- Never declare work complete without real command output; both commands must
  exit with code 0.
- When you change a source file that is under mutation scope
  (`[tool.mutmut].only_mutate`: `security.py`, `lockfile.py`, `installer.py`,
  `yamlio.py`, `validator.py`, and the three skill analyzer scripts), run mutation
  testing **scoped to just that file**, never the whole scope:
  ```bash
  python scripts/mutation.py <path-or-short-name>   # e.g. security  OR  src/skill_library/security.py
  ```
  The wrapper caps parallelism (CPU − 2) and derives the mutant glob from the
  file, so it re-tests only that module's mutants. Editing a file outside the
  scope is a no-op (the wrapper exits 0 and says so) — nothing to run. The full
  cross-file run stays in CI (`.github/workflows/mutation.yml`, weekly/manual);
  do not run it locally by hand.
- Keep `README.md` (Russian) in sync with actual CLI behaviour; never document
  features that do not exist. Only the root `README.md`, `__test__/README.md`
  and `docs/history.rus.md` are written in Russian; every other document is in
  English. The untracked working areas `_audit/` (review reports), `_temp/`
  (scratch notes) and `_promts/` (task briefs) are exempt — they are not
  repository content.
- Bump the skill's `version` in `skills.yaml` whenever its content changes.

## Release discipline

- The project version has a single source: `pyproject.toml` (`[project].version`).
  `src/skill_library/__init__.py` (`__version__`) and the first `## [X.Y.Z]`
  entry of `CHANGELOG.md` must always match it —
  `scripts/check_version_drift.py` fails CI on any drift.
- Releases are published automatically by `.github/workflows/release.yml` on
  push to `main` only (direct commit or merged PR). Branches `test` and `dev`
  never produce releases. Release assets: a `git archive` source tarball plus
  its SHA256; no build artifacts.
- To bump the version, ALWAYS run `python3 scripts/bump_version.py <X.Y.Z>`
  (or `--patch/--minor/--major`) — it updates all version-carrying files
  atomically (including the project entry in `uv.lock` when present, without
  invoking `uv`), inserts a `CHANGELOG.md` entry stub and self-checks for
  drift. Never edit the version in these files by hand: that is duplicate
  work and a drift risk. The only manual step left is replacing the TODO line in the new
  `CHANGELOG.md` entry with the actual change description (it becomes the
  GitHub release notes).
- Which SemVer component of the project version to bump:
  - **major** (first digit) — a skill is created in or deleted from the
    library (a `skills/<name>/` directory appears or disappears);
  - **minor** (middle digit) — the rules of an existing skill change
    (`SKILL.md`, layers, its catalog entry);
  - **patch** (last digit) — a bug fix that does not change functionality, or
    a change to the package's own infrastructure (`src/`, `scripts/`,
    `templates/`, `pyproject.toml`) that does not affect skill behaviour.
  This chooses the digit only when the release gate requires a bump at all;
  gate-infrastructure paths (`__test__/`, `.github/`, docs) still must not
  change the version.
- Version bump rules, enforced by `scripts/check_release_gate.py` (runs on PRs
  to `main` and on `main` pushes):
  - changing used code (`skills/`, `src/`, `scripts/`, `templates/`,
    `skills.yaml`, `pyproject.toml`, `LICENSE`; **not** `vendors.yaml`, which is
    cached vendor facts rather than shipped content) requires bumping the version
    (via `scripts/bump_version.py`) and describing the change in
    `CHANGELOG.md`;
  - infrastructure-only changes (`__test__/`, `.github/`, `README.md`,
    `AGENTS.md`, etc.) must NOT change the version — no release is published;
  - the version only grows; `0.0.0` is the unreleased baseline and is never
    published.
- Publication is idempotent: if release `v<version>` already exists, the
  publish step is a no-op, so infra-only merges to `main` are safe.

## Safety rules

- No network calls, destructive operations or credential-sensitive actions in
  tests; tests must create temporary directories and clean them up.
- Never commit secrets, tokens, real credentials, PII, client data or
  production logs — in any layer, including `data/` and `observations/`.
  The validator's secret scan is a heuristic backstop, not permission to rely
  on it. Test markers must be obviously fake (e.g. AWS's documented
   example key A...EXAMPLE).
- Mutating CLI operations must stay fail-closed: validate paths via
  `skill_library.security`, touch only lock-managed files, require `--force`
  for anything that overwrites local changes.
- Preserve provenance: every skill keeps an accurate `ORIGIN.yaml`; vendored
  skills keep their upstream license, source and commit.
