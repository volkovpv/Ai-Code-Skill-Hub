# testing-discipline

> Documentation for people using this library. The agent itself reads
> [SKILL.md](SKILL.md); this file is not installed in runtime mode.

## What this skill does

Gives an AI coding agent a standard for **unit and integration tests** —
one that holds in any language, with any test runner, on any platform.
Once installed, the agent applies it whenever it writes, reviews, or
reworks tests, whatever the code under test is written in.

**Scope, stated as a limit.** Two levels are covered:

| Level | The question it answers |
|---|---|
| **Unit** | do our objects do the right thing, and are they convenient to work with? |
| **Integration** | does our code work against code we cannot change? |

Testing a whole deployed system from outside it — its packaging, its
environment, its release process, its users — is a different discipline
with different subjects, lifecycles and owners. **The skill deliberately
says nothing about it**, and an agent that meets such a question is told
to say so rather than to answer from these rules.

The core discipline it enforces:

- tests land in the same change as the code, and every bug fix ships a
  regression test that fails before the fix;
- **a test is not evidence until it has been seen red for its own reason** —
  free if it was written first, one deliberate break-and-restore otherwise;
- **and the failure message is made legible before the code that turns it
  green is written**: the cycle has four steps — fail, *report*, pass,
  refactor;
- the two levels answer different questions and are kept apart; a unit
  test that acquires a real connection, file or clock has changed level
  and is moved;
- a test that is hard to write, slow or fragile is treated as a **report on
  the design**, answered by changing the code rather than bending the test;
- Arrange/Act/Assert, one act step, no branching, one scenario per test,
  names that state the behaviour and the condition as a fact, assertions
  that pin the expected error *and* its condition;
- a test is judged by four attributes at once — protection against bugs,
  resistance to refactoring, feedback speed, maintenance cost — and asserts
  the observable behaviour, never an implementation detail;
- output verification before state verification before asserting an
  interaction, and an interaction is asserted only where it crosses the
  application boundary;
- **exact about the claim, silent about the rest** — queries may be called
  any number of times, commands exactly as often as the contract says,
  arguments are matched only as tightly as the scenario constrains them,
  and call order is pinned only where the order *is* the contract;
- unit tests touch nothing external; time is injected rather than slept
  through, and every awaited assertion carries a deadline;
- an asynchronous test **waits for success and times out for failure**, and
  never asserts a state the system could already have been in before it
  started;
- fakes are bound to the seams the code exposes — **peers, never
  internals** — and to a role you named rather than a concrete type;
  patching is a justified last resort;
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
- the expected value is named exactly and its derivation from the inputs is
  visible in the test; no constant means two things in one case;
- generic mapping code is exercised with purpose-built types, persistent
  state is cleaned at the *start* of a test, and transaction boundaries are
  written into the test rather than replaced by a rollback;
- only code you wrote is on the hook, depth follows the cost of being
  wrong, and a test is deleted only when it is redundant *both* on
  confidence and on communication;
- suite hygiene: no committed focus/skip markers, no test tuned to the
  gate, no flickering test tolerated, no red suite shared, deterministic
  runs, test-only secrets.

## The unit-testing school is your project's decision

There are two schools of unit testing, and they disagree about one word —
*isolation*:

| | Isolation applies to | A "unit" is | Test doubles are used for |
|---|---|---|---|
| **London (mockist)** | the units | a class | collaborators — every mutable dependency |
| **Classical (Detroit)** | the tests | a class or a cluster of classes | shared dependencies |

Everything else they disagree about follows from that — including, and
this is the load-bearing consequence for a two-level skill, **where the
line between a unit test and an integration test runs**:

| | A test is a **unit** test when… | …and an **integration** test when… |
|---|---|---|
| **London** | every collaborator is a double | any real collaborator runs |
| **Classical** | it is fast, isolated from other tests, and covers one unit of behaviour | it reaches a shared dependency, or is slow, or spans more than one unit of behaviour |

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
as unmanaged, where an interaction may be asserted, where the unit /
integration line runs, and whether you practise test-driven development.

### Each school gets its own operational half

A skill that only catalogued the schools would leave London named but
unequipped. Both halves are carried:

| | Where its discipline lives |
|---|---|
| **Classical** | the value model, structure, data and hygiene files — collaborators run for real, so the pressure is on assertions and case provenance |
| **London** | [`references/interface-discovery.md`](references/interface-discovery.md) — how a collaborator that does not exist yet is named from its client, plus the interaction-precision rules in [`references/unit-test-value.md`](references/unit-test-value.md) that keep a double-heavy suite survivable |

## Test-driven development is your project's decision too

The skill carries the **red/green/refactor cycle** — never more than one
red test at once, the smallest change that reaches green, and the
duplication between the test and the code removed in the refactor step —
in [`references/tdd-cycle.md`](references/tdd-cycle.md).

**It is applied only where your project rules declare that you practise
it**, the same way the school is. What holds either way, and is never
optional, is the evidence rule: a test that has never been seen to fail is
not yet protection.

## Key features

- **Universal by contract.** No language, runner, framework, mocking
  library or architecture is assumed. How a rule is *spelled* belongs to
  the host project and to the language standards; which rules apply
  belongs here.
- **Scoped by contract.** Unit and integration only. The limit is stated
  in the skill itself, so an agent declines out-of-scope questions instead
  of improvising an answer from unit-test rules.
- **School-neutral by contract.** The strategy that decides *which*
  collaborators get replaced is a project declaration, not a rule of this
  skill.
- **Evidence-backed rules.** The load-bearing rules (external-system fake
  provenance, outbound substitution, wiring-level construction, case-set
  provenance, the runaway asynchronous test, silent rot in a mapping test)
  each ship a minimal, deterministic reproduction — they were written
  because a green suite hid a real defect, not because they sound prudent.
- **Progressive disclosure.** `SKILL.md` stays short and routes to
  fourteen reference files: the two schools, the two levels and the line
  between them, the test-first cycle, interface discovery, test
  diagnostics, tests as design feedback, structure and naming, test data
  builders, what makes a test worth having, isolation and fakes,
  asynchrony and concurrency, adapters and persistence, suite hygiene with
  case provenance, and the anti-pattern catalog.

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

The skill covers *what makes a unit or integration test worth having*;
your project rules cover the mechanics of your suite. Effective split:

- **Put in project rules:** the **unit-testing school** and everything that
  follows from it (see above); **where your unit / integration line runs
  and what each side may touch**; **whether you practise test-driven
  development**; the runner and its invocation, where tests live and how
  they are named for discovery, which fixtures/factories the project ships,
  how integration tests get their environment, the coverage or mutation
  thresholds the build enforces, and any deliberate deviations. Anything
  about testing the deployed system as a whole also belongs here — the
  skill does not cover it. Project instructions always take precedence
  over the skill.
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
