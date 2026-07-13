# Changelog

Versions follow SemVer. The first entry of this file always matches the current
version in `pyproject.toml` — enforced by the `scripts/check_version_drift.py`
gate. Entry header format: `## [X.Y.Z] — YYYY-MM-DD`; the entry body becomes
the GitHub release notes (extracted by `.github/workflows/release.yml`).

## [0.0.1] — 2026-07-13

- Hardened skill testing: stable gates, placeholder and network bans in Python tests, transactional installer rollback, coverage/mutation gates and executable eval manifests.
- The project moved to Python ≥ 3.12 (`requires-python`, `uv.lock`, CI, documentation).
- Audit follow-ups: `skillctl test <skill>` looks up tests by exact module name (`test_<name>.py`) — prefix collisions between skills are ruled out; the YAML parser rejects empty flow-list items (`[a,,b]`); the link-install message no longer reports a bogus copied-file count; the test network blocker additionally denies UDP `sendto`/`sendmsg`; killer tests were added after triaging surviving mutants (previous-scope score 76.6% → 81.2%); the mutation-testing scope was extended to `yamlio.py` and `validator.py` (2034 mutants, score 78.6% against the 75 gate).

## [0.0.0] — 2026-07-12

Baseline: no published releases yet. Version `0.0.0` is never published —
releases start with the first version bump.
