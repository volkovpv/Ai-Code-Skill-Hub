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

A widely read dialect of this approach is Vieira's **three-hexagon model**
(Domain / Application / Framework "hexagons"), where "hexagon" names a
layer: the Domain hexagon holds entities, value objects, specifications and
domain services and depends on nothing; the Application hexagon holds
use-case contracts and their implementations plus output-port declarations
and controls only data flow — no business rule lives there; the Framework
hexagon holds all adapters and every technology decision. Its dependency
chain (Framework → Application → Domain) is this skill's inward rule, and
its maintainability claim is the selling point of the whole approach: a
business-rule change touches only the domain, a new technology touches only
the framework layer. Mind the vocabulary clash — Vieira also swaps the
names *use case* and *input port*; see the terminology table in
[architecture.md](architecture.md). Domain building blocks for this and any
layered approach are cataloged in [domain-modeling.md](domain-modeling.md).

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

Layered is the *accidental default*: model/repository/service/controller
packages with downward dependencies emerge without anyone choosing an
architecture. Its decoupling is partial — the service layer depends
directly on the data layer, so a persistence change (a database swap, a
lost ORM feature) ripples into business rules. The observable differences
land on two spots: the **driven side** (layered has no output-port
abstraction, so a new data source disturbs core logic; hexagonal adds an
adapter) and **testability** (a rule that needed a running database becomes
a pure unit test on a domain entity). The driving side barely changes — an
input adapter looks much like a REST layer — so judge any "we're hexagonal"
claim by the driven side. Migration from layered is a cataloged strategy:
see "Layered → hexagonal" in [strategies.md](strategies.md).

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

### SOLID

SOLID and the hexagon pursue the same goal at two scales: the pattern
governs the boundary, SOLID governs the code on both sides of it. The
mapping:

- **SRP** — one actor per changeable unit: a class serving two stakeholders
  means fixing one silently breaks the other. Inside the hexagon this
  motivates per-actor behavior implementations; at module scale it *is* the
  bounded context ([domain-modeling.md](domain-modeling.md)). Premature
  abstraction ("a base class for all future implementations") is itself an
  SRP hazard.
- **OCP** — extend the domain by adding implementations of an existing
  abstraction (a new subtype, a new specification), not by editing logic
  that already serves existing features.
- **LSP** — subtypes honoring the supertype contract are what make
  domain-typed port signatures safe: a use case accepts the abstract domain
  type and works with any subtype.
- **ISP** — a driving port carries only the operations its clients actually
  need; a fat interface forcing dummy implementations is split per client.
- **DIP** — the SOLID name for the binding rule: adapters and the
  composition root depend on the port *interface* (the stable contract),
  never on the implementation; the configurator supplies the concrete class.

### Adapter categories

An adapter *category* is the group of adapters enabling one technology (the
REST category, the gRPC category, one per database). Multiple **driving**
categories are cheap — they share the same input ports. Multiple **driven**
categories are the maintainability hazard: each needs its own domain-model
translation, and those multiply per capability. The classic anti-pattern is
the unfinished migration where two driven adapters (old store, new
subsystem) serve the *same* purpose indefinitely, doubling translation
maintenance. Weigh the translation tax consciously before adding a driven
category.

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
design, a steeper learning curve, slower project start, and onboarding —
layered is what most developers already know, the hexagon needs ramp-up
time. They pay off through the test wall (fast in-memory tests, leak
detection), swappable technology, and **postponed technology decisions** —
the design does not have to pick REST vs gRPC or one database vendor before
the core exists, and frameworks stay ordinary libraries instead of the
center of the design. A further payoff at organization scale:
the pattern is a standardization blueprint — services that share the
structure give a developer switching projects a shallow learning curve.

When *not* to use it: a one-off script or a small app doing one or two
things (a hexagon there is a gun brought to kill an ant); a purely
technological problem domain (a framework, a driver) where there is no
business core to protect. A medium-to-large, long-lived, frequently
changing system — especially one expecting infrastructure-level change —
almost always repays the ceremony. And it is not a silver bullet: it cannot
fix debt caused by a team's tolerance for complexity; it only helps teams
already committed to keeping things simple. Whatever is chosen must be
written into the host project's rules — this skill never decides for the
project.
