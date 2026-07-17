# Adoption strategies — declared by the project, never by this skill

An approach ([approaches.md](approaches.md)) says how the hexagon is
structured conceptually; a **strategy** says how it lands in a concrete
repository: directory layout, port granularity, wiring mechanics, rollout
order. The pattern legislates none of this, so the choice must be made
once, deliberately, and recorded in the rules of the host project. This
file is the catalog to choose from.

**Resolution order when working in a project:**

1. The project's rules declare a strategy → follow it exactly.
2. No declaration, but the code has a consistent de-facto layout → follow
   the code and propose recording the strategy in the project rules.
3. Greenfield with no declaration → propose a strategy from this catalog
   (with a recommendation), get it recorded, then build.

Never invent a private layout, and never mix strategies within one service.

## Code layout strategies

### Module-first

The repository is a set of bounded-context modules; each module is its own
small hexagon with internal layers and a single composition root. Cross-
module imports go only through a module's public surface (barrel /
`__init__` / index), which exports input-port bindings and domain types —
never use-case classes, repositories, or DI internals. Scales well when one
service hosts several business areas. A typical module shape (illustrative —
names and mechanics per language/framework skill):

```text
modules/<module>/
├── domain/                     # pure core: entities, value objects, events,
│   │                           #   errors, policies
│   └── ports/
│       ├── in/                 # input ports + binding points
│       └── out/                # output ports (repositories, clients, …)
├── application/
│   ├── dto/                    # plain immutable Input/Result types
│   ├── use-cases/              # input-port implementations
│   └── services/               # orchestration reused by 2+ use cases
├── infrastructure/
│   ├── adapters/driving/       # controllers, handlers, error mappers
│   ├── adapters/driven/        # repositories, clients, producers
│   └── persistence/            # storage models + mappers
├── <composition root>          # factories, port→implementation bindings
└── <public surface>            # the only cross-module import point
```

### Layer-first

Top-level directories are the layers (`domain/`, `application/`,
`infrastructure/`), with business areas as subfolders inside each layer.
Simple to explain and fine for services with one dominant business area;
degrades as areas multiply, because one feature's code is scattered across
all layers and module boundaries have no directory expression.

### Domain-first (feature slices)

Top-level directories are business capabilities; each slice carries its own
ports, use cases, and adapters, and shared kernel code is minimal and
explicit. Optimizes for feature locality and team ownership; requires
discipline (ideally a machine check) to keep slices from importing each
other's internals, since no layer skeleton enforces it.

### Ports-first (the book's literal layout)

Folders mirror the pattern elements directly: one space for the app plus
`driving-ports/` and `driven-ports/` (in declaration-requiring languages),
and outside it `driving-adapters/` and `driven-adapters/`, one subfolder per
adapter, plus the test folder. Closest to the canon, minimal vocabulary;
best for small services and for teaching the pattern. Set the folders up
**before writing any code** — with the skeleton in place it is obvious where
everything goes.

### Hexagon-per-service

In a multi-service system, each deployable is one hexagon; ports sit at
network boundaries and each service picks its own internal layout (any of
the above). The rule that survives aggregation: hexagons do not nest — a
service is one hexagon, not a hexagon of hexagons.

## Rollout (build-order) strategies

### Walking skeleton (outside-in)

Stand the architecture up before the logic. The canonical sequence —
folders first, then: **test-to-test** (a test drives the app returning a
constant through the first driving port, then through a driven-port test
double — at this point the architecture exists), **real-to-test** (add the
production driver against the double), **test-to-real** (connect the real
driven technology), **real-to-real** (wire production end to end). Steps 2–3
may swap. Connecting real technologies early de-risks integration and sets
up the delivery pipeline from day one.

### Inside-out (domain-first build)

Implement the whole core against test doubles first, connect real
technologies at the end. Maximizes focus on the domain and suits well-
understood integrations; defers integration risk, so reserve it for known
technology stacks. The per-feature recipe in
[checklist.md](checklist.md) is the inside-out order applied at feature
scale.

## Migration strategies (existing systems)

- **Test-wall-first:** before restructuring anything, put characterization
  tests around the code you intend to make the app; the boundary becomes
  real only when tests enforce it.
- **Seam extraction:** at every place the logic touches a technology,
  introduce a required interface (a driven port) and move the technology
  code behind it as an adapter, one seam at a time; the composition root
  grows as seams accumulate. The core shrinks toward purity without a
  rewrite.
- **Strangler fig:** stand up a new hexagonal service (or module) next to
  the legacy one, route one capability at a time through the new hexagon,
  retire legacy paths as they empty. Combine with an ACL-style driven
  adapter to talk to the legacy system during the transition.

## What the project rules must declare

A project adopting this skill records, in its own rules:

- the **approach** (two-layer, layered, +DDD, …) and the **layout strategy**
  (module-first, layer-first, domain-first, ports-first);
- **port granularity** (per actor intention vs per use case) and naming
  conventions for ports and bindings;
- **wiring mechanics**: constructor/setter injection or lookup, the DI
  container if any, and where composition roots live;
- where the **error-mapping table** and boundary filter live
  ([error-flow.md](error-flow.md) defines the flow, the project fixes the
  place);
- the **machine boundary check** (import-graph tool and its config) that
  enforces the declared layout in CI.

Anything a project leaves undeclared falls back to the invariant core of
[architecture.md](architecture.md) — never to a layout guess.
