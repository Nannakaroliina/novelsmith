"""Load the YAML that novelsmith's book files use, with or without PyYAML.

PyYAML is used when it is installed. Otherwise a small parser handles the subset
the templates use: block mappings and sequences, flow lists and maps on one line
(read in a single pass, so even adversarial input is linear), quoted and plain
scalars, numbers, booleans, null, and | / > block scalars.
Anything outside that subset raises YAMLError with a line number, so the author
learns to install PyYAML rather than getting a silently wrong manifest.

Both paths refuse what book files never need and an adversarial writer could
abuse: anchors and aliases (exponential "alias bombs"), duplicate keys,
non-scalar keys and nesting deeper than MAX_DEPTH. Every failure, including a
parser crash on a strange value, surfaces as YAMLError, never as another
exception; the canon guard relies on that to deny instead of failing open.

Set NOVELSMITH_YAML=fallback to use the built-in parser even when PyYAML is installed.
"""

import json
import os
import re

try:
    import yaml as _pyyaml
except ImportError:  # pragma: no cover - depends on the machine
    _pyyaml = None

MAX_DEPTH = 64
_FORCE_FALLBACK = os.environ.get("NOVELSMITH_YAML") == "fallback"
_CRASHES = (ValueError, TypeError, OverflowError, RecursionError, MemoryError, KeyError, IndexError,
            AttributeError)


class YAMLError(ValueError):
    def __init__(self, message, line=None):
        self.line = line
        super().__init__(f"line {line}: {message}" if line else message)


if _pyyaml is not None:
    class _StrictLoader(_pyyaml.SafeLoader):
        """SafeLoader without anchors, aliases, duplicate or non-scalar keys, or deep nesting."""

        _depth = 0

        def compose_node(self, parent, index):
            event = self.peek_event()
            if isinstance(event, _pyyaml.AliasEvent) or getattr(event, "anchor", None):
                raise _pyyaml.composer.ComposerError(
                    None, None, "anchors (&name) and aliases (*name) are not allowed in book files",
                    event.start_mark)
            self._depth += 1
            try:
                if self._depth > MAX_DEPTH:
                    raise _pyyaml.composer.ComposerError(
                        None, None, f"nested more than {MAX_DEPTH} levels deep", event.start_mark)
                return super().compose_node(parent, index)
            finally:
                self._depth -= 1

        def construct_mapping(self, node, deep=False):
            seen = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError:
                    raise _pyyaml.constructor.ConstructorError(
                        None, None, "a key must be a plain value, not a list or mapping",
                        key_node.start_mark) from None
                if key in seen:
                    raise _pyyaml.constructor.ConstructorError(
                        None, None, f"duplicate key {key!r}", key_node.start_mark)
                seen.add(key)
            return super().construct_mapping(node, deep=deep)


def _describe(exc):
    """One line from a PyYAML error: the problem, its context, and a fix hint where there is one."""
    problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
    context = getattr(exc, "context", None)
    message = f"{problem} ({context})" if context else problem
    if "mapping values are not allowed" in problem:
        message += "; quote a value that contains ': '"
    return message


def _error_line(exc):
    """The line to fix. For an unclosed quote, a key missing its ':' or an unclosed [ … ], PyYAML's problem
    mark is where it gave up (often the end of the file); the context mark is where that value starts."""
    context = getattr(exc, "context", None) or ""
    mark = getattr(exc, "context_mark", None)
    if not (mark and (context.startswith("while scanning a") or context.startswith("while parsing a flow"))):
        mark = getattr(exc, "problem_mark", None)
    return mark.line + 1 if mark else None


def load(text):
    text = text[1:] if text.startswith("\ufeff") else text  # a byte-order mark, which PyYAML skips too
    if _pyyaml is not None and not _FORCE_FALLBACK:
        try:
            return _pyyaml.load(text, Loader=_StrictLoader)
        except _pyyaml.YAMLError as exc:
            raise YAMLError(_describe(exc), _error_line(exc)) from exc
        except _CRASHES as exc:
            raise YAMLError(f"cannot read a value ({type(exc).__name__}: {exc})") from exc
    try:
        return _Parser(text).parse()
    except YAMLError:
        raise
    except _CRASHES as exc:
        raise YAMLError(f"cannot read a value ({type(exc).__name__}: {exc})") from exc


