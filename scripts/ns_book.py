"""Shared readers for the author's book/ files.

The canon guard and the outline validator must agree on what counts as an
author-owned region, so both import these helpers instead of keeping their
own regexes.
"""

import re

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.M)
ANCHOR = "⚓"
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def strip_html_comments(text):
    return COMMENT_RE.sub("", text)


def anchored_sections(text):
    """Every heading containing ⚓ with its body, in order: [(heading line, body)].

    A body runs to the next heading of the same or a higher level, so ###
    subsections stay inside their ⚓ section. Headings inside HTML comments are
    included on purpose: a commented-out ⚓ block is still author text, and a
    decoy hidden in a comment must count as a change.
    """
    heads = list(HEADING_RE.finditer(text))
    out = []
    for i, m in enumerate(heads):
        if ANCHOR not in m.group(2):
            continue
        level = len(m.group(1))
        end = len(text)
        for nxt in heads[i + 1:]:
            if len(nxt.group(1)) <= level:
                end = nxt.start()
                break
        out.append((m.group(0).strip(), text[m.end():end]))
    return out


def anchored_text(text):
    """The author's anchored decisions as plain text, comments removed (for reading, not comparing)."""
    visible = strip_html_comments(text)
    return "\n".join(body for _, body in anchored_sections(visible))


def section(md, heading_pattern):
    """Text of the first ## section whose heading matches, up to the next ## heading."""
    m = re.search(r"^##\s+" + heading_pattern + r".*$", md, re.M | re.I)
    if not m:
        return ""
    rest = md[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


BOOK_SETTINGS = ("Base genre", "Subgenre / variant", "Structural model")


def book_setting(premise, label):
    """A premise.md setting: the author's ⚓ sections win; otherwise the visible (comment-free) text."""
    return field(anchored_text(premise), label) or field(strip_html_comments(premise), label)


def field(md, label):
    """Value of a '- Label: value' line, ignoring template placeholders like '(e.g. …)' and '{{x}}'."""
    m = re.search(r"^[ \t]*[-*]?[ \t]*" + re.escape(label) + r"[ \t]*:[ \t]*(\S.*)$", md, re.M | re.I)
    if not m:
        return ""
    value = re.sub(r"\((?:e\.g\.|eg|for example)[^)]*\)|\{\{[^}]*\}\}", "", m.group(1), flags=re.I)
    return value.strip(" \t-")
