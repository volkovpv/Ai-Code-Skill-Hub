---
name: testing-discipline
description: Universal discipline for writing and reviewing tests, with no language, runner, framework, or platform assumptions. A change without its tests is incomplete and every bug fix ships a regression test that fails first; Arrange/Act/Assert, one scenario per test, names stating behaviour and condition; unit tests touch nothing external and fake only the seams the code exposes, never someone else's internals; a fake standing in for an external system has its contract pinned by a live observation, never by re-reading documentation; construction and outbound-substitution properties are tested through the production wiring, not a hand-built copy; case sets, subjects and dimensions come from the specification, never from the artifact under test, because a healthy mutation score is not evidence of specification coverage; suite hygiene — no committed focus/skip, no tuning a test to the gate, determinism, test-only secrets. Use whenever writing, reviewing, or reworking tests, in any language and with any runner.
---

# Testing discipline (universal)

Write tests that establish what they claim to establish. This skill is
**universal by contract**: every rule here holds for any language, test
runner, framework and platform — it assumes no ecosystem, no mocking
library, no architectural style. *How* a rule is spelled in a given
language (which marker, which assertion helper, which patching facility)
belongs to that language's own standard. Wiring conventions for a
ports-and-adapters codebase — which collaborator is faked at which seam,
where the DI boundary sits — live in the `hexagonal-service` skill; when
the host project uses it, apply that skill on top of this one.

## Workflow

1. **Ship the tests with the change.** A code change without its tests is
   not done, and every bug fix ships a regression test that reproduces the
   defect and fails before the fix.
2. **Structure and name each test so it reads as a claim.**
   Arrange/Act/Assert, one scenario per test, a name that states the
   behaviour and the condition, assertions that pin the error *and* its
   condition — see
   [references/structure-and-naming.md](references/structure-and-naming.md).
3. **Isolate the unit and fake only the seams the code exposes.** No
   network, disk, database or wall-clock dependence; time is injected, not
   slept through — see
   [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
4. **Pin an external system's behaviour by observing it, not by reading
   about it.** When the property under test belongs to a system this
   project does not own, the fake's contract is established by a probe
   against the real system and then reused as a fixture — see
   [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
5. **Exercise the production wiring, not a hand-built copy of it.** How a
   collaborator gets constructed, and what a client substitutes on the way
   out of a call, are only testable where the product itself does them —
   see [references/isolation-and-fakes.md](references/isolation-and-fakes.md).
6. **Derive the case set, the subject and the dimensions from the
   specification.** Never from the artifact under test: a mutation battery
   can score healthy while the specification stays uncovered — see
   [references/hygiene.md](references/hygiene.md).
7. **Keep the suite honest.** No committed focus/skip markers, no test
   tuned to the gate, no non-determinism, no real credentials — see
   [references/hygiene.md](references/hygiene.md).
8. **Let the static checks and the tests divide the work.** Where the
   project has a type checker, do not test what it already forbids, and do
   test the guards, bypasses and type-level utilities it cannot verify —
   see [references/types-and-tests.md](references/types-and-tests.md).

## Routing: what to read when

Do not preload the whole skill; open a file only when its trigger fires.

| Situation | Read |
|-----------|------|
| Laying out a test, naming it, asserting an error, choosing between example-based and property-based cases | [references/structure-and-naming.md](references/structure-and-naming.md) |
| Deciding what to fake, how a fake's contract is established, testing construction or an outgoing call | [references/isolation-and-fakes.md](references/isolation-and-fakes.md) |
| Choosing the case set, judging whether coverage or a mutation score means anything, reviewing suite hygiene | [references/hygiene.md](references/hygiene.md) |
| The project has a static type checker and you are deciding what still needs a test | [references/types-and-tests.md](references/types-and-tests.md) |

## Rules

- A code change without its tests is incomplete; every bug fix ships a
  regression test that fails before the fix and passes after it.
- One scenario per test, Arrange/Act/Assert (or Given/When/Then), a name
  that states the behaviour and the condition — never `test_2` or
  `works`.
- A unit test touches nothing external: no network, disk, database, or
  wall-clock dependence. Control time by injecting a clock, never by
  sleeping.
- Fake the seams the code exposes (a parameter, an interface, an injected
  dependency) — never someone else's internals. Patching whatever the
  language lets you patch is a last resort, used only when no seam exists,
  with a justifying comment.
- A fake's contract for a system this project does not own is established
  by observing that system once, never by reading about it; reuse the
  pinned observation as a fixture instead of re-deriving it from prose.
- A property that lives in the product's own construction or on the way
  out of a call is tested through the production factory or entry point,
  never through an instance the test assembled itself.
- The case set, the subject under test and the dimensions varied all come
  from the specification, never from the artifact under test; a surviving
  mutation is evidence of a missing dimension, and a healthy mutation
  score is not evidence of specification coverage.
- No focused or skipped tests committed, no commented-out tests, no
  conditional assertions, no empty tests, no duplicate test names.
- Never tune a test to the gate: no expected value hardcoded "so it
  passes", no check disabled, no snapshot refreshed without understanding
  the cause.
- Tests are deterministic — no reliance on iteration-order accidents,
  wall-clock time, unpinned random seeds, or test execution order.
- Secrets in tests are test-only values, generated or signed for the test;
  never a real credential, and never a verification mocked away to avoid
  one.
- Keep this skill universal: language spellings, runner mechanics,
  framework and architecture choices belong to the host project or to the
  dedicated skills — never here. Project instructions always take
  precedence over this skill.
