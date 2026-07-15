# Testing NestJS code

Universal test hygiene comes from the `typescript-coding` skill; this file
covers only the NestJS-specific seams.

## Unit tests — no container at all

- A use case is a plain class: construct it directly with mocked **ports**
  (`jest.Mocked<UserRepositoryPort>` or the runner's equivalent). No
  `Test.createTestingModule`, no reflection, no container.
- Mock ports (interfaces), never concrete adapters, private methods, or ORM
  models. If a test needs to reach into an implementation, the seam is
  missing — fix the design, not the test.
- Naming: `<subject>.spec.ts` next to unit scope; test titles state behaviour
  and condition (`test_rejects_unknown_user`), even inside `it('...')`.

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
