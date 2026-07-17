# The pattern canon: ports and adapters

The official pattern name is **Ports & Adapters**; "Hexagonal Architecture"
is its nickname (the number six means nothing — a system has as many ports
as it needs). Everything here is language-, framework-, and project-neutral;
concrete layouts and mechanics come from the host project's declared
strategy (see [strategies.md](strategies.md)).

## What the pattern requires — the invariant core

These hold in every approach and every strategy; violating any of them means
the system is not ports-and-adapters, whatever the diagrams say:

- The app defines a **provided or required interface for every external
  interaction**: driving ports (provided interfaces, called by driving
  actors) and driven ports (required interfaces, implemented by driven
  actors). The ports define the true boundary of the app and belong to it.
- The app has **no source dependency on any actor or adapter** — all
  compile-time dependencies point inward to the app.
- **Driven actors are configurable at runtime**: the app can be wired to
  production technology, a test double, or an in-memory fake without
  recompiling.
- External actors interact **only through the ports** — nothing reaches
  inside the hexagon directly.
- Port contracts are **technology-neutral**: they use business terms only,
  never transport, storage, or vendor vocabulary.

What is explicitly **outside the pattern**: how you structure the inside of
the app (layers, DDD, use cases, a ball of mud — your choice; see
[approaches.md](approaches.md)), how you organize adapters and folders, and
how you implement the configurator. Those are approach and strategy
decisions — deliberate, recorded in the project rules, but not part of the
pattern.

## The elements

- **App (hexagon, core)** — all the business logic, written only in business
  terms, with no reference to any technology. Anything the team cannot
  change the interface of (database, UI, third-party API, another team's
  subsystem) is outside.
- **Ports** — interaction points grouped by *intention* of the conversation.
  Name each port for its purpose: "for placing orders", "for getting tax
  rates", "for notifying shipment". Common driving kinds: for using the
  system, for administering it, for configuring it. Common driven kinds: for
  getting data from a repository, for notifying a recipient, for controlling
  a device.
- **Actors** — anything with behavior outside the app. A **driving
  (primary)** actor initiates a conversation with the app; a **driven
  (secondary)** actor is called by the app. The same party can be driving in
  one conversation and driven in another; tests are a driving actor, test
  doubles are driven actors.
- **Adapters** — the translation code between an actor's technology and a
  port's contract. A driving adapter (controller, CLI, message consumer,
  GUI) converts technology input into port calls; a driven adapter
  (repository, API client, producer) implements a required interface on top
  of a technology. When an actor already speaks the port's language (a test,
  a matching microservice), no adapter is needed — "interactor" covers both.
- **Configurator (composition root)** — the fifth element, outside the
  pattern but always present: the only code that knows all the players. It
  instantiates the driven interactors, instantiates the app and hands the
  driven interactors to it, then instantiates the driving interactors and
  hands them the app. In tests, the test case is the configurator; in
  production it is `main`, a DI container, or the framework bootstrap.
  Recognized wiring styles: **constructor injection**, **setter injection**
  (swappable at any time), and **dependency lookup** (service locator /
  broker). Which one to use is a strategy choice.

## Port design

- **Boundary placement:** put a port wherever the app meets an external
  system — one whose interface your team can't change — or where your team's
  decision-making authority ends. Make a driven port for the **external
  system, not for a domain concept**: a port represents a conversation with
  the outside, and translating the outside model into the domain model is
  the adapter's job.
- **How many ports:** start with one port per driving actor role and one per
  driven external system; each port carries one intention and one permission
  scope (a sales clerk and a sales manager get different ports). Splitting
  further is allowed but adds complexity fast. Typical systems end with a
  few driving ports and up to a handful of driven ports.
- **Granularity is an approach choice:** intention-level ports bundle
  related operations behind one interface (the book's default); use-case
  level ports give each use case its own single-entry input port (common in
  layered practice). The project rules declare which applies — apply it
  consistently, do not mix ad hoc.
- A **port is an interface plus an explicit binding point** (a token, a
  named registration — whatever the stack provides), so there is exactly one
  obvious place where an implementation is attached. Binding identifiers are
  never reused.
- Signatures are expressed in domain terms (entities, value objects, ids) —
  never transport DTOs, ORM models, or vendor types.

## Symmetry and asymmetry

The pattern is symmetric: inside vs outside, with ports as the boundary —
the database is not "below" the app any more than the UI is "above" it; both
are outside. The implementation is asymmetric: driving actors know the app
to call it; the app knows only the *interfaces* of its driven actors and is
handed the implementations by the configurator. Hence provided interfaces on
the driving side, required interfaces on the driven side.

## The test wall

Every port gets a test driver (driving side) or a test double (driven side).
This is not optional ceremony — the tests are what make the boundary real: a
line on a diagram protects nothing, while a test suite that runs the app
with no production technology attached instantly detects business logic
leaking into adapters or technology details leaking into the core. If the
app cannot be tested without its technologies, it is not a component and the
boundary does not exist.

## Inside the hexagon: use cases and layers

The pattern says nothing about the inside; the following discipline applies
once the project's approach introduces application/domain structure (see
[approaches.md](approaches.md) for the options):

- A **use case** is a plain function/class with no framework coupling. Its
  constructor (or closure) takes only output ports and application services —
  never a concrete adapter. It throws only typed domain errors.
  Infrastructure limits (timeouts, retries, page sizes) arrive as parameters
  from configuration via the composition root; a use case never reads config
  itself.
- Assemble use cases in the composition root with the declared type being
  the **port** (interface), not the concrete class; bind each output port to
  its implementation once.
- **Adapters stay thin.** Driving: transport DTO → application DTO → input
  port → response DTO, with validation at the boundary. Driven: implements
  an output port, returns domain objects via a mapper, and translates
  infrastructure errors into domain errors (see
  [error-flow.md](error-flow.md)). Business logic in an adapter is a defect.
- **A mapper is the only domain ↔ persistence-model bridge.** A stateless
  `toDomain()` / `toPersistence()` pair is the single translation point;
  passing a domain object straight into an ORM model, or leaking a model out
  of a repository, bypasses the boundary.
- Cyclic dependencies are forbidden. Enforce all boundaries with a machine
  import-graph check (dependency-cruiser, import-linter, or equivalent) that
  blocks CI. Never relax a boundary rule to get a green run.
