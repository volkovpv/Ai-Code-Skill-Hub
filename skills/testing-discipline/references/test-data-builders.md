# Constructing the data a test needs

Production code builds its complex objects in a handful of places, from
values it already has. A test has to build one every time — and if it
builds them literally, the construction crowds out the behaviour under
test and every constructor change breaks tests that never cared about it.

This file is about the arrange step's scaling problem. The rules for what
the values themselves should *say* are in
[structure-and-naming.md](structure-and-naming.md) and
[test-diagnostics.md](test-diagnostics.md).

## Three answers, and when each stops working

| Approach | Shape | Fails when |
|---|---|---|
| **Literal construction** | build the whole graph in the test | more than a couple of fields, or more than a couple of tests |
| **Named factory method** | `an_order_with_two_items()` | variation arrives — one method per combination, growing without bound |
| **Builder** | safe defaults + override only what matters | rarely; see the traps below |

- **A named factory method is the right answer where there is no
  variation.** One shape, one name, reused; nothing to gain from a
  builder. This is the same preference as *factory methods over shared
  setup hooks* in [anti-patterns.md](anti-patterns.md).
- **Reach for a builder when the tests vary the object along several
  independent axes.** The tell is a factory method acquiring parameters,
  then overloads, then near-duplicate siblings whose names no longer
  distinguish them.
- **Never build a value type through a builder just because it is a
  value.** If constructing it is one obvious call, make the call.

## What a builder is

One field per constructor argument, each initialized to a **safe
default**; chainable methods that override individual fields; a terminal
call that produces the object. Optionally a factory function named after
what is being built, so the call site reads as a noun phrase.

The properties that matter, in order of importance:

- **The test states only the fields its scenario depends on**, and
  inherits the rest. A reader can therefore tell what the test cares
  about by looking at it — which is the whole point, and is impossible
  with literal construction.
- **A constructor change touches the builder and the tests that drove the
  change**, not every test that happened to build one of these.
- **Each value is labelled at the point it is supplied.** Three strings
  passed positionally can be silently transposed and still compile; the
  same three supplied through named steps cannot.
- **Defaults must be safe, not realistic.** A default exists so the test
  need not think about that field; if it can make a test pass or fail, it
  is not doing its job. Prefer defaults that are obviously canned — see
  [test-diagnostics.md](test-diagnostics.md) — so a default that leaks
  into an assertion is recognisable.

## Similar objects, and the trap in reusing one builder

Two objects that differ in one field should be visibly identical
everywhere else, so partially configure one builder and finish it twice:

```
base    = an_order().with_line("hat", 1).with_line("cape", 1)
small   = base.with_discount(0.10).build()
large   = base.with_discount(0.25).build()
```

**This is only safe while the objects differ in the *same* field.** A
chainable builder mutates itself, so the moment two uses override
*different* fields, the second object silently inherits the first one's
override:

```
discounted = base.with_discount(0.10).build()
voucher    = base.with_voucher("abc").build()   # also carries the 0.10 discount
```

Nothing in the test says so, and nothing fails until an assertion happens
to depend on it. Two ways out, both fine:

- **Copy the builder** at each branch, so each object starts from the
  shared state and nothing accumulates.
- **Make the override steps functional** — each returns a new builder
  rather than mutating itself. Costs an allocation per step and removes
  the trap entirely; the safer default for anything complex.

## Combining builders

Where a built object contains other built objects, **pass the builders,
not the objects they produce**. The nested terminal calls are pure noise,
and removing them leaves the structure of what is being built visible:

```
an_order().from(a_customer().with(an_address().with_no_postcode()))
```

Overloading a single `with` step by argument type, where the language
allows it, compresses this further — and pushes gently toward introducing
domain types instead of passing bare strings, because only distinct types
can be told apart.

## Remove duplication at the point of use — by passing the builder through

Tests often repeat not just construction but what follows it: build,
submit, wait, repeat. The obvious refactoring extracts a helper that takes
the *values*:

```
submit_order_for("hat", "cape")
```

and it works exactly once. As the tests vary, that helper grows the same
combinatorial explosion of overloads the object mother had:

```
submit_order_for(products)
submit_order_for(product, count, other_product, other_count)
submit_order_for(product, discount)
submit_order_for(product, voucher_code)
```

**Pass the builder into the helper instead of its arguments.** The helper
finishes the object — supplying whatever infrastructure detail the test
should not have to mention — and performs the common steps:

```
having_received(an_order().with_line("hat", 1).with_line("cape", 1))
having_received(an_order().with_line("hat", 1))
```

One helper, unlimited variation, and the varying part stays visible in the
test where it belongs.

**Then rename for the reader.** Once the mechanics are in helpers, the
test's remaining text is free to describe the scenario rather than the
script that drives it — `having_received(...)` rather than
`send_and_wait(...)`, `displays_total_for(...)` rather than
`check_displayed_total_for(...)`. What you want at the end is something
you could read aloud to someone who knows the domain and not the codebase;
that is the same standard the test's *name* is held to.

## The limit

Factoring the arrange step out has the failure mode all abstraction has:
**a test can become so declarative that a reader can no longer tell what
it does.** Refactor test code far enough to see the flow of the scenario,
and no further — production code is held to a stricter standard here than
tests are, because tests are read for their story rather than composed
into a system.
