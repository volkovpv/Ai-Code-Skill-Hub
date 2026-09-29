#!/usr/bin/env python3
"""Heuristic convention checker for Go source (stdlib-only, offline).

Scan ``.go`` files (or stdin) for a curated set of high-signal, framework-
and architecture-neutral coding-standard violations and print one line per
finding::

    <path>:<line>: <CODE> <message>

Usage::

    python scripts/check_go_conventions.py ./internal/          # walk a directory
    python scripts/check_go_conventions.py a.go b_test.go       # explicit files
    cat snippet.go | python scripts/check_go_conventions.py     # stdin (label <stdin>)

Exit codes: ``0`` no findings, ``1`` findings printed, ``2`` an IO error or a
malformed/forbidden suppression pragma (fail-closed).

Masking model
-------------

A lexical scanner separates code, comments, and literal content before any
rule runs:

* text inside interpreted strings (``"..."``), raw strings (`` `...` ``,
  which may span lines) and rune literals (``'...'``) never produces a
  finding from a code rule — quoting a rule (e.g. in a message) is not a
  violation;
* ``//`` line comments and ``/* ... */`` block comments are moved to a
  separate comment view; ``GO-SUPPRESS`` looks only there, because
  ``//nolint`` / ``//lint:ignore`` / ``#nosec`` live in comments. A
  line-scoped ``//nolint:<linter> // <reason>`` naming exactly one linter
  (never ``all``) with a non-empty reason — or the single-check
  ``//lint:ignore <CHECK> <reason>`` and ``#nosec <RULE> -- <reason>`` forms —
  is not reported; every blanket, multi-linter, unjustified or file-wide form
  is still a finding;
* a few rules must read literal text (an import path, a shell name passed to
  ``exec.Command``, SQL text handed to ``fmt.Sprintf``); they match the raw
  line but only count when the match is anchored in code (or, for the
  string-anchored SQL concatenation form, in a string literal), so the same
  text inside a comment stays silent.

Files carrying the standard ``// Code generated ... DO NOT EDIT.`` header are
skipped entirely, and directory walks skip ``vendor/``, ``testdata/`` and
hidden directories, as the Go tool does.

Contexts relax exactly what the reference lint configuration also allows:
``package main`` may call ``os.Exit`` and create the root context; test files
may *read* the environment (gating integration tests); configuration files
may access the environment. The context of a file is decided by its path
relative to the nearest ``go.mod`` — directories above the module never count.

The scanner is line-oriented lexical analysis, not a Go parser: a construct
split across lines is seen line by line, and the project's compiler,
``go vet`` and linter remain authoritative. Treat every finding as a prompt to
look, not a verdict.

Suppression contract (strict, fail-closed)
------------------------------------------

    // skill-check-ignore: GO-ENV -- reason this line is a checked false positive

* only specific, known rule codes may be suppressed (comma-separated for
  several) — there is no "suppress everything" form;
* the justification after ``--`` is mandatory and must be non-empty;
* a bare ``skill-check-ignore``, an unknown code, or any malformed pragma
  aborts the whole check with exit code ``2``;
* ``GO-SUPPRESS`` itself can never be suppressed;
* the pragma only counts inside a comment: a pragma-looking string literal
  neither suppresses nor errors, and never bypasses a finding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

GO_SUFFIXES = (".go",)

# --- Context ---------------------------------------------------------------

_TEST_DIRS = ("/test/", "/tests/", "/testdata/", "/__test__/", "/__tests__/")
_CONFIG_DIRS = ("/config/", "/settings/")


def _normalized(path: str) -> tuple[str, str]:
    """Return ``(path, basename)`` lower-cased, forward-slashed, rooted at ``/``."""
    p = "/" + path.replace("\\", "/").lower().lstrip("/")
    return p, p.rsplit("/", 1)[-1]


def context_path(path: Path) -> str:
    """The part of *path* that decides its context: relative to the module root.

    Directory names above the nearest ``go.mod`` (a checkout under ``~/tests/``
    or ``/srv/config/``) must not turn every file into a test or config file,
    so the path is taken relative to the directory holding the nearest
    ``go.mod``; without one, relative to the working directory when the file
    lies under it; otherwise as given.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return path.as_posix()
    for parent in resolved.parents:
        if (parent / "go.mod").is_file():
            return resolved.relative_to(parent).as_posix()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def is_test_path(path: str) -> bool:
    """A test file: the test-only relaxation (environment reads) applies here."""
    p, base = _normalized(path)
    return base.endswith("_test.go") or any(d in p for d in _TEST_DIRS)


