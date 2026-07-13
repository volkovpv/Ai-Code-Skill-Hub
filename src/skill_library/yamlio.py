"""Minimal safe YAML subset parser and emitter (stdlib only).

The library deliberately avoids third-party YAML dependencies so that the
CLI and the tests run on a bare Python installation. This module implements
only the narrow subset of YAML that the library files actually use:

* nested mappings with 2-space indentation;
* block lists (``- item``), including list items that are mappings;
* flow lists of scalars (``[a, b]``) and the empty forms ``[]`` / ``{}``;
* scalars: plain / single-quoted / double-quoted strings, integers, floats,
  ``true``/``false``, ``null``/``~``;
* full-line and trailing ``#`` comments (outside quotes).

Anchors, aliases, tags, flow mappings, multi-line strings and multi-document
streams are rejected with :class:`YamlError`. Parsing never constructs
arbitrary objects, so it is safe on untrusted input.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["YamlError", "loads", "dumps", "load_file", "dump_file"]

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
# Strings matching this pattern (and passing extra checks) may be emitted
# without quotes.
_PLAIN_RE = re.compile(r"^[A-Za-z0-9._/+][A-Za-z0-9 ._/+:@=-]*$")
_RESERVED_PLAIN = {"null", "Null", "NULL", "~", "true", "True", "TRUE", "false", "False", "FALSE"}


class YamlError(ValueError):
    """Raised when input does not conform to the supported YAML subset."""


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------

def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment that is outside of quotes."""
    out: list[str] = []
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if quote == '"' and ch == "\\" and i + 1 < len(line):
                out.append(line[i : i + 2])
                i += 2
                continue
            if ch == quote:
                quote = ""
            out.append(ch)
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1] in " \t"):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _scan_lines(text: str) -> list[tuple[int, str, int]]:
    lines: list[tuple[int, str, int]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        indent_part = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in indent_part:
            raise YamlError(f"line {lineno}: tabs are not allowed in indentation")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip(), lineno))
    return lines


def _unquote_double(s: str, lineno: int) -> str:
    body = s[1:-1]
    out: list[str] = []
    i = 0
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            if i + 1 >= len(body) or body[i + 1] not in escapes:
                raise YamlError(f"line {lineno}: unsupported escape sequence")
            out.append(escapes[body[i + 1]])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_flow_list(s: str, lineno: int) -> list:
    inner = s[1:-1].strip()
    if not inner:
        return []
    items: list[str] = []
    buf: list[str] = []
    quote = ""
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[]{}":
            raise YamlError(f"line {lineno}: nested flow collections are not supported")
        elif ch == ",":
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if quote:
        raise YamlError(f"line {lineno}: unterminated quote in flow list")
    items.append("".join(buf).strip())
    # Fail closed: an empty element ("[a,,b]", "[a,]") is a typo, not data.
    if any(item == "" for item in items):
        raise YamlError(f"line {lineno}: empty item in flow list")
    return [_parse_scalar(item, lineno) for item in items]


