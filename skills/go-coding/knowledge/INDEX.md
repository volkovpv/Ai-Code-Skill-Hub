# Knowledge index — go-coding

Verified, generalizable knowledge for writing Go to this standard. Read a file
only when its trigger matches the current task; do not preload everything.

| File | Read when |
|------|-----------|
| [patterns.md](patterns.md) | applying a recurring pattern (typed-constant enum with an end marker, sealed interface, id type parsed at the boundary, wrap-once-and-inspect errors, write-path `Close` joined into the result, consumer-owned interface as a test seam, options struct, owned goroutine, bounded fan-out, `os.Root`, HTTP with timeouts, config loaded once, thin `main`) |
| [pitfalls.md](pitfalls.md) | a checker finding looks wrong, or a Go gotcha bites (typed nil errors, `:=` shadowing, subslice `append`, bare-integer durations, `break` in `select`, `defer` in loops, errcheck and `Close`, what a green lint run misses, map writes across goroutines, embedded types leaking methods, security rules in tests) |

Rules for adding knowledge:

- only verified, generalizable statements with an explicit applicability scope;
- every entry links to its evidence (reference, fixture, test, or accepted
  observation);
- do not duplicate the main workflow from SKILL.md;
- files longer than 100 lines must start with a short table of contents.
