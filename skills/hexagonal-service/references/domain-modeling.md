# Domain modeling inside the hexagon

The pattern itself does not legislate the inside; once a project's approach
introduces a domain core ([approaches.md](approaches.md)), the following
building blocks and practices keep that core worth protecting. Everything
here is language- and framework-neutral. Design starts before code: seek
business knowledge first — a mistake in the business fundamentals poisons
everything built on top and is expensive to reverse, while a mistake in a
detail is cheap to fix.

## Building blocks

- **Entities carry behavior, not just data.** An entity couples business
  data with the business operations that change it; its mutating methods
  enforce the rules before changing state. A data-only entity (the *anemic
  domain model*) forces the rules to leak into services and adapters — treat
  it as a defect to refactor, not a style.
- **Value objects** are immutable, identity-less types that measure,
  quantify, or describe (money, address, network range, an entity id).
  Validate in the constructor/factory — a value object that exists is valid,
  so no client re-checks it. They are the raw material: build value objects
  first, then entities from them.
- **Identity is generated inside the domain**, never delegated to external
  technology (a database sequence is a technical detail). Provide two
  factory paths: create-new (generates an id) and reconstitute (accepts an
  existing id, used by driven adapters when loading).
- **Aggregates** draw a consistency boundary entered only through the
  aggregate root. Keep aggregates small (typically one root entity plus
  value objects); aggregates reference each other only via root identities.
  Persistence follows the boundary: **one repository-style output port per
  aggregate root**, and every write goes through the root — a sub-entity
  never gets its own persistence operation. Objects are correlated by domain
  identity, never by storage keys: the domain model is imposed on the
  technology, never the reverse.
- **Specifications** encapsulate business predicates as named, combinable
  objects (and/or/not) with a satisfaction check and an enforcing check that
  throws the typed domain error. Entities call specifications inside their
  mutating methods instead of inlining if-else chains; a specification typed
  against a supertype is reusable across entities. Where the language can
  close a type hierarchy, closing the set of legal specifications is a
  useful extra guarantee.
- **Policies** (the strategy pattern in domain clothes) encapsulate a
  swappable domain algorithm as a named object kept separate from entities,
  so algorithm evolution does not churn the entity.
- **Domain services** hold domain behavior that belongs to no single entity
  or value object — typically operations over collections, driven by
  predicates the entities expose. They are stateless and, like everything in
  the domain, **never call outward**: no output port, no application or
  infrastructure code.
- Domain build order that works with the grain: **value objects → entities →
  specifications → domain services**.

## From business knowledge to use cases

- **Ubiquitous language.** Humans disambiguate with context; code cannot.
  Fix one shared vocabulary with the domain experts and use it verbatim in
  type, port, and method names.
- **Subdomains.** Separate the core domain (the primary activities) from
  supporting subdomains (secondary activities enabling the core) and generic
  subdomains (standalone capabilities like authentication that know nothing
  about the others). Blending them yields a mixed-concern model — tolerable
  in a small system, complexity poison in a large one.
- **Bounded contexts.** The same business word may legitimately mean
  different things in different contexts; make each context explicit so the
  meanings don't blur. A bounded context is the single-responsibility
  principle applied at module scale — one reason to change per module — and
  is enforced with the module boundaries of
  [strategies.md](strategies.md), not by a line on a context map.
- **Discovery techniques.** Event Storming (mapping a business process into
  domain events, commands, actors, and aggregates together with the domain
  experts) and a Business Model Canvas are cheap structured ways to acquire
  the business fundamentals before modeling.
- **Write use cases before coding them.** Express each use case first in
  written form — a fully dressed use case (actor, goal, trigger, steps), a
  casual paragraph, or BDD scenarios — then derive the input-port contract
  from the text, and let the same scenarios become the port's executable
  tests. A use case exists to express an actor's intent; some operations are
  *application-specific* (they exist only to support the software's
  automation) — those belong in the application layer, while rules that
  would exist without the software belong in the domain.
- **Keep a short overview document.** A concise map of the system's building
  blocks, written for the next newcomer, beats both no documentation and a
  comprehensive tome nobody maintains.

## Honest costs

Separating domain models from persistence and transport models buys
changeability at the price of translation code — mappers at every port
crossing. The trade is deliberate: you give up reuse of one class for two
purposes in exchange for a core that technology changes cannot reach. If a
problem domain is purely technological (building a framework, a driver, a
codec), a rich domain model — and often the hexagon itself — is the wrong
tool; see "Choosing" in [approaches.md](approaches.md).
