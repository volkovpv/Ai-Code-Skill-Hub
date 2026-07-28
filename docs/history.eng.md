# Skill improvement history — the human-readable edition

> Russian version: [`history.rus.md`](history.rus.md) · Machine-readable version:
> [`../CHANGELOG.md`](../CHANGELOG.md)

`CHANGELOG.md` answers *what changed in which release*. This file answers a
different question: **what was going wrong, why it was wrong, and what the fix
actually does** — in plain words, for a person who was not there.

## How to read this file

Every entry follows the same shape:

| Block | What it gives you |
|---|---|
| **Releases** | every version that carries this change, in one place |
| **In one sentence** | the whole story, if that is all you have time for |
| **AS IS** | what used to happen, as a diagram |
| **TO BE** | what happens now, as a diagram |
| **Example** | the smallest thing you can run yourself to see it |
| **What the skill now says** | the rule in its final wording |
| **Where the rule stops** | the cases it deliberately does not cover |

Three conventions hold everywhere in this file:

1. **One story, one entry.** When the same fix lands in several skills across
   several releases, all of those versions are listed in a single **Releases**
   line. The story is not retold once per skill.
2. **No names of consuming projects.** A defect found while a skill was in use
   is described by its technical content only. Which project ran into it, which
   file it was found in, and that project's internal record identifiers never
   appear here — the same rule applies to `CHANGELOG.md`.
3. **Newest first — the latest entry at the top, a new one added above the
   others.** Same order as `CHANGELOG.md`. The oldest entry covers project
   version 2.5.0; anything older is in `CHANGELOG.md` only.

---

## One rule, two homes — the test rules become a skill of their own

**Releases:** project `3.0.0` (new skill `testing-discipline` `1.0.0` ·
`python-coding` `1.4.0 → 1.5.0` · `typescript-coding` `1.6.0 → 1.7.0`)
**Type:** duplication removed — the same rule was being maintained twice

### In one sentence

How to write a test is a property of tests, not of a programming language —
but each language standard carried its own full copy of those rules, so every
fix had to be made twice, by hand, in two separate releases.

### The problem, precisely

The three most recent test-rule fixes each landed in one standard first and
then had to be mirrored into the other one:

| The rule that was fixed | Landed first | Mirrored later |
|---|---|---|
| Where a test's cases, subject and dimensions come from | project `2.5.0` | project `2.6.0` |
| How a stub's contract for an external system is established | project `2.7.0` | project `2.8.0` |
| Values substituted on the way out, and who builds the collaborator | project `2.9.0` | project `2.10.0` |

Six releases for three rules. Nothing about any of them was
language-specific: each one shipped its own universality check, and the
mirrored copy differed only in which library the example named. The cost was
not just the duplicated work — it was that the two copies could disagree, and
that a third language would have needed a third copy of everything.

### AS IS — how it went wrong

```mermaid
flowchart LR
    A["A test rule is fixed in\none language standard"] --> B["Someone must remember\nthe other standard"]
    B --> C["A second release re-states\nthe same rule in other idiom"]
    C --> D{"Two copies of one rule"}
    D -->|"one gets edited"| E["Wordings drift apart"]
    D -->|"a third language arrives"| F["A third copy is needed"]
```

### TO BE — how it goes now

```mermaid
flowchart LR
    A["A test rule is fixed once,\nin the testing standard"] --> B{"One copy"}
    B --> C["Language standards keep only\na spelling map for their idiom"]
    C --> D["A new language costs\na spelling map, not a rule set"]
```

### Example — what moved and what stayed

The rule and its reproduction are language-neutral, so they moved:

> A fake's own return values, when the property under test belongs to an
> external system, are established by observing that system once, never by
> reading.

What stayed behind in each language standard is only the vocabulary that
expresses it — a row in a table, not a rule:

| What the test needs | Stays in the language standard |
|---|---|
| A stand-in for a seam the project owns | which construct satisfies the declared interface |
| Last-resort patching | which patching facility, and that it needs a justification |
| A skip that must ship | which marker carries the reason |
| A negative type-level assertion | which suppression the checker itself polices |

