# Pitfalls: known failure modes of the helper script

Read this when the script's suggestion looks wrong. Every pitfall lists its
evidence; treat anything without evidence as a hypothesis, not knowledge.

## Deletion-heavy fixes are misclassified as `refactor`

**Applies when** a bug fix removes more lines than it adds (e.g. deleting a
faulty workaround). The classifier sees `removed > added * 2` and suggests
`refactor` unless an added line contains fix/bug/regression keywords.
Override the type manually when the *intent* of the change is a fix.
Evidence: accepted observation
[OBS-20260712-001](../observations/accepted/OBS-20260712-001.md) with the
reproducible fixture `data/fixtures/mixed_change.diff`.

## Keyword detection reads added lines only

**Applies when** the fix is visible only in *removed* lines or in the
surrounding context. The script scans `+` lines for fix keywords, so deleting
buggy code without adding commentary yields no `fix` signal. This is a
deliberate design limit (scanning removed lines produces false positives on
refactors); compensate by reading the diff yourself.

## Renames inflate both counters

**Applies when** the diff contains file renames without content changes.
Renames appear as full deletions plus additions, so the size-based heuristics
overestimate the change. Prefer `refactor` with an explicit `rename` mention
in the body, and say so if the diff should be split.
