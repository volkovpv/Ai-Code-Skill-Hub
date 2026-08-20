# Duplication survey: search before you write

The four SonarJS/ESLint rules named in
[references/lint-clean.md](lint-clean.md) catch only a same-file,
textual-identity duplicate, and only after it already exists. This file is
the other half: what to do **before** the first line of a new
implementation is written, so there is nothing left for those rules — or a
human reviewer — to catch.

## Contents

- [Search by shape, never by name](#search-by-shape-never-by-name)
- [The decision order](#the-decision-order)
- [A new file is the last step, not the first](#a-new-file-is-the-last-step-not-the-first)
- [An environment variable is named by its role, not by its caller](#an-environment-variable-is-named-by-its-role-not-by-its-caller)
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
   branded identifier, an error code, a message, and — **only where one
   process legitimately holds two principals** — an environment-variable
   key; see [An environment variable is named by its role, not by its
   caller](#an-environment-variable-is-named-by-its-role-not-by-its-caller)).
   Two occurrences can still be coincidence; a third is a pattern.
4. **Write a new file only because the search above came back genuinely
   empty** — never because writing felt faster than searching.

## A new file is the last step, not the first

An absence nobody searched for is not a finding. "I didn't find an
existing implementation" only counts once the search above actually
happened — by shape, across the whole tree — not after grepping the one
name you were about to give the new symbol.

## An environment variable is named by its role, not by its caller

The decision order above lists the data a caller may legitimately supply.
An environment-variable **key** belongs on that list far less often than it
looks, and getting it wrong is what licenses the copy in the first place.

When the callers are separate **processes**, they read the **same** name,
and each process is handed its own **value** by whatever starts it — a
container orchestrator, a unit file, a deployment template. `DB_USER` is the
name of a role; `DB_SERVICE_A_USER` and `DB_SERVICE_B_USER` are two names
for one role, and the moment both exist the resolver that reads them is
duplicated too, because a single shared resolver has nothing left to be
parameterized by.

Separation of principals survives this intact, because it never depended on
the spelling: distinct principals stay distinct as distinct **values**, and
no process gains reach into another's credentials by sharing a name.

Two boundaries, stated here rather than left to judgement:

- **One process, two principals** is the case that does warrant a second
  name — a service's runtime role beside a maintenance/migration role, or a
  provisioner that seeds several accounts in a single run. There the second
  name is written next to the fact that makes one name impossible.
- **One shared environment for every process** is a deployment gap, not a
  naming rule. Where every process starts from a single shared environment
  file, one name genuinely cannot hold two values — so the per-caller names
  are the symptom, not the design. Close the gap (an environment per
  process), then collapse; do not write the workaround into the code and
  call it a parameter.

The failure this prevents is ordinary: the second configuration module is
written "because this service needs its own variable", the third copies the
second, and by the time the fail-closed startup check has to be hardened it
exists in as many independently maintained copies as there are processes.

## Two invariants a collapse may not weaken

Reducing several copies to one shared implementation is safe only when it
keeps what made each of them individually correct:

- **Per-caller negative coverage.** A fail-closed or defensive branch (a
  rejected-input path, a `never`-typed exhaustiveness default, an error
  path) needs a test that exercises it **for each caller**, not once
  against the shared helper. A helper's defensive branch tested through
  only one caller is formally covered and actually unverified for every
  other caller.
- **Union, never a pick, for a routine defending untrusted input.**
  Collapsing a parsing or validation routine that stands over untrusted
  input (a network payload, file content, another process's or model's
  output) into one shared implementation means giving it the **union** of
  every calling site's cases — malformed, partial, adversarial included —
  never the slice of cases the first caller happened to be written
  against.

## Measured on one live tree

Evidence from a live TypeScript service codebase (293 files of at least 12
code lines each, comments and blank lines stripped, every identifier and
string literal rewritten to one token, then hashed — a rename-tolerant
structural fingerprint):

- A prior de-duplication task had already extracted three shared pieces of
  logic into a common module, and still left the scaffold standing around
  them in ten independently maintained configuration modules — a shape
  interface, an error subclass, a resolver, a registration factory, and an
  exported type, differing in exactly four values each. Two of those ten
  were **token-identical after renaming even after that extraction** (one
  pair 39/39 code lines, one hash; another 35/35).
- Five files implementing the same kind of access guard (13 code lines
  each) differed in nothing but the guard's class name.
- Four wiring modules (12 lines each) and three data-access repositories
  (20 lines each) each formed a single-hash cluster, differing in 2–4
  values.
- The same tree already held the correct shape throughout, one directory
  away: two shared utilities (used by 4 and 5 call sites respectively)
  where each caller kept only the data that was actually its own. The
  authors of the ten copies had a worked example in the same plane and did
  not look — which is exactly why the missing instruction is *survey*, not
  *avoid duplication*: a duplication rule already existed, twice over (a
  lint rule and a prior extraction task); nobody had been told where to
  look before writing.