### What the skills now say

- `testing-discipline` owns the rules: tests ship with the change, one
  scenario per test, isolation and injected time, what may be faked and how a
  fake's contract is justified, evidence collected where the property lives,
  where cases come from, and suite hygiene.
- `python-coding` and `typescript-coding` keep a spelling map each and no
  longer state test rules of their own.

### Where the rule stops

The testing standard says nothing about which runner to use, where test files
live, or what coverage number the build demands — those belong to the project.
Which collaborator is faked at which seam in a ports-and-adapters codebase
still belongs to `hexagonal-service`, and how a rule is written in a given
language still belongs to that language's standard.

---

## What a stub still can't see — two more shapes of the same blind spot

**Releases:** project `2.10.0` (`typescript-coding` `1.5.0 → 1.6.0`) · project
`2.9.0` (`python-coding` `1.3.0 → 1.4.0`)
**Type:** a gap widened — the previous fix's own scope sentence was too narrow

### In one sentence

The rule about faking a third-party seam said "the stub's **return values** are
established by observing the real system" — but a stub can also miss a value the
real system changes on the way **out** of a call, and it can also miss whether the
*product itself* ever builds the collaborator the way the stub assumed.

### The gap, precisely

The previous entry fixed *how a stub's return values become known to be true*.
Its own wording, read literally, only covers a stub computing the wrong **output**
for a given input. Two adjacent shapes fall outside that wording on a first read:

1. **Nothing comes back at all.** Some third-party clients substitute a value the
   caller does not fully control — a request id, a retry token, a default header —
   on the way *out* of a call, before anything returns. A stub bound at exactly
   that layer has no return value to check, so the "check the return value" framing
   does not put a reader on notice.
2. **The stub built the thing itself.** A test asserting *how* a collaborator is
   constructed — which arguments, which hooks — sometimes builds that collaborator
   by hand inside the test, instead of calling the one production factory that
   really builds it. The test can prove the property is *possible*; it proves
   nothing about whether the *product* does it.

### AS IS — how it went wrong

```mermaid
flowchart LR
    A["Adapter passes a value to\nthe third-party client"] --> B["Client silently substitutes\nits own value on the way out"]
    B --> C["Test fakes the client method\nthat performs the substitution"]
    C --> D{"Unit test"}
    D -->|"green"| E["Value never verified\nto reach the wire"]

    F["Production factory wires\nan argument onto the client"] --> G["Test builds its own\nclient instance instead"]
    G --> H{"Unit test"}
    H -->|"green"| I["Factory's own wiring\nnever exercised"]
```

Both loops share one shape: the evidence the test collects is gathered somewhere
other than where the property under test actually lives.

### TO BE — how it goes now

```mermaid
flowchart LR
    A["Ask: is there a return\nvalue to check at all?"] -->|"no — it's substituted on the way out"| B["Probe the real client once;\npin what actually reaches the wire"]
    A -->|"yes"| C["Existing rule applies:\nprobe, then reuse as a fixture"]

    D["Ask: does the test build\nthe collaborator itself?"] -->|"yes"| E["Exercise the production\nfactory instead"]
    D -->|"no — factory is exercised"| F["Test is measuring\nthe right code path"]
```

### Example you can run in your head

A test faking a third-party client:

```python
monkeypatch.setattr(sdk.chat, "completions", fake_domain)
assert request.trace_id == "t-1"          # true — but never observed
```

This only checks what the caller *passed in*. It says nothing about what the SDK
did with it after that — and the SDK in question regenerated its own id on every
call, unconditionally. The fake stood in for exactly the code that would have
shown that.

The wiring case is shorter still: a factory function is the only place a client
gets built for real use; every test builds a parallel client of its own. Delete
the argument from the factory call, and the whole suite — every test file — stays
green, because none of them ever call the factory.

### The same two shapes, in another language

Neither shape belongs to Python. Both rules ship in the TypeScript standard too,
restated in the tools a Node project uses:

```ts
const send = jest.fn();
client.send = send;
expect(send.mock.calls[0][0].traceId).toBe("t-1");  // what was passed in — never what left
```

