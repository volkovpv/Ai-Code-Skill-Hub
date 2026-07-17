# Approaches to hexagonal architecture

The pattern fixes only the boundary: an inside (the app) and an outside
(everything else), separated by ports. Everything about the *inside* is an
approach choice. This file maps the recognized approaches and how the
pattern relates to neighboring architectures, so a project can pick
deliberately — the pick itself is recorded in the project rules (see
[strategies.md](strategies.md)).

## Structuring the inside

### Strict two-layer (classic Cockburn)

The app is one undivided core: business logic written in business terms,
ports declared at its edge, and no prescribed internal structure. Layers,
DDD, functional or OO design inside are all "not the pattern's job". Best
for small services and for teams that want the minimum ceremony that still
yields the test wall and swappable technology. The invariant core
([architecture.md](architecture.md)) is the entire rulebook.

### Layered hexagonal (domain → application → infrastructure)

The common industry refinement: the inside splits into a **domain** core
(entities, value objects, domain events, domain errors, policies) and an
**application** ring (use cases, orchestration, application DTOs); the
outside is the **infrastructure** (driving and driven adapters) plus the
composition root. Dependency rule inside the hexagon: `domain` imports no
framework and no other layer; `application` imports `domain` but never
`infrastructure`. Ports live with the inside (input ports fronting use
cases, output ports phrased in domain terms). This approach adds discipline
useful in medium-to-large codebases at the cost of more indirection.

### Onion / clean refinements

Onion architecture and clean architecture prescribe concentric rings inside
the app (entities → use cases → interface adapters, dependencies pointing
inward). They are compatible refinements of the hexagon's inside, not
competitors: ports-and-adapters specifies only two layers (inside/outside)
and how the outside connects (ports); onion/clean additionally legislate the
internal rings. A project may adopt "hexagonal boundary + clean-style
inside" — then both rulebooks apply, each on its own turf.

### Traditional layered (n-tier) — what the pattern rejects

A layered architecture stacks UI above business logic above the database, so
the core depends on the persistence below it. Ports-and-adapters flips this:
the database is not "at the bottom" but **outside**, exactly like the UI —
the core has zero compile-time dependencies on either. If a diagram shows
the domain importing a repository implementation, it is n-tier with extra
hexagons drawn on it.

## Relations to neighboring concepts

### Use cases

Use-case modeling and ports-and-adapters align one-to-one: the system under
design is the app, primary actors are driving actors, secondary actors are
driven actors. A good starting port inventory is one port per actor,
named for the intention of that actor's conversation. Adapters do not appear
in use cases at all — which is exactly the neutrality the app must keep.

### Domain-driven design

DDD and ports-and-adapters are independent and compose well: the hexagon
evicts all technology from the inside, giving DDD the clean bounded context
it needs. Key clarifications from the canon:

- A **bounded context is not automatically a hexagon**. It becomes one only
  when it owns both its provided and required interfaces and has tests at
  every port; a line on a context map protects nothing.
- An **anti-corruption layer is an adapter only sometimes**. When the
  bounded context is a real component (ports + tests), the ACL translating
  a foreign model sits outside as a driven adapter. Without ports and tests,
  the ACL is just part of the system.
- Make a **driven port per external system, not per domain concept** —
  abstracting a domain concept behind a "port" while the real external
  conversation leaks elsewhere is the classic DDD-flavored mistake.

### CQRS

CQRS separates the command and query sides; each side *may* be built as its
own ports-and-adapters app (decoupled from driving/driven technologies), but
nothing in CQRS forces that, and a CQRS system as a whole (with its UIs and
repositories) is not itself a hexagon. Treat CQRS as a way to use hexagons
in a larger system, not as an instance of the pattern.

### Component + Strategy and nested hexagons

Ports-and-adapters is a special case of the general Component + Strategy
pattern: a component with declared provided/required interfaces, configured
by passing in strategy objects, with tests making the boundary real. The
general pattern lets you draw a tested boundary anywhere — including
components within components. The hexagonal special case pins the boundary
to **external technology / team-authority edges**, and therefore **does not
nest**: one hexagon per app. If you need protected subsystems inside a
larger system, model each as its own component (or its own hexagon at its
own technology edge, e.g. per microservice), not as hexagons-within-a-
hexagon.

## Choosing

| Situation | Reasonable approach |
|-----------|---------------------|
| Small service, small team, minimum ceremony | Strict two-layer |
| Medium/large service, several people touching the core | Layered hexagonal |
| Rich domain, invariants worth modeling explicitly | Layered hexagonal + DDD inside |
| Read/write loads diverge sharply | CQRS with a hexagon per side |
| Many subsystems owned by many teams | One hexagon per subsystem at each team's authority edge |

The costs are real: extra interfaces and indirection, a configurator to
design, a steeper learning curve, slower project start. They pay off through
the test wall (fast in-memory tests, leak detection), swappable technology,
and delayed technology decisions. A one-off script does not need a hexagon;
a long-running system almost always does. Whatever is chosen must be written
into the host project's rules — this skill never decides for the project.