def is_config_path(path: str) -> bool:
    """A configuration-layer file: reading the environment is allowed only here."""
    p, base = _normalized(path)
    stem = base[:-3] if base.endswith(".go") else base
    return (
        stem in ("config", "settings")
        or stem.endswith(("_config", "_settings"))
        or stem.startswith(("config_", "settings_"))
        or any(d in p for d in _CONFIG_DIRS)
    )


_PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_]\w*)")
_GENERATED_RE = re.compile(r"^// Code generated .* DO NOT EDIT\.$")


def package_name(code_lines: list[str]) -> str | None:
    """The name in the file's package clause, or ``None`` when there is none."""
    for line in code_lines:
        match = _PACKAGE_RE.match(line)
        if match is not None:
            return match.group(1)
    return None


def is_generated(lines: list[str]) -> bool:
    """True when a ``// Code generated ... DO NOT EDIT.`` line precedes the package clause."""
    for line in lines:
        if _PACKAGE_RE.match(line) is not None:
            return False
        if _GENERATED_RE.match(line.rstrip("\r")) is not None:
            return True
    return False


# --- Checks ----------------------------------------------------------------
# Each check: (code, message, view, compiled pattern, flags).
#   view "code"    — the executable-code view (literals and comments blanked);
#   view "comment" — the comment view (used by GO-SUPPRESS only);
#   view "raw"     — the original line, counted only when the match starts on
#                    a code character (flag "anchor_string": on a character
#                    inside a string literal instead, with its "op" group in
#                    code).
# Flags: skip_in_test | skip_in_config | skip_in_main | anchor_string.
# All rules are framework- and architecture-neutral; layer- or framework-bound
# rules are out of this checker's scope. Several entries may share one code;
# a line reports each code at most once.

# SQL text is recognized by its shape — a verb and its companion keyword in
# one case, all upper or all lower — not by a leading word alone, so a UI
# string such as "Select an item from the list" stays silent.
_SQL_SHAPE_UPPER = (
    r"SELECT\b[^\"`\n]*\bFROM\b|INSERT\s+INTO\b|UPDATE\b[^\"`\n]*\bSET\b|DELETE\s+FROM\b"
)
_SQL_SHAPE = "(?:" + _SQL_SHAPE_UPPER + "|" + _SQL_SHAPE_UPPER.lower() + ")"
_DB_METHOD = r"(?:Query|QueryRow|Exec|Prepare)(?:Context)?"

