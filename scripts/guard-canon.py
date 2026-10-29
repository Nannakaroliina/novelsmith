#!/usr/bin/env python3
"""PreToolUse guard for Write/Edit/MultiEdit under book/, and Bash for novelsmith agents.

Rules, enforced here because plugin agents cannot carry their own hooks:

1. Author-owned regions: every heading containing ⚓ (with its body, HTML
   comments included) in any book file, and book.waivers in
   outline/scenes.yaml. A subagent changing one is denied; in the main
   conversation the author is asked to confirm.
2. Write scopes: each novelsmith agent may write only its own files
   (AGENT_SCOPES); a novelsmith agent missing from AGENT_SCOPES may write
   nothing under book/. Any other subagent may not write under book/bible/.
3. Shell: a novelsmith agent may run exactly one command, the outline
   validator; any other Bash call is denied (shell writes would skip rules 1-2).

Paths are compared case-insensitively, because macOS and Windows treat
book/Bible and book/bible as the same folder.

Reads the hook input JSON on stdin; prints a hookSpecificOutput decision or nothing.
Fails open (exit 1, non-blocking) on its own errors so a bug never locks the author out.
"""

import fnmatch
import json
import os
import re
import shlex
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ns_book  # noqa: E402
import ns_yaml  # noqa: E402

AGENT_SCOPES = {
    "story-architect": ["bible/premise.md", "outline/acts.md", "proposals/*"],
    "character-designer": ["bible/characters/*", "proposals/*"],
    "worldbuilder": ["bible/world/*", "bible/timeline.md", "proposals/*"],
    "outliner": ["outline/*", "bible/clues.md", "bible/timeline.md", "proposals/*", "critiques/outline/*"],
}
CANON = ["bible/*"]
SCENES = "outline/scenes.yaml"
VALIDATOR = HERE / "validate-outline.py"
SHELL_META = re.compile(r"[;&|<>$`\\\n\r(){}*?!~]")


def fold(s):
    return unicodedata.normalize("NFC", s).casefold()


def book_relative(path, book_root):
    """Path of `path` inside book/ (casefolded, posix), or None when it is outside."""
    p, root = fold(path.as_posix()), fold(book_root.as_posix()).rstrip("/")
    if p == root:
        return ""
    if p.startswith(root + "/"):
        return p[len(root) + 1:]
    return None


def read(path):
    return path.read_text(encoding="utf-8", errors="surrogateescape") if path.is_file() else ""


def apply_edits(old, tool, inp):
    """The file as it would be after the tool call, and whether every old_string matched exactly."""
    if tool == "Write":
        return inp.get("content", ""), True
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    new, exact = old, True
    for e in edits or []:
        a, b = e.get("old_string", ""), e.get("new_string", "")
        if a == "":
            if new.strip() == "":
                new = b  # Edit with an empty old_string fills an empty or new file
            continue
        if a not in new:
            exact = False  # the real tool may still match (it normalises curly quotes)
            continue
        new = new.replace(a, b) if e.get("replace_all") else new.replace(a, b, 1)
    return new, exact


def anchors(text):
    """Comparable form of every ⚓ section: heading plus whitespace-normalised body, comments kept."""
    return [(" ".join(h.split()), " ".join(body.split())) for h, body in ns_book.anchored_sections(text)]


def has_content(sections):
    return any(ns_book.strip_html_comments(body).strip() for _, body in sections)


def stray_waivers(node, where=()):
    """True if a 'waivers' key appears anywhere except book.waivers (a decoy for a human reader)."""
    if isinstance(node, dict):
        return any((k == "waivers" and where != ("book",)) or stray_waivers(v, where + (k,))
                   for k, v in node.items())
    if isinstance(node, list):
        return any(stray_waivers(x, where + ("[]",)) for x in node)
    return False


def waivers_of(text):
    """(waivers, problem): book.waivers as parsed data, or a reason it cannot be read safely."""
    if not text.strip():
        return {}, None
    try:
        data = ns_yaml.load(text)
    except ns_yaml.YAMLError as exc:
        return None, f"does not parse ({exc})"
    if not isinstance(data, dict):
        return None, "is not a mapping"
    if stray_waivers(data):
        return None, "has a 'waivers' key outside book"
    book = data.get("book") or {}
    if not isinstance(book, dict):
        return None, "has a 'book' that is not a mapping"
    return book.get("waivers") or {}, None


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))
    return 0


