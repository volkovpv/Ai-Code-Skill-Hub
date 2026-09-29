# Style and naming

The formatter settles layout; this file covers what it cannot write for you —
names, comments, control-flow shape, declarations and the suppression policy.
Everything here holds in any Go codebase; no framework is assumed.

## Contents

- [Formatting](#formatting)
- [Naming](#naming)
- [Package names](#package-names)
- [Doc comments](#doc-comments)
- [Line of sight: keep the happy path left](#line-of-sight-keep-the-happy-path-left)
- [Declarations and shadowing](#declarations-and-shadowing)
- [Constants and literals](#constants-and-literals)
- [Imports](#imports)
- [Suppressions](#suppressions)

## Formatting

- `gofmt` (or `goimports`, which is `gofmt` plus import management) output is
  the only accepted layout. Run it before every commit; a stray formatting
  diff in a logic change is noise that hides the change.
- One formatter per project. `gofumpt` is a stricter superset some projects
  choose; follow the project's choice, never run two that disagree.
- Never fight the formatter by hand (manual alignment, braces on their own
  line — the latter does not even compile, because of semicolon insertion).

## Naming

- **MixedCaps**, never `snake_case` or `SCREAMING_CASE` — the case of the first
  letter *is* the export decision. Constants are MixedCaps too
  (`MaxRetries`, `defaultTimeout`).
- **Initialisms keep one case**: `userID`, `HTTPClient`, `parseURL`,
  `ServeHTTP`, `xmlDecoder` — never `UserId`, `HttpClient`.
- **Length follows scope**: `i`, `k`, `v`, `r`, `w` in a few-line loop or
  handler; descriptive names at package level. A long function full of
  one-letter names is too long, not too tersely named. Never encode the type in
  the name (`nameString`, `userStruct`).
- **Units the type cannot carry go in the name** (`sizeBytes`, `ttlSeconds`
  when an `int` is forced on you) — but prefer a type that carries the unit:
  `time.Duration`, a named `type Cents int64`.
- **Receivers**: one or two letters abbreviating the type (`func (s *Store)`),
  the same on every method of the type; never `this`, `self`, `me`.
- **No `Get` prefix** on accessors: `Owner()`, `SetOwner()`. Write accessors
  only when they add value (validation, derived value, locking, an interface
  to satisfy); otherwise export the field.
- **Interfaces** name a behaviour; a one-method interface is the method name
  plus `-er`: `Reader`, `Notifier`, `OrderFinder`.
- **Errors**: sentinel variables `ErrNotFound`, error types `ValidationError`,
  messages lowercase without trailing punctuation (`"order not found"`), so
  they compose into `"cancel order ord_1: order not found"`.
- **Test names** may use underscores to separate the case:
  `TestParseOrderID_rejectsUppercase`.
- Never reuse a predeclared identifier or an imported package name as a
  variable: `len`, `cap`, `new`, `copy`, `min`, `max`, `clear`, `error`,
  `string`, `url`, `json` — the builtin or package becomes unreachable in that
  scope (the `predeclared` linter and govet `shadow` catch most of it).

## Package names

- Short, lowercase, one word, a noun for what the package **provides**:
  `orders`, `ledger`, `pgstore`. The package clause matches the directory
  name, and the directory name is a valid identifier (no hyphens).
- **No meaningless names**: `util`, `utils`, `common`, `shared`, `base`,
  `helper(s)`, `misc`. They tell a reader nothing and attract unrelated code;
  split them by what their functions actually do (`stringset`, `retry`). The
  checker flags these package clauses as `GO-PKG-NAME`. Much of what used to
  live in such packages is now in `slices`, `maps`, `cmp` and the `min`/`max`/
  `clear` builtins.
- **No stutter**: callers read `orders.Service`, `orders.New`, not
  `orders.OrderService`, `orders.NewOrderService`. The exception is a package
  whose main type *is* the concept (`context.Context`, `time.Time`).

## Doc comments

- Every exported identifier and every package has a doc comment: a full
  sentence that starts with the identifier's name and says what it does or is,
  not how. The package comment starts `// Package orders …` and sits directly
  above the `package` clause; a long one lives in `doc.go`.
- Doc comments use the Go doc syntax: blank `//` lines between paragraphs,
  `[pkg.Symbol]` links, `# Heading`, indented blocks for code.
- Deprecation is its own paragraph so tools recognize it:

  ```go
  // ComputePath returns the fastest path between two points.
  //
  // Deprecated: use [ComputeFastestPath], which handles one-way edges.
  func ComputePath(a, b Point) Path
  ```

- Comments explain *why* and constraints (units, invariants, concurrency
  safety, who closes what); they do not narrate the code line by line.

## Line of sight: keep the happy path left

- Handle errors and edge cases first and return; the expected flow reads down
  the left margin:

  ```go
  order, err := s.store.Find(ctx, id)
  if err != nil {
  	return fmt.Errorf("find order %s: %w", id, err)
  }
  if order.Status != StatusPending {
  	return ErrNotCancellable
  }
  if err := s.store.SetStatus(ctx, id, StatusCancelled); err != nil {
  	return fmt.Errorf("cancel order %s: %w", id, err)
  }
  return nil
  ```

- No `else` after a branch that returns, breaks or continues; invert the
  condition instead of nesting. Four levels of indentation is a function
  asking to be split.
- Use `switch` (tagless or on one value) for three or more related branches;
  `if`/`else if` for unrelated conditions. Never `fallthrough` where a
  comma-separated case list says the same thing.

## Declarations and shadowing

- `:=` inside functions by default; `var x T` when the zero value is the
  intended start (`var buf bytes.Buffer`, `var retries int`); `var x T = v`
  when the literal's default type is wrong (`var mask byte = 0x0f`).
- **Shadowing**: `:=` in an inner block declares a *new* variable. Assigning
  an outer variable from an inner block needs `=`:

  ```go
  var client *http.Client
  var err error
  if tracing {
  	client, err = newTracingClient() // `:=` here would shadow both
  } else {
  	client, err = newClient()
  }
  if err != nil {
  	return err
  }
  ```

  Enable govet's `shadow` analyzer; treat its findings on `err` as defects.
- The `if v, err := f(); err != nil {` form is for variables used only inside
  that `if`/`else` chain; do not put unrelated side effects in the init slot.
- Struct literals name their fields (`Order{ID: id, Total: t}`); a
  positional literal stops compiling when a field is added and silently swaps
  values when two fields of the same type are reordered (govet `composites`
  reports unkeyed literals of other packages' struct types).
- Name results only when two or more share a type (`(lat, lng float64, err
  error)` documents the order; gocritic `unnamedResult` asks for it) or when a
  deferred closure must modify them; never a bare `return` in a function that
  returns values.

## Constants and literals

- A literal with meaning (anything but `0` and `1`) is a named constant next
  to the code that owns it — never repeated magic values (`mnd` flags even a
  `2` in `x / 2`; `goconst` flags repeated strings). Tunables (limits, timeouts,
  sizes) come from configuration, not from constants baked into code paths.
- Constants stay **untyped** when they combine with several numeric types;
  they are **typed** when they belong to a domain type (`const
  defaultTimeout = 5 * time.Second` is a `time.Duration`).
- Octal is `0o644`, never `0644`; group long numbers with `_`
  (`1_000_000`); binary masks as `0b1010`.
- `any`, never `interface{}` (`GO-LEGACY-API`).
- Durations are written with unit constants — see
  [runtime-correctness.md](runtime-correctness.md#time).

## Imports

- `goimports` groups standard library, then third-party, then the module's
  own packages, separated by blank lines. Check each import it adds — its
  guess between two packages of the same name (`math/rand/v2` vs
  `crypto/rand`) can be wrong, and for randomness the wrong guess is a
  security bug.
- No dot imports (`import . "pkg"`); alias an import only to resolve a
  collision (`crand "crypto/rand"`).
- No blank import for side effects (driver or codec registration through
  `init`) without a comment naming the side effect; prefer explicit
  registration — see [packages-and-apis.md](packages-and-apis.md#no-init-no-mutable-package-state).

## Suppressions

Do not silence a linter to get a green run; fix the cause. The one sanctioned
exception is a documented limitation of **one** linter on **one** line:

```go
sum := sha1.Sum(content) //nolint:gosec // git object IDs are SHA-1 by definition
```

Each reported line carries its own directive: gosec reports the `crypto/sha1`
import (G505) and the call (G401) separately, so both lines need one.

- `//nolint:<one-linter> // <written reason>` — exactly one linter, never
  `all`, never file- or block-scoped, never without the reason. The
  reference configuration enforces this with `nolintlint`
  (`require-specific: true`, `require-explanation: true`).
- In a project that runs staticcheck or gosec standalone, the equivalent
  single-check forms are `//lint:ignore SA1019 <reason>` and
  `// #nosec G401 -- <reason>`. `//lint:file-ignore`, `//revive:disable`,
  `//exhaustive:ignore` and every blanket or unjustified form are findings.
- Each reported line needs its own directive. A directive covering a whole
  function hides every later finding of that linter inside it — use one only
  when the finding is the declaration itself (`gochecknoinits` on `init`);
  otherwise put it on the one line it justifies.
- The checker enforces this as `GO-SUPPRESS`, which can itself never be
  suppressed. Its own escape for a checked false positive is a separate,
  equally strict pragma — see [lint-clean.md](lint-clean.md#the-skill-checker).
