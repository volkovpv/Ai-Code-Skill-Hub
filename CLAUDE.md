# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A self-contained, vendor-neutral library of **Agent Skills** ("git repo as a skill": instructions + tools + knowledge + data, versioned together) plus its management CLI **`skillctl`**. Two distinct kinds of content live here, with different rules:

- **Skill content**: `skills/` (canonical sources), `skills.yaml` (catalog), `templates/skill/` (scaffold for `skillctl new` — never validated or installed directly).
- **CLI implementation**: `src/skill_library/` (Python ≥ 3.12, **stdlib only — never add dependencies**), thin wrappers in `scripts/`.

`AGENTS.md` is the authoritative rules file for agents/developers; only the root `README.md` and `__test__/README.md` are in **Russian** — all other docs (including `CHANGELOG.md` and `__test__/scenarios/README.md`) are in English; audit reports under `_audit/` are exempt from the language rule. `README.md` must be kept in sync with actual CLI behaviour — never document features that don't exist.

## Commands

The default package manager is **uv** (`uv.lock` and `.python-version` are committed). `uv sync` creates `.venv` with an editable install of the project, so `skillctl` is available as a console command and code edits apply without re-syncing. Do NOT add runtime dependencies — the library stays stdlib-only; uv manages the environment, not dependencies.

```bash
uv sync                                          # one-time environment setup
uv run skillctl validate                         # whole library (structure, metadata, links, secret scan)
uv run skillctl validate <skill>                 # one skill
uv run skillctl test                             # full test suite (= unittest discover -s __test__ -t .)
uv run skillctl test <skill> -v                  # one skill: validation + __test__/skills/test_<name_with_underscores>.py
uv run python -m unittest __test__.test_layers -v                          # single test module
uv run python -m unittest __test__.test_installer.InstallTests.test_name -v   # single test

uv run skillctl list                             # catalog overview
uv run skillctl new <name> --with knowledge,data,observations   # scaffold + register in skills.yaml
uv run skillctl install <skill> --target <proj> --agent claude  # smoke-test installation
uv run scripts/bump_version.py --patch           # THE ONLY way to bump the project version
uv run scripts/check_version_drift.py            # pyproject = __init__.py = CHANGELOG gate
uv run scripts/check_release_gate.py             # code-change ⇔ version-bump gate (needs full git history)
```

Zero-tooling fallback (no uv, no venv — the library has no dependencies): `python scripts/skillctl.py <command>` is equivalent to `uv run skillctl <command>`; CI uses the plain-python form to prove self-containment on 3.12 and 3.13.

**Definition of done** (from AGENTS.md): `skillctl validate` and `skillctl test` both run with real output and exit code 0. Any behaviour change requires adding/updating tests in `__test__/`.

## Architecture

`skillctl` command flow: `scripts/skillctl.py` → `cli.py` (argparse, exit codes 0/1/2) → domain modules:

- `discovery.py` — scans `skills/`, parses SKILL.md frontmatter, loads `skills.yaml` into `models.py` dataclasses (`SkillMeta`, `CatalogEntry`).
- `validator.py` — structure, metadata, local-link resolution, layer rules, capabilities↔directories consistency, file-size limits and heuristic secret scan. **Fail-closed**: anything suspicious blocks validation.
- `installer.py` — install/diff/update/remove/status against a target project. Two distribution modes: `runtime` (default; excludes `observations/candidates/`, `observations/rejected/`, `data/fixtures/`) and `full`. Agent → target dir mapping in `AGENT_TARGET_DIRS` (`claude` → `.claude/skills`, most others → `.agents/skills`, `hermes` requires `--target-skills-dir`).
- `lockfile.py` — `.agent-skills.lock.yaml` in the target project: per-file sha256 lets the installer distinguish managed files from foreign ones and detect local edits (update/remove refuse without `--force`).
- `observations.py` — lifecycle `candidate → approve/reject`; approve requires non-empty `evidence` and `--reviewed-by`.
- `security.py` — `safe_join`/`validate_relative_path`/`ensure_no_symlinks`; every mutating path goes through it. Symlinks inside skills are forbidden everywhere.
- `yamlio.py` — in-house parser for a **narrow YAML subset** (2-space nested mappings, lists, scalars, quotes, flow lists of scalars). Anchors, aliases, tags and multiline strings are rejected. All YAML in the repo (catalog, ORIGIN.yaml, frontmatter, lockfiles) must stay within this subset — needing more means the data should be simplified.