_CHECKS: list[tuple[str, str, str, re.Pattern, frozenset]] = [
    (
        "GO-PRINT",
        "fmt.Print*/print/println/log.Print* writes around the project's logging; log "
        "through an injected logger, write output to an injected io.Writer, use t.Log in tests",
        "code",
        re.compile(
            r"\bfmt\.Print(?:f|ln)?\s*\(|(?<![\w.])(?:print|println)\s*\("
            r"|\blog\.Print(?:f|ln)?\s*\("
        ),
        frozenset(),
    ),
    (
        "GO-ENV",
        "environment access outside the config layer; centralize os.Getenv/LookupEnv "
        "in configuration code (tests set variables with t.Setenv)",
        "code",
        re.compile(
            r"\bos\.(?:Getenv|LookupEnv|Environ|ExpandEnv)\s*\("
            r"|\bsyscall\.(?:Getenv|Environ)\s*\("
        ),
        frozenset({"skip_in_config", "skip_in_test"}),
    ),
    (
        "GO-ENV",
        "",
        "code",
        re.compile(r"\bos\.(?:Setenv|Unsetenv|Clearenv)\s*\(|\bsyscall\.Setenv\s*\("),
        frozenset({"skip_in_config"}),
    ),
    (
        "GO-SUPPRESS",
        "lint suppression without the sanctioned form; fix the cause or use "
        "//nolint:<one-linter> // <reason>",
        "comment",
        re.compile(
            r"(?<![\w-])nolint\b|\blint:(?:ignore|file-ignore)\b|#nosec\b"
            r"|\brevive:disable|\bexhaustive:ignore\b"
        ),
        frozenset(),
    ),
    (
        "GO-EXIT",
        "os.Exit below main, or log.Fatal anywhere, skips deferred cleanup and takes the "
        "exit decision away from the caller; return an error and let main call os.Exit",
        "code",
        re.compile(r"\bos\.Exit\s*\("),
        frozenset({"skip_in_main"}),
    ),
    (
        "GO-EXIT",
        "",
        "code",
        re.compile(r"\blog\.Fatal(?:f|ln)?\s*\("),
        frozenset(),
    ),
    (
        "GO-CTX-ROOT",
        "root context created below main; accept ctx context.Context from the caller "
        "(t.Context() in tests, context.WithoutCancel to detach deliberately)",
        "code",
        re.compile(r"\bcontext\.(?:Background|TODO)\s*\(\s*\)"),
        frozenset({"skip_in_main"}),
    ),
    (
        "GO-INIT",
        "init() runs implicitly on import, cannot return an error and hides "
        "dependencies; initialize explicitly from main or a constructor",
        "code",
        re.compile(r"^\s*func\s+init\s*\(\s*\)"),
        frozenset(),
    ),
    (
        "GO-PANIC-ERR",
        "panic on an ordinary error; return it — panic is for programmer errors "
        "and impossible states",
        "code",
        re.compile(r"\bpanic\s*\(\s*(?:err\s*\)|fmt\.Errorf\s*\(|errors\.New\s*\()"),
        frozenset(),
    ),
    (
        "GO-LEGACY-API",
        "superseded form; use the Go 1.27 replacement (any, slices.Sort*, atomic.Int64 "
        "and friends, reflect.TypeFor, errors.AsType, b.Loop, no per-iteration copy)",
        "code",
        re.compile(
            r"\binterface\s*\{\s*\}"
            r"|\bsort\.(?:Slice|SliceStable|Strings|Ints|Float64s)\s*\("
            r"|\batomic\.(?:Add|Load|Store|Swap|CompareAndSwap)"
            r"(?:Int32|Int64|Uint32|Uint64|Uintptr|Pointer)\s*\("
            r"|\breflect\.TypeOf\s*\(\s*\(\s*\*"
            r"|\bstrings\.Title\s*\("
            r"|\berrors\.As\s*\("
            r"|\bb\.N\b"
            r"|^\s*([A-Za-z_]\w*)\s*:=\s*\1\s*$"
        ),
        frozenset(),
    ),
    (
        "GO-ERR-MATCH",
        "error matched by == or by its message; use errors.Is / errors.AsType so "
        "wrapped errors still match",
        "code",
        re.compile(
            r"\.Error\s*\(\s*\)\s*(?:==|!=)"
            r"|(?:==|!=)\s*[\w.]+\.Error\s*\(\s*\)"
            r"|\bstrings\.(?:Contains|HasPrefix|HasSuffix|EqualFold|Index)\s*\(\s*[\w.]+\.Error\s*\(\s*\)"
            r"|\berr\w*\s*(?:==|!=)\s*(?:[a-z]\w*\.)?Err[A-Z]\w*"
        ),
        frozenset(),
    ),
    (
        "GO-TYPE-ASSERT",
        "unchecked type assertion panics on mismatch; use the comma-ok form or a "
        "type switch",
        "code",
        re.compile(r"\.\(\s*(?!type\s*\))[*\[\]\w.{}]+\s*\)"),
        frozenset({"comma_ok"}),
    ),
    (
        "GO-SQL-FMT",
        "SQL text built with fmt.Sprintf or concatenation; pass values as query "
        "arguments through placeholders",
        "code",
        re.compile(r"\." + _DB_METHOD + r"\s*\((?:\s*[\w.]+\s*,)?\s*fmt\.Sprintf?\s*\("),
        frozenset(),
    ),
    (
        "GO-SQL-FMT",
        "",
        "raw",
        re.compile(r"\bfmt\.Sprintf?\s*\(\s*[\"`]\s*" + _SQL_SHAPE),
        frozenset(),
    ),
    (
        "GO-SQL-FMT",
        "",
        "raw",
        re.compile(r"\"\s*" + _SQL_SHAPE + r"[^\"\n]*\"\s*(?P<op>\+)\s*[A-Za-z_(]"),
        frozenset({"anchor_string"}),
    ),
    (
        "GO-SHELL",
        "command line goes through a shell; run the program directly with an "
        "argument list (exec.CommandContext(ctx, name, args...))",
        "raw",
        re.compile(
            r"\bexec\.Command(?:Context)?\s*\(\s*(?:[\w.]+\s*,\s*)?"
            r"\"(?:/usr)?(?:/bin/)?(?:sh|bash|zsh|dash|ksh|cmd|cmd\.exe|powershell|pwsh)\"\s*,\s*"
            r"\"(?:-c|/c|/C|-Command)\""
        ),
        frozenset(),
    ),
    (
        "GO-TLS-INSECURE",
        "TLS certificate verification disabled or a pre-1.2 protocol allowed; keep "
        "verification on and fix the trust store instead",
        "code",
        re.compile(
            r"\bInsecureSkipVerify\s*[:=]\s*true\b"
            r"|\bMinVersion\s*[:=]\s*tls\.Version(?:SSL30|TLS10|TLS11)\b"
        ),
        frozenset(),
    ),
    (
        "GO-DURATION",
        "bare integer used as a time.Duration counts nanoseconds; multiply a unit "
        "constant (5 * time.Second)",
        "code",
        re.compile(
            r"\btime\.(?:Sleep|After|Tick|NewTimer|NewTicker|AfterFunc)\s*\(\s*[1-9][0-9_]*\s*[,)]"
            r"|\bcontext\.WithTimeout\s*\([^,()]+,\s*[1-9][0-9_]*\s*\)"
            r"|\b\w*Timeout\s*(?::|=)\s*[1-9][0-9_]*\s*(?:[,}]|$)"
        ),
        frozenset(),
    ),
    (
        "GO-EMBED-LOCK",
        "embedded sync.Mutex/RWMutex promotes Lock/Unlock into the type's API; use a "
        "named unexported field (mu sync.Mutex)",
        "code",
        re.compile(r"^\s*\*?sync\.(?:Mutex|RWMutex)\s*$"),
        frozenset(),
    ),
    (
        "GO-PKG-NAME",
        "package name says nothing about its content; name it for what it provides",
        "code",
        re.compile(r"^\s*package\s+(?:util|utils|common|shared|base|helper|helpers|misc)\b"),
        frozenset(),
    ),
    (
        "GO-HTTP-TIMEOUT",
        "HTTP call or server without timeouts; use an http.Server with "
        "ReadHeaderTimeout and an http.Client with Timeout plus request contexts",
        "code",
        re.compile(
            r"\bhttp\.(?:ListenAndServe|ListenAndServeTLS|Serve|ServeTLS)\s*\("
            r"|\bhttp\.(?:Get|Head|Post|PostForm)\s*\("
            r"|\bhttp\.DefaultClient\b"
            r"|\bhttp\.Client\s*\{\s*\}"
        ),
        frozenset(),
    ),
]

