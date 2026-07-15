# DI and modules

NestJS provides the container; the architecture decides what may know about
it. The container's reach stops at `providers/` and the adapters — the domain
and the use cases never see a decorator.

## Tokens

- A DI token is a **named `unique symbol`** whose description equals its
  export name, declared next to the port it binds:

  ```ts
  export const CREATE_USER: unique symbol = Symbol('CREATE_USER');
  ```

- `@Inject('createUser')` (string) and `@Inject(Symbol('...'))` (inline) are
  forbidden — both defeat find-usages and invite collisions. Inject only an
  imported token constant: `@Inject(CREATE_USER)`.
- A description string is never reused across tokens.

## Use cases and providers

- A **use case is a plain class**: no `@Injectable()`, no `@Inject()` in its
  constructor, no framework imports. It takes output ports and application
  services as constructor parameters.
- Assembly happens in `providers/` with a factory provider:

  ```ts
  export const useCaseProviders: readonly Provider[] = [
    {
      provide: CREATE_USER,
      useFactory: (users: UserRepositoryPort): CreateUserPort =>
        new CreateUserUseCase(users),
      inject: [USER_REPOSITORY], // order matches the constructor exactly
    },
  ];
  ```

  The factory's declared return type is the **port interface**, never the
  concrete class.
- Bind an output port to its implementation with `useClass` (or a factory)
  once, in the providers of the owning module. Keep provider assembler files
  per kind (use cases, repositories, adapters); an empty one is an explicit
  empty `readonly Provider[]` stub, so the wiring surface is always visible.

## Modules and files

- `<module>.module.ts` only registers providers and imports/exports; it holds
  no logic. The module **exports only input-port tokens** (and domain types
  via the barrel); exporting an output port needs a written justification.
- Cross-module imports go through the target module's public barrel
  (`index.ts`) — never import another module's `*.module.ts`, use cases,
  repositories, or DI factories.
- Bootstrap files (`main.ts`, `app.module.ts`, swagger setup where used) live
  at the service root, outside `modules/`.
- **File suffixes are mandatory and one class lives in one file:**
  `.entity.ts`, `.vo.ts`, `.port.ts`, `.use-case.ts`, `.dto.ts`, `.error.ts`,
  `.controller.ts`, `.guard.ts`, `.filter.ts`, `.interceptor.ts`,
  `.adapter.ts`, `.repository.ts`, `.mapper.ts`, `.model.ts`, `.config.ts`,
  `.module.ts`.

## What the layers may import

- `domain/` — nothing from `@nestjs/*`, no ORM, no validators, no rxjs: the
  pure core (the checker flags this as `NEST-DOMAIN-IMPORT`).
- `application/` — from the framework base package only **type-only** imports
  (`import type { OnApplicationBootstrap } ...`); a runtime `@nestjs/*`
  import in application code is a boundary leak (`NEST-APP-IMPORT`).
- `infrastructure/` and `providers/` — the only layers where NestJS
  decorators, ORM models, and client SDKs live.
