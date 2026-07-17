# AGENTS.md — rules for developers and coding harnesses working on this library

## Structure invariants

- Canonical skills live only in `skills/`; the directory name is fixed.
- All tests live only in `__test__/`; the directory name is fixed (not `tests`).
- `templates/skill/` is a scaffold, not a published skill — never validate or
  install it directly.
- Keep canonical skills vendor-neutral. Anything specific to one harness goes
  into the skill's `agents/` adapter files or into installer code, never into
  `SKILL.md`.
- Do not put product- or project-specific decisions into universal skills.
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
- Do not create a `history/` directory — Git history is the history.

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
  `yamlio.py`, `validator.py`, and the two skill analyzer scripts), run mutation
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
  features that do not exist. Only the root `README.md` and
  `__test__/README.md` are written in Russian; every other document is in
  English (audit reports under `_audit/` are exempt).
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
    `skills.yaml`, `pyproject.toml`, `LICENSE`) requires bumping the version
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
