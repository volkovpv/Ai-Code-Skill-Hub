# Testing NestJS code

This file covers only the seams NestJS itself provides: the testing module,
the token override, the module graph. Universal test discipline — what a
test must establish, what may be replaced by a double, how a suite stays
honest — is **outside this skill's scope**; the host project's rules decide
it.

## Unit tests — no container at all

- A use case is a plain class assembled by a factory provider, so a test
  constructs it directly: no `Test.createTestingModule`, no reflection, no
  container. That is the whole payoff of keeping DI decorators out of the
  use case — the container is a wiring concern, not a unit-test concern.
- **What stands in for each injected port is the project's call**, not
  NestJS's: the constructor takes port interfaces, so anything satisfying
  them works, and this skill does not decide which of them a given test
  replaces.
- File naming: `<subject>.spec.ts`, alongside the unit it covers.

## Integration tests — override at the token

- Build the module graph with `Test.createTestingModule({ imports: [...] })`
  and substitute at the DI seam:

  ```ts
  const moduleRef = await Test.createTestingModule({ imports: [BillingModule] })
    .overrideProvider(PAYMENT_GATEWAY)   // the unique-symbol token
    .useValue(fakeGateway)
    .compile();
  ```

  Overriding by token is the payoff of tokenized ports — never patch module
  internals or swap classes by name.
- Drive the scenario **through the boundary** (HTTP request to the
  controller, message to the consumer), never by importing a driven adapter
  directly. Scenario order: happy path → input validation → business errors →
  authentication/authorization.
- File naming: `<subject>.integration-spec.ts`.
- Stub the logger provider so assertions stay output-free, and close every
  connection (`app.close()`, pools, brokers) in teardown — a leaked handle
  hangs the runner on shutdown.
- Guards and filters are part of the wiring: integration tests assert the
  error envelope (status, machine code, masked 5xx) and the auth behaviour,
  not just the happy-path body.