# The one message each code prints (entries with an empty message reuse it).
MESSAGES: dict[str, str] = {}
for _code, _message, _view, _pattern, _flags in _CHECKS:
    if _message:
        MESSAGES.setdefault(_code, _message)

# Import paths with a standard-library (or first-party) successor.
LEGACY_IMPORTS: dict[str, str] = {
    "io/ioutil": "io and os",
    "math/rand": "math/rand/v2 (crypto/rand for secrets)",
    "golang.org/x/exp/slices": "slices",
    "golang.org/x/exp/maps": "maps",
    "golang.org/x/exp/constraints": "cmp.Ordered or your own constraint",
    "golang.org/x/exp/slog": "log/slog",
    "golang.org/x/exp/rand": "math/rand/v2",
    "golang.org/x/net/context": "context",
    "github.com/pkg/errors": "errors and fmt.Errorf with %w",
    "go.uber.org/automaxprocs": "nothing: GOMAXPROCS follows the container CPU limit since Go 1.25",
}
LEGACY_IMPORT_CODE = "GO-LEGACY-IMPORT"
MESSAGES[LEGACY_IMPORT_CODE] = "import of a superseded package; use its successor"

KNOWN_CODES = frozenset(MESSAGES)

# Sanctioned, line-scoped suppression forms: exactly one linter/check/rule
# (a comma — the multi form — breaks the match), never `all`, and a mandatory
# non-empty written reason, consumed to end of line. They are cut out of the
# comment view before GO-SUPPRESS looks; whatever remains is still a finding.
_JUSTIFIED_SUPPRESSIONS = (
    re.compile(r"(?<![\w-])nolint:(?!all\b)[a-z][a-z0-9_-]*[ \t]*//[ \t]*\S.*"),
    re.compile(r"\blint:ignore[ \t]+[A-Z]{1,4}[0-9]{1,5}[ \t]+\S.*"),
    re.compile(r"#nosec[ \t]+G[0-9]{3}[ \t]+--[ \t]*\S.*"),
)

