#!/usr/bin/env python3
"""Heuristic convention checker for Python source (stdlib-only, offline).

Scan ``.py`` files (or stdin) for a curated set of high-signal, framework-
and architecture-neutral coding-standard violations and print one line per
finding::

    <path>:<line>: <CODE> <message>

Usage::

    python scripts/check_py_conventions.py src/            # walk a directory
    python scripts/check_py_conventions.py a.py b.py       # explicit files
    cat snippet.py | python scripts/check_py_conventions.py # stdin (label <stdin>)

Exit codes: ``0`` no findings, ``1`` findings printed, ``2`` an IO error or a
malformed/forbidden suppression pragma (fail-closed).

Masking model
-------------

A lexical scanner separates code, comments, and literal content before any
rule runs:

* text inside string literals (including triple-quoted strings and
  docstrings) and comments never produces a finding — quoting a rule
  (e.g. in a message) is not a violation;
* code inside f-string interpolations (``{...}``) IS scanned;
* ``PY-SUPPRESS`` looks only at comment text, because ``# type: ignore`` /
  ``# noqa`` live in comments; the same text inside a string is data.
  A line-scoped ``# noqa: <RULE>`` naming exactly one rule code with a
  non-empty ``--`` justification is not reported — that is the sanctioned
  way to hold a documented upstream limitation of a lint rule; every
  blanket, multi-rule, or unjustified form and every type-level
  suppression (``type: ignore``) is still a finding.

The scanner is still line-oriented lexical analysis, not a Python AST:
a multi-line construct is seen line by line, and the project's type checker
in strict mode plus its linter remain authoritative. Treat every finding as
a prompt to look, not a verdict.

Suppression contract (strict, fail-closed)
------------------------------------------

    # skill-check-ignore: PY-ENV -- reason this line is a checked false positive

* only specific, known rule codes may be suppressed (comma-separated for
  several) — there is no "suppress everything" form;
* the justification after ``--`` is mandatory and must be non-empty;
* a bare ``skill-check-ignore``, an unknown code, or any malformed pragma
  aborts the whole check with exit code ``2``;
* ``PY-SUPPRESS`` itself can never be suppressed;
* the pragma only counts inside a comment: a pragma-looking string literal
  neither suppresses nor errors, and never bypasses a finding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PY_SUFFIXES = (".py",)

# --- Context ---------------------------------------------------------------


def is_test_path(path: str) -> bool:
    """A test file: strictness relaxations (print/Any/assert) apply here."""
    p = path.replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    stem = base[:-3] if base.endswith(".py") else base
    return (
        stem.startswith("test_")
        or stem.endswith("_test")
        or base == "conftest.py"
        or "/__test__/" in p
        or "/__tests__/" in p
        or "/test/" in p
        or "/tests/" in p
    )


def is_config_path(path: str) -> bool:
    """A configuration-layer file: reading the environment is allowed only here."""
    p = path.replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    stem = base[:-3] if base.endswith(".py") else base
    return (
        stem in ("config", "settings")
        or stem.endswith(("_config", "_settings"))
        or stem.startswith(("config_", "settings_"))
        or "/config/" in p
        or "/settings/" in p
    )


# --- Checks ----------------------------------------------------------------
# Each check: (code, message, compiled pattern, {"skip_in_test"|"skip_in_config"}).
# All rules are framework- and architecture-neutral; layer- or framework-bound
# rules live in sibling skills (hexagonal-service).

_CHECKS: list[tuple[str, str, re.Pattern, frozenset]] = [
    (
        "PY-PRINT",
        "print() call in shipped code; route output through the project's logging seam",
        re.compile(r"\bprint\s*\("),
        frozenset({"skip_in_test"}),
    ),
    (
        "PY-ENV",
        "environment read outside the config layer; centralize os.environ in configuration code",
        re.compile(r"\bos\.environ\b|(?<![\w.])environ\b|\bgetenv\s*\("),
        frozenset({"skip_in_config"}),
    ),
    (
        "PY-ANY",
        "Any defeats strict typing; type the value or take object and narrow",
        re.compile(r"\bAny\b"),
        frozenset({"skip_in_test"}),
    ),
    (
        "PY-SUPPRESS",
        "type/lint suppression; fix the cause instead of silencing the checker",
        re.compile(r"type:\s*ignore|noqa|pylint:\s*disable|mypy:\s*ignore-errors"),
        frozenset(),
    ),
    (
        "PY-BARE-EXCEPT",
        "bare or BaseException except; catch the narrowest exception type",
        re.compile(r"\bexcept\s*(?::|BaseException\b)"),
        frozenset(),
    ),
    (
        "PY-ASSERT",
        "assert as runtime validation in shipped code (stripped under -O); raise a typed error",
        re.compile(r"^\s*assert\b"),
        frozenset({"skip_in_test"}),
    ),
    (
        "PY-DEBUG",
        "debugger invocation left in code; remove breakpoint()/set_trace()",
        re.compile(r"\bbreakpoint\s*\(|\bset_trace\s*\("),
        frozenset(),
    ),
    (
        "PY-EVAL",
        "eval()/exec() executes dynamic code; restructure so data is never executable "
        "(ast.literal_eval for literals)",
        re.compile(r"(?<![\w.])(?:eval|exec)\s*\("),
        frozenset(),
    ),
    (
        "PY-SHELL",
        "command line goes through a shell; pass an argument list to subprocess "
        "without shell=True",
        re.compile(r"\bshell\s*=\s*True\b|\bos\.(?:system|popen)\s*\("),
        frozenset(),
    ),
    (
        "PY-PICKLE",
        "pickle deserialization executes arbitrary code on untrusted input; "
        "use a data-only format or justify the trusted source",
        re.compile(r"\bpickle\.(?:loads?\s*\(|Unpickler\b)"),
        frozenset(),
    ),
    (
        "PY-YAML-LOAD",
        "yaml.load can instantiate arbitrary objects; use yaml.safe_load",
        re.compile(r"\byaml\.(?:unsafe_|full_)?load(?:_all)?\s*\("),
        frozenset(),
    ),
    (
        "PY-MKTEMP",
        "tempfile.mktemp is a create-after-name race; use mkstemp / "
        "NamedTemporaryFile / TemporaryDirectory",
        re.compile(r"\bmktemp\s*\("),
        frozenset(),
    ),
    (
        "PY-UTCNOW",
        "naive-UTC datetime (deprecated since 3.12); use "
        "datetime.now(timezone.utc) / fromtimestamp(..., tz=...)",
        re.compile(r"\butc(?:now|fromtimestamp)\s*\("),
        frozenset(),
    ),
    (
        "PY-TLS-NOVERIFY",
        "TLS certificate verification disabled; keep verification on and fix "
        "the trust store instead",
        re.compile(
            r"\bverify\s*=\s*False\b|\bcheck_hostname\s*=\s*False\b|_create_unverified_context"
        ),
        frozenset(),
    ),
]

KNOWN_CODES = frozenset(code for code, _, _, _ in _CHECKS)

# A justified, single-rule, line-scoped `# noqa: <RULE> -- <reason>` is the
# sanctioned way to hold a documented upstream limitation of one lint rule
# and is NOT a PY-SUPPRESS finding: it must name exactly one rule code (a
# comma — the multi-rule form — breaks the match), and everything after the
# mandatory ` -- ` is its non-empty written justification, consumed to end
# of line. Type-level suppressions (`type: ignore`) have no such escape.
_JUSTIFIED_LINE_DISABLE = re.compile(
    r"noqa:[ \t]*[A-Z][A-Z0-9]+[ \t]+--[ \t]+\S.*"
)

# String literal prefixes (any order/case): r, b, f, u and combinations.
_STRING_PREFIX_RE = re.compile(r"^[rbfuRBFU]{1,3}$")

# --- Lexical masking ---------------------------------------------------------


def mask_source(text: str) -> tuple[list[str], list[str]]:
    """Split *text* into parallel per-line views preserving columns.

    Returns ``(code_lines, comment_lines)``:

    * ``code_lines`` — only executable code; comments and the contents of
      string literals are blanked, f-string interpolation code (``{...}``)
      is kept;
    * ``comment_lines`` — only comment text (without the ``#`` delimiter);
      everything else is blanked.

    Blanking replaces characters with spaces, so line numbers and columns in
    findings match the original source.
    """
    code_lines: list[str] = []
    comment_lines: list[str] = []
    code_buf: list[str] = []
    comment_buf: list[str] = []

    # Frame stack: ["code", brace_depth] | ["fstring", quote, triple].
    # Plain strings and comments are flat states on top of the innermost
    # frame; f-strings are frames because interpolations nest code inside.
    frames: list[list] = [["code", 0]]
    state = "code"  # code|comment|string|fstring
    str_quote = ""
    str_triple = False
    last_word = ""  # last identifier token seen in code (for string prefixes)
    word_open = False  # True while last_word is still being extended

    def flush_line() -> None:
        code_lines.append("".join(code_buf))
        comment_lines.append("".join(comment_buf))
        code_buf.clear()
        comment_buf.clear()

    def emit(code_ch: str, comment_ch: str) -> None:
        code_buf.append(code_ch)
        comment_buf.append(comment_ch)

    def innermost_fstring_is_single_line() -> bool:
        for frame in reversed(frames):
            if frame[0] == "fstring":
                return not frame[2]
        return False

    def pop_unterminated_fstring() -> None:
        # Drop the innermost single-line f-string frame and everything
        # nested inside it (interpolation code frames).
        while frames[-1][0] != "fstring":
            frames.pop()
        frames.pop()

    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if ch == "\n":
            # Single-line states cannot span a newline.
            if state == "comment":
                state = "code" if frames[-1][0] == "code" else "fstring"
            elif state == "string" and not str_triple:
                state = "code" if frames[-1][0] == "code" else "fstring"
            if state in ("code", "fstring") and innermost_fstring_is_single_line():
                pop_unterminated_fstring()
                state = "code" if frames[-1][0] == "code" else "fstring"
            last_word, word_open = "", False
            flush_line()
            i += 1
            continue

        if state == "comment":
            emit(" ", ch)
            i += 1
            continue

        if state == "string":
            if ch == "\\":
                emit(" ", " ")
                if nxt and nxt != "\n":
                    emit(" ", " ")
                    i += 2
                    continue
                i += 1
                continue
            if ch == str_quote and (
                not str_triple or text[i : i + 3] == str_quote * 3
            ):
                span = 3 if str_triple else 1
                for _ in range(span):
                    emit(" ", " ")
                state = "code" if frames[-1][0] == "code" else "fstring"
                if state == "code":
                    last_word, word_open = "", False
                i += span
                continue
            emit(" ", " ")
            i += 1
            continue

        if state == "fstring":
            quote, triple = frames[-1][1], frames[-1][2]
            if ch == "\\":
                emit(" ", " ")
                if nxt and nxt != "\n":
                    emit(" ", " ")
                    i += 2
                    continue
                i += 1
                continue
            if ch == "{" and nxt == "{":
                emit(" ", " ")
                emit(" ", " ")
                i += 2
                continue
            if ch == "}" and nxt == "}":
                emit(" ", " ")
                emit(" ", " ")
                i += 2
                continue
            if ch == "{":
                emit(" ", " ")
                frames.append(["code", 0])
                state = "code"
                last_word, word_open = "", False
                i += 1
                continue
            if ch == quote and (not triple or text[i : i + 3] == quote * 3):
                span = 3 if triple else 1
                for _ in range(span):
                    emit(" ", " ")
                frames.pop()
                state = "code" if frames[-1][0] == "code" else "fstring"
                if state == "code":
                    last_word, word_open = "", False
                i += span
                continue
            emit(" ", " ")
            i += 1
            continue

        # state == "code"
        if ch == "#":
            state = "comment"
            emit(" ", " ")
            i += 1
            continue
        if ch in ("'", '"'):
            triple = text[i : i + 3] == ch * 3
            is_fstring = (
                word_open
                and _STRING_PREFIX_RE.match(last_word) is not None
                and "f" in last_word.lower()
            )
            span = 3 if triple else 1
            for _ in range(span):
                emit(" ", " ")
            if is_fstring:
                frames.append(["fstring", ch, triple])
                state = "fstring"
            else:
                state = "string"
                str_quote = ch
                str_triple = triple
            i += span
            continue
        if ch == "{":
            frames[-1][1] += 1
            emit(ch, " ")
            last_word, word_open = "", False
            i += 1
            continue
        if ch == "}":
            if frames[-1][1] == 0 and len(frames) > 1:
                # Close of an f-string interpolation: back into the literal.
                frames.pop()
                state = "fstring"
                emit(" ", " ")
                i += 1
                continue
            frames[-1][1] = max(0, frames[-1][1] - 1)
            emit(ch, " ")
            last_word, word_open = "", False
            i += 1
            continue

        emit(ch, " ")
        if ch.isspace():
            word_open = False  # the word ends but stays the last token
        elif ch.isalnum() or ch == "_":
            last_word = last_word + ch if word_open else ch
            word_open = True
        else:
            last_word, word_open = "", False
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
    if "PY-SUPPRESS" in codes:
        errors.append(f"{where}: PY-SUPPRESS can never be suppressed; fix the suppression instead")
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
            # type: ignore/noqa live in comments, so PY-SUPPRESS scans the
            # comment view; every other rule scans only executable code.
            # Justified single-rule noqa disables are cut out first — what
            # remains (a blanket/multi-rule/unjustified form, or a type-level
            # suppression on the same line) is still a finding.
            if code == "PY-SUPPRESS":
                target = _JUSTIFIED_LINE_DISABLE.sub("", comment_line)
            else:
                target = code_line
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
            files.extend(sorted(q for q in p.rglob("*") if q.suffix in PY_SUFFIXES))
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
