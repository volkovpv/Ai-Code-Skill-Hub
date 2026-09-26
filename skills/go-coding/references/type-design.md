# Type design

Shape the types so that wrong code fails to compile, fails a linter, or fails
loudly at the boundary — instead of producing a plausible wrong value later.
Go has no sum types and no enums; the idioms below are how Go code gets most
of their benefit.

## Contents

- [Closed sets: typed constants](#closed-sets-typed-constants)
- [Exhaustive switches](#exhaustive-switches)
- [Variant state: a sealed interface](#variant-state-a-sealed-interface)
- [Named types for ids and units](#named-types-for-ids-and-units)
- [Absent is not zero](#absent-is-not-zero)
- [Invariants live behind a constructor](#invariants-live-behind-a-constructor)
- [Nil: what each kind does](#nil-what-each-kind-does)
- [A typed nil is not a nil interface](#a-typed-nil-is-not-a-nil-interface)
- [Values by default, pointers with a reason](#values-by-default-pointers-with-a-reason)
- [Receivers](#receivers)
- [Embedding is composition, not inheritance](#embedding-is-composition-not-inheritance)
- [Boundary data: decode into types, then validate](#boundary-data-decode-into-types-then-validate)
- [Equality](#equality)

## Closed sets: typed constants

A value that ranges over a fixed set is a named type with typed constants —
never loose strings or bare ints compared by value across the codebase:

```go
// Status is the closed set of order states; the zero value is not a state.
type Status uint8

const (
	StatusUnspecified Status = iota
	StatusPending
	StatusPaid
	StatusCancelled
	statusCount // end marker: every constant above it is a member of the set
)
```

- The zero value is either a deliberate "unspecified/unknown" (so an
  uninitialized field is detectable) or a genuinely sensible default.
- `iota` numbering is for values that never leave the process. A value stored
  in a database, sent on the wire or fixed by a spec gets explicit constants
  (`StatusPaid Status = 2`) or a string type (`type Status string` with
  `const StatusPaid Status = "paid"`) — inserting a constant must never
  renumber persisted data.
- Printable names come from a `String()` method: generated with
  `//go:generate go tool stringer -type=Status` (stringer pinned with the
  `tool` directive) when the text is just the constant's name, hand-written
  (as below) when the text differs — never both, which is a duplicate method.
- The unexported end marker, declared **inside** the `iota` block, gives code
  and tests a range to iterate (`for s := StatusUnspecified + 1; s <
  statusCount; s++`) that grows by itself when a constant is added above it —
  the set's owner, not a hand-copied list (see
  [generics-and-interfaces.md](generics-and-interfaces.md#a-completeness-check-derives-its-cases-from-the-sets-owner)).
  Name the zero value `…Unspecified` and the unexported marker `…Count`: the
  reference `exhaustive` configuration ignores exactly those two shapes
  (`Unspecified$|\.[a-z]\w*Count$`), so switches and maps are not asked to
  handle them while an exported member such as `FieldCount` still is.
- Nothing stops other code from writing `Status(42)`; validate values that
  arrive from outside (`ParseStatus(raw) (Status, error)`).

## Exhaustive switches

Every `switch` over a closed set lists **every** constant **and** keeps a
`default` that fails loudly for a value outside the set:

```go
func (s Status) String() string {
	switch s {
	case StatusUnspecified:
		return "unspecified"
	case StatusPending:
		return "pending"
	case StatusPaid:
		return "paid"
	case StatusCancelled:
		return "cancelled"
	default:
		return fmt.Sprintf("Status(%d)", uint8(s))
	}
}
```

- The `exhaustive` linter with `default-signifies-exhaustive: false` reports a
  switch that forgot a constant even when a `default` exists — so adding a
  constant breaks the build at every switch that must handle it. With
  `check: [switch, map]` it also reports a map literal keyed by the enum that
  misses a key (a handler table, a label table).
- A typed end marker inside the block is itself a member to `exhaustive`;
  without the `ignore-enum-members` setting every switch would have to list
  it (measured on golangci-lint 2.13) — keep the naming convention and the
  setting together.
- The `default` returns an error in business code (`fmt.Errorf("fee: unknown
  payment method %d", m)`); a `panic` is acceptable only when the value can
  come from nowhere but a programmer error inside the package.

## Variant state: a sealed interface

Model "one of several shapes" as an interface with an unexported marker method
and one struct per variant — never as one struct with a flag plus
independently optional fields that admit impossible combinations:

```go
// Event is sealed: only this package can add variants.
type Event interface{ isEvent() }

type OrderPaid struct {
	ID     OrderID
	Amount Money
}

type OrderCancelled struct {
	ID     OrderID
	Reason string
}

func (OrderPaid) isEvent()      {}
func (OrderCancelled) isEvent() {}

func Describe(e Event) (string, error) {
	switch ev := e.(type) {
	case OrderPaid:
		return fmt.Sprintf("order %s paid %d", ev.ID, ev.Amount), nil
	case OrderCancelled:
		return fmt.Sprintf("order %s cancelled: %s", ev.ID, ev.Reason), nil
	default:
		return "", fmt.Errorf("unknown event %T", e)
	}
}
```

- The unexported method stops other packages from adding variants; the
  `default` case catches a variant added later without updating the switch
  (the `gochecksumtype` linter can enforce exhaustiveness with a
  `//sumtype:decl` marker where the project uses it).
- `switch v := x.(type)` is the one idiomatic use of shadowing.

## Named types for ids and units

- No raw `string`/`int` for identifiers and quantities with units:
  `type OrderID string`, `type Cents int64`, `time.Duration`. A function taking
  `(OrderID, CustomerID)` rejects swapped arguments at compile time.
- The raw value becomes the domain type in exactly one place — a parse
  function at the boundary:

  ```go
  func ParseOrderID(raw string) (OrderID, error) {
  	if !orderIDPattern.MatchString(raw) {
  		return "", &ValidationError{Field: "order_id"}
  	}
  	return OrderID(raw), nil
  }
  ```

- A named string type still accepts untyped string constants and explicit
  conversions (`OrderID("anything")`). Where construction must be controlled
  (security-relevant tokens, validated emails), wrap the value in a struct
  with an unexported field so only the parse function can build one:
  `type Email struct{ v string }`.

## Absent is not zero

- "No value" is `(v, false)` or `(v, err)` from the function that looks it up
  — never an in-domain sentinel (`-1`, `""`, `time.Time{}`) that callers can
  forget to check:

  ```go
  func (c *Cache) Get(key string) (Entry, bool)
  ```

- Pointer fields express optionality only for external formats that
  distinguish `null`/missing from zero (JSON PATCH-style input, nullable
  columns — `sql.Null[T]` for the latter). Inside the program prefer an
  explicit field or a variant type.
- `time.Time` has `IsZero()`; a zero time as "unset" is acceptable only when
  zero can never be a real value in that field.

## Invariants live behind a constructor

A type whose fields must agree (a range with `start <= end`, a money amount
with a currency) keeps them unexported, validates them once in its
constructor and exposes methods — so no code path can hold an invalid
instance. Exported fields are for plain data with no invariant.

## Nil: what each kind does

| Kind | Read / call | Write / send | Other |
|---|---|---|---|
| slice | `len` 0, `range` fine, index panics | `append` works | valid empty slice |
| map | lookup returns zero value | assignment **panics** | create with `make` or a literal first |
| pointer | dereference **panics** | — | a nil receiver is legal if the method handles it |
| channel | receive blocks forever | send blocks forever | `close` panics; useful to disable a `select` case |
| func | call **panics** | — | guard optional callbacks |
| interface | method call panics | — | see the next section |

- Test emptiness with `len(s) == 0`, never `s == nil`: callers may hand you a
  non-nil empty slice, and an API must not give nil and empty different
  meanings.
- Return a nil slice for "no results" (`var out []T`); the JSON consequence
  (`null` vs `[]`) is covered in
  [runtime-correctness.md](runtime-correctness.md#slices).

## A typed nil is not a nil interface

An interface value is nil only when both its dynamic type and value are nil.
Returning a nil pointer through an interface result yields a **non-nil**
interface:

```go
func validate(o Order) error {
	var verr *ValidationError // nil pointer
	if o.Total < 0 {
		verr = &ValidationError{Field: "total"}
	}
	return verr // WRONG: non-nil error holding a nil *ValidationError
}
```

Declare results as `error` (or the interface), never hold a to-be-returned
error in a variable of the concrete type, and `return nil` on success.
Aggregate several failures with `errors.Join(errs...)`, which returns nil
when every input is nil.

## Values by default, pointers with a reason

- Pass and return values by default. Use a pointer when the callee must
  mutate the argument, when the type must not be copied (it holds a lock, an
  atomic, a `noCopy` marker), when the value is large (think kilobytes, not
  "a struct with five fields"), or for a stateful object with identity (a
  `*Service`, a `*bytes.Buffer`). (gocritic's `hugeParam` would push 80-byte
  structs into pointers; the reference configuration disables it for this
  reason.)
- A pointer is not a free optimization: returning `&v` usually moves `v` to
  the heap and adds GC work. Measure before switching for speed.
- Have functions construct and return a value (`func NewReport() (Report,
  error)`) instead of filling a pointer the caller passes in; out-parameters
  are for APIs that must accept any type (`json.Unmarshal(data, &v)`) or that
  let the caller reuse a buffer.

## Receivers

- Pointer receivers when a method mutates the receiver, when the type holds
  a `sync.Mutex`/`sync.WaitGroup`/atomic (copying it copies the lock — govet
  `copylocks`), or when the type is large.
- Value receivers for small immutable values (`time.Time`-style types) and
  for map, func and channel types.
- **Never mix kinds on one type** (linter `recvcheck`): if any method needs a
  pointer receiver, all methods get one — it keeps the method set predictable
  (a `T` does not have `*T`'s methods, so only `*T` satisfies an interface
  that includes a pointer-receiver method).

## Embedding is composition, not inheritance

- Embedding promotes **every** exported field and method of the embedded type
  into the outer type's API. Embed only when that is the intent (a wrapper
  that deliberately exposes an `io.ReadCloser`).
- Never embed `sync.Mutex` or `sync.RWMutex`: callers could then lock your
  value. Use a named, unexported field — `mu sync.Mutex` — declared next to
  the data it guards (checker `GO-EMBED-LOCK`).
- An embedded type that implements an interface makes the outer type
  implement it too. Embedding `time.Time` hands its `MarshalJSON` to the outer
  struct and the other fields silently vanish from the output — name the
  field (`At time.Time`) instead.
- A promoted method always runs on the inner value; there is no dynamic
  dispatch back to the outer type.
- Since Go 1.27 a struct literal may set a field promoted through embedded
  non-pointer structs directly: `Config{Port: 8080}` instead of
  `Config{Server: Server{Port: 8080}}` (`go fix` embedlit rewrites the old
  form). `Config{Server.Port: …}` is not a key, and a field promoted through
  an embedded pointer cannot be set this way.

## Boundary data: decode into types, then validate

- Data from the network, files, environment or a queue is decoded into a
  typed struct with an explicit tag on every serialized field, then validated
  once into domain types; nothing downstream sees the raw form:

  ```go
  type createOrderRequest struct {
  	CustomerID string `json:"customer_id"`
  	TotalCents int64  `json:"total_cents"`
  }
  ```

- `map[string]any` is for exploring an unknown payload, never for code that
  ships: every number in it is a `float64` and every access needs an
  assertion.
- Where the contract is closed, reject unknown fields
  (`json.RejectUnknownMembers(true)` in `encoding/json/v2`,
  `Decoder.DisallowUnknownFields()` in v1) — use the JSON package the module
  already uses. Bound the input size before decoding — see
  [security.md](security.md#decoding-untrusted-input).
- Keep the wire shape separate from the domain type when they differ (date
  formats, renamed fields): a small request struct plus a conversion
  function, not custom marshalers welded onto the domain type.

## Equality

- `==` works only on comparable types. Compare slices and maps with
  `slices.Equal` / `maps.Equal` (and the `Func` variants); `reflect.DeepEqual`
  is a legacy test helper, not an API tool.
- `==` on interface values compiles even when the dynamic type is not
  comparable, and then panics at run time — avoid it unless every possible
  dynamic type is comparable.
- Compare `time.Time` with `Equal`, never `==` (location and monotonic
  reading take part in `==`).
