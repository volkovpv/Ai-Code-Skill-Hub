#!/usr/bin/env python3
"""Heuristic convention checker for TypeScript source (stdlib-only, offline).

Scan ``.ts``/``.mts``/``.cts`` files (or stdin) for a curated set of
high-signal, framework- and architecture-neutral coding-standard violations
and print one line per finding::

    <path>:<line>: <CODE> <message>

Usage::

    python scripts/check_conventions.py src/            # walk a directory
    python scripts/check_conventions.py a.ts b.mts      # explicit files
    cat snippet.ts | python scripts/check_conventions.py # stdin (label <stdin>)

Exit codes: ``0`` no findings, ``1`` findings printed, ``2`` an IO error or a
malformed/forbidden suppression pragma (fail-closed).

Masking model
-------------

A lexical scanner separates code, comments, and literal content before any
rule runs:

* text inside string literals, template literals, regex literals and comments
  never produces a finding — quoting a rule (e.g. in a message or a regex)
  is not a violation;
* code inside template-literal interpolations (``${...}``) IS scanned;
* ``TS-SUPPRESS`` looks only at comment text, because ``@ts-ignore`` /
  ``eslint-disable`` live in comments; the same text inside a string is data.

The scanner is still line-oriented lexical analysis, not a TypeScript AST:
a multi-line construct is seen line by line, and the project's compiler in
``strict`` mode plus its linter remain authoritative. Treat every finding as
a prompt to look, not a verdict.

Suppression contract (strict, fail-closed)
------------------------------------------

    // skill-check-ignore: TS-ENV -- reason this line is a checked false positive

* only specific, known rule codes may be suppressed (comma-separated for
  several) — there is no "suppress everything" form;
* the justification after ``--`` is mandatory and must be non-empty;
* a bare ``skill-check-ignore``, an unknown code, or any malformed pragma
  aborts the whole check with exit code ``2``;
* ``TS-SUPPRESS`` itself can never be suppressed;
* the pragma only counts inside a comment: a pragma-looking string literal
  neither suppresses nor errors, and never bypasses a finding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TS_SUFFIXES = (".ts", ".mts", ".cts")

# --- Context ---------------------------------------------------------------

_TS_EXT_RE = re.compile(r"\.(?:m|c)?ts$")


def is_test_path(path: str) -> bool:
    """A test file: strictness relaxations (any/non-null/console) apply here."""
    p = path.replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    stem = _TS_EXT_RE.sub("", base)
    return (
        stem.endswith((".spec", ".integration-spec", ".test", "_test"))
        or base.startswith("test_")
        or "/__test__/" in p
        or "/__tests__/" in p
        or "/test/" in p
        or "/tests/" in p
    )


def is_config_path(path: str) -> bool:
    """A configuration-layer file: reading env is allowed only here."""
    p = path.replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    stem = _TS_EXT_RE.sub("", base)
    return (
        stem.endswith(".config")
        or base == "env.validator.ts"
        or base.startswith("config.")
        or "/config/" in p
    )


# --- Checks ----------------------------------------------------------------
# Each check: (code, message, compiled pattern, {"skip_in_test"|"skip_in_config"}).
# All rules are framework- and architecture-neutral; layer- or framework-bound
# rules live in the sibling skills (hexagonal-service, typescript-nestjs).

_CHECKS: list[tuple[str, str, re.Pattern, frozenset]] = [
    (
        "TS-CONSOLE",
        "console.* call in shipped code; route output through the project's logging seam",
        re.compile(r"\bconsole\s*\.\s*\w+\s*\("),
        frozenset({"skip_in_test"}),
    ),
    (
        "TS-ENV",
        "process.env outside the config layer; centralize env reads in configuration code",
        re.compile(r"\bprocess\.env\b"),
        frozenset({"skip_in_config"}),
    ),
    (
        "TS-ENUM",
        "native enum; model closed sets as an `as const` object + derived union type",
        re.compile(r"\b(?:const\s+)?enum\s+[A-Za-z_$]"),
        frozenset(),
    ),
    (
        "TS-ANY",
        "explicit any defeats strict typing; type the value or use unknown + narrowing",
        re.compile(r":\s*any\b|\bas\s+any\b|<any>|Array<any>|Promise<any>"),
        frozenset({"skip_in_test"}),
    ),
    (
        "TS-NONNULL",
        "non-null assertion (!); narrow the type instead of asserting",
        re.compile(r"[A-Za-z0-9_$\)\]]!(?=[.\)\];,])"),
        frozenset({"skip_in_test"}),
    ),
    (
        "TS-SUPPRESS",
        "type/lint suppression; fix the cause instead of silencing the checker",
        re.compile(r"@ts-ignore|@ts-nocheck|eslint-disable"),
        frozenset(),
    ),
    (
        "TS-FOCUSED",
        "focused test (.only); never commit .only",
        re.compile(r"\.only\s*\("),
        frozenset(),
    ),
]

KNOWN_CODES = frozenset(code for code, _, _, _ in _CHECKS)

# --- Lexical masking ---------------------------------------------------------

# Last-word keywords after which a `/` starts a regex literal, not a division.
_REGEX_PREV_KEYWORDS = frozenset(
    "return typeof instanceof in of new void delete case do else yield await throw".split()
)
_REGEX_PREV_CHARS = frozenset("=(:,;[!&|?{}+-*%~^<>")


def mask_source(text: str) -> tuple[list[str], list[str]]:
    """Split *text* into parallel per-line views preserving columns.

    Returns ``(code_lines, comment_lines)``:

    * ``code_lines`` — only executable code; comments and the contents of
      string/template/regex literals are blanked, template interpolation
      code (``${...}``) is kept;
    * ``comment_lines`` — only comment text (without the ``//``/``/*``/``*/``
      delimiters); everything else is blanked.

    Blanking replaces characters with spaces, so line numbers and columns in
    findings match the original source.
    """
    code_lines: list[str] = []
    comment_lines: list[str] = []
    code_buf: list[str] = []
    comment_buf: list[str] = []

    # Frame stack: ("code", brace_depth) | ("template",). Literals and
    # comments are flat states on top of the innermost frame.
    frames: list[list] = [["code", 0]]
    state = "code"  # code|line_comment|block_comment|squote|dquote|template|regex
    regex_in_class = False
    last_char = ""  # last significant code character (for regex-vs-division)
    last_word = ""  # last identifier token seen in code
    word_open = False  # True while last_word is still being extended

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
            # Single-line states cannot span a newline; fall back to the
            # innermost frame (code or template).
            if state in ("line_comment", "squote", "dquote", "regex"):
                state = frames[-1][0]
            flush_line()
            i += 1
            continue

        if state == "line_comment":
            emit(" ", ch)
            i += 1
            continue

        if state == "block_comment":
            if ch == "*" and nxt == "/":
                emit(" ", " ")
                emit(" ", " ")
                state = "code" if frames[-1][0] == "code" else "template"
                i += 2
                continue
            emit(" ", ch)
            i += 1
            continue

        if state in ("squote", "dquote"):
            if ch == "\\":
                emit(" ", " ")
                if nxt and nxt != "\n":
                    emit(" ", " ")
                    i += 2
                    continue
                i += 1
                continue
            if (state == "squote" and ch == "'") or (state == "dquote" and ch == '"'):
                emit(" ", " ")
                state = "code" if frames[-1][0] == "code" else "template"
                if state == "code":
                    last_char, last_word, word_open = ")", "", False  # a string value
                i += 1
                continue
            emit(" ", " ")
            i += 1
            continue

        if state == "regex":
            if ch == "\\":
                emit(" ", " ")
                if nxt and nxt != "\n":
                    emit(" ", " ")
                    i += 2
                    continue
                i += 1
                continue
            if ch == "[":
                regex_in_class = True
            elif ch == "]":
                regex_in_class = False
            elif ch == "/" and not regex_in_class:
                emit(" ", " ")
                state = "code"
                # A regex is a value: a following `/` divides.
                last_char, last_word, word_open = ")", "", False
                i += 1
                continue
            emit(" ", " ")
            i += 1
            continue

        if state == "template":
            if ch == "\\":
                emit(" ", " ")
                if nxt and nxt != "\n":
                    emit(" ", " ")
                    i += 2
                    continue
                i += 1
                continue
            if ch == "`":
                emit(" ", " ")
                frames.pop()
                state = "code" if frames[-1][0] == "code" else "template"
                if state == "code":
                    last_char, last_word, word_open = ")", "", False  # a template value
                i += 1
                continue
            if ch == "$" and nxt == "{":
                emit(" ", " ")
                emit(" ", " ")
                frames.append(["code", 0])
                state = "code"
                last_char, last_word, word_open = "", "", False
                i += 2
                continue
            emit(" ", " ")
            i += 1
            continue

        # state == "code"
        if ch == "/" and nxt == "/":
            state = "line_comment"
            emit(" ", " ")
            emit(" ", " ")
            i += 2
            continue
        if ch == "/" and nxt == "*":
            state = "block_comment"
            emit(" ", " ")
            emit(" ", " ")
            i += 2
            continue
        if ch == "'":
            state = "squote"
            emit(" ", " ")
            i += 1
            continue
        if ch == '"':
            state = "dquote"
            emit(" ", " ")
            i += 1
            continue
        if ch == "`":
            frames.append(["template"])
            state = "template"
            emit(" ", " ")
            i += 1
            continue
        if ch == "/":
            starts_regex = (
                last_char == ""
                or last_char in _REGEX_PREV_CHARS
                or last_word in _REGEX_PREV_KEYWORDS
            )
            if starts_regex:
                state = "regex"
                regex_in_class = False
                emit(" ", " ")
                i += 1
                continue
            emit(ch, " ")
            last_char, last_word, word_open = ch, "", False
            i += 1
            continue
        if ch == "{":
            frames[-1][1] += 1
            emit(ch, " ")
            last_char, last_word, word_open = ch, "", False
            i += 1
            continue
        if ch == "}":
            if frames[-1][1] == 0 and len(frames) > 1:
                # Close of a template interpolation: back into the template.
                frames.pop()
                state = "template"
                emit(" ", " ")
                i += 1
                continue
            frames[-1][1] = max(0, frames[-1][1] - 1)
            emit(ch, " ")
            last_char, last_word, word_open = ch, "", False
            i += 1
            continue

        emit(ch, " ")
        if ch.isspace():
            word_open = False  # the word ends but stays the last token
        elif ch.isalnum() or ch in "_$":
            last_word = last_word + ch if word_open else ch
            word_open = True
            last_char = ch
        else:
            last_word, word_open = "", False
            last_char = ch
        i += 1

    flush_line()
    return code_lines, comment_lines


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
    if "TS-SUPPRESS" in codes:
        errors.append(f"{where}: TS-SUPPRESS can never be suppressed; fix the suppression instead")
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


def check_text(text: str, label: str) -> tuple[list[tuple[str, int, str, str]], list[str]]:
    """Return ``(findings, errors)``.

    ``findings`` is ``[(label, line_no, code, message)]`` sorted by
    ``(line, code)``; ``errors`` are fail-closed pragma problems.
    """
    code_lines, comment_lines = mask_source(text)
    test_ctx = is_test_path(label)
    config_ctx = is_config_path(label)
    findings: list[tuple[str, int, str, str]] = []
    errors: list[str] = []
    for idx, (code_line, comment_line) in enumerate(zip(code_lines, comment_lines)):
        suppressed, line_errors = parse_pragmas(comment_line, label, idx + 1)
        errors.extend(line_errors)
        for code, message, pattern, flags in _CHECKS:
            if "skip_in_test" in flags and test_ctx:
                continue
            if "skip_in_config" in flags and config_ctx:
                continue
            # @ts-ignore/eslint-disable live in comments, so TS-SUPPRESS scans
            # the comment view; every other rule scans only executable code.
            target = comment_line if code == "TS-SUPPRESS" else code_line
            if not pattern.search(target):
                continue
            if code in suppressed:
                continue
            findings.append((label, idx + 1, code, message))
    return sorted(findings, key=lambda f: (f[1], f[2])), errors


# --- Driver ----------------------------------------------------------------


def _iter_paths(args: list[str]) -> list[Path]:
    files: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*") if q.suffix in TS_SUFFIXES))
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
            file_findings, file_errors = check_text(text, path.as_posix())
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
