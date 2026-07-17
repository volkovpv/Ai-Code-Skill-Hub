# Security

Framework-neutral rules that keep Python code safe against the attack
classes the language itself makes easy: injection, unsafe deserialization,
path escapes, weak randomness, disabled TLS. Every rule here applies to any
codebase; the skill's checker flags the mechanical subset (`PY-EVAL`,
`PY-SHELL`, `PY-PICKLE`, `PY-YAML-LOAD`, `PY-MKTEMP`, `PY-TLS-NOVERIFY`).
Treat untrusted input as hostile by default: anything from the network, a
file, an environment variable, a queue, or another process.

## Contents

- [Injection: keep data out of code](#injection-keep-data-out-of-code)
- [Deserialization: only data-only formats for untrusted input](#deserialization-only-data-only-formats-for-untrusted-input)
- [Files, paths, and archives](#files-paths-and-archives)
- [Randomness, secrets, and comparison](#randomness-secrets-and-comparison)
- [Password hashing](#password-hashing)
- [TLS](#tls)
- [Regular expressions on untrusted input](#regular-expressions-on-untrusted-input)
- [Secrets hygiene](#secrets-hygiene)

## Injection: keep data out of code

- **SQL: values go through placeholders, never through the string.**
  Parameterized queries send values out-of-band; any f-string, `%`,
  `.format`, or `+` that builds a query from input is an injection:

  ```python
  cur.execute("SELECT * FROM users WHERE email = ?", (email,))   # yes
  cur.execute(f"SELECT * FROM users WHERE email = '{email}'")    # never
  ```

  Identifiers (table/column names) cannot be parameterized — they come from
  a closed allowlist in code, never from input. The same discipline applies
  to every query-like string: LDAP filters, NoSQL queries, search DSLs.
- **Subprocess: pass an argument list, never a shell string.**
  `subprocess.run([exe, *args])` cannot be injected; `shell=True`,
  `os.system`, and `os.popen` hand your string to a shell. If a shell is
  genuinely unavoidable, quote every fragment with `shlex.quote()` — and
  treat that as a smell to remove. Prefer absolute executable paths over
  `PATH` lookup for anything privileged, and give every subprocess call a
  `timeout`.
- **`eval()`/`exec()` never see data.** There is no safe way to run
  attacker-influenced text as Python. Replace dynamic code with data-driven
  structures: a dict of functions, an enum-keyed dispatch, a small parser.
  `ast.literal_eval` is safe against code execution for literal-shaped
  trusted-format input, but is not hardened against malformed-input DoS —
  it is a convenience, not a security boundary.
- **Prefer injection-proof seams over escaping.** Where the toolchain
  offers an API that keeps static text and values structurally separate —
  parameterized queries, DOM-building, and on Python 3.14+ t-string
  (`Template`) processors — use it instead of hand-escaping. Hand-escaping
  belongs only inside such a seam's implementation, in one audited place —
  see [modern-python.md](modern-python.md) for t-strings.

## Deserialization: only data-only formats for untrusted input

- **`pickle` executes arbitrary code by design** — never unpickle data you
  did not produce and store yourself; the same holds for `shelve` and
  `marshal`. For interchange use a data-only format (JSON, msgpack-style)
  plus explicit validation — see the trust-boundary rules in
  [type-design.md](type-design.md).
- **YAML: `yaml.safe_load` only.** `yaml.load`, `yaml.full_load`, and
  `yaml.unsafe_load` can instantiate arbitrary objects from the document.
  There is no reason to ever use them on config or input files.
- **XML from untrusted sources is an attack surface** (entity-expansion
  DoS, external entities). Parse it with a hardened parser (the
  `defusedxml` approach) or avoid XML at the boundary; the stdlib parsers
  are documented as not secure against malicious data.

## Files, paths, and archives

- **Path traversal: resolve, then containment-check.** Any path built from
  input must be proven to stay inside its base directory:

  ```python
  base = Path(root).resolve()
  target = (base / user_supplied).resolve()
  if not target.is_relative_to(base):
      raise PathEscapeError(user_supplied)
  ```

  String checks (`startswith`) are broken by `..`, prefix collisions, and
  symlinks. When serving or extracting a tree, reject symlinks that point
  outside it.
- **Temporary files: `tempfile.mkstemp` / `NamedTemporaryFile` /
  `TemporaryDirectory`.** `tempfile.mktemp` only invents a name — the gap
  between naming and creating is a classic race; it is banned. Never
  hand-build paths under `/tmp`.
- **Archives: extract with an explicit safety filter and a budget.** Pass
  `filter="data"` explicitly to `TarFile.extract`/`extractall` (PEP 706;
  the default only became safe in 3.14 — the explicit argument keeps
  behaviour identical across versions). Filters do not stop decompression
  bombs: budget total size and entry count when the archive is untrusted.
  For zip files, validate member names the same way as any untrusted path.

## Randomness, secrets, and comparison

- **`secrets`, not `random`, for anything security-relevant** — tokens,
  reset codes, salts, session ids: `secrets.token_urlsafe()`,
  `secrets.token_bytes()`, `secrets.choice()`. The `random` module is
  deterministic and predictable by construction. (For time-sortable
  non-secret identifiers, `uuid.uuid7()` on 3.14+ — see
  [modern-python.md](modern-python.md).)
- **Compare secrets in constant time**: `hmac.compare_digest(a, b)` for
  MACs, tokens, and signatures — `==` leaks timing. A plain `==` on a
  secret is a defect even when the measurable difference seems negligible.

## Password hashing

- Use a **memory-hard password hash**: Argon2id via a maintained
  implementation where third-party dependencies are acceptable; otherwise
  the stdlib `hashlib.scrypt` (calibrate its cost parameters to current
  OWASP guidance). PBKDF2 only under FIPS constraints.
- A general-purpose digest (`sha256`, `md5`) over a password is a defect,
  salted or not. For non-security digests (cache keys, dedup), state it:
  `hashlib.md5(data, usedforsecurity=False)`.

## TLS

- **Never disable verification.** `verify=False`,
  `check_hostname = False`, `CERT_NONE`, and
  `ssl._create_unverified_context()` are banned in shipped code paths; a
  broken corporate or staging certificate is fixed in the trust store, not
  by turning verification off.
- Build contexts with **`ssl.create_default_context()`** — a hand-rolled
  `SSLContext` misses the secure defaults (and 3.13+ default contexts
  validate strictly per RFC 5280; fix the certificate rather than un-set
  `VERIFY_X509_STRICT`).

## Regular expressions on untrusted input

Python's `re` is a backtracking engine with no timeout: a crafted input
against a pattern with nested or overlapping quantifiers (`(a+)+`,
`(\w+\s?)*`) can run for minutes (ReDoS). On untrusted input: keep patterns
anchored and linear, bound every repetition (`{0,256}` instead of `*`),
limit input length before matching, and for hostile input at scale use a
linear-time engine. Treat every regex that faces the network as code
review-worthy attack surface.

## Secrets hygiene

- Secrets come only from the environment or a secret store — never
  hardcoded, never committed, never logged; see
  [errors-config-logging.md](errors-config-logging.md) for the config and
  logging side.
- Keep secrets out of `repr` and error messages: `field(repr=False)` on
  dataclass secret fields, redaction where objects are dumped. An exception
  message that embeds a connection string leaks it to every log sink.
- Tests use obviously fake values (the vendor-documented example
  credentials), never real ones.
