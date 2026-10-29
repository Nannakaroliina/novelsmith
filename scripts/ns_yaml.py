"""Load the YAML that novelsmith's book files use, with or without PyYAML.

PyYAML is used when it is installed. Otherwise a small parser handles the subset
the templates use: block mappings and sequences, flow lists and maps on one line,
quoted and plain scalars, numbers, booleans, null, and | / > block scalars.
Anything outside that subset raises YAMLError with a line number, so the author
learns to install PyYAML rather than getting a silently wrong manifest.
"""

import json
import re

try:
    import yaml as _pyyaml
except ImportError:  # pragma: no cover - depends on the machine
    _pyyaml = None


class YAMLError(ValueError):
    def __init__(self, message, line=None):
        self.line = line
        super().__init__(f"line {line}: {message}" if line else message)


def load(text):
    if _pyyaml is not None:
        try:
            return _pyyaml.safe_load(text)
        except _pyyaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            raise YAMLError(str(exc), mark.line + 1 if mark else None) from exc
    return _Parser(text).parse()


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


def _strip_comment(s):
    """Drop a trailing # comment that is outside quotes."""
    quote, prev = None, None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and _opens_quote(prev):
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
        if ch not in " \t":
            prev = ch
    return s.rstrip()


def _split_top(s, sep):
    """Split on sep outside quotes and brackets."""
    parts, depth, quote, cur, prev = [], 0, None, [], None
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            prev = ch
            continue
        if ch not in " \t":
            was, prev = prev, ch
        else:
            cur.append(ch)
            continue
        if ch in "\"'" and _opens_quote(was):
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return parts


def _key_split(s):
    """Return (key, rest) if s is 'key: value' or 'key:', else None."""
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            if i == 0:
                quote = ch
        elif ch in "[{" and i == 0:
            return None
        elif ch == ":" and (i + 1 == len(s) or s[i + 1] == " "):
            key = s[:i].strip()
            if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
                key = key[1:-1]
            return key, s[i + 1:].strip()
    return None


def _scalar(raw, line):
    s = raw.strip()
    if s == "":
        return None
    if s[0] == "[":
        if not s.endswith("]"):
            raise YAMLError("multi-line flow lists need PyYAML (pip install pyyaml)", line)
        inner = s[1:-1].strip()
        return [] if not inner else [_scalar(p, line) for p in _split_top(inner, ",")]
    if s[0] == "{":
        if not s.endswith("}"):
            raise YAMLError("multi-line flow maps need PyYAML (pip install pyyaml)", line)
        inner = s[1:-1].strip()
        out = {}
        for part in ([] if not inner else _split_top(inner, ",")):
            kv = _key_split(part.strip())
            if kv is None:
                raise YAMLError(f"cannot read flow map entry {part.strip()!r}", line)
            out[kv[0]] = _scalar(kv[1], line)
        return out
    if s[0] == '"':
        if not s.endswith('"') or len(s) < 2:
            raise YAMLError("unterminated double-quoted string", line)
        try:
            return json.loads(s)
        except ValueError:
            return s[1:-1]
    if s[0] == "'":
        if not s.endswith("'") or len(s) < 2:
            raise YAMLError("unterminated single-quoted string", line)
        return s[1:-1].replace("''", "'")
    if s in ("~", "null", "Null", "NULL"):
        return None
    if s in _BOOLS:
        return _BOOLS[s]
    if _INT.match(s):
        return _to_int(s)
    if _FLOAT.match(s):
        return _to_float(s)
    if s[0] in "&*!%@`":
        raise YAMLError(f"YAML feature {s[0]!r} needs PyYAML (pip install pyyaml)", line)
    if ": " in s or s.endswith(":"):
        raise YAMLError("mapping values are not allowed here; quote a value that contains ': '", line)
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

    def _block(self, indent):
        line = self._peek()
        if line[2] == "-" or line[2].startswith("- "):
            return self._seq(indent)
        if _key_split(line[2]) is not None:
            return self._map(indent)
        self.i += 1
        return _scalar(line[2], line[0])

    def _seq(self, indent):
        out = []
        while True:
            line = self._peek()
            if line is None or line[1] != indent or not (line[2] == "-" or line[2].startswith("- ")):
                break
            n, _, content, raw = line
            item = content[1:].strip()
            if item == "":
                self.i += 1
                nxt = self._peek()
                out.append(self._block(nxt[1]) if nxt and nxt[1] > indent else None)
            elif _key_split(item) is not None:
                # "- key: value" opens a mapping indented to where "key" starts.
                col = indent + (len(content) - len(item))
                self.lines[self.i] = (n, col, item, raw)
                out.append(self._map(col))
            else:
                self.i += 1
                out.append(_scalar(item, n))
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
                out[key] = _scalar(rest, n)
        return out

    def _block_scalar(self, indent, header, lineno):
        folded = header[0] == ">"
        chomp = header[1:].strip()
        body, block_indent = [], None
        while self.i < len(self.lines):
            n, ind, content, raw = self.lines[self.i]
            if ind is not None and ind <= indent:
                break
            if ind is not None and block_indent is None:
                block_indent = ind
            body.append(raw[block_indent:] if block_indent is not None and raw.strip() else "")
            self.i += 1
        while body and body[-1] == "":
            body.pop()
        text = " ".join(body) if folded else "\n".join(body)
        return text if chomp == "-" else text + "\n"
