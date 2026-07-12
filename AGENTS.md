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
- Do not add `README.md`/`CHANGELOG.md` and similar documents inside a skill.
  The single exception is `data/README.md` — the dataset contract.
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
  based on observations.

## Change discipline (layers)

- Any change to the knowledge/data/observation policy requires updating the
  tests in `__test__/` that pin the policy.
- Changing skill content (including layers) means bumping its `version` in
  `skills.yaml`; keep `capabilities` flags in sync with actual directories.

## Change discipline

- Any behaviour change requires adding or updating tests in `__test__/`.
- Before declaring work done, actually run and show the output of:
  ```bash
  python scripts/skillctl.py validate
  python scripts/skillctl.py test
  ```
- Never declare work complete without real command output; both commands must
  exit with code 0.
- Keep `README.md` (Russian) in sync with actual CLI behaviour; never document
  features that do not exist.
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
- Version bump rules, enforced by `scripts/check_release_gate.py` (runs on PRs
  to `main` and on `main` pushes):
  - changing used code (`skills/`, `src/`, `scripts/`, `templates/`,
    `skills.yaml`, `pyproject.toml`, `LICENSE`) requires bumping the version
    in all three files above and adding a `CHANGELOG.md` entry;
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
  `AKIAIOSFODNN7EXAMPLE`).
- Mutating CLI operations must stay fail-closed: validate paths via
  `skill_library.security`, touch only lock-managed files, require `--force`
  for anything that overwrites local changes.
- Preserve provenance: every skill keeps an accurate `ORIGIN.yaml`; vendored
  skills keep their upstream license, source and commit.