def _parse_scalar(s: str, lineno: int):
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s.startswith("[") and s.endswith("]"):
        return _parse_flow_list(s, lineno)
    if s.startswith("{"):
        raise YamlError(f"line {lineno}: flow mappings are not supported")
    if s.startswith('"'):
        if len(s) < 2 or not s.endswith('"'):
            raise YamlError(f"line {lineno}: unterminated double-quoted string")
        return _unquote_double(s, lineno)
    if s.startswith("'"):
        if len(s) < 2 or not s.endswith("'"):
            raise YamlError(f"line {lineno}: unterminated single-quoted string")
        return s[1:-1].replace("''", "'")
    if s[0] in "&*!|>":
        raise YamlError(f"line {lineno}: unsupported YAML feature: {s[0]!r}")
    if s in ("null", "Null", "NULL", "~"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if _INT_RE.match(s):
        # A zero-padded token (e.g. "007", an ID or index) is a string in the
        # YAML 1.2 core schema; coercing it to int would silently drop the
        # padding and lose the original value irreversibly.
        digits = s.lstrip("-")
        if len(digits) > 1 and digits[0] == "0":
            return s
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _split_key(text: str, lineno: int) -> tuple[str, str]:
    """Split a ``key: value`` line into (key, rest). Raises if not a mapping line."""
    if text[0] in "\"'":
        quote = text[0]
        i = 1
        while i < len(text):
            if quote == '"' and text[i] == "\\":
                i += 2
                continue
            if text[i] == quote:
                break
            i += 1
        if i >= len(text):
            raise YamlError(f"line {lineno}: unterminated quoted key")
        key = _parse_scalar(text[: i + 1], lineno)
        rest = text[i + 1 :].lstrip()
        if not rest.startswith(":"):
            raise YamlError(f"line {lineno}: expected ':' after quoted key")
        return str(key), rest[1:].strip()
    idx = -1
    for m in re.finditer(":", text):
        j = m.start()
        if j + 1 == len(text) or text[j + 1] == " ":
            idx = j
            break
    if idx < 0:
        raise YamlError(f"line {lineno}: expected 'key: value'")
    key = text[:idx].strip()
    if not key:
        raise YamlError(f"line {lineno}: empty mapping key")
    return key, text[idx + 1 :].strip()


class _Parser:
    def __init__(self, lines: list[tuple[int, str, int]]):
        self.lines = lines
        self.i = 0

    def peek(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse_block(self, indent: int):
        _, text, _ = self.lines[self.i]
        if text == "-" or text.startswith("- "):
            return self.parse_list(indent)
        return self.parse_map(indent)

    def parse_value(self, rest: str, indent: int, lineno: int):
        if rest:
            return _parse_scalar(rest, lineno)
        nxt = self.peek()
        if nxt is not None and nxt[0] > indent:
            return self.parse_block(nxt[0])
        return None

    def parse_map(self, indent: int, first: tuple[str, str, int] | None = None) -> dict:
        result: dict = {}
        if first is not None:
            key, rest, lineno = first
            result[key] = self.parse_value(rest, indent, lineno)
        while True:
            cur = self.peek()
            if cur is None:
                break
            ind, text, lineno = cur
            if ind < indent:
                break
            if ind > indent:
                raise YamlError(f"line {lineno}: unexpected indentation")
            if text == "-" or text.startswith("- "):
                raise YamlError(f"line {lineno}: unexpected list item inside mapping")
            key, rest = _split_key(text, lineno)
            if key in result:
                raise YamlError(f"line {lineno}: duplicate key {key!r}")
            self.i += 1
            result[key] = self.parse_value(rest, indent, lineno)
        return result

    def parse_list(self, indent: int) -> list:
        items: list = []
        while True:
            cur = self.peek()
            if cur is None:
                break
            ind, text, lineno = cur
            if ind < indent:
                break
            if ind > indent:
                raise YamlError(f"line {lineno}: unexpected indentation")
            if not (text == "-" or text.startswith("- ")):
                raise YamlError(f"line {lineno}: expected list item")
            rest = "" if text == "-" else text[2:].strip()
            self.i += 1
            if not rest:
                nxt = self.peek()
                if nxt is not None and nxt[0] > indent:
                    items.append(self.parse_block(nxt[0]))
                else:
                    items.append(None)
                continue
            try:
                key, r2 = _split_key(rest, lineno)
                first = (key, r2, lineno)
            except YamlError:
                first = None
            if first is None:
                items.append(_parse_scalar(rest, lineno))
            else:
                # List items that are mappings continue at indent + 2
                # (aligned under the first key after "- ").
                items.append(self.parse_map(indent + 2, first=first))
        return items


def loads(text: str):
    """Parse a YAML-subset document into dicts/lists/scalars."""
    lines = _scan_lines(text)
    if not lines:
        return {}
    if lines[0][0] != 0:
        raise YamlError(f"line {lines[0][2]}: top-level content must not be indented")
    parser = _Parser(lines)
    result = parser.parse_block(0)
    if parser.i < len(parser.lines):
        _, _, lineno = parser.lines[parser.i]
        raise YamlError(f"line {lineno}: unexpected content after document")
    return result


def load_file(path: Path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # A binary or mis-encoded file must not crash callers with a bare
        # UnicodeDecodeError; surface it as a YamlError they already handle.
        raise YamlError(f"file is not valid UTF-8 ({exc})") from exc
    return loads(text)


# ----------------------------------------------------------------------------
# Emitting
# ----------------------------------------------------------------------------

def _is_scalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def _fmt_str(s: str) -> str:
    if "\r" in s:
        raise YamlError("carriage returns are not supported in strings")
    if (
        s
        and "\n" not in s
        and _PLAIN_RE.match(s)
        and not s.endswith(" ")
        and ": " not in s
        and " #" not in s
        and s not in _RESERVED_PLAIN
        and not _INT_RE.match(s)
        and not _FLOAT_RE.match(s)
    ):
        return s
    escaped = (
        s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _fmt_scalar(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    return _fmt_str(v)


def _dump_map(d: dict, indent: int, lines: list[str]) -> None:
    pad = "  " * indent
    for k, v in d.items():
        key = _fmt_str(str(k))
        if _is_scalar(v):
            lines.append(f"{pad}{key}: {_fmt_scalar(v)}")
        elif isinstance(v, dict):
            if not v:
                lines.append(f"{pad}{key}: {{}}")
            else:
                lines.append(f"{pad}{key}:")
                _dump_map(v, indent + 1, lines)
        elif isinstance(v, (list, tuple)):
            if not v:
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}:")
                _dump_list(list(v), indent + 1, lines)
        else:
            raise YamlError(f"unsupported value type: {type(v).__name__}")


def _dump_list(items: list, indent: int, lines: list[str]) -> None:
    pad = "  " * indent
    for item in items:
        if _is_scalar(item):
            lines.append(f"{pad}- {_fmt_scalar(item)}")
        elif isinstance(item, dict) and item:
            sub: list[str] = []
            _dump_map(item, indent + 1, sub)
            lines.append(f"{pad}- {sub[0][len(pad) + 2:]}")
            lines.extend(sub[1:])
        else:
            raise YamlError("unsupported list item type (empty dicts and nested lists are not supported)")


def dumps(data) -> str:
    lines: list[str] = []
    if isinstance(data, dict):
        if not data:
            return "{}\n"
        _dump_map(data, 0, lines)
    elif isinstance(data, list):
        if not data:
            return "[]\n"
        _dump_list(data, 0, lines)
    else:
        raise YamlError("top-level value must be a mapping or a list")
    return "\n".join(lines) + "\n"


def dump_file(path: Path, data) -> None:
    Path(path).write_text(dumps(data), encoding="utf-8")
