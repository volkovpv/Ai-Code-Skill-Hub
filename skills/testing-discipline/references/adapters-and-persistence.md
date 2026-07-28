# Testing the adapters: persistent state and reflective mappings

The tests in this file all have the same subject: **the thin layer where
your objects meet infrastructure you did not write** — a persistence
mapper, a serializer, a message translator. They are integration tests by
the definition in [test-levels.md](test-levels.md), and they carry
problems no unit test has: state that survives between runs, a large
amount of configuration behind a small API, and failures that could have
come from any of a dozen layers.

A mapping is usually a few lines of declaration standing in for a great
deal of behaviour. That is why its defects are hard to diagnose, and why
these tests are worth their cost.

## Clean persistent state at the *start* of a test, not at the end

The runner cannot isolate tests from data that outlives them, so the
fixture must. Do it on the way in.

| | Clean at the start | Clean at the end |
|---|---|---|
| Isolation | the next test cleans before it runs | broken as soon as a test fails before its cleanup |
| After a failure | the data that caused it is still there to look at | the evidence has been deleted |
| Running one test alone | works, and leaves an inspectable state | works, and tells you nothing |

- **Capture the order of the cleanup in one place.** Where integrity
  constraints force a particular order, that order is a fact about the
  schema and will need updating as the schema changes; scattered across
  test files it will not be.
- The same reasoning applies to anything else that persists between runs —
  a log the test will assert against, a queue, a directory of files. Clear
  it as part of arranging, not as part of tidying up.

## Make transaction boundaries explicit; do not isolate by rolling back

A common shortcut runs each test inside a transaction and rolls it back at
the end, so the store is unchanged. It is convenient and it removes the
most interesting part of the test.

- **Commit is where the work happens.** Pending changes are flushed,
  integrity constraints are checked, generated values are assigned,
  triggers fire. A test that never commits never exercises any of it.
- **Interactions between transactions become untestable** — which is
  exactly the class of defect a persistence test should be catching.
- **Rolling back destroys the evidence** of a failure, for the same reason
  cleaning up at the end does.

Write the transaction boundaries into the test, and make them visible:
wrap each unit of work in a named helper so a reader can see where one
transaction ends and the next begins. Frameworks that manage transactions
declaratively around production code leave nothing in that code to mark
the boundaries — which is precisely why the *test* has to mark them, using
the same transaction machinery the application is configured with.

## Round-trip the mapping, one entity at a time

When a mapping is misconfigured, the failure surfaces far from its cause:
a query test goes red, and the cause might be the query, the mapping of
any type it touches, the mapper's configuration, the connection, or the
schema.

**Add a test that takes each mapped type, writes it and reads it back,
and compares.** It is the cheapest way to convert "something in the
persistence layer is wrong" into "this type's mapping is wrong".

- Applies to every reflective translation, not only databases: object
  serialization, document mapping, wire formats, configuration binding.
- Drive it from a list of builders, one per mapped type, so adding a type
  means adding a line — see
  [test-data-builders.md](test-data-builders.md).
- Where saving one entity does not cascade to a related one it references,
  the related entity must already exist before the round trip. Compose the
  builders so the prerequisite is created and stored as part of building
  the subject, rather than leaving each test to remember.

### Reflection is legitimate here, and only here

The rest of this skill says to test through the public surface and never
to reach into private state — see [anti-patterns.md](anti-patterns.md).
A round-trip test breaks that, deliberately:

- **The subject is the mapping configuration, not the object's design.**
  These tests are not test-driving the entity's API and are not meant to
  give feedback about it.
- **The mapper reaches the object's state reflectively**, so a test that
  verifies the mapper reaches it the same way. Asserting through the
  public surface here would verify the accessors instead of the mapping.

The exception is bounded by that argument. It licenses round-tripping a
mapped type; it does not license reaching into private state in any test
whose subject is your own behaviour.

## Do not exercise generic mapping code with production domain types

A mapper, marshaller or serializer is usually generic: it works on any
type. It is tempting to test it against a real domain type, since one
exists. **Use purpose-built types instead** — types that exist only in the
test and are named for the features they represent.

Two distinct costs, and the second is the dangerous one:

- **Coupling.** The domain type can no longer be deleted or restructured
  without breaking tests that were never about it — irrelevant rework, and
  a refactoring blocked for no reason.
- **Silent rot.** The domain type was chosen because it happened to
  exercise every path — it had a transient field, an optional field, a
  nested collection. When someone later removes that field, the mapper's
  handling of it stops being covered **and no test fails.** The suite
  reports the same green it always did, over a case that no longer exists.

A purpose-built type cannot rot this way: it exists for the case it
covers, its name says which case that is, and nobody edits it for reasons
unrelated to the mapper. Its fields double as self-describing values —
see [test-diagnostics.md](test-diagnostics.md).

## Name the fixtures for their role in the test

Persistence tests set up several similar records and assert which subset
came back. Name each record after **why it is in the test** — the entity
whose date falls before the boundary, the one exactly on it, the one after
— rather than after a plausible real-world value. The failure report then
reads as a sentence about the boundary condition instead of a list of
identifiers.

Prefer a name you chose over an identifier the store assigned: the
assigned one is not stable, is often not exposed, and explains nothing
when it appears in a report.

## These tests are slow, and that is the reason for the layering

Nothing here runs in memory or in milliseconds. The response is not to
make them faster but to **keep them few and keep them out of the fast
suite**: define the persistence interface in your own domain's terms,
unit-test everything above it against a double, and let this layer of
tests cover the implementation of that one interface. That is the
arrangement described in [test-levels.md](test-levels.md), and this is
what the middle layer of it looks like in practice.