# `v, ok := x.(T)` — two operands on the left make the assertion checked.
_COMMA_OK_RE = re.compile(r"[\w.\]]+\s*,\s*[\w.]+\s*(?::=|=)")

# --- Lexical masking ---------------------------------------------------------


def mask_source(text: str) -> tuple[list[str], list[str]]:
    """Split *text* into parallel per-line views preserving columns.

    Returns ``(code_lines, comment_lines)``:

    * ``code_lines`` — only executable code; comments and the contents and
      delimiters of string, raw-string and rune literals are blanked;
    * ``comment_lines`` — only comment text (without the ``//`` / ``/* */``
      delimiters); everything else is blanked.

    Blanking replaces characters with spaces, so line numbers and columns in
    findings match the original source. Interpreted strings and rune literals
    cannot span a newline in Go; an unterminated one ends at the line break.
    """
    code_lines: list[str] = []
    comment_lines: list[str] = []
    code_buf: list[str] = []
    comment_buf: list[str] = []
    state = "code"  # code|line_comment|block_comment|string|raw|rune

    def flush_line() -> None:
        code_lines.append("".join(code_buf))
        comment_lines.append("".join(comment_buf))
        code_buf.clear()
        comment_buf.clear()

    def emit(code_ch: str, comment_ch: str) -> None:
        code_buf.append(code_ch)
        comment_buf.append(comment_ch)

    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if ch == "\n":
            if state in ("line_comment", "string", "rune"):
                state = "code"
            flush_line()
            i += 1
            continue

        if state in ("line_comment", "block_comment"):
            if state == "block_comment" and ch == "*" and nxt == "/":
                emit(" ", " ")
                emit(" ", " ")
                state = "code"
                i += 2
                continue
            emit(" ", ch)
            i += 1
            continue

        if state in ("string", "rune"):
            quote = '"' if state == "string" else "'"
            if ch == "\\":
                emit(" ", " ")
                if nxt and nxt != "\n":
                    emit(" ", " ")
                    i += 2
                    continue
                i += 1
                continue
            emit(" ", " ")
            if ch == quote:
                state = "code"
            i += 1
            continue

        if state == "raw":
            emit(" ", " ")
            if ch == "`":
                state = "code"
            i += 1
            continue

        # state == "code"
        if ch == "/" and nxt == "/":
            emit(" ", " ")
            emit(" ", " ")
            state = "line_comment"
            i += 2
            continue
        if ch == "/" and nxt == "*":
            emit(" ", " ")
            emit(" ", " ")
            state = "block_comment"
            i += 2
            continue
        if ch == '"':
            emit(" ", " ")
            state = "string"
            i += 1
            continue
        if ch == "'":
            emit(" ", " ")
            state = "rune"
            i += 1
            continue
        if ch == "`":
            emit(" ", " ")
            state = "raw"
            i += 1
            continue
        emit(ch, " ")
        i += 1

    flush_line()
    return code_lines, comment_lines


# --- Imports -----------------------------------------------------------------

_IMPORT_LINE_RE = re.compile(r"^\s*import\b")
_IMPORT_BLOCK_OPEN_RE = re.compile(r"^\s*import\s*\(")
_IMPORT_SPEC_RE = re.compile(r"(?:^|[\s(;])(?:[A-Za-z_.]\w*\s+)?[\"`]([^\"`\n]+)[\"`]")


def _without_comments(raw: str, comment: str) -> str:
    """*raw* with every comment character blanked (string literals kept)."""
    return "".join(
        " " if idx < len(comment) and comment[idx] != " " else ch
        for idx, ch in enumerate(raw)
    )


