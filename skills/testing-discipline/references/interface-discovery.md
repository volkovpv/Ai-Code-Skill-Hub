# Interface discovery: where the doubled collaborators come from

The London school replaces every collaborator, which looks from outside
like a taste for mocking. It is not. **The collaborator does not exist
yet**, and standing a double in for it is how it comes into existence —
the test states the protocol between two objects before either side of
it is written.

This is a **unit-test technique**, and it applies where the host project
declares the London school, or declares interaction-based design
explicitly — the same way it declares anything else, see
[schools.md](schools.md). Under the classical school the collaborators
are mostly real, and this file does not apply.

## The loop, per object

1. You are implementing an object and reach something it should not do
   itself.
2. **Name the service in the client's terms**, from the client's point of
   view — what this object needs, not what some future implementation
   will happen to provide.
3. Stand a double in for it and write the test as though the service
   already existed. The test now states the protocol between the two.
4. Then write something that provides the service — and repeat from (1)
   for *its* needs.

- **"If this worked, who would know?"** When the honest answer is not the
  object under test, that answer names a collaborator that ought to
  exist, and the double you are about to write is standing in for it.
- **Pull interfaces into existence from the client, do not push them out
  from the implementation.** An interface designed from the client's need
  leaks nothing about who will implement it; one extracted from an
  existing class carries that class's shape into every future
  implementation.
- **Keep the discovered surface narrow.** The fewer operations it
  declares, the more obvious its role at the call site, and the easier it
  is to write another implementation, adapter or decorator for it. Many
  narrow roles beat few wide ones.
- **A name you cannot find is a signal, not a formality.** If nothing but
  a restatement of the implementation fits, the responsibility is
  probably misplaced, or the "interface" is really a value; see
  [isolation-and-fakes.md](isolation-and-fakes.md).
- **Revisit the roles as they accumulate.** Two that turn out to mean the
  same thing get merged — more things become interchangeable. Two that
  look alike but differ get renamed apart, so they cannot be combined by
  accident.

## Start at the object that receives the request

Discovery has a direction: **begin with the object that receives the
incoming event and follow the chain of needs inward**, until it reaches
objects that already exist or the boundary where the response leaves.

Beginning in the domain model instead feels faster because nothing
constrains it yet, and that is exactly the problem: without the pull of a
real caller it is easy to build functionality that is unnecessary,
wrongly shaped, or impossible to fit together — and the cost surfaces
when the pieces are assembled, which is the most expensive moment to
find it.

## What discovery costs, and the discipline that pays it

Every discovered role that a test doubles is a claim about *how* the
subject reaches its result, and interactions that never leave the
application are implementation details. That is the standing cost of this
technique, and it is paid down by rules that live elsewhere in the skill:

| The cost | What keeps it survivable |
|---|---|
| A double binds the test to a collaboration | replace **peers**, never internals, and double only roles you named — [isolation-and-fakes.md](isolation-and-fakes.md) |
| A pinned interaction binds the test to a call | allow queries, expect commands; few expectations; arguments and order matched only as tightly as the scenario constrains them — [unit-test-value.md](unit-test-value.md) |
| A role you discovered may be wrong | a surface you cannot name, or an arrange step that will not shrink, is design feedback — [tests-as-design-feedback.md](tests-as-design-feedback.md) |

**A project that declares London and skips these has bought the cost
without the benefit.**

## Where this does not reach

Discovery tells you which collaborators exist and what each is for. It
does not tell you whether the assembled product works, whether the entry
point reaches your objects at all, or whether the deployment is
configured correctly — none of which any unit test can establish. Those
belong to levels outside this skill's scope; what *is* in scope is
keeping the unit level honest about not having answered them. See
[test-levels.md](test-levels.md).