# YAML 1.1 implicit types, as PyYAML's SafeLoader resolves them.
_BOOLS = {v: True for v in ("yes", "Yes", "YES", "true", "True", "TRUE", "on", "On", "ON")}
_BOOLS.update({v: False for v in ("no", "No", "NO", "false", "False", "FALSE", "off", "Off", "OFF")})
_INT = re.compile(r"""^(?:[-+]?0b[0-1_]+
                   |[-+]?0[0-7_]+
                   |[-+]?(?:0|[1-9][0-9_]*)
                   |[-+]?0x[0-9a-fA-F_]+
                   |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$""", re.X)
_FLOAT = re.compile(r"""^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?
                     |\.[0-9_]+(?:[eE][-+][0-9]+)?
                     |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*
                     |[-+]?\.(?:inf|Inf|INF)
                     |\.(?:nan|NaN|NAN))$""", re.X)


_TIMESTAMP = re.compile(r"""^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]
                         |[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?
                          (?:[Tt]|[ \t]+)[0-9][0-9]?:[0-9][0-9]:[0-9][0-9](?:\.[0-9]*)?
                          (?:[ \t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$""", re.X)


def _sexagesimal(s, cast):
    sign = -1 if s[0] == "-" else 1
    value = 0
    for part in s.lstrip("+-").split(":"):
        value = value * 60 + cast(part)
    return sign * value


def _to_int(s):
    s = s.replace("_", "")
    sign, body = (-1, s[1:]) if s[0] == "-" else (1, s.lstrip("+"))
    if body.startswith("0b"):
        return sign * int(body[2:], 2)
    if body.startswith("0x"):
        return sign * int(body[2:], 16)
    if ":" in body:
        return sign * _sexagesimal(body, int)
    if len(body) > 1 and body[0] == "0":
        return sign * int(body, 8)
    return sign * int(body)


def _to_float(s):
    s = s.replace("_", "")
    low = s.lower()
    if low.endswith(".inf"):
        return float("-inf") if s[0] == "-" else float("inf")
    if low == ".nan":
        return float("nan")
    if ":" in s:
        return _sexagesimal(s, float)
    return float(s)


def _opens_quote(prev):
    """A quote character starts a quoted scalar only where a value can start."""
    return prev is None or prev in ":-[{,?"


def _quote_end(s, i):
    """Index of the quote closing the quoted scalar that opens at s[i], or -1.

    Double quotes skip backslash escapes; single quotes treat '' as an escaped quote.
    """
    q, j = s[i], i + 1
    while j < len(s):
        ch = s[j]
        if q == '"' and ch == "\\":
            j += 2
            continue
        if ch == q:
            if q == "'" and s[j + 1:j + 2] == "'":
                j += 2
                continue
            return j
        j += 1
    return -1


def _strip_comment(s):
    """Drop a trailing # comment that is outside quotes."""
    i, prev = 0, None
    while i < len(s):
        ch = s[i]
        if ch in "\"'" and _opens_quote(prev):
            end = _quote_end(s, i)
            if end == -1:
                return s.rstrip()
            i, prev = end + 1, ch
            continue
        if ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
        if ch not in " \t":
            prev = ch
        i += 1
    return s.rstrip()


def _key_text(text, line=None):
    """A key as PyYAML would read it, or YAMLError."""
    key = _scalar(text, line) if text[:1] in "\"'" else text
    if text[:1] not in "\"'" and (text in ("<<", "=") or _scalar(text, line) != text):
        raise YAMLError(f"quote the key {text!r}; PyYAML would not read it as text", line)
    if not isinstance(key, str):
        raise YAMLError(f"keys must be text, got {text!r}", line)
    return key


def _key_split(s):
    """Return (key, rest) if s is 'key: value' or 'key:', else None. Keys read like PyYAML's or raise."""
    i = 0
    if s[:1] in "\"'":
        i = _quote_end(s, 0)
        if i == -1:
            return None
        i += 1
    elif s[:1] in "[{":
        return None
    while i < len(s):
        if s[i] == ":" and (i + 1 == len(s) or s[i + 1] == " "):
            return _key_text(s[:i].strip()), s[i + 1:].strip()
        i += 1
    return None


_FLOW_STOP = ",[]{}"


def _skip_space(s, i):
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


def _flow(s, line, depth):
    """A [ … ] or { … } value written on one line, read in a single pass (linear in its length)."""
    value, i = _flow_node(s, 0, line, depth)
    if _skip_space(s, i) != len(s):
        raise YAMLError(f"unexpected text after the closing bracket: {s[i:].strip()!r}", line)
    return value