def import_paths(
    code_lines: list[str], comment_lines: list[str], raw_lines: list[str]
) -> list[tuple[int, str]]:
    """Every ``(line_no, path)`` import spec, read from code-anchored raw text.

    The code view decides where an import clause or block is (so an
    ``import`` inside a comment or a string never counts); the raw line, with
    its comment text blanked, supplies the quoted path the code view has
    blanked — a path quoted in a trailing comment is never an import.
    """
    found: list[tuple[int, str]] = []
    in_block = False
    for idx, (code, comment, full) in enumerate(zip(code_lines, comment_lines, raw_lines)):
        raw = _without_comments(full, comment)
        if in_block:
            # A spec line is all string literal, so its code view is blank;
            # only the closing parenthesis is code.
            closing = code.find(")")
            segment = raw if closing < 0 else raw[:closing]
            found.extend((idx + 1, path) for path in _IMPORT_SPEC_RE.findall(segment))
            if closing >= 0:
                in_block = False
            continue
        if _IMPORT_BLOCK_OPEN_RE.match(code) is not None:
            start = code.index("(") + 1
            closing = code.find(")", start)
            segment = raw[start:] if closing < 0 else raw[start:closing]
            found.extend((idx + 1, path) for path in _IMPORT_SPEC_RE.findall(segment))
            in_block = closing < 0
            continue
        if _IMPORT_LINE_RE.match(code) is not None:
            keyword_end = code.index("import") + len("import")
            match = _IMPORT_SPEC_RE.search(raw, keyword_end)
            if match is not None:
                found.append((idx + 1, match.group(1)))
    return found


# --- Suppression pragmas -----------------------------------------------------

_PRAGMA_WORD_RE = re.compile(r"skill-check-ignore")
_PRAGMA_RE = re.compile(
    r"skill-check-ignore\s*:\s*"
    r"(?P<codes>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+(?:\s*,\s*[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)*)"
    r"\s*--[ \t]*(?P<why>.*)"
)

_PRAGMA_FORMAT_HINT = (
    "expected 'skill-check-ignore: <CODE>[, <CODE>...] -- <non-empty justification>'"
)


def parse_pragmas(
    comment_line: str, label: str, line_no: int, known_codes: frozenset[str] = KNOWN_CODES
) -> tuple[set[str], list[str]]:
    """Parse suppression pragmas found in one line's comment text.

    Returns ``(suppressed_codes, errors)``. Any malformed or forbidden pragma
    produces an error entry (and suppresses nothing) — fail-closed.
    """
    occurrences = list(_PRAGMA_WORD_RE.finditer(comment_line))
    if not occurrences:
        return set(), []
    where = f"{label}:{line_no}"
    if len(occurrences) > 1:
        return set(), [f"{where}: multiple skill-check-ignore pragmas on one line; {_PRAGMA_FORMAT_HINT}"]
    match = _PRAGMA_RE.match(comment_line, occurrences[0].start())
    if match is None:
        return set(), [f"{where}: malformed skill-check-ignore pragma; {_PRAGMA_FORMAT_HINT}"]
    codes = {c.strip() for c in match.group("codes").split(",")}
    errors: list[str] = []
    if "GO-SUPPRESS" in codes:
        errors.append(f"{where}: GO-SUPPRESS can never be suppressed; fix the suppression instead")
    unknown = sorted(codes - known_codes)
    if unknown:
        errors.append(
            f"{where}: unknown rule code(s) {', '.join(unknown)}; "
            f"known codes: {', '.join(sorted(known_codes))}"
        )
    if not match.group("why").strip():
        errors.append(f"{where}: suppression justification must not be empty; {_PRAGMA_FORMAT_HINT}")
    if errors:
        return set(), errors
    return codes, []


# --- Core --------------------------------------------------------------------


def _anchored(match: re.Match, code_line: str, comment_line: str, want_string: bool) -> bool:
    """True when a raw-line match starts in code (or, if asked, in a string literal).

    A string-anchored match must also have its ``op`` group (the operator
    joining the literal to a value) in code, so text that merely looks like
    a concatenation inside one literal — escaped quotes included — is data.
    """
    start = match.start()
    if start >= len(code_line):
        return False
    if want_string:
        op = match.start("op")
        return (
            code_line[start] == " "
            and comment_line[start] == " "
            and 0 <= op < len(code_line)
            and code_line[op] != " "
        )
    return code_line[start] != " "


def _unchecked_assertion(pattern: re.Pattern, code_line: str) -> bool:
    """True when the line holds a single-value type assertion (no comma-ok)."""
    for match in pattern.finditer(code_line):
        if _COMMA_OK_RE.search(code_line, 0, match.start()) is None:
            return True
    return False


