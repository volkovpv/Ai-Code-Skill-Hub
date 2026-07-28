# Suite hygiene and the provenance of cases

A suite is only worth its runtime if a green run means something. These
rules are about the ways a suite goes quietly green while the property it
claims to protect is unprotected.

## Hygiene (non-negotiable)

- **No focused or skipped tests committed.** A focus marker silently
  disables every other test in its file; a skip marker disables itself. A
  skip that must ship carries a written reason and a tracking reference —
  never a bare marker.
- No commented-out tests, no conditional assertions, no empty tests, no
  duplicate test names. Each of them reports success without checking
  anything.
- Strictness relaxations the project forbids in shipped code — dynamic
  escapes from the type system, direct console output, patching — are
  allowed **only** inside test files, and only where the test genuinely
  needs them.
- **Do not tune a test to the gate:** never hardcode an expected value "so
  it passes", never disable a check, never refresh a snapshot or golden
  file without understanding the cause. A red test means dig into the
  cause.
- **Every bug fix ships a regression test** that reproduces the defect and
  fails before the fix. Tests are mandatory for any behaviour change.
- Tests are deterministic: no reliance on iteration-order accidents,
  wall-clock time, random seeds you did not pin, network availability, or
  test execution order. A test that passes only when the whole file runs
  is already broken.
- Coverage is a floor, not evidence. A line executed by a test that
  asserts nothing about it is covered and unprotected.

## Where a test's cases, subject and dimensions come from

**A test's case set, its subject, and its dimensions are all chosen from
the specification, never from the artifact under test.** This is distinct
from "do not tune a test to the gate" above: nothing here is hardcoded to
pass, every case is genuinely red before its fix, and a mutation battery
can still report a healthy score while the property below is violated.
Three rules, one family:

- **Provenance of the case set.** Derive cases from the specification's
  class, never copied from — or parametrized over — the artifact under
  test. A healthy mutation score is not evidence of specification
  coverage: when the case set mutates together with the implementation,
  the mutant is killed and the unmet specification stays invisible.
  Minimal reproduction: an implementation exposing `ALLOWED = {a, b, c}`
  for a rule the specification states as an open class; a test
  parametrized over that same `ALLOWED`; a mutation of the implementation
  set turns the test red (healthy mutation score); one specification-class
  member `d` is silently unhandled and no test notices. Stricter variant:
  if the test *imports* the enumeration rather than copying it literally,
  the mutation does not even fail — mutation testing is blind to the
  pattern in that form.
- **Subject of the test under layered protection.** When a property is
  protected by more than one layer, a test that reaches it through the
  outer layer proves nothing about the inner one; a defence-in-depth claim
  is unverified until each layer is exercised on a path where it is the
  only protection. Equivalently: every layer needs a test that goes red
  when that layer alone is deleted. Minimal reproduction: a value guarded
  both by an upstream filter keyed on field name and by an unconditional
  downstream overwrite in the serializer; a test that injects the value
  through the filtered channel; deleting the downstream overwrite alone
  leaves the suite green, because the upstream filter already intercepts
  the value before the downstream layer is ever reached.
- **Totality across the dimensions a control discriminates on.** A
  parametrized set that varies one dimension of the input says nothing
  about the others, and its size is not evidence — eleven cases over
  eleven names cover one dimension eleven times. Where the implementation
  carries a dedicated mechanism for another dimension (a raw-versus-
  normalized key form, an exhaustive branch over a variant's tag), that
  mechanism is by construction untested until the case set varies that
  dimension too. For each guard, name the dimensions of the input it
  discriminates on and require at least one case per dimension; treat a
  surviving mutation as evidence of a missing dimension, not merely of a
  missing case. Minimal reproduction: a mapping whose keys are normalized
  by a dedicated function before a membership test; a case set that varies
  only the key's text; a mutation that moves the membership test from the
  normalized key to the raw key — green, because no case supplies a key
  whose raw and normalized forms differ.

## Secrets in tests

Use test-only values; never pull real credentials into a test. Where a
test needs a signed token or a key, generate or sign a genuine test-only
one rather than mocking the verification away — the code under test should
run its real checks. A fake marker must be obviously fake, so that neither
a scanner nor a reader mistakes it for a live credential.
