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


def normalize(text):
    """Line endings as Python's read_text() and Markdown renderers see them: \\r\\n and \\r become \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_html_comments(text):
    """Remove <!-- … --> comments; an unclosed <!-- is left as it is."""
    out, i = [], 0
    while True:
        start = text.find("<!--", i)
        if start == -1:
            out.append(text[i:])
            return "".join(out)
        end = text.find("-->", start + 4)
        if end == -1:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:start])
        i = end + 3


def headings(text):
    """ATX headings as (level, title, line start, line end, line text), in order."""
    out, pos = [], 0
    for line in text.split("\n"):
        hashes = len(line) - len(line.lstrip("#"))
        if 1 <= hashes <= 6 and line[hashes:hashes + 1] in (" ", "\t"):
            title = line[hashes:].strip(" \t").rstrip("#").rstrip(" \t")
            out.append((hashes, title, pos, pos + len(line), line))
        pos += len(line) + 1
    return out


def anchored_sections(text):
    """Every heading containing ⚓ with its body, in order: [(heading line, body)].

    A body runs to the next heading of the same or a higher level, so ###
    subsections stay inside their ⚓ section. Headings inside HTML comments are
    included on purpose: a commented-out ⚓ block is still author text, and a
    decoy hidden in a comment must count as a change.
    """
    heads = headings(text)
    out = []
    for i, (level, title, _, line_end, line) in enumerate(heads):
        if ANCHOR not in title:
            continue
        end = len(text)
        for nxt in heads[i + 1:]:
            if nxt[0] <= level:
                end = nxt[2]
                break
        out.append((line.strip(), text[line_end:end]))
    return out


def anchored_text(text):
    """The author's anchored decisions as plain text, comments removed (for reading, not comparing)."""
    return "\n".join(body for _, body in anchored_sections(strip_html_comments(text)))


def section(md, heading_title):
    """Text of the first ## section whose title starts with heading_title, up to the next ## heading."""
    want = heading_title.casefold()
    heads = [h for h in headings(md) if h[0] == 2]
    for i, (_, title, _, line_end, _) in enumerate(heads):
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