def check_text(
    text: str, label: str, context: str | None = None
) -> tuple[list[tuple[str, int, str, str]], list[str]]:
    """Return ``(findings, errors)``.

    ``findings`` is ``[(label, line_no, code, message)]`` sorted by
    ``(line, code)``; ``errors`` are fail-closed pragma problems. *context*
    is the path that decides the test/config context (default: *label*).
    """
    raw_lines = text.split("\n")
    if is_generated(raw_lines):
        return [], []
    code_lines, comment_lines = mask_source(text)
    where = label if context is None else context
    test_ctx = is_test_path(where)
    config_ctx = is_config_path(where)
    main_ctx = package_name(code_lines) == "main"
    seen: set[tuple[int, str]] = set()
    findings: list[tuple[str, int, str, str]] = []
    errors: list[str] = []
    suppressed_by_line: dict[int, set[str]] = {}

    def report(line_no: int, code: str) -> None:
        if code in suppressed_by_line.get(line_no, set()) or (line_no, code) in seen:
            return
        seen.add((line_no, code))
        findings.append((label, line_no, code, MESSAGES[code]))

    for idx, comment_line in enumerate(comment_lines):
        suppressed, line_errors = parse_pragmas(comment_line, label, idx + 1)
        errors.extend(line_errors)
        suppressed_by_line[idx + 1] = suppressed

    for idx, (code_line, comment_line) in enumerate(zip(code_lines, comment_lines)):
        raw_line = raw_lines[idx] if idx < len(raw_lines) else ""
        for code, _message, view, pattern, flags in _CHECKS:
            if "skip_in_test" in flags and test_ctx:
                continue
            if "skip_in_config" in flags and config_ctx:
                continue
            if "skip_in_main" in flags and main_ctx:
                continue
            if view == "comment":
                # Justified single-rule forms are cut out first — what remains
                # (a blanket/multi/unjustified form on the same line) is
                # still a finding.
                target = comment_line
                for sanctioned in _JUSTIFIED_SUPPRESSIONS:
                    target = sanctioned.sub("", target)
                hit = pattern.search(target) is not None
            elif view == "raw":
                want_string = "anchor_string" in flags
                hit = any(
                    _anchored(m, code_line, comment_line, want_string)
                    for m in pattern.finditer(raw_line)
                )
            elif "comma_ok" in flags:
                hit = _unchecked_assertion(pattern, code_line)
            else:
                hit = pattern.search(code_line) is not None
            if hit:
                report(idx + 1, code)

    for line_no, path in import_paths(code_lines, comment_lines, raw_lines):
        if path in LEGACY_IMPORTS:
            report(line_no, LEGACY_IMPORT_CODE)

    return sorted(findings, key=lambda f: (f[1], f[2])), errors


# --- Driver ----------------------------------------------------------------


_SKIPPED_DIRS = frozenset({"vendor", "testdata"})


def _walk(directory: Path) -> list[Path]:
    """``.go`` files under *directory*, skipping ``vendor/``, ``testdata/`` and hidden dirs.

    The Go tool itself ignores the same directories: vendored code is not the
    author's, and ``testdata/`` holds fixtures that may break rules on purpose.
    """
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        rel_parts = path.relative_to(directory).parts
        if any(part in _SKIPPED_DIRS or part.startswith(".") for part in rel_parts[:-1]):
            continue
        if path.suffix in GO_SUFFIXES and path.is_file():
            files.append(path)
    return files


def _iter_paths(args: list[str]) -> list[Path]:
    files: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            files.extend(_walk(p))
        else:
            files.append(p)
    # A path listed twice (directly or via overlapping directories) is checked
    # once — findings stay deterministic and are never doubled.
    return list(dict.fromkeys(files))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    findings: list[tuple[str, int, str, str]] = []
    errors: list[str] = []
    had_io_error = False

    if not args or args == ["-"]:
        findings, errors = check_text(sys.stdin.read(), "<stdin>")
    else:
        for path in _iter_paths(args):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                print(f"error: cannot read {path}: {exc}", file=sys.stderr)
                had_io_error = True
                continue
            file_findings, file_errors = check_text(text, path.as_posix(), context_path(path))
            findings.extend(file_findings)
            errors.extend(file_errors)

    findings.sort(key=lambda f: (f[0], f[1], f[2]))
    for label, line_no, code, message in findings:
        print(f"{label}:{line_no}: {code} {message}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    print(f"# {len(findings)} finding(s)", file=sys.stderr)

    if had_io_error or errors:
        return 2
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
