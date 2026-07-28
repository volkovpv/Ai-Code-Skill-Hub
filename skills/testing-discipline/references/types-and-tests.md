# Static checks and tests divide the work

Applies only where the project has a static type checker (or an equivalent
static analysis the build enforces). The checker eliminates whole classes
of invalid inputs; tests demonstrate behaviour on the valid ones. Writing
one where the other belongs is wasted work at best and false assurance at
worst.

- **Do not test inputs the checker already forbids.** A test that calls a
  function with a value the checker rejects demonstrates no expected
  behaviour — it demonstrates that the escape hatch used to write the test
  works. Remember the checker only covers checked callers: at a public API
  boundary that unchecked code can reach, validation is a runtime feature
  and **is** tested.
- **Exception — harmful bypasses.** When a type-level restriction guards
  against data corruption or a security breach, enforce it at runtime too,
  and test that enforcement. This runtime check is a feature, not
  redundancy; the test that exercises it is the one sanctioned place for a
  type-level escape hatch, scoped to the single line that needs it and
  carrying a justification.
- **Every narrowing predicate gets unit tests, including near-miss
  values.** A checker never verifies that a hand-written guard's body
  matches the type it claims to narrow to, and a wrong guard poisons every
  downstream branch that trusts it.
- **Nontrivial type-level utilities get type-level tests pinned next to
  them**: positive cases asserting the computed type is the expected one,
  negative cases asserting the checker rejects what it must reject. Plain
  assignability checks are not enough — they silently accept dropped
  parameters and extra members. Where the toolchain can report an unused
  or obsolete suppression as an error, enable it: that is what keeps a
  negative type-level test honest as the types evolve.
- A generated or inferred type is not a specification. When a type is
  derived from a schema, a query, or a code generator, the test that
  matters is the one pinning the *runtime* shape the boundary actually
  produces.
