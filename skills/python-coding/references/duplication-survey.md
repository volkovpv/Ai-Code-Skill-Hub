# Duplication survey: search before you write

[references/lint-clean.md](lint-clean.md) already states that this stack's
duplication guidance has no blocking-linter backing and that the advisory
detector that does exist for it is blind to identifier renaming — both are
about the moment *after* a duplicate exists. This file is the other half:
what to do **before** the first line of a new implementation is written, so
there is nothing left for a green lint run — or a human reviewer — to miss.

## Contents

- [Search by shape, never by name](#search-by-shape-never-by-name)
- [The decision order](#the-decision-order)
- [A new file is the last step, not the first](#a-new-file-is-the-last-step-not-the-first)
- [Two invariants a collapse may not weaken](#two-invariants-a-collapse-may-not-weaken)
- [Measured on one live tree](#measured-on-one-live-tree)

## Search by shape, never by name

Before writing a new function, class, or module, search for the home this
logic already has — by what it is **built out of** (the same sequence of
operations assembled from the same primitives), never by the name you are
about to give the new symbol. A copy is renamed by construction: its
author gives it a name that fits the new call site, not the name of the
implementation it duplicates, so a search by name is the one search method
guaranteed to miss exactly the case that matters. Read the sibling call
sites of the same concern — the other places the same kind of decision,
transformation, validation, or wiring already happens — before concluding
there is nothing to extend.

## The decision order

Stop at the first step below that applies; do not skip ahead to "write a
new file" because it is the fastest step to take.

1. **Extend the existing home.** The logic already exists once — add the
   missing behaviour there.
2. **Call it with your own parameters.** The logic already exists and
   covers your case — call it, rather than re-implementing it just for this
   caller.
3. **At the third occurrence of one shape, introduce a parameterized
   factory** in the shared home, and reduce every caller — including the
   first two — to the data that genuinely differs between them (a name, a
   `NewType`-branded identifier, an error type, a message, an
   environment-variable key). Two occurrences can still be coincidence; a
   third is a pattern.
4. **Write a new file only because the search above came back genuinely
   empty** — never because writing felt faster than searching.

## A new file is the last step, not the first

An absence nobody searched for is not a finding. "I didn't find an
existing implementation" only counts once the search above actually
happened — by shape, across the whole tree — not after grepping the one
name you were about to give the new symbol.

## Two invariants a collapse may not weaken

Reducing several copies to one shared implementation is safe only when it
keeps what made each of them individually correct:

- **Per-caller negative coverage.** A fail-closed or defensive branch (a
  rejected-input path, an `assert_never` default, an exception path) needs
  a test that exercises it **for each caller**, not once against the shared
  helper. A helper's defensive branch tested through only one caller is
  formally covered and actually unverified for every other caller.
- **Union, never a pick, for a routine defending untrusted input.** Already
  the rule for this stack — see
  [references/security.md](security.md#a-defensive-routine-over-untrusted-input-has-one-home-the-union-of-every-callers-cases):
  collapsing a parsing or validation routine over untrusted input into one
  shared implementation means giving it the union of every caller's cases,
  never a pick of one. The search below is what gets a project to one
  shared routine in the first place, before that rule has anything to
  apply to.

## Measured on one live tree

Evidence already on record for this skill
([observations/accepted/OBS-20260818-001.md](../observations/accepted/OBS-20260818-001.md)):
on one live Python codebase, one repository-style adapter's core method was
byte-identical across more than a dozen call sites introduced in over ten
separate tasks — 11 of 13 repository bodies byte-identical in the most
affected module — and a defensive parser standing over untrusted model
output existed in five independently maintained copies, each tested only
against its own caller's historical inputs. A fix applied to one copy in
response to its own caller's bug report did not propagate to a sibling
copy that was never told about it. Nothing in that measurement is specific
to this project's domain, framework, or architecture: no installed skill
told this codebase's authors to look before writing, even though a correct
worked example of the collapsed shape already existed nearby in the same
tree.
