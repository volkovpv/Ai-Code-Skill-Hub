# Knowledge index — python-coding

Verified, generalizable knowledge for writing Python to this standard.
Read a file only when its trigger matches the current task; do not preload
everything.

| File | Read when |
|------|-----------|
| [patterns.md](patterns.md) | applying a recurring typing pattern (enum/Literal closed sets, NewType ids, frozen dataclasses, tagged unions + `assert_never`, cause-preserving `raise ... from`, Protocol test seams, boundary schemas) |
| [pitfalls.md](pitfalls.md) | a checker finding looks wrong, or a typing/runtime edge case bites (`or`-defaults, mutable default arguments, un-awaited coroutines, `assert` under `-O`, `Any` leaks, unchained raise in `except`) |

Rules for adding knowledge:

- only verified, generalizable statements with an explicit applicability scope;
- every entry links to its evidence (reference, fixture, test, or accepted
  observation);
- do not duplicate the main workflow from SKILL.md;
- files longer than 100 lines must start with a short table of contents.
