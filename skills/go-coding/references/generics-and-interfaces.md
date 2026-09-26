# Interfaces and generics

Interfaces describe behaviour a consumer needs; type parameters relate types
so one implementation serves several. Both are abstractions, and in Go an
abstraction is discovered from real duplication or a real seam — never
designed up front.

## Contents

- [Interfaces belong to the consumer](#interfaces-belong-to-the-consumer)
- [Accept interfaces, return concrete types](#accept-interfaces-return-concrete-types)
- [Type assertions and type switches](#type-assertions-and-type-switches)
- [When a type parameter earns its place](#when-a-type-parameter-earns-its-place)
- [Constraints](#constraints)
- [Generic methods (Go 1.27)](#generic-methods-go-127)
- [Iterators](#iterators)
- [Reflection is the last resort](#reflection-is-the-last-resort)
- [A completeness check derives its cases from the set's owner](#a-completeness-check-derives-its-cases-from-the-sets-owner)

## Interfaces belong to the consumer

- Declare an interface in the package that **uses** it, listing only the
  methods that package calls; usually unexported:

  ```go
  // package notify
  type addressFinder interface {
  	EmailAddress(ctx context.Context, id user.ID) (string, error)
  }
  ```

  The producer (`pgstore`) exports a concrete type and never learns the
  interface exists — Go satisfies interfaces implicitly.
- Create an interface only for a present need: two or more implementations,
  a seam a test must substitute, or restricting a value to part of its
  behaviour. "In case we switch databases later" is not a need.
- Small beats big: "the bigger the interface, the weaker the abstraction".
  One to three methods is typical; a 20-method repository interface next to
  its implementation is a smell — each consumer declares the slice it uses.
- Reuse the standard ones when they fit: `io.Reader`, `io.Writer`,
  `io.Closer`, `fmt.Stringer`, `error`, `http.Handler`.
- Pin a required implementation at compile time where the type and the
  interface live together: `var _ http.Handler = (*Server)(nil)`.
- A function type with a method (`type HandlerFunc func(...)`) lets plain
  functions satisfy a one-method interface; take a plain func parameter for
  a stateless callback.

## Accept interfaces, return concrete types

- Parameters take the narrowest interface that works; results are concrete
  (`*Store`, not `Store`) so adding methods or fields later is backward
  compatible and callers keep full access.
- Return an interface only when it is the contract itself: `error`, a
  plugin/driver contract, a stable standard adapter (`io.NopCloser`), or a
  function that genuinely returns one of several implementations.
- Returning an interface from a constructor "to hide the implementation"
  forces one abstraction on every caller and invites import cycles.

## Type assertions and type switches

- Always the comma-ok form; a single-value assertion panics on a mismatch
  (checker `GO-TYPE-ASSERT`, linter `forcetypeassert`):

  ```go
  s, ok := v.(fmt.Stringer)
  if !ok {
  	return fmt.Errorf("value %T has no String method", v)
  }
  ```

- A type switch has a `default` case.
- Assertions are for optional capabilities (`if wt, ok := r.(io.WriterTo)`)
  and closed variant sets, not a way around a signature that should have
  declared what it needs. Remember that a wrapper hides the optional
  interfaces of what it wraps.
- **Never assert or switch on an error's type** — wrapped errors hide it; use
  `errors.AsType` (see [errors-config-logging.md](errors-config-logging.md#inspecting-errors)).
- The same holds for `pool.Get().(*bytes.Buffer)` on a `sync.Pool` whose
  `New` returns only that type: write the comma-ok form — the bare form is
  both a `forcetypeassert` and an `errcheck` finding, and one line cannot
  justify two linters.

## When a type parameter earns its place

- A type parameter must **relate** types — a parameter to a result, two
  parameters to each other, a container to its elements — or remove real
  duplication across element types. If `T` appears once, delete it:
  `func Log[T any](v T)` is `func Log(v any)`.
- Use generics for data structures and algorithms that would otherwise be
  copied per type or fall back to `any` plus assertions: containers,
  `Map`/`Filter`-style helpers, "any integer" utilities — after checking
  `slices`, `maps` and `cmp` do not already provide it.
- Do **not** use a type parameter when the function only calls methods of the
  argument — take the interface. Do not convert interface code to generics
  for speed: Go compiles generics by GC shape with dictionaries, and the
  generic version can be slower; benchmark before claiming a win.
- A type parameter that appears only in the result cannot be inferred and is
  a disguised conversion the caller controls; return a concrete type or `any`
  plus a checked assertion at the call site instead.
- Return a zero value of a type parameter with `var zero T`.
- Do not rewrite working code to generics just because it can be.

## Constraints

- `comparable` when you need `==` (map keys); `cmp.Ordered` when you need
  `<`; custom constraints with type terms and `~` to admit named types:

  ```go
  type Integer interface {
  	~int | ~int8 | ~int16 | ~int32 | ~int64
  }

  func Clamp[T Integer](v, lo, hi T) T { return min(max(v, lo), hi) }
  ```

- Constraints with type terms are only valid as constraints, never as
  ordinary parameter types.
- A generic container takes the ordering as a function
  (`func(a, b T) int`, e.g. `cmp.Compare[int]`) so it works for any type
  without operator overloading.
- `comparable` does not protect you when the type argument is an interface:
  comparing two interface values with non-comparable dynamic types panics.

## Generic methods (Go 1.27)

Since Go 1.27 a method may declare its own type parameters:

```go
type Store struct{ /* ... */ }

func (s *Store) Load[V any](ctx context.Context, key string, decode func([]byte) (V, error)) (V, error) {
	raw, err := s.get(ctx, key)
	if err != nil {
		var zero V
		return zero, fmt.Errorf("load %s: %w", key, err)
	}
	return decode(raw)
}
```

- Use one where an operation relates types *and* belongs in the receiver's
  namespace — the standard example is `(*rand.Rand).N[I intType](n I) I`.
- Interface methods cannot declare type parameters, and a generic method
  never satisfies an interface method — do not design an interface around
  one.
- A generic method is still subject to the rule above: if its type parameter
  appears once, it should not exist.

## Iterators

- A custom sequence is an `iter.Seq[T]` / `iter.Seq2[K, V]` method, consumed
  with `for v := range tree.All()`; the standard library already returns them
  (`maps.Keys`, `slices.Values`, `strings.SplitSeq`, `strings.Lines`).
- An iterator that holds a resource releases it when the consumer's loop
  exits early — put the cleanup in the iterator function after the `yield`
  loop, and stop yielding when `yield` returns false.
- Collect when you need a slice: `slices.Collect(seq)`, sorted:
  `slices.Sorted(maps.Keys(m))`.

## Reflection is the last resort

Reflection (and `unsafe`) is for boundaries where types are genuinely unknown
at compile time — encoders, ORMs, templating — and is documented where used.
If a generic function or a plain interface can express the operation, use it:
reflection is slower by orders of magnitude, allocates, and turns type errors
into runtime panics. Use `reflect.TypeFor[T]()` rather than
`reflect.TypeOf((*T)(nil)).Elem()`.

## A completeness check derives its cases from the set's owner

A check that claims "every member of set S is handled" — a test, a registry,
a guard, an allowlist, a coverage table — must obtain S from S's owner and
diff it against what the code handles. Writing the list by reading off the
cases the code already handles is **self-referential**: it reports full
coverage of a set it never read.

| | Cases derived from the owner | Cases read off the handler |
|---|---|---|
| A member the handler covers | passes | passes |
| A member the handler forgot | fails, by name | invisible to both |
| Coverage reported | the truth | 100 %, always |

**In-program owners.** The owner of an iota enum is its constant block. Let
the `exhaustive` linter check switches and map literals against it
(`check: [switch, map]`), and iterate the range up to the unexported end
marker in tests — never a hand-copied slice of constants:

```go
func TestEveryKindHasAHandler(t *testing.T) {
	for k := KindUnspecified + 1; k < kindCount; k++ {
		if _, ok := handlers[k]; !ok {
			t.Errorf("no handler for %v", k)
		}
	}
}
```

**Owners outside the program** — a database schema's foreign keys, another
service's enum, a protocol's message types, the files in a directory: read
the owner (query `information_schema` / `pg_constraint`, parse the
specification, walk the directory) and diff; a member present in the owner
and absent from the handler is reported by name:

```go
func TestDeleteOrderCoversEveryForeignKey(t *testing.T) {
	declared := foreignKeyEdges(t, db) // SELECT ... FROM information_schema.referential_constraints
	for _, e := range declared {
		if !slices.Contains(deleteOrderEdges, e) {
			t.Errorf("delete order misses %s -> %s", e.From, e.To)
		}
	}
}
```

- A mutation run does not rescue a self-referential check: mutants come from
  the same code the list was read off, so a member the code never mentions
  cannot be mutated into view.
- The rule holds for any artifact that enumerates a set — production
  registries and guards included — not only for tests.
- Where the owner cannot be read at test time, generate the list from the
  owner's artifact (`go generate` from the spec) and commit it, so drift
  shows up as a diff someone must accept.