```ts
createClient({ interceptors: [logging] });     // the one place the product builds a client
new SdkClient({ interceptors: [logging] });    // what every test builds instead
```

An options object instead of keyword arguments, an interceptor array instead of a
list — the same construction seam, and the same question: is the thing under test
the one that ships?

### What the skill now says

| Rule | In plain words |
|---|---|
| Outbound substitution counts too | A fake must also be checked for a value the real layer changes on the way out, not only for what it returns — there may be no return value to inspect at all |
| Construction is a code path too | A test asserting how a collaborator is built must exercise the production factory, never a hand-built copy — a hand-built copy proves the property achievable, not that the product achieves it |

### Where the rule stops

Neither addition reaches further than its own shape. A fake for a project-owned
seam with no outbound call is unaffected by the first rule. A test that calls the
real production factory directly — not a substitute — already satisfies the
second rule; it is not asked to do anything more. Both additions ship a dedicated
negative test to keep them from being over-applied.

### How the change was made

Test first: a regression pinning the two new rules and their two reproductions
was written and confirmed genuinely red against the pre-change text → the minimal
guidance was added → the regression went green → two behavior and two negative
evaluation cases were added, one pair per shape → the full suite ran with no
regressions.

---

## Where a stub gets its truth from

**Releases:** project `2.8.0` (`typescript-coding` `1.4.0 → 1.5.0`) · project
`2.7.0` (`python-coding` `1.2.0 → 1.3.0`)
**Type:** a gap closed — the skill was not wrong, it was silent

### In one sentence

The skill told you **what** to replace with a stub in a unit test, but never
said **where the stub's answers come from** — so a stub could encode a wrong
belief about somebody else's system, and the test would stay green forever.

### The gap, precisely

`references/testing.md` already carried a good rule:

> fake protocols and seams the code exposes, never someone else's internals

That rule is about the **shape** of a stub. It says nothing about the stub's
**content** — the values it hands back. When those values describe a system your
project did not write (a message broker, a database driver, an authentication
encoder), believing them is a leap of faith, and nothing in the skill said so.

### AS IS — how it went wrong

```mermaid
flowchart LR
    A["Read the vendor docs<br/>or the project's own norm"] --> B["Write the stub<br/>from what you believe"]
    B --> C{"Unit test"}
    C -->|"green"| D["Change is merged"]
    D --> E["The real system<br/>behaves differently"]
    E --> F["Failure, found late"]
    F -->|"re-read the docs again"| A
```

The loop is the damaging part. The stub checks itself: if it lies, the test
lies with it and stays green through any number of fix rounds. Each round
produced a *new reading* of the same documentation, and a new reading is the one
thing that could never settle the question.

### TO BE — how it goes now

```mermaid
flowchart LR
    A["Probe the real system once"] --> B["Pin the observed answer<br/>as a fixture"]
    B --> C["Write the stub<br/>from the fixture"]
    C --> D{"Unit test"}
    D -->|"green"| E["Change is merged"]
    E --> F["The real system<br/>behaves as pinned"]
```

One live observation replaces an unbounded number of readings.

### Example you can run in two lines

A connection opened with `psycopg`'s `dict_row` row factory:

| Query | What the driver actually returns |
|---|---|
| `SELECT true AS a, false AS b` | `{"a": True, "b": False}` — two keys |
| `SELECT true, false` (no aliases) | `{"?column?": False}` — **one** key; the columns collapse |

What the test contained:

```python
cursor.fetchone.return_value = (True, False)   # an ordinary DB-API tuple
```

That is what every DB-API tutorial leads you to write, and it is exactly wrong
for a connection using `dict_row` — a choice made by the library, not by the
project. The test passed. The live query raised
`ValueError: not enough values to unpack`.

A second, equally short one:

```python
yarl.URL.build(scheme="amqp", host="h", port=1, user="", password="p").user
# -> None
```

An empty user is indistinguishable from an absent user, so any client library
reading that URL is free to substitute its own default identity. No stub placed
at the wrapper's own seam can see this happen — the stub stands in for the very
layer that does the substituting.

### The same two facts, in another language

