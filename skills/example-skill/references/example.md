# Conventional Commits checklist

Load this file when reviewing a drafted commit message.

## Types

| Type       | Use for                                              |
|------------|------------------------------------------------------|
| `feat`     | new user-visible behaviour                           |
| `fix`      | bug fixes                                            |
| `docs`     | documentation only                                   |
| `test`     | adding or fixing tests only                          |
| `refactor` | code change that is neither a feature nor a fix      |
| `perf`     | performance improvement                              |
| `build`    | build system, dependencies, packaging                |
| `ci`       | CI configuration                                     |
| `chore`    | maintenance that touches no source or test files     |

## Checklist

1. The type matches the *dominant* change in the diff; tests accompanying a
   feature do not turn `feat` into `test`.
2. The scope is a short noun taken from the touched module or directory name;
   omit it when the change is cross-cutting.
3. Subject: imperative mood ("add", not "added"/"adds"), ≤ 72 characters,
   no trailing period.
4. Breaking changes are marked with `!` after the type/scope and explained in
   the body with a `BREAKING CHANGE:` footer.
5. The message describes *what and why*, never *how*.

## Layout notes (for skill authors)

This skill doubles as a structural reference:

- `SKILL.md` — compact, imperative instructions; loaded when the skill fires.
- `references/` — detail loaded on demand (this file).
- `scripts/` — deterministic helpers executed by the agent.
- `assets/` — static files shipped with the skill (empty here).
- `agents/openai.yaml` — vendor-specific adapter, ignored by other harnesses.
- `ORIGIN.yaml` — provenance record, required by library validation.
