# Security

Framework-neutral rules against the attack classes Go code meets most:
injection, path escapes, weak randomness, disabled TLS, unbounded input and
servers without timeouts. Treat anything from the network, a file, the
environment, a queue or another process as hostile until validated. The
checker flags the mechanical subset (`GO-SQL-FMT`, `GO-SHELL`,
`GO-TLS-INSECURE`, `GO-HTTP-TIMEOUT`); gosec in the reference lint config
catches more — but not everything (see
[lint-clean.md](lint-clean.md#what-the-stack-does-not-catch)).

## Contents

- [A defensive routine over untrusted input has one home, the union of every caller's cases](#a-defensive-routine-over-untrusted-input-has-one-home-the-union-of-every-callers-cases)
- [A filter guarding an input a downstream parser also normalizes decides with that parser's own normalization](#a-filter-guarding-an-input-a-downstream-parser-also-normalizes-decides-with-that-parsers-own-normalization)
- [Injection: keep data out of code](#injection-keep-data-out-of-code)
- [Files and paths](#files-and-paths)
- [Randomness, secrets, comparison, passwords](#randomness-secrets-comparison-passwords)
- [TLS](#tls)
- [HTTP servers and clients](#http-servers-and-clients)
- [Decoding untrusted input](#decoding-untrusted-input)
- [Bound everything the input sizes](#bound-everything-the-input-sizes)
- [Secrets hygiene](#secrets-hygiene)
- [Unsafe code and dependencies](#unsafe-code-and-dependencies)

## A defensive routine over untrusted input has one home, the union of every caller's cases

A parser or validator standing over untrusted input — a request body, an
external API's or model's output, file content — lives in **one** place. When
each caller keeps its own copy, each copy covers only the cases its author
anticipated; an input shape only one caller has seen is unguarded in every
other copy, and a fix made against one caller's bug report never reaches the
siblings. Give the routine one home and make its cases the **union of every
caller's cases** — malformed, truncated and adversarial included — never one
caller's slice of the input space.

## A filter guarding an input a downstream parser also normalizes decides with that parser's own normalization

When a security filter sits in front of a component that parses and
normalizes the same input, the filter's comparison must **be** that
component's normalization (or be proven equivalent to it). Otherwise the two
disagree, and an input in the gap passes the filter and still reaches the
parser in the shape it trusts:

```go
var denied = map[string]bool{"x-internal-token": true} // the filter's own spelling

for name := range r.Header { // net/http already canonicalized: "X-Internal-Token"
	if denied[name] {          // never matches: the header sails through
		r.Header.Del(name)
	}
}
```

Decide with the downstream rule itself: key the set and the lookup by
`http.CanonicalHeaderKey(name)` (the function `net/http` applies). The same
shape recurs wherever one component gates a namespace another normalizes: a
path prefix check before a handler that runs `path.Clean` (`/public/../admin`
passes `strings.HasPrefix(p, "/admin")`), a host allowlist compared as a raw
string before `url.Parse`/`net/netip` normalization, file extensions before
case folding. Never hand-roll a second comparison that is supposed to track a
parser's rules — it is a gap with a name.

## Injection: keep data out of code

- **SQL: values go through placeholders, never into the query text.**

  ```go
  row := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE email = $1", email) // yes
  q := fmt.Sprintf("SELECT id FROM users WHERE email = '%s'", email)                   // never
  ```

  Placeholders are `$1` (PostgreSQL) or `?` (MySQL, SQLite) per driver.
  Identifiers (table or column names, `ORDER BY` direction) cannot be
  parameterized: map them from a closed allowlist in code, never from input.
  The checker flags SQL text built with `fmt.Sprintf` or `+` as `GO-SQL-FMT`.
  gosec (G201/G202) reports the "build into a variable, then call" shape in
  an assignment but not a `fmt.Sprintf` passed inline as the query argument
  nor `return db.QueryContext(ctx, q)` — a green gosec run does not clear
  string-built SQL.
- **Commands: a program and an argument list, never a shell.**

  ```go
  cmd := exec.CommandContext(ctx, "git", "log", "--oneline", "--end-of-options", rev) //nolint:gosec // G204: one argv element, no shell
  ```

  `exec.Command("sh", "-c", line)` hands the string to a shell (checker
  `GO-SHELL`). gosec G204 fires on *any* variable argument, the safe argv
  form above included, so under the reference linters the line carries a
  justified `//nolint:gosec` naming the argv discipline — never on a line
  that builds a shell string. Stop option parsing before an untrusted
  argument so a value starting with `-` cannot become a flag — and check what
  the tool's terminator means: for most programs it is `--`, but for `git`
  everything after `--` is a *path*, so a revision goes after
  `--end-of-options`. Prefer an absolute path or a vetted `exec.LookPath`
  result for privileged binaries; use `CommandContext` so the process dies
  with the context.
- **HTML: `html/template`, never `text/template`**, for anything a browser
  renders; it escapes by context. Never convert untrusted input to
  `template.HTML`, `template.JS` or `template.URL` — that switches the
  escaping off. Templates themselves are code: never parse a template from
  untrusted input.
- The same discipline covers every query-like string: LDAP filters, search
  DSLs, NoSQL queries, log lines consumed by parsers.

## Files and paths

- A file name from input is opened through **`os.Root`** — it refuses any
  path that resolves outside the root, symbolic links included:

  ```go
  root, err := os.OpenRoot(uploadsDir)
  if err != nil {
  	return fmt.Errorf("open uploads: %w", err)
  }
  defer func() { _ = root.Close() }()
  f, err := root.Open(name) // "../etc/passwd" and escaping symlinks are rejected
  ```

  `os.OpenInRoot(dir, name)` is the one-shot form; `filepath.IsLocal(name)`
  validates a name without opening it. Never `filepath.Join` plus a
  `strings.HasPrefix` check — `..`, prefix collisions (`/data` vs
  `/data-old`) and symlinks defeat it. `http.FileServerFS` over
  `root.FS()` serves a confined tree.
- Archive extraction (zip, tar) writes every entry through an `os.Root` and
  budgets total size and entry count (decompression bombs); an entry name
  with `..` or an absolute path is rejected, not cleaned.
- gosec G304 flags every file opened through a variable path. For a path the
  operator controls (a flag, a configuration value), `filepath.Clean(path)`
  satisfies it — that is lint hygiene, not containment; a name from untrusted
  input goes through `os.Root`, which gosec accepts.
- Temporary files and directories come from `os.CreateTemp` / `os.MkdirTemp`
  (or `t.TempDir()` in tests) — never a hand-built name under `/tmp`.
- New files get the narrowest mode that works (`0o600` for secrets).

## Randomness, secrets, comparison, passwords

- Anything an attacker must not predict — tokens, session ids, reset codes,
  keys, salts — comes from **`crypto/rand`**: `rand.Text()` (Go 1.24) for a
  URL-safe token, `rand.Read` for bytes. `math/rand/v2` is for simulations,
  sampling and jitter only (gosec G404 flags every use; hold the non-security
  ones with `//nolint:gosec // jitter, not security`). Identifiers that must
  merely be unique: `uuid.New()` / `uuid.NewV7()` (Go 1.27).
- Compare secrets (tokens, MACs, API keys) in constant time:
  `subtle.ConstantTimeCompare([]byte(got), []byte(want)) == 1` or
  `hmac.Equal`. A plain `==` leaks timing.
- Passwords are stored with a memory-hard hash — argon2id
  (`golang.org/x/crypto/argon2`) or bcrypt / scrypt — never a general digest
  (`sha256`, `md5`), salted or not.
- Use the standard `crypto/...` packages; never implement a primitive
  yourself.

## TLS

- **Never disable verification** — `InsecureSkipVerify: true` is banned in
  shipped code and in tests (checker `GO-TLS-INSECURE`, gosec G402); a test
  talks to `httptest.NewTLSServer` through its `srv.Client()`, which already
  trusts the test certificate. A private or staging CA is added to the trust
  instead:

  ```go
  pool := x509.NewCertPool()
  if !pool.AppendCertsFromPEM(caPEM) {
  	return nil, errors.New("tls: no CA certificates in bundle")
  }
  cfg := &tls.Config{RootCAs: pool}
  ```

- Keep the default `tls.Config` minimum version and cipher suites; never
  lower `MinVersion` below TLS 1.2 (also `GO-TLS-INSECURE`). The standard
  library enables post-quantum hybrid key exchange by default — do not pin
  `CurvePreferences` without a reason.

## HTTP servers and clients

- A server is an `http.Server` on its own `http.NewServeMux()`, with
  timeouts — never `http.ListenAndServe` (no timeouts possible) and never the
  global `DefaultServeMux` (any imported package can register handlers on it):

  ```go
  srv := &http.Server{
  	Addr:              addr,
  	Handler:           mux,
  	ReadHeaderTimeout: 5 * time.Second,
  	ReadTimeout:       30 * time.Second,
  	WriteTimeout:      30 * time.Second,
  	IdleTimeout:       2 * time.Minute,
  }
  ```

  Streaming handlers extend their own deadlines per request with
  `http.ResponseController`.
- The server stops when the root context ends, gracefully, and
  `http.ErrServerClosed` — what `ListenAndServe` returns after `Shutdown` — is
  the normal outcome, not a failure:

  ```go
  func Serve(ctx context.Context, srv *http.Server) error {
  	errc := make(chan error, 1)
  	go func() { errc <- srv.ListenAndServe() }()
  	select {
  	case err := <-errc:
  		return fmt.Errorf("serve: %w", err)
  	case <-ctx.Done():
  	}
  	shutdownCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), shutdownTimeout)
  	defer cancel()
  	if err := srv.Shutdown(shutdownCtx); err != nil {
  		return fmt.Errorf("shutdown: %w", err)
  	}
  	if err := <-errc; !errors.Is(err, http.ErrServerClosed) {
  		return fmt.Errorf("serve: %w", err)
  	}
  	return nil
  }
  ```
- Cap request bodies with `http.MaxBytesReader(w, r.Body, limit)`; the
  server's `MaxHeaderBytes` and (Go 1.27) `MaxHeaderValueCount` bound headers.
- State-changing endpoints reached by browsers are wrapped in
  `http.CrossOriginProtection` (Go 1.25) or the project's CSRF defence.
- A client is one shared `*http.Client` with a `Timeout` (it is safe for
  concurrent use), and every request is built with
  `http.NewRequestWithContext` — never `http.Get`/`http.Post` or
  `http.DefaultClient`, which have no timeout (checker `GO-HTTP-TIMEOUT`,
  linter `noctx`).
- Always close `resp.Body`, check `resp.StatusCode` before decoding, and read
  the body through `io.LimitReader`.
- Outbound requests to URLs that come from input (webhooks, fetchers) are an
  SSRF surface: parse and allowlist the scheme and host, and refuse private,
  loopback and link-local addresses at dial time (a `net.Dialer` `Control`
  function checking the resolved `netip.Addr`), not only on the name.
- `net/http/pprof` is served on a private listener, never on the public mux
  (its blank import registers on `DefaultServeMux`).

## Decoding untrusted input

- Limit the size before decoding (`http.MaxBytesReader`, `io.LimitReader`).
- Decode into typed structs, then validate into domain types — see
  [type-design.md](type-design.md#boundary-data-decode-into-types-then-validate).
- JSON: use the package the module already uses. `encoding/json/v2`
  (Go 1.27) rejects duplicate object names, invalid UTF-8 and trailing data by
  default — the better choice for a module that has no JSON package yet or
  migrates deliberately; add `json.RejectUnknownMembers(true)` where the
  contract is closed (v1: `Decoder.DisallowUnknownFields()`). A v1
  `json.Decoder` stops after the first value and ignores what follows —
  check `dec.More()` (or that a second `Decode` returns `io.EOF`) when the body
  must hold exactly one value.
- `encoding/gob` is for trusted peers only; never decode gob, or anything
  that instantiates arbitrary types, from untrusted input.
- `encoding/xml` does not resolve external entities, but still bound size and
  nesting.
- `regexp` is RE2 — linear time, no catastrophic backtracking — yet still cap
  the input length before matching.

## Bound everything the input sizes

- A count, length, page size or offset taken from input is range-checked
  before it drives `make`, a loop or an allocation: a negative value panics,
  a huge one is an out-of-memory kill. Fuzz every parser of untrusted data.
- Integer conversions from input check the range first — narrowing
  `int64 → int32` or signed/unsigned conversions wrap silently (gosec G115).
- Decompression, recursion depth and fan-out driven by input all get budgets.

## Secrets hygiene

- Secrets come from the environment or a secret store, parsed once in the
  configuration package; never hardcoded, never committed, never logged.
- Types that hold secrets redact themselves in logs and formatting
  (`slog.LogValuer`, `String()`), and error messages never carry secret
  values — including through a wrapped cause that echoes its input (see
  [errors-config-logging.md](errors-config-logging.md#a-wrapped-cause-that-echoes-its-input-is-a-disclosure-channel)).
- Tests use obviously fake values (vendor-documented example credentials),
  never real ones.

## Unsafe code and dependencies

- No `unsafe` or `reflect` to reach unexported fields of other packages; no
  `//go:linkname` to runtime internals. `unsafe` and cgo need a measured
  reason, a small boundary and a comment.
- Run `govulncheck ./...` in CI and before releases; fix reachable findings
  with the smallest upgrade that includes the fix.
- Keep the module proxy and checksum database on; set `GOPRIVATE` for private
  modules instead of disabling verification.