Nothing here belongs to Python. The rule ships in the TypeScript standard too,
with the same two examples restated in the tools a Node project uses:

```ts
new URL("amqp://:p@h:1").username;  // "" — and so is new URL("amqp://h:1").username
```

| What the query looks like | What a driver that builds rows as objects returns |
|---|---|
| `SELECT true AS a, false AS b` | `{ "a": true, "b": false }` — two keys |
| `SELECT true, false` (no aliases) | `{ "?column?": false }` — **one** key; the database names both columns `?column?` and the second overwrites the first |

The language changed; the lesson did not. Which is the point: the rule is about
where a belief comes from, not about a syntax.

### The same mistake, three times over

| # | Third-party system | What the stub believed | What is actually true |
|---|---|---|---|
| 1 | a message broker, via `aio-pika` | the event name can be read off the routing key | the broker **rewrites** the delivery key at every dead-letter hop, while carrying the message type through untouched |
| 2 | `aiormq`, SASL-PLAIN | "a non-empty string in settings means the login is set" | an empty user counts as absent, and the encoder substitutes a default identity one layer below the seam under test |
| 3 | `psycopg`, `dict_row` | the cursor hands back a tuple | unaliased columns collapse into a single-key mapping |

Three different libraries, three independent occurrences, one shared cause: a
belief about someone else's runtime behaviour was **assumed** instead of
**measured**. Every one of them was settled by a live probe. None was ever
settled by reading.

### What the skill now says

| Rule | In plain words |
|---|---|
| Observation, not reading | For an external system, the stub's return values are established by probing the real thing once — not from vendor prose, not from a project norm |
| Probe first, stub second | Write the stub only after the probe has pinned the behaviour, then reuse that pinned result as a fixture |
| **The second-rejection trigger** | If the same reading of the same external property is rejected twice, stop reading. Switch evidence class: go and measure. Do not produce a third reading |

### Where the rule stops

It applies to systems **you do not own**. A stub for a port your own project
defines is a different matter entirely: there the contract *is* the project's
own decision, and reading it is the correct way to know it. The change ships a
dedicated negative test to keep the rule from being over-applied to that case.

### How the change was made

Test first, in this order: a regression test pinning the new wording was written
and confirmed genuinely red (4 of 5 assertions failing) → the guidance block was
added → the test went green (5 of 5) → two evaluation cases were added, one for
the behaviour and one guarding against the false positive above → the full suite
ran 684 of 684 with no regressions.

---

## Where a test gets its cases from

**Releases:** project `2.5.0` (`python-coding` `1.1.0 → 1.2.0`) · project
`2.6.0` (`typescript-coding` `1.3.0 → 1.4.0`)
**Type:** a gap closed — one story, two languages, two releases

### In one sentence

The skill checked the **quality** of a test — it must be red before the fix, it
must be deterministic — but said nothing about where the test's **cases come
from**. So cases were copied from the code under test instead of derived from
the specification, and test and code went wrong in the same direction, agreeing
with each other all the way.

### The gap, precisely

The nearest existing rule was:

> Do not tune a test to the gate: never hardcode an expected value "so it
> passes".

It covers none of what actually happened. Nothing was hardcoded to pass; every
case was honestly red before its fix. What was missing was three different
things: **where the cases come from**, **what the test's subject is**, and
**which dimensions it has to vary**.

### AS IS — how a green suite stayed blind

```mermaid
flowchart TD
    SPEC["SPECIFICATION<br/>an open class:<br/>'a, b, c, d, … — anything that qualifies'"]
    IMPL["IMPLEMENTATION<br/>a closed list:<br/>ALLOWED = {a, b, c}"]
    TEST["TEST<br/>cases copied from ALLOWED"]
    GAP["member d is not in the list<br/>= an unmet requirement"]
    BLIND["nobody ever checks d"]

    SPEC -->|"d must be handled"| GAP
    IMPL -->|"cases copied out of the code"| TEST
    TEST -->|"only a, b, c are exercised"| BLIND
    GAP -.->|"the hole is invisible"| BLIND
```

