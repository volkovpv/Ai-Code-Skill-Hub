#!/usr/bin/env python3
"""Heuristic NestJS convention checker (stdlib-only, offline, layer-aware).

Scan ``.ts``/``.mts``/``.cts`` files (or stdin) for NestJS-specific,
layer-bound violations and print one line per finding::

    <path>:<line>: <CODE> <message>

Rules::

    NEST-DI-TOKEN       @Inject('string') / @Inject(Symbol(...)) — use a named
                        `unique symbol` token constant (any layer, any file)
    NEST-RAW-THROW      `throw new Error(...)` inside domain/ or application/
                        — throw a typed domain error from the registry
    NEST-DOMAIN-IMPORT  a framework import (@nestjs/*, ORM, rxjs, validators,
                        HTTP clients) inside domain/ — the core stays pure
    NEST-APP-IMPORT     a runtime @nestjs/* import inside application/ —
                        only `import type` from the framework base is allowed

Layer detection is **path-based**: a file is in a layer when its path contains
a ``domain/`` or ``application/`` segment. Content arriving via stdin has no
path, so the layer rules stay silent for it — only ``NEST-DI-TOKEN`` applies.
Test files (``*.spec.ts``, ``*.integration-spec.ts``, test directories) are
exempt from the layer rules; ``NEST-DI-TOKEN`` stays active everywhere.

Exit codes: ``0`` no findings, ``1`` findings printed, ``2`` an IO error or a
malformed/forbidden suppression pragma (fail-closed).

The checker shares its lexical masking model and strict suppression contract
with the ``typescript-coding`` skill's ``check_conventions.py`` (each skill is
self-contained, so the scanner is deliberately duplicated, not imported):
string/template/regex literals and comments never produce findings, template
interpolation code is scanned, and a suppression requires a specific known
code plus a non-empty justification::

    // skill-check-ignore: NEST-DI-TOKEN -- migrating a legacy token in this PR

A bare ``skill-check-ignore``, an unknown code, or an empty justification
aborts the check with exit code ``2``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TS_SUFFIXES = (".ts", ".mts", ".cts")

# --- Context ---------------------------------------------------------------

_TS_EXT_RE = re.compile(r"\.(?:m|c)?ts$")


def is_test_path(path: str) -> bool:
    """A test file: the layer rules do not apply here."""
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


def layer_of(path: str) -> str | None:
    """Return 'domain' or 'application' when the path names the layer."""
    parts = path.replace("\\", "/").lower().split("/")
    if "domain" in parts[:-1]:
        return "domain"
    if "application" in parts[:-1]:
        return "application"
    return None


# --- Lexical masking (kept identical to typescript-coding's checker) --------

_REGEX_PREV_KEYWORDS = frozenset(
    "return typeof instanceof in of new void delete case do else yield await throw".split()
)
_REGEX_PREV_CHARS = frozenset("=(:,;[!&|?{}+-*%~^<>")


def mask_source(text: str) -> tuple[list[str], list[str]]:
    """Split *text* into parallel per-line views preserving columns.

    Returns ``(code_lines, comment_lines)``: executable code with literals
    and comments blanked (interpolation code kept), and comment text with
    everything else blanked. Columns match the original source.
    """
    code_lines: list[str] = []
    comment_lines: list[str] = []
    code_buf: list[str] = []
    comment_buf: list[str] = []

    frames: list[list] = [["code", 0]]
    state = "code"
    regex_in_class = False
    last_char = ""
    last_word = ""
    word_open = False

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
                    last_char, last_word, word_open = ")", "", False
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
                    last_char, last_word, word_open = ")", "", False
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
            word_open = False
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


# --- Rules -------------------------------------------------------------------

_MESSAGES = {
    "NEST-DI-TOKEN": "string or inline-Symbol DI token; use a named `unique symbol` token constant",
    "NEST-RAW-THROW": "throw new Error in domain/application; throw a typed domain error from the registry",
    "NEST-DOMAIN-IMPORT": "framework import inside domain/; the domain core imports no framework",
    "NEST-APP-IMPORT": "runtime @nestjs import inside application/; use `import type` from the framework base only",
    "NEST-HTTP-STATUS-LITERAL": (
        "raw numeric HTTP-status literal; use `HttpStatus.*` from `@nestjs/common` "
        "(exception args, @HttpCode, status maps and test assertions alike)"
    ),
}

KNOWN_CODES = frozenset(_MESSAGES)

_INJECT_RE = re.compile(r"@Inject\s*\(")
_INLINE_SYMBOL_RE = re.compile(r"\s*Symbol\s*\(")
_RAW_THROW_RE = re.compile(r"\bthrow\s+new\s+Error\s*\(")
_IMPORT_LINE_RE = re.compile(r"^\s*(?:import\b|export\s+(?:\*|\{).*\bfrom\b)|\brequire\s*\(")
_IMPORT_TYPE_RE = re.compile(r"^\s*(?:import|export)\s+type\b")
_MODULE_SPEC_RE = re.compile(r"(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)['\"]([^'\"]+)['\"]")

# Standard HTTP status-code registry (RFC 9110 + widely used extensions) —
# used to disambiguate a genuine status literal from an unrelated 3-digit
# magic number (OBS-20260717-001).
_HTTP_STATUS_CODES = frozenset(
    {
        100, 101, 102, 103,
        200, 201, 202, 203, 204, 205, 206, 207, 208, 226,
        300, 301, 302, 303, 304, 305, 306, 307, 308,
        400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413,
        414, 415, 416, 417, 418, 421, 422, 423, 424, 425, 426, 428, 429, 431,
        451,
        500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511,
    }
)
_HTTP_CODE_DECORATOR_RE = re.compile(r"@HttpCode\s*\(\s*(\d{3})\s*\)")
_HTTP_EXCEPTION_RE = re.compile(r"\bnew\s+HttpException\s*\([^()]*,\s*(\d{3})\s*\)")
_HTTP_STATUS_MAP_ENTRY_RE = re.compile(r"\[\s*(\d{3})\s*,\s*[A-Za-z_$][\w$.]*\s*\]")
_HTTP_TEST_ASSERTION_RE = re.compile(r"\.(?:toBe|toEqual)\s*\(\s*(\d{3})\s*\)")

_DOMAIN_FORBIDDEN_PREFIXES = ("@nestjs/",)
_DOMAIN_FORBIDDEN_MODULES = frozenset(
    {
        "rxjs",
        "reflect-metadata",
        "sequelize",
        "sequelize-typescript",
        "typeorm",
        "fastify",
        "express",
        "axios",
        "class-validator",
        "class-transformer",
    }
)


def _is_forbidden_in_domain(module: str) -> bool:
    if module.startswith(_DOMAIN_FORBIDDEN_PREFIXES):
        return True
    base = module.split("/", 1)[0]
    return base in _DOMAIN_FORBIDDEN_MODULES


def _line_modules(code_line: str, raw_line: str) -> list[str]:
    """Module specifiers on an import-looking line.

    The *code view* decides whether the line is an import statement (so a
    quoted ``import ... from '@nestjs/x'`` inside a string or template never
    counts); the specifier itself is then read from the raw line, because
    literals are blanked in the code view.
    """
    if not _IMPORT_LINE_RE.search(code_line):
        return []
    return _MODULE_SPEC_RE.findall(raw_line)


# --- Suppression pragmas (same strict contract as typescript-coding) ----------

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
    """Parse suppression pragmas in one line's comment text (fail-closed)."""
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
    """Return ``(findings, errors)`` for one file's content."""
    raw_lines = text.split("\n")
    code_lines, comment_lines = mask_source(text)
    layer = layer_of(label)
    test_ctx = is_test_path(label)
    findings: list[tuple[str, int, str, str]] = []
    errors: list[str] = []

    for idx, (code_line, comment_line) in enumerate(zip(code_lines, comment_lines)):
        raw_line = raw_lines[idx]
        suppressed, line_errors = parse_pragmas(comment_line, label, idx + 1)
        errors.extend(line_errors)
        hits: set[str] = set()

        for m in _INJECT_RE.finditer(code_line):
            after_raw = raw_line[m.end():].lstrip()
            if after_raw.startswith(("'", '"')) or _INLINE_SYMBOL_RE.match(code_line, m.end()):
                hits.add("NEST-DI-TOKEN")
                break

        for pattern in (_HTTP_CODE_DECORATOR_RE, _HTTP_EXCEPTION_RE, _HTTP_STATUS_MAP_ENTRY_RE):
            for m in pattern.finditer(code_line):
                if int(m.group(1)) in _HTTP_STATUS_CODES:
                    hits.add("NEST-HTTP-STATUS-LITERAL")
        if test_ctx:
            for m in _HTTP_TEST_ASSERTION_RE.finditer(code_line):
                if int(m.group(1)) in _HTTP_STATUS_CODES:
                    hits.add("NEST-HTTP-STATUS-LITERAL")

        if not test_ctx and layer in ("domain", "application"):
            if _RAW_THROW_RE.search(code_line):
                hits.add("NEST-RAW-THROW")
            modules = _line_modules(code_line, raw_line)
            if layer == "domain":
                if any(_is_forbidden_in_domain(mod) for mod in modules):
                    hits.add("NEST-DOMAIN-IMPORT")
            else:  # application
                if any(mod.startswith("@nestjs/") for mod in modules) and not _IMPORT_TYPE_RE.match(
                    code_line
                ):
                    hits.add("NEST-APP-IMPORT")

        for code in hits:
            if code in suppressed:
                continue
            findings.append((label, idx + 1, code, _MESSAGES[code]))

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