def _flow_node(s, i, line, depth):
    if depth > MAX_DEPTH:
        raise YAMLError(f"nested more than {MAX_DEPTH} levels deep", line)
    ch = s[i] if i < len(s) else ""
    if ch and ch in "[{":
        close, out = ("]", []) if ch == "[" else ("}", {})
        i = _skip_space(s, i + 1)
        while True:
            if i >= len(s):
                raise YAMLError("put this [ … ] list on one line, or write it as '- item' lines" if ch == "[" else
                                "put this { … } map on one line, or write it as 'key: value' lines", line)
            if s[i] == close:
                return out, i + 1
            if ch == "[":
                item, i = _flow_node(s, i, line, depth + 1)
                out.append(item)
            else:
                key, i = _flow_key(s, i, line)
                if key in out:
                    raise YAMLError(f"duplicate key {key!r}", line)
                out[key], i = _flow_node(s, _skip_space(s, i), line, depth + 1)
            i = _skip_space(s, i)
            if i < len(s) and s[i] == ",":
                i = _skip_space(s, i + 1)  # a comma before the closing bracket is allowed, as in PyYAML
            elif i < len(s) and s[i] != close:
                raise YAMLError(f"expected ',' or '{close}' in {s.strip()!r}", line)
    if ch and ch in "\"'":
        end = _quote_end(s, i)
        if end == -1:
            raise YAMLError("unterminated quoted string", line)
        return _scalar(s[i:end + 1], line, depth), end + 1
    j = i
    while j < len(s) and s[j] not in _FLOW_STOP:
        j += 1
    text = s[i:j].strip()
    if not text:
        raise YAMLError(f"empty item in {s.strip()!r}", line)
    return _scalar(text, line, depth), j


def _flow_key(s, i, line):
    """The key of a flow map entry starting at s[i], and the index after its ':'."""
    if s[i] in "\"'":
        end = _quote_end(s, i)
        if end == -1:
            raise YAMLError("unterminated quoted key", line)
        text, j = s[i:end + 1], _skip_space(s, end + 1)
        if j >= len(s) or s[j] != ":":
            raise YAMLError(f"expected ':' after the key {text}", line)
        return _key_text(text, line), j + 1
    j = i
    while j < len(s) and not (s[j] == ":" and (j + 1 == len(s) or s[j + 1] in " \t" + _FLOW_STOP)):
        if s[j] in _FLOW_STOP:
            raise YAMLError(f"cannot read flow map entry {s[i:j + 1].strip()!r}", line)
        j += 1
    text = s[i:j].strip()
    if j >= len(s) or not text:
        raise YAMLError(f"cannot read flow map entry {s[i:].strip()!r}", line)
    return _key_text(text, line), j + 1


def _scalar(raw, line, depth=1):
    """A value on one line; depth is how deeply this value is nested (refused past MAX_DEPTH)."""
    s = raw.strip()
    if depth > MAX_DEPTH:
        raise YAMLError(f"nested more than {MAX_DEPTH} levels deep", line)
    if s == "":
        return None
    if s[0] in "[{":
        return _flow(s, line, depth)
    if s[0] in "\"'" and _quote_end(s, 0) != len(s) - 1:
        if _quote_end(s, 0) == -1:
            raise YAMLError("unterminated quoted string", line)
        raise YAMLError("text after the closing quote; inside single quotes write an apostrophe as '' "
                        "(e.g. 'Don''t'), or use double quotes", line)
    if s[0] == '"':
        try:
            value = json.loads(s)
        except ValueError:
            raise YAMLError("this double-quoted string uses an escape the built-in parser cannot read; "
                            "use single quotes or install PyYAML", line) from None
        if not isinstance(value, str):
            raise YAMLError("unterminated double-quoted string", line)
        return value
    if s[0] == "'":
        return s[1:-1].replace("''", "'")
    if s in ("~", "null", "Null", "NULL"):
        return None
    if s in _BOOLS:
        return _BOOLS[s]
    if _INT.match(s):
        return _to_int(s)
    if _FLOAT.match(s):
        return _to_float(s)
    if s[0] in "&*":
        raise YAMLError("anchors (&name) and aliases (*name) are not allowed in book files", line)
    if s[0] in "!%@`":
        raise YAMLError(f"remove the YAML tag or directive starting with {s[0]!r}, or quote the value", line)
    if ": " in s or s.endswith(":"):
        raise YAMLError("mapping values are not allowed here; quote a value that contains ': '", line)
    if _TIMESTAMP.match(s):
        raise YAMLError(f"quote dates and times, e.g. \"{s}\" (PyYAML would read this as a date)", line)
    return s


