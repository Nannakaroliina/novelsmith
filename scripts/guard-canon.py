#!/usr/bin/env python3
"""PreToolUse guard for Write/Edit/MultiEdit and Bash in a novelsmith book project.

Rules, enforced here because plugin agents cannot carry their own hooks:

1. Author-owned text: every heading containing ⚓ (with its body, HTML comments
   included) in any book file, book.waivers in outline/scenes.yaml, and the
   genre/structure settings of bible/premise.md. A subagent changing one is
   denied; in the main conversation the author is asked to confirm.
2. Write scopes: each novelsmith agent may write only its own files under
   book/ (AGENT_SCOPES) and nothing outside book/; a novelsmith agent missing
   from AGENT_SCOPES may write nothing. Any other subagent may not write under
   book/bible/.
3. Shell: a novelsmith agent may run exactly one command, the outline
   validator. Other subagents may not run shell commands that touch book/.
   In the main conversation the author is asked before inline code
   (python3 -c, sh -c, …) or a shell command that could change book/.
   (Shell writes would otherwise skip rules 1-2.)

Paths are compared case-insensitively, because macOS and Windows treat
book/Bible and book/bible as the same folder.

Reads the hook input JSON on stdin; prints a hookSpecificOutput decision or nothing.
If the guard itself fails, a subagent's call is denied (it cannot be checked);
the main conversation fails open (exit 1, non-blocking) so a bug never locks
the author out.
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
PREMISE = "bible/premise.md"
VALIDATOR = HERE / "validate-outline.py"
SELFCHECK = HERE / "selfcheck.py"
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
SHELL_META = re.compile(r"[;&|<>$`\\\n\r(){}*?!~]")
OPERATORS = {";", "&&", "||", "|", "&", "(", ")"}
REDIRECTS = re.compile(r"^\d*(>>?|<>|>&|&>|<<<?|<)")
INTERPRETER = re.compile(r"^(python[0-9.]*|perl|ruby|node|deno|bun|php|osascript|sh|bash|zsh|dash|fish|ksh)$")
INLINE_FLAGS = {"-c", "-e", "-E", "--eval", "-", "-r"}
READ_ONLY = {"ls", "cat", "head", "tail", "wc", "grep", "egrep", "rg", "stat", "file", "less", "more", "diff",
             "tree", "du", "pwd", "true", "cd"}
READ_ONLY_GIT = {"status", "diff", "log", "show", "ls-files", "blame"}


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


def new_strings(tool, inp):
    if tool == "Write":
        return [inp.get("content", "")]
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    return [e.get("new_string", "") for e in edits or []]


def anchors(text):
    """Comparable form of every ⚓ section: heading plus whitespace-normalised body, comments kept."""
    return [(" ".join(h.split()), " ".join(body.split())) for h, body in ns_book.anchored_sections(text)]


def visible_anchors(text):
    """The same, as the author sees it: a ⚓ section wrapped in a comment disappears from this view."""
    return anchors(ns_book.strip_html_comments(text))


def setting(premise, label):
    """A premise setting as the validator reads it; the structural model is its first word."""
    value = fold(ns_book.book_setting(premise, label))
    return value.split(" ")[0] if label == "Structural model" else " ".join(value.split())


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
        if not isinstance(data, dict):
            return None, "is not a mapping"
        if stray_waivers(data):
            return None, "has a 'waivers' key outside book"
    except Exception as exc:  # any failure means the waivers cannot be checked
        return None, f"cannot be read safely ({exc})"
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


def is_script_command(command, cwd, script, extra):
    """True only for: python3 <this plugin's script> <extra args>, with no other shell syntax."""
    if SHELL_META.search(command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if len(argv) < 2 or argv[0] != "python3" or not extra(argv[2:]):
        return False
    target = Path(argv[1]) if os.path.isabs(argv[1]) else cwd / argv[1]
    try:
        return target.resolve().samefile(script)
    except OSError:
        return False


def is_validator_command(command, cwd):
    return is_script_command(command, cwd, VALIDATOR,
                             lambda a: a[:1] == ["--book"] and len(a) in (2, 3) and a[2:] in ([], ["--json"]))


def is_selfcheck_command(command, cwd):
    return is_script_command(command, cwd, SELFCHECK, lambda a: a == [])


def shell_words(command):
    """Shell words with operators split out; a rough fallback when the command does not tokenize."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return re.split(r"\s+|(?=[;&|<>()])|(?<=[;&|<>()])", command)


def segments(words):
    seg = []
    for w in words:
        if w in OPERATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(w)
    if seg:
        yield seg


def touches_book(words, cwd, book_root):
    if book_relative(cwd.resolve(), book_root.resolve()) is not None:
        return True
    for w in words:
        for part in w.split("="):
            p = fold(part.strip("'\""))
            if re.search(r"(^|/)book(/|$)", p):
                return True
            if part and (os.path.isabs(part) or "/" in part):
                target = Path(part) if os.path.isabs(part) else cwd / part
                if book_relative(target.resolve(), book_root.resolve()) is not None:
                    return True
    return False


def runs_inline_code(words):
    for seg in segments(words):
        if INTERPRETER.match(os.path.basename(seg[0])) and any(a in INLINE_FLAGS for a in seg[1:]):
            return True
        if "<<" in seg or "<<<" in seg:
            return True
    return False


def read_only(words):
    if any(REDIRECTS.match(w) for w in words):
        return False
    for seg in segments(words):
        cmd = os.path.basename(seg[0])
        if cmd == "git":
            if len(seg) < 2 or seg[1] not in READ_ONLY_GIT:
                return False
        elif cmd == "find":
            if any(a in ("-exec", "-execdir", "-delete", "-ok", "-okdir", "-fprint", "-fprintf", "-fls")
                   for a in seg[1:]):
                return False
        elif cmd not in READ_ONLY:
            return False
    return True


def check_bash(command, agent, ours, short, cwd, book_root):
    if ours:
        if not is_validator_command(command, cwd):
            return decide("deny", f"novelsmith: {short} may run only the outline validator "
                                  f"(python3 \"{VALIDATOR}\" --book book [--json]) with no other shell syntax. "
                                  f"Use the Write and Edit tools for files.")
        return 0
    if not book_root.is_dir() or is_validator_command(command, cwd) or is_selfcheck_command(command, cwd):
        return 0
    words = shell_words(command)
    touches = touches_book(words, cwd, book_root)
    if agent:
        if touches:
            return decide("deny", "novelsmith: subagents may not run shell commands on book/; the canon guard "
                                  "cannot check them. Use the Read, Write and Edit tools.")
        return 0
    if runs_inline_code(words):
        return decide("ask", "novelsmith: this runs inline code in a book project, which the canon guard cannot "
                             "check. Allow it only if you asked for it.")
    if touches and not read_only(words):
        return decide("ask", "novelsmith: this shell command could change files under book/, which the canon "
                             "guard cannot check. Allow it only if you asked for it.")
    return 0


def main(data):
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    book_root = project / "book"

    agent = (data.get("agent_type") or "").strip()
    short = agent.split(":")[-1] if agent else ""
    ours = agent.startswith("novelsmith:") or (short in AGENT_SCOPES and ":" not in agent)

    # Rule 3: the shell.
    if tool == "Bash":
        return check_bash(inp.get("command", ""), agent, ours, short, cwd, book_root)

    if tool not in WRITE_TOOLS:
        return 0
    raw = inp.get("file_path")
    if not raw:
        return 0
    path = (cwd / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    rel = book_relative(path, book_root.resolve())
    if rel is None:
        if ours:
            return decide("deny", f"novelsmith: {short} writes only under book/; {raw} is outside the book.")
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

    # Rule 1: author-owned text.
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
                problems.append(f"book/{rel}, which {bad_new} after this change, so its waivers cannot be checked")
        elif (after if bad_old else before != after):
            # An unreadable old file may be repaired, as long as the repair adds no waivers.
            problems.append(f"the book.waivers block of book/{rel}")
    old_anchors, new_anchors = anchors(old), anchors(new)
    if (old_anchors != new_anchors or visible_anchors(old) != visible_anchors(new)) and (
            exists or has_content(new_anchors)):
        problems.append(f"a ⚓ section of book/{rel}")
    if rel == PREMISE:
        changed = [label for label in ns_book.BOOK_SETTINGS
                   if setting(old, label) and setting(old, label) != setting(new, label)]
        if changed:
            problems.append(f"the {', '.join(changed)} setting of book/{rel}")
    protected = rel in (SCENES, PREMISE) or bool(old_anchors)
    if not exact and (protected or any(ns_book.ANCHOR in s for s in new_strings(tool, inp))):
        problems.append(f"book/{rel} with an old_string that does not match the file exactly, in a change that "
                        f"touches author-owned text, so it cannot be checked")

    if not problems:
        return 0
    what = "; ".join(problems)
    if agent:
        return decide("deny", f"novelsmith: this would change {what}. Those are the author's decisions; agents never "
                              f"change them. Report the tension or write the proposal in book/proposals/.")
    return decide("ask", f"novelsmith: this changes {what}, which holds your decisions as the author. "
                         f"Allow it only if you asked for this change.")


if __name__ == "__main__":
    payload = {}
    try:
        payload = json.load(sys.stdin)
        sys.exit(main(payload))
    except Exception as exc:
        tool = payload.get("tool_name", "") if isinstance(payload, dict) else ""
        if isinstance(payload, dict) and payload.get("agent_type") and tool in WRITE_TOOLS + ("Bash",):
            # A subagent's call that cannot be checked is denied, not waved through.
            decide("deny", f"novelsmith: the canon guard could not check this call ({type(exc).__name__}), "
                           f"so it is denied for subagents.")
            sys.exit(0)
        print(f"guard-canon: {exc}", file=sys.stderr)  # the author's own call fails open
        sys.exit(1)