def is_validator_command(command, cwd):
    """True only for: python3 <this plugin's validate-outline.py> --book <dir> [--json]."""
    if SHELL_META.search(command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if len(argv) not in (4, 5) or argv[0] != "python3" or argv[2] != "--book":
        return False
    if len(argv) == 5 and argv[4] != "--json":
        return False
    script = Path(argv[1]) if os.path.isabs(argv[1]) else cwd / argv[1]
    try:
        return script.resolve().samefile(VALIDATOR)
    except OSError:
        return False


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)

    agent = (data.get("agent_type") or "").strip()
    short = agent.split(":")[-1] if agent else ""
    ours = agent.startswith("novelsmith:") or (short in AGENT_SCOPES and ":" not in agent)

    # Rule 3: novelsmith agents get the validator and nothing else from the shell.
    if tool == "Bash":
        if ours and not is_validator_command(inp.get("command", ""), cwd):
            return decide("deny", f"novelsmith: {short} may run only the outline validator "
                                  f"(python3 \"{VALIDATOR}\" --book book [--json]) with no other shell syntax. "
                                  f"Use the Write and Edit tools for files.")
        return 0

    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    raw = inp.get("file_path")
    if not raw:
        return 0
    path = (cwd / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    rel = book_relative(path, (project / "book").resolve())
    if rel is None:
        return 0

    # Rule 2: write scopes for subagents.
    if agent:
        scopes = AGENT_SCOPES.get(short) if ours else None
        if ours and scopes is None:
            return decide("deny", f"novelsmith: agent {agent} has no write scope registered in guard-canon.py "
                                  f"AGENT_SCOPES, so it may not write under book/.")
        if scopes is not None and not any(fnmatch.fnmatchcase(rel, g) for g in scopes):
            return decide("deny", f"novelsmith: {short} may write only {', '.join('book/' + g for g in scopes)}; "
                                  f"book/{rel} belongs to another stage. Write a proposal in book/proposals/ instead.")
        if scopes is None and any(fnmatch.fnmatchcase(rel, g) for g in CANON):
            return decide("deny", f"novelsmith: book/{rel} is canon. Only the bible stage agents (or the author in the "
                                  f"main conversation) edit book/bible/. Propose the change in book/proposals/.")

    # Rule 1: author-owned regions.
    exists = path.is_file()
    old = read(path)
    new, exact = apply_edits(old, tool, inp)
    if not exists and not agent:
        return 0  # the author creating a file (novel-start) owns everything in it

    problems = []
    if rel == SCENES:
        before, bad_old = waivers_of(old)
        after, bad_new = waivers_of(new)
        if bad_new:
            if agent:
                problems.append(f"book/{rel} {bad_new} after this change, so its waivers cannot be checked")
        elif (after if bad_old else before != after):
            # An unreadable old file may be repaired, as long as the repair adds no waivers.
            problems.append(f"the book.waivers block of book/{rel}")
    old_anchors, new_anchors = anchors(old), anchors(new)
    if old_anchors != new_anchors and (exists or has_content(new_anchors)):
        problems.append(f"a ⚓ section of book/{rel}")
    protected = rel == SCENES or bool(old_anchors)
    if not exact and protected:
        problems.append(f"book/{rel}, which holds author-owned text, with an old_string that does not match the file "
                        f"exactly, so the change cannot be checked")

    if not problems:
        return 0
    what = "; ".join(problems)
    if agent:
        return decide("deny", f"novelsmith: this would change {what}. Those are the author's decisions; agents never "
                              f"change them. Report the tension or write the proposal in book/proposals/.")
    return decide("ask", f"novelsmith: this changes {what}, which records the author's decisions. "
                         f"Allow only if the author asked for this change.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open: a guard bug must not lock the author out
        print(f"guard-canon: {exc}", file=sys.stderr)
        sys.exit(1)
