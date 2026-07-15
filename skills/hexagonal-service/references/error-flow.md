# Error flow: one wrap in, one map out

Every error crosses the hexagon along exactly one sanctioned path. The two
transformation points are fixed: a foreign error becomes a domain error
**once, at the driven adapter**; a domain error becomes a transport response
**once, at the boundary filter**. Everything in between lets errors bubble
untouched.

## The taxonomy

- **Single root.** Every domain error extends one base
  (`DomainError`/`DomainException`), carries a stable machine-readable `code`
  from the module's error registry, and builds its message through a
  formatter. The domain knows nothing about transport status codes.
- **Raw throws are forbidden in `domain` and `application`.** No
  `throw new Error(...)`, no bare framework/runtime exceptions — only typed
  domain errors from the registry. A new failure mode starts by adding the
  typed error, not by improvising at the call site.

## Where a raw error is allowed to exist

A raw error legitimately appears in exactly one place: **inside a driven
adapter**, where a foreign library (DB driver, HTTP client, broker SDK)
constructs and throws it. That adapter — the source — is the only code that
catches it:

```text
driven adapter (the source):
    try:
        row = driver.query(...)          # foreign code throws its own error
    catch (infraError):
        throw StorageUnavailableError(   # typed domain error, wrapped ONCE
            message = format(...),
            cause   = infraError,        # the original is always preserved
        )
```

- Wrap **exactly once**, at the source, and always preserve the original as
  `cause` (`raise ... from ...` in Python, `{ cause }` in JS/TS) — the full
  chain and stack must survive to the boundary.
- Classify, don't blur: map driver error kinds to distinct domain errors
  (not-found vs conflict vs unavailable), reusing the module's error
  classifier if one exists.

## Between the source and the boundary: hands off

- The wrapped error **bubbles untouched** through use cases, application
  services, and driving adapters.
- **Re-wrapping and catch-and-rethrow in intermediate layers are forbidden** —
  each extra wrap buries the original stack one level deeper and duplicates
  context; that is precisely what destroys the trace.
- An intermediate layer may catch only to **handle** (a real fallback, a
  compensating action) — never to log-and-rethrow, wrap-and-rethrow, or
  "add context" to a passing error. If context is missing, add it at the
  source wrap.
- **Never swallow.** An empty catch is a defect; whatever is caught is either
  genuinely handled or left to bubble.

## The boundary filter: log once, map once

The transport boundary (exception filter, error middleware, handler-of-last-
resort) is the single place where a domain error meets the protocol:

- **Log once, with the stack** — the full error chain including every
  `cause`, plus the correlation/trace id. No other layer logs a passing
  error; one failure produces one ERROR record, not a cascade.
- **Map once** — a per-module table (domain error → transport status) plus a
  global envelope builder. For HTTP, emit RFC 9457 Problem Details
  (`application/problem+json`): `type`/`title`/`status`/`detail`/`instance`
  plus the stable machine `code` and the correlation id.
- **Mask internals**: a `5xx` response never leaks the raw message, payloads,
  or stack; untrusted input and raw external-service responses never enter
  the error body.
- A schema violation at the boundary is a `400`-class failure; a schema-valid
  but domain-invalid request is a `422`-class failure.

## Review heuristics

- `grep` for `catch` in `application/` and `domain/`: each hit must be a real
  handling decision, not a rethrow.
- Any `throw new Error` / bare `raise Exception` outside a driven adapter is
  a violation; inside one it is too — the adapter throws typed wraps.
- One failing request should produce exactly one ERROR log record (at the
  filter) with the complete cause chain visible.