And the trap closes: **mutation testing cannot save you here.** Mutate `ALLOWED`
in the code and the test — copied from `ALLOWED` — mutates with it, goes red,
kills the mutant, and reports a healthy score. In the stricter form, where the
test *imports* the enumeration instead of copying it, the mutation does not even
fail. A healthy mutation score is not evidence of specification coverage.

### TO BE — how it goes now

```mermaid
flowchart TD
    SPEC["SPECIFICATION<br/>name the class, not the list"]
    CASES["CASES<br/>derived from the class,<br/>including members the code does not have yet"]
    TEST["TEST"]
    IMPL["IMPLEMENTATION"]
    SPEC --> CASES --> TEST
    TEST -->|"exercises the code"| IMPL
    IMPL -.->|"never feeds cases back"| CASES
```

The arrow from implementation to cases is the one that must not exist.

### Example you can hold in your head

```python
ALLOWED = {"totalTokens", "inputTokens", "outputTokens"}   # the code

@pytest.mark.parametrize("field", ALLOWED)                 # the test
def test_field_is_handled(field): ...
```

The specification says "any token-count field". The code knows three. The test
asks the code which three. A fourth real field — `totalTokenCount` — is handled
by nobody, and no run of this suite will ever say so. The TypeScript shape is
the same: an `as const` registry with `it.each(ALLOWED)` over it.

### The three rules that were added

They ship as one family, under a single thesis: **a test's case set, its
subject and its dimensions are all chosen from the specification, never from
the artifact under test.**

| Rule | In plain words | The mistake it prevents |
|---|---|---|
| **1. Provenance of the case set** | Derive cases from the class the specification names; never copy or parametrize over the code's own list | The suite can only ever confirm what the code already knows |
| **2. Subject under layered protection** | A defence-in-depth claim is unproven until each layer is exercised on a path where it is the **only** protection | One end-to-end test through two layers proves nothing about either |
| **3. Totality across dimensions** | Name the dimensions a guard discriminates on and require at least one case per dimension; a surviving mutant means a missing **dimension**, not just a missing case | 11 cases over 11 names cover one dimension eleven times |

Rule 2, drawn:

```mermaid
flowchart LR
    IN["a secret arrives"] --> L1["Layer 1<br/>upstream filter by field name"]
    L1 --> L2["Layer 2<br/>unconditional downstream rewrite"]
    L2 --> OUT["clean output"]
    T["one end-to-end test<br/>injects through the filtered channel"] -.->|"only ever looks at the output"| OUT
    DEL["delete Layer 2"] -.->|"the test stays GREEN —<br/>Layer 1 already caught it"| L1
```

Rule 3 in numbers, measured rather than argued: a suite of **303 passing** tests
went to **11 failing** the moment a single case was added that varied the *form*
of a key (raw vs normalized) rather than its *text*. Eleven real holes, one
missing dimension.

### How bad it got before anyone noticed

Nine independent occurrences in one build, over thirteen fix rounds. Every one
was found by a live probe or by a mutation battery — **not once by the suite
that was supposed to be guarding the property**, which stayed green at 133, 247,
251, 276, 303, 320 and 310 passing tests while real defects walked through.

The decisive evidence that this was a missing rule and not a careless author:
two of the nine occurrences appeared **inside the very change that was fixing a
third one** — the pattern reproduced in its own cure, in a round whose author
had just been warned about it and whose test file named the pattern out loud.

### Where the rule stops

Rule 3 is about inputs a guard genuinely discriminates on. An input with one
real dimension needs one dimension's worth of cases and no more; the change
ships a dedicated negative test so the rule is not turned into a demand for
ceremonial cases.

### How the change was made

Test first, both times: a regression pinning the new wording was written and
confirmed genuinely red (5 of 6 assertions failing) → the guidance block was
added → green → evaluation cases, one per rule plus a false-positive guard.
Full suite 673 of 673 for the Python release and 679 of 679 for the TypeScript
one, no regressions. The TypeScript half is a deliberate mirror: same three
rules, examples re-cast in TypeScript idiom (an `as const` registry, `it.each`,
a `Map` with normalized keys, an exhaustive `switch` over a discriminated union
as a second dimension).
