# Knowledge index — typescript-coding

Verified, generalizable knowledge for writing TypeScript to this standard.
Read a file only when its trigger matches the current task; do not preload
everything.

| File | Read when |
|------|-----------|
| [patterns.md](patterns.md) | applying a recurring typing pattern (registries, branded ids, readonly surfaces, cause-preserving wraps, discriminated unions + `assertUnreachable`, `satisfies` registries, structural test seams, boundary schemas) |
| [pitfalls.md](pitfalls.md) | a checker finding looks wrong, or a `strict`-mode / structural-typing edge case bites (excess-property freshness, `Object.keys`, `filter(Boolean)`, shallow utility types, runtime-visible `private`) |

Rules for adding knowledge:

- only verified, generalizable statements with an explicit applicability scope;
- every entry links to its evidence (reference, fixture, test, or accepted
  observation);
- do not duplicate the main workflow from SKILL.md;
- files longer than 100 lines must start with a short table of contents.
