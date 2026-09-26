# Duplication survey: search before you write

[lint-clean.md](lint-clean.md#duplication-what-the-stack-sees-and-what-it-does-not)
states what the duplication detector of this stack can and cannot see once a
copy exists. This file is the other half: what to do **before** the first
line of a new implementation is written, so there is nothing left for a green
lint run — or a reviewer — to miss.

## Contents

- [Search by shape, never by name](#search-by-shape-never-by-name)
- [The decision order](#the-decision-order)
- [A new file is the last step, not the first](#a-new-file-is-the-last-step-not-the-first)
- [An environment variable is named by its role, not by its caller](#an-environment-variable-is-named-by-its-role-not-by-its-caller)
- [Two invariants a collapse may not weaken](#two-invariants-a-collapse-may-not-weaken)
- [Why the linter will not do this for you](#why-the-linter-will-not-do-this-for-you)

## Search by shape, never by name

Before writing a new function, method, type or package, search for the home
this logic already has — by what it is **built out of** (the same sequence of
operations over the same primitives: the same `strconv` call and fallback, the
same `QueryRowContext` + `Scan` + `sql.ErrNoRows` mapping, the same retry
loop), never by the name you are about to give the new symbol. A copy is
renamed by construction: its author names it for the new call site, not after
the implementation it duplicates, so a search by name is the one search
guaranteed to miss exactly the case that matters.

Practical spellings in a Go module:

- `grep -rn "strconv.ParseInt(" --include='*.go'`, `grep -rn "errors.Is(err, sql.ErrNoRows)"`
  — search for the distinctive call, not the concept's name;
- `go doc -all ./internal/...` and `gopls` "find references" on the primitive
  you are about to call — every existing caller is a candidate home;
- read the sibling call sites of the same concern (the other places the same
  kind of decision, parsing, validation or wiring already happens) before
  concluding there is nothing to extend.

## The decision order

Stop at the first step that applies; do not skip to "write a new file"
because it is the fastest step to type.

1. **Extend the existing home.** The logic already exists once — add the
   missing behaviour there.
2. **Call it with your own parameters.** The logic exists and covers your
   case — import the package and call it, rather than re-implementing it for
   this caller. If it lives in a package you cannot import (another module's
   `internal/`), move it to a shared package first.
3. **At the third occurrence of one shape, introduce a parameterized helper**
   (a function, a small type, or a generic function when only the element
   type differs) in the shared home, and reduce every caller — including the
   first two — to the data that genuinely differs: a name, a named ID type,
   an error value, a message, and — **only where one process legitimately
   holds two principals** — an environment-variable key (see
   [below](#an-environment-variable-is-named-by-its-role-not-by-its-caller)).
   Two occurrences can still be coincidence; a third is a pattern.
4. **Write new code only because the search came back genuinely empty** —
   never because writing felt faster than searching.

## A new file is the last step, not the first

An absence nobody searched for is not a finding. "There is no existing
implementation" counts only once the search above actually happened — by
shape, across the whole module — not after grepping the one name you were
about to type. Conversely, once that search is done and empty, writing the
new code is the normal outcome; the survey never blocks genuinely new
capability.

## An environment variable is named by its role, not by its caller

An environment-variable **key** belongs on the "data that differs" list far
less often than it looks, and getting it wrong is what licenses the copy in
the first place.

When the callers are separate **processes**, they read the **same** name and
each process is handed its own **value** by whatever starts it — a container
orchestrator, a unit file, a deployment manifest. `PG_USER` is the name of a
role; `BILLING_PG_USER` and `REPORTS_PG_USER` are two names for one role, and
the moment both exist the config loader that reads them is duplicated too,
because a single shared loader has nothing left to be parameterized by.

Separation of principals survives this intact, because it never depended on
the spelling: distinct principals stay distinct as distinct **values**, and no
process gains reach into another's credentials by sharing a name.

Two boundaries, stated rather than left to judgement:

- **One process, two principals** is the case that does warrant a second
  name — a service's runtime role beside its migration role, or a provisioner
  that seeds several accounts in one run. There the second name sits next to
  the fact that makes one name impossible.
- **One shared environment for every process** is a deployment gap, not a
  naming rule. Where every process starts from one shared env file, one name
  genuinely cannot hold two values — the per-caller names are the symptom.
  Close the gap (an environment per process), then collapse.

## Two invariants a collapse may not weaken

Reducing several copies to one shared implementation is safe only when it
keeps what made each of them individually correct:

- **Per-caller negative coverage.** A fail-closed branch (a rejected-input
  path, the `default:` of an exhaustive switch, an error return) needs a test
  that exercises it **for each caller**, not once against the shared helper.
  A helper's defensive branch tested through one caller is formally covered
  and actually unverified for every other caller.
- **Union, never a pick, for a routine defending untrusted input.** Already a
  rule of this standard — see
  [security.md](security.md#a-defensive-routine-over-untrusted-input-has-one-home-the-union-of-every-callers-cases):
  collapsing a parser or validator over untrusted input into one shared
  implementation means giving it the union of every caller's cases, never one
  caller's slice.

## Why the linter will not do this for you

The structural clone detector of this stack (`dupl`, via golangci-lint) is
rename-blind — it compares syntax-tree shapes, so a copy with renamed
identifiers is visible to it — but it runs **per package** and reports only
above a token threshold (150 tokens by default). Measured on golangci-lint
2.13 with one 17-line function copied and renamed: in two different packages
it was not reported at any threshold down to 20; in two files of one package
it was reported only once the threshold dropped to 75. A copy in a sibling
package, or any function of ordinary length, is invisible to it at the
default — the search above is the only defence. Details: [lint-clean.md](lint-clean.md#duplication-what-the-stack-sees-and-what-it-does-not).
