# Patterns: choosing type, scope and subject

Verified heuristics for Conventional Commits. Each pattern states its scope
of applicability — none of them is an unconditional rule.

## Dominant-change rule

**Applies when** a diff mixes categories (e.g. a feature plus its tests).
Pick the type of the *dominant* change: tests shipped together with a feature
do not turn `feat` into `test`; documentation accompanying a fix does not
turn `fix` into `docs`. Evidence: the classifier in `scripts/example.py`
implements exactly this ordering (all-tests before all-docs before content
heuristics), verified by the skill tests.

## Scope from the deepest common module

**Applies when** all changed files share a top-level directory. Use that
directory (or a well-known module name inside it) as the scope; omit the
scope entirely for cross-cutting changes. A wrong-but-plausible scope is
worse than no scope: it misleads changelog readers.

## Subject states the intent, not the mechanics

**Applies always.** `fix(cache): drop double invalidation` beats
`fix(cache): change invalidate()`. The script can only see mechanics
(files, added/removed lines), so rewriting its subject line is the agent's
job, not an optional polish step. See the input/output pair in
[../data/examples/feature_change.diff](../data/examples/feature_change.diff)
and [../data/examples/feature_change.expected](../data/examples/feature_change.expected):
the expected output is a *starting point* that still names only the file.