### Skill anatomy (enforced by validator)

`skills/<name>/` requires `SKILL.md` (frontmatter `name` must equal the directory name) and `ORIGIN.yaml` (provenance: `original`/`vendored`). Optional directories — only these are allowed: `agents/`, `references/`, `scripts/`, `assets/`, and the layers `knowledge/`, `data/`, `observations/`. A non-empty layer requires its `knowledge/INDEX.md` / `data/README.md` / `observations/INDEX.md`. No `README.md`/`CHANGELOG.md`/`history/` inside a skill (sole exception: `data/README.md`); executables only in `scripts/`. Layer flags in `skills.yaml` `capabilities:` must match the actual directories. Progressive disclosure: `SKILL.md` stays short and routes to deeper files; never duplicate `references/` content into it.

## Two independent version systems — do not mix them up

1. **Per-skill versions** live in `skills.yaml`. Changing any skill's content (including its layers) requires bumping that skill's `version` there.
2. **Project version** lives in `pyproject.toml` and is mirrored in `src/skill_library/__init__.py`, the top `CHANGELOG.md` entry and the project entry in `uv.lock`. Never edit these by hand — always `scripts/bump_version.py` (it updates all of them, including `uv.lock`, without invoking uv); then replace the TODO line in the new CHANGELOG entry (it becomes the GitHub release notes).

Which component of the project version to bump: **major** — a skill is created or deleted; **minor** — the rules of an existing skill change; **patch** — a bug fix with no functional change, or a change to the package's own infrastructure (`src/`, `scripts/`, `templates/`) that doesn't affect skill behaviour. This picks the digit only when the release gate requires a bump at all — gate-infrastructure paths below still get no bump.

The release gate (CI, on PRs to main and main pushes) enforces both directions:
- changed **used code** (`skills/`, `src/`, `scripts/`, `templates/`, `skills.yaml`, `pyproject.toml`, `LICENSE`) → project version **must** be bumped;
- changed **only infrastructure** (`__test__/`, `.github/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, …) → version **must not** change (no release is published).

Releases are auto-published from `main` only (`.github/workflows/release.yml`, idempotent per tag; `0.0.0` is the unreleased baseline and never published).

## Testing conventions

- The test directory is exactly `__test__/` (not `tests/`); framework is stdlib `unittest`; files `test_*.py`.
- No network, no secrets, no destructive operations; use `TempDirTestCase` and the library/skill factories from `__test__/helpers.py` (`make_library`, `make_layered_library`, `write_skill`, `add_layers`).
- Per-skill tests: `__test__/skills/test_<name_with_underscores>.py`, using the skill's own `data/fixtures/` as inputs (they double as observation evidence).
- Fixtures: `__test__/fixtures/valid-skill/` (positive) and `invalid-skill/` (intentionally broken — don't "fix" it). Policy changes require updating the tests that pin the policy.

## Hard rules (violations are expensive)

- Never write to `observations/accepted/` directly or auto-modify `SKILL.md` from observations. New observations only via `skillctl observation add` (always lands in `candidates/`); promotion only via `skillctl observation approve --reviewed-by <name>` with evidence. Observation → `knowledge/` promotion is a separate reviewed change.
- Keep canonical skills vendor-neutral: harness-specific bits go in the skill's `agents/` adapters or installer code, never in `SKILL.md`.
- `content_policy` flags `pii_allowed: false`, `secrets_allowed: false`, `observation_review_required: true` must stay as-is; the validator rejects anything else. The secret scan is a heuristic backstop, not permission to rely on it. Fake test markers must be obviously fake (e.g. `AKIAIOSFODNN7EXAMPLE`).
- Mutating installer operations stay fail-closed: paths via `skill_library.security`, touch only lock-managed files, require `--force` to overwrite local changes.
- `skills.yaml` must keep `skills:` as its **last top-level key** — `skillctl new` appends entries textually.
- Vendored skills keep an accurate `ORIGIN.yaml` (source, commit, license); updating vendored content is a deliberate re-import, never automatic sync.
