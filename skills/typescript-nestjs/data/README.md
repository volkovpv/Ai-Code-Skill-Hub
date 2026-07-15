# Data contract — typescript-nestjs

- **Purpose**: reproducible TypeScript inputs for the NestJS convention
  checker (`scripts/check_nest_conventions.py`). The directory layout of
  `fixtures/sample-module/` is part of the data: the checker detects layers
  from path segments (`domain/`, `application/`, `infrastructure/`).
- **Source / generation**: hand-written synthetic TypeScript; no real project
  code. Regenerate by editing the files directly.
- **License**: MIT (same as the skill; see ORIGIN.yaml).
- **Format**: `.ts` source files laid out as a miniature hexagonal module.
- **Allowed use**: input for the checker in tests and demos. The data never
  overrides the agent's own judgement about real code.
- **PII / secrets**: none — every identifier, path, and value is invented;
  the library's secret scan runs over this directory on every validation.
- **Update procedure**: edit → `skillctl validate typescript-nestjs` →
  `skillctl test typescript-nestjs` → bump `version` in skills.yaml.
- **Size limits**: each file stays far below the default
  `content_policy.max_tracked_file_bytes` (256 KiB).

Layout convention (`fixtures/sample-module/`, test-only, **not** installed in
runtime mode):

- `domain/user.entity.ts` — clean pure domain: zero findings;
- `domain/bad.entity.ts` — `NEST-DOMAIN-IMPORT` (a `@nestjs/common` import)
  and `NEST-RAW-THROW` (a raw `throw new Error`), exactly once each;
- `application/clean.use-case.ts` — type-only framework import and a typed
  domain error: zero findings;
- `application/bad.use-case.ts` — `NEST-APP-IMPORT` (runtime `@nestjs/common`
  import) and `NEST-DI-TOKEN` (string token), exactly once each;
- `infrastructure/user.repository.ts` — `NEST-DI-TOKEN` (inline `Symbol()`)
  exactly once; its raw `throw` is deliberately NOT flagged — the layer rule
  does not apply to infrastructure, pinning the layer-difference behaviour.
