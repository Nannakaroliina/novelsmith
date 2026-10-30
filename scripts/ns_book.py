"""Shared readers for the author's book/ files.

The canon guard and the outline validator must agree on what counts as an
author-owned region and on what the premise settings say, so both import these
helpers instead of keeping their own parsing.

Everything here runs in linear time on adversarial input (no backtracking
regexes over whole lines), because the guard must decide well inside its hook
timeout, and works on text whose line endings went through normalize().
"""

import re
import unicodedata

ANCHOR = "⚓"
BOOK_SETTINGS = ("Base genre", "Subgenre / variant", "Structural model")
_PLACEHOLDER = re.compile(r"\((?:e\.g\.|eg|for example)[^)]*\)|\{\{[^}]*\}\}", re.I)
_ANCHOR_REF = re.compile(r"&#(?:0*9875|x0*2693);?|:anchor:", re.I)
_QUOTE_MARKS = re.compile(r"(?: {0,3}>)* {0,3}")
_SETEXT = re.compile(r" {0,3}(?:=+|-+)[ \t]*$")
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)$")
_LIST_ITEM = re.compile(r"(?:[-*+]|[0-9]{1,9}[.)])(?:[ \t]|$)")
_BREAK = re.compile(r"(?:-[ \t]*){3,}$|(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$")
_HIDDEN = {"Cc", "Cf", "Mn", "Me", "Zs", "Zl", "Zp"}


def normalize(text):
    """Line endings as Python's read_text() and Markdown renderers see them: \\r\\n and \\r become \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode_anchor(text):
    """⚓ written another way Markdown shows as the symbol (&#9875;, &#x2693;, :anchor:) is ⚓."""
    return _ANCHOR_REF.sub(ANCHOR, text) if "&#" in text or ":" in text else text


def strip_html_comments(text):
    """Remove <!-- … --> comments; an unclosed <!-- hides the rest of the file, as it does in Markdown."""
    out, i = [], 0
    while True:
        start = text.find("<!--", i)
        if start == -1:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:start])
        end = text.find("-->", start + 4)
        if end == -1:
            return "".join(out)
        i = end + 3


def _atx(line):
    """(level, title) of an ATX heading as CommonMark reads it (up to three spaces in, inside > quotes too)."""
    s = line[_QUOTE_MARKS.match(line).end():]
    hashes = len(s) - len(s.lstrip("#"))
    if 1 <= hashes <= 6 and s[hashes:hashes + 1] in ("", " ", "\t"):
        return hashes, s[hashes:].strip(" \t").rstrip("#").rstrip(" \t")
    return None


def _paragraph_line(line):
    """A line that starts or continues a plain paragraph, which a --- or === line below turns into a heading."""
    s = line.lstrip(" ")
    return (bool(s.strip()) and len(line) - len(s) <= 3 and s[0] not in ">|<`~"
            and not _LIST_ITEM.match(s) and not _BREAK.match(s) and _atx(line) is None)


def _opens_fence(match):
    return match and not (match.group(1)[0] == "`" and "`" in match.group(2))


def _closes_fence(match, fence):
    return match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip()


def headings(text):
    """ATX and setext headings as (level, title, start, end, text, clear), in order. A setext heading spans its
    paragraph and underline; nothing inside a ``` or ~~~ fence is a heading.

    clear is True only where every Markdown reader shows a heading that starts a new section: an ATX heading
    at the margin, or a setext heading whose paragraph starts at the margin after a blank line or a heading
    (not a list item's wrapped line). Indented, quoted and other setext headings may open a ⚓ section, but
    only clear ones end one, so a ⚓ section never ends early.
    """
    out, pos, para, fence, fresh = [], 0, None, None, True  # para: (start, lines, clear); fresh: after a break
    for line in text.split("\n"):
        end = pos + len(line)
        mark = _FENCE.match(line)
        if fence:
            if _closes_fence(mark, fence):
                fence = None
            fresh = False
        elif _opens_fence(mark):
            fence, para, fresh = mark.group(1), None, False
        elif _atx(line):
            level, title = _atx(line)
            out.append((level, title, pos, end, line, line.startswith("#")))
            para, fresh = None, True
        elif para and _SETEXT.match(line):
            title = " ".join(part.strip() for part in para[1])
            out.append((1 if "=" in line else 2, title, para[0], end, "\n".join(para[1] + [line]), para[2]))
            para, fresh = None, True
        elif para and (_paragraph_line(line) or line.startswith("    ")):
            para[1].append(line)
        elif _paragraph_line(line):
            para, fresh = (pos, [line], fresh and line[:1] not in " \t"), False
        else:
            para, fresh = None, not line.strip()
        pos = end + 1
    return out


