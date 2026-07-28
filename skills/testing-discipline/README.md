# testing-discipline

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Gives an AI coding agent a **universal test-writing standard** — one that
holds in any language, with any test runner, on any platform. Once
installed, the agent applies it whenever it writes, reviews, or reworks
tests, whatever the code under test is written in.

The core discipline it enforces:

- tests land in the same change as the code, and every bug fix ships a
  regression test that fails before the fix;
- Arrange/Act/Assert, one act step, no branching, one scenario per test,
  names that state the behaviour and the condition as a fact, assertions
  that pin the expected error *and* its condition;
- a test is judged by four attributes at once — protection against bugs,
  resistance to refactoring, feedback speed, maintenance cost — and asserts
  the observable behaviour, never an implementation detail;
- output verification before state verification before asserting an
  interaction, and an interaction is asserted only where it crosses the
  application boundary;
- unit tests touch nothing external; time is injected rather than slept
  through, and every awaited assertion carries a deadline;
- fakes are bound to the seams the code exposes, never to someone else's
  internals; patching is a justified last resort;
- a fake standing in for a system the project does not own has its
  contract pinned by a **live observation** of that system — never by
  re-reading a project norm, an RFC, or vendor documentation;
- properties that live in the product's own construction, or on the way
  *out* of a call, are exercised through the production factory or entry
  point, never through an instance the test assembled itself;
- case sets, subjects and dimensions come from the specification, never
  from the artifact under test: a healthy mutation score is not evidence
  of specification coverage, and a surviving mutation is evidence of a
  missing dimension;
- suite hygiene: no committed focus/skip markers, no test tuned to the
  gate, deterministic runs, test-only secrets.

## The unit-testing school is your project's decision

There are two schools of unit testing, and they disagree about one word —
*isolation*:

| | Isolation applies to | A "unit" is | Test doubles are used for |
|---|---|---|---|
| **London (mockist)** | the units | a class | collaborators — every mutable dependency |
| **Classical (Detroit)** | the tests | a class or a cluster of classes | shared dependencies |

Everything else they disagree about — what counts as an integration test,
which direction test-driven development runs, whether a test may assert an
interaction between two of your own classes — follows from that.

**The skill never picks one.** It carries the catalog, the vocabulary
(shared vs private, in- vs out-of-process, managed vs unmanaged, value vs
collaborator) and the rules that hold either way; the choice is declared in
**your project's rules**, and those rules take precedence. Declare it and
the agent applies it; leave it undeclared and the agent follows the
existing suite, proposes recording the choice, and falls back to the
rules that hold under both schools — never to a guess.

What your rules should state is listed in
[`references/schools.md`](references/schools.md): the school (and the
boundary, if it varies by layer), what a unit is here, which dependencies
get a double, which out-of-process dependencies count as managed and which
as unmanaged, where an interaction may be asserted, and the direction of
test-driven development if you practise it.

## Key features

- **Universal by contract.** No language, runner, framework, mocking
  library or architecture is assumed. How a rule is *spelled* belongs to
  the host project and to the language standards; which rules apply
  belongs here.
- **School-neutral by contract.** The strategy that decides *which*
  collaborators get replaced is a project declaration, not a rule of this
  skill.
- **Evidence-backed rules.** The load-bearing rules (external-system fake
  provenance, outbound substitution, wiring-level construction, case-set
  provenance) each ship a minimal, deterministic reproduction — they were
  written because a green suite hid a real defect, not because they sound
  prudent.
- **Progressive disclosure.** `SKILL.md` stays short and routes to seven
  reference files: the two schools, structure and naming, what makes a test
  worth having, isolation and fakes, suite hygiene and case provenance, the
  anti-pattern catalog, and the division of labour between static checks
  and tests.

## How to install

From a checkout of this library:

```bash
# Claude Code → <project>/.claude/skills/testing-discipline
uv run skillctl install testing-discipline --target ~/work/my-project --agent claude

# Codex / OpenCode / any generic harness → <project>/.agents/skills/
uv run skillctl install testing-discipline --target ~/work/my-project --agent codex
```

Later: `skillctl status` / `diff` / `update` / `remove` against the same
`--target`. The install is recorded in `.agent-skills.lock.yaml`.

## Using it with your project rules

The skill covers *what makes a test worth having*; your project rules
cover the mechanics of your suite. Effective split:

- **Put in project rules:** the **unit-testing school** and everything that
  follows from it (see above); the runner and its invocation, where tests
  live and how they are named for discovery, which fixtures/factories the
  project ships, how integration tests get their environment, the
  coverage or mutation thresholds the build enforces, and any deliberate
  deviations. Project instructions always take precedence over the skill.
- **Leave to the skill:** what a test must establish, how a test is judged,
  what may be faked and how a fake's contract is justified, where cases
  come from, and the hygiene rules — no need to restate them in your rules;
  reference the skill instead ("test discipline: see the testing-discipline
  skill; our school is classical, doubles only for unmanaged
  dependencies").

## Works well with

- `hexagonal-service` — which collaborator is faked at which seam in a
  ports-and-adapters codebase (wiring-level conventions live there, not
  here).
