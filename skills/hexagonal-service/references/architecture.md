# Architecture: hexagonal, module-first

A service is a set of bounded-context **modules**. Inside a module, code is
laid out by layers and assembled at a single composition root. The shape does
not drift between modules. Everything below is language-neutral; file-name
suffixes and DI mechanics are defined by the language/framework skill of the
host project.

## Module shape

```text
modules/<module>/
├── domain/                     # PURE core — no frameworks at all
│   ├── entities/  value-objects/  events/  errors/  constants/  policies/
│   └── ports/
│       ├── in/                 # input ports (use-case contracts) + binding tokens
│       └── out/                # output ports (repositories, clients, publishers)
├── application/
│   ├── dto/                    # plain immutable Input/Result types
│   ├── use-cases/              # input-port implementations
│   └── services/               # orchestration reused by 2+ use cases
├── infrastructure/
│   ├── adapters/
│   │   ├── driving/            # controllers, message handlers, auth gates, error mappers
│   │   └── driven/             # repositories, clients, producers, storage
│   └── persistence/            # ORM models, mappers, persistence constants
├── providers/                  # composition root: factory/binding registrations
├── <module entry>              # DI registration (wires providers)
└── <public barrel/index>       # public surface: input-port tokens + domain types
```

One concept lives in one file; a module exposes a single public entry point
(barrel/`__init__`/index) through which all cross-module imports go.

## The dependency rule — inward only

- `domain` imports **no** framework (web, ORM, DB drivers, brokers, HTTP
  clients, crypto/JWT, loggers, schema validators, cloud SDKs) and no other
  layer.
- `application` does not import `infrastructure` or the composition root;
  where the language allows it, framework base types may appear as
  **type-only** references, never as runtime imports.
- `infrastructure` talks to `application` only through ports; driving and
  driven adapters are siblings and never import each other. The composition
  root is imported only by the module entry.
- **Single boundary exception:** an input port may reference **types** from
  `application/dto` (types only, never use-case implementations).
- Cross-module import goes only through the target module's public barrel,
  which exports input-port tokens and domain types — never use-case classes,
  repositories, DI factories, or the module entry itself.
- Cyclic dependencies are forbidden. Enforce the boundaries with a machine
  import-graph check (dependency-cruiser, import-linter, or equivalent) that
  blocks CI. Never relax a boundary rule to get a green run.

## Ports and binding

- A **port is an interface plus an explicit binding point** (a token, a named
  registration — whatever the stack provides), so there is exactly one
  obvious place where an implementation is attached. Binding identifiers are
  never reused.
- One use case = **one input port with a single `execute()`-style entry**.
  Signatures are expressed in domain types (entities, value objects, branded
  ids), not in transport DTOs or ORM models. An **output port** is phrased in
  domain terms and holds no business logic.

## Use cases and adapters

- A **use case** is a plain class/function with no framework coupling. Its
  constructor (or closure) takes only output ports and application services —
  never a concrete adapter. It throws only domain errors. Infrastructure
  limits (timeouts, retries, page sizes) arrive as parameters from
  configuration via the composition root; a use case never reads config
  itself.
- Assemble use cases in the composition root with a factory whose declared
  type is the **port** (interface), not the concrete class. Bind an output
  port to its implementation once, in the composition root of the owning
  module.
- **Adapters stay thin.** Driving: transport DTO → application DTO → input
  port → response DTO, with validation at the boundary. Driven: implements an
  output port, returns entities/value objects via a mapper, and translates
  infrastructure errors into domain errors (see
  [error-flow.md](error-flow.md)). Business logic in an adapter is a defect.
- **A mapper is the only entity ↔ persistence-model bridge.** A stateless
  `toDomain()` / `toPersistence()` pair is the single translation point;
  passing an entity straight into an ORM model, or leaking a model out of a
  repository, bypasses the boundary.