def _visible(title):
    """True if a heading title shows anything (an empty or invisible heading does not end a ⚓ section)."""
    return any(unicodedata.category(ch) not in _HIDDEN for ch in strip_html_comments(title))


def anchored_sections(text):
    """Every heading containing ⚓ with its body, in order: [(heading line, body)].

    A body runs to the next clear heading (see headings()) or ⚓ heading of the
    same or a higher level, so ### subsections stay inside their ⚓ section.
    Headings inside HTML comments are included on purpose: a commented-out ⚓
    block is still author text, and a decoy hidden in a comment must count as a
    change. A heading that shows nothing (## alone, or only a comment) does not
    end a section unless it holds ⚓. One backward pass, so the work stays linear.
    """
    text = decode_anchor(text)
    heads = headings(text)
    nearest, ends = [len(text)] * 7, [len(text)] * len(heads)  # nearest[k]: next section end for level k
    for i in range(len(heads) - 1, -1, -1):
        level, title, start, _, _, clear = heads[i]
        ends[i] = nearest[level]
        if ANCHOR in title or (clear and _visible(title)):  # what a ⚓ heading ends is still in its own section
            for k in range(level, 7):
                nearest[k] = start
    return [(line.strip(), text[line_end:ends[i]])
            for i, (_, title, _, line_end, line, _) in enumerate(heads) if ANCHOR in title]


def anchor_lines(text, markdown=True):
    """Every line containing ⚓, in order and as written, each with its place: the nearest line above it that is
    less indented, or for a line at the margin the nearest heading above it (comment-only lines never count as a
    place). So moving a ⚓ line to another scene or section is a change, as rewording it is. A ⚓ heading has no
    place: the section comparison covers it. In YAML (markdown=False) no line is a heading."""
    text = decode_anchor(text)
    heads = headings(text) if markdown else []
    comment = "<!--" if markdown else "#"
    out, parents, place, k, pos = [], [], "", 0, 0  # parents: (indent, line) of the open lines above
    for line in text.split("\n"):
        start, pos = pos, pos + len(line) + 1
        while k < len(heads) and heads[k][3] < start:
            k += 1
        if not line.strip():
            continue
        line = line.rstrip()
        if k < len(heads) and heads[k][2] <= start:
            if ANCHOR in line:
                out.append(("", line))
            place, parents = " ".join(heads[k][4].split()), []
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        while parents and parents[-1][0] >= indent:
            parents.pop()
        if ANCHOR in line:
            out.append((parents[-1][1] if parents else place, line))
        if not line.lstrip(" \t").startswith(comment):
            parents.append((indent, line))
    return out


def anchored_text(text):
    """The author's anchored decisions as plain text, comments removed (for reading, not comparing)."""
    return "\n".join(body for _, body in anchored_sections(strip_html_comments(text)))


def section(md, heading_title):
    """Text of the first ## section whose title starts with heading_title, up to the next ## heading."""
    want = heading_title.casefold()
    heads = [h for h in headings(md) if h[0] == 2 and h[5]]
    for i, (_, title, _, line_end, _, _) in enumerate(heads):
        if title.casefold().startswith(want):
            end = heads[i + 1][2] if i + 1 < len(heads) else len(md)
            return md[line_end:end]
    return ""


def field(md, label):
    """Value of the first '- Label: value' line, ignoring template placeholders like '(e.g. …)' and '{{x}}'."""
    want = label.casefold()
    for line in md.split("\n"):
        s = line.lstrip(" \t")
        if s[:1] in ("-", "*"):
            s = s[1:].lstrip(" \t")
        if not s.casefold().startswith(want):
            continue
        rest = s[len(label):].lstrip(" \t")
        if not rest.startswith(":"):
            continue
        value = rest[1:].strip(" \t")
        if value:
            return _PLACEHOLDER.sub("", value).strip(" \t-")
    return ""


def book_setting(premise, label):
    """A premise.md setting as written: the author's ⚓ sections win; otherwise the visible (comment-free) text."""
    return field(anchored_text(premise), label) or field(strip_html_comments(premise), label)


def fold_setting(value):
    """Compatibility-folded, case-folded, single-spaced: 'myſtery' and 'MYSTERY' both become 'mystery'."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def book_settings(premise):
    """The premise settings exactly as the validator acts on them. The guard compares these same values."""
    structure = fold_setting(book_setting(premise, "Structural model")).split(" ")[0] if book_setting(
        premise, "Structural model") else ""
    structure = "".join(ch for ch in unicodedata.normalize("NFKD", structure) if not unicodedata.combining(ch))
    return {
        "genre": fold_setting(book_setting(premise, "Base genre")),
        "variant": fold_setting(book_setting(premise, "Subgenre / variant")),
        "structure": re.sub(r"[\W_]+", "_", structure).strip("_"),
    }