class _Parser:
    def __init__(self, text):
        self.lines = []  # (lineno, indent, content, raw)
        for n, raw in enumerate(text.splitlines(), 1):
            if "\t" in raw[: len(raw) - len(raw.lstrip())]:
                raise YAMLError("tabs are not allowed for indentation", n)
            content = _strip_comment(raw)
            if content.strip() in ("", "---"):
                self.lines.append((n, None, "", raw))
                continue
            self.lines.append((n, len(content) - len(content.lstrip()), content.strip(), raw))
        self.i = 0

    def _skip_blank(self):
        while self.i < len(self.lines) and self.lines[self.i][1] is None:
            self.i += 1

    def _peek(self):
        self._skip_blank()
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse(self):
        first = self._peek()
        if first is None:
            return None
        value = self._block(first[1])
        rest = self._peek()
        if rest is not None:
            raise YAMLError("unexpected indentation", rest[0])
        return value

    _depth = 0

    def _block(self, indent):
        line = self._peek()
        self._depth += 1
        try:
            if self._depth > MAX_DEPTH:
                raise YAMLError(f"nested more than {MAX_DEPTH} levels deep", line[0])
            if line[2] == "-" or line[2].startswith("- "):
                return self._seq(indent)
            if _key_split(line[2]) is not None:
                return self._map(indent)
            self.i += 1
            return _scalar(line[2], line[0], self._depth)
        finally:
            self._depth -= 1

    def _seq(self, indent):
        out = []
        while True:
            line = self._peek()
            if line is None or line[1] != indent or not (line[2] == "-" or line[2].startswith("- ")):
                break
            n, _, content, raw = line
            item = content[1:].strip()
            if item == "-" or item.startswith("- "):
                raise YAMLError("a list inside a list on one line ('- - x') needs PyYAML; "
                                "put the inner list on its own indented lines", n)
            if item == "":
                self.i += 1
                nxt = self._peek()
                out.append(self._block(nxt[1]) if nxt and nxt[1] > indent else None)
            elif _key_split(item) is not None:
                # "- key: value" opens a mapping indented to where "key" starts.
                col = indent + (len(content) - len(item))
                self.lines[self.i] = (n, col, item, raw)
                out.append(self._block(col))
            else:
                self.i += 1
                out.append(_scalar(item, n, self._depth + 1))
        return out

    def _map(self, indent):
        out = {}
        while True:
            line = self._peek()
            if line is None or line[1] < indent:
                break
            n, ind, content, _ = line
            if ind > indent:
                raise YAMLError("unexpected indentation", n)
            if content == "-" or content.startswith("- "):
                break
            kv = _key_split(content)
            if kv is None:
                raise YAMLError(f"expected 'key: value', got {content!r}", n)
            key, rest = kv
            if key in out:
                raise YAMLError(f"duplicate key {key!r}", n)
            self.i += 1
            if rest == "":
                nxt = self._peek()
                if nxt and nxt[1] > indent:
                    out[key] = self._block(nxt[1])
                elif nxt and nxt[1] == indent and (nxt[2] == "-" or nxt[2].startswith("- ")):
                    out[key] = self._seq(indent)
                else:
                    out[key] = None
            elif rest[0] in "|>":
                out[key] = self._block_scalar(indent, rest, n)
            else:
                out[key] = _scalar(rest, n, self._depth + 1)
        return out

    def _block_scalar(self, indent, header, lineno):
        """| and > scalars, read from the raw lines: a '#' inside the block is text, not a comment."""
        if header.strip() not in ("|", "|-", ">", ">-"):
            raise YAMLError(f"block scalar header {header.strip()!r} needs PyYAML; use | or > (optionally with -)",
                            lineno)
        folded, strip = header[0] == ">", header.strip().endswith("-")
        body, block_indent = [], None
        while self.i < len(self.lines):
            n, _, _, raw = self.lines[self.i]
            if raw.strip():
                raw_indent = len(raw) - len(raw.lstrip())
                if raw_indent <= indent:
                    break
                if block_indent is None:
                    block_indent = raw_indent
                elif raw_indent < block_indent:
                    raise YAMLError("a line in this block is less indented than its first line", n)
                line = raw[block_indent:]
                if folded and line[:1] in (" ", "\t"):
                    raise YAMLError("more-indented lines inside a > block need PyYAML; use |", n)
                body.append(line)
            else:
                body.append("")
            self.i += 1
        while body and body[-1] == "":
            body.pop()
        if not body:
            return ""
        if folded:
            text, blanks = "", 0
            for line in body:
                if line == "":
                    blanks += 1
                    continue
                text = line if not text and not blanks else text + ("\n" * blanks if blanks else " ") + line
                blanks = 0
        else:
            text = "\n".join(body)
        return text if strip else text + "\n"
