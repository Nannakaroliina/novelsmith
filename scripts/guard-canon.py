#!/usr/bin/env python3
"""PreToolUse guard for Write/Edit/MultiEdit, Bash and MCP tools in a novelsmith book project.

Rules, enforced here because plugin agents cannot carry their own hooks:

1. Author-owned text: every heading containing ⚓ (with its body, HTML comments
   included) in any book file, every other line containing ⚓ (so an indented,
   underlined or quoted "heading" cannot pass as a decision), book.waivers in
   outline/scenes.yaml, and the genre/structure settings of bible/premise.md.
   A subagent changing one is denied; in the main conversation the author is
   asked to confirm. A new file may carry only the ⚓ lines the templates have.
2. Write scopes: each novelsmith agent may write only its own files under
   book/ (AGENT_SCOPES) and nothing outside book/; a novelsmith agent missing
   from AGENT_SCOPES may write nothing. Any other subagent may not write under
   book/bible/. A subagent's edit must match the file exactly (the Edit tool
   otherwise matches curly quotes loosely, so the result cannot be predicted).
3. Shell, for subagents in a book project: a novelsmith agent may run exactly
   one command, the outline validator; any other subagent may run only a short
   list of read-only commands written without shell syntax. Everything else is
   denied: shell commands can write files these rules never see, and guessing
   from a command's text what it will touch cannot be made complete. The main
   conversation's shell is left to Claude Code's own permission prompts.
4. MCP tools: a subagent's MCP call that names a path inside book/ is denied
   (a filesystem server's write tools bypass rules 1 and 2); subagents read
   book files with Read, Glob and Grep.

The guard decides in linear time with its own deadline (DEADLINE seconds, below
the hook's 10 s timeout, kept by a watchdog thread on every platform) and size
caps, because a hook that times out lets the call through. Line endings are
normalised the way the readers see them, and
paths are compared case-insensitively, because macOS and Windows treat
book/Bible and book/bible as the same folder.

Reads the hook input JSON (UTF-8) on stdin; prints a hookSpecificOutput decision
(ASCII) or nothing. If the guard cannot check a subagent's call, it is denied;
the main conversation fails open (exit 1, non-blocking) so a bug never locks the
author out.
"""

import fnmatch
import json
import os
import re
import shlex
import sys
import threading
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
TEMPLATES = HERE.parent / "templates"
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
DEADLINE = 6.0
MAX_CHARS = 1_000_000
MAX_LINE = 20_000
MAX_PATH = 4096
SHELL_META = re.compile(r"[;&|<>$`\\\n\r(){}\[\]*?!~#]")
SAFE_READS = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "stat", "file", "diff"}

_decided = threading.Lock()  # held once a decision is printed, so a late second one is dropped


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
    return ns_book.normalize(path.read_text(encoding="utf-8", errors="surrogateescape")) if path.is_file() else ""


def edits_of(tool, inp):
    if tool == "Write":
        return []
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    return [{k: ns_book.normalize(v) if isinstance(v, str) else v for k, v in e.items()} for e in edits or []]


def apply_edits(old, tool, inp):
    """The file as it would be after the tool call (None if it would outgrow MAX_CHARS), and whether every
    old_string matched exactly. Growth is computed before replacing, so a huge replace_all is never built."""
    if tool == "Write":
        return ns_book.normalize(inp.get("content", "")), True
    new, exact = old, True
    for e in edits_of(tool, inp):
        a, b = e.get("old_string", ""), e.get("new_string", "")
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeError("old_string and new_string must be text")
        if a == "":
            if new.strip() == "":
                new = b  # Edit with an empty old_string fills an empty or new file
            continue
        count = new.count(a) if e.get("replace_all") else int(a in new)
        if not count:
            exact = False  # the real tool may still match (it normalises curly quotes)
            continue
        if len(new) + count * (len(b) - len(a)) > MAX_CHARS:
            return None, exact
        new = new.replace(a, b) if e.get("replace_all") else new.replace(a, b, 1)
    return new, exact


def too_big(text):
    return len(text) > MAX_CHARS or any(len(line) > MAX_LINE for line in text.split("\n"))


def anchors(text):
    """Comparable form of every ⚓ section: heading plus whitespace-normalised body, comments kept."""
    return [(" ".join(h.split()), " ".join(body.split())) for h, body in ns_book.anchored_sections(text)]


def visible_anchors(text):
    """The same, as the author sees it: a ⚓ section wrapped in a comment disappears from this view."""
    return anchors(ns_book.strip_html_comments(text))


def has_content(sections):
    return any(ns_book.strip_html_comments(body).strip() for _, body in sections)


def anchor_lines(text):
    """Every line containing ⚓, as written (indentation kept): the symbol marks author text wherever it is."""
    return sorted(line.rstrip() for line in text.split("\n") if ns_book.ANCHOR in line)


def template_anchor_lines():
    """The ⚓ lines a file copied from a template may start with (e.g. the empty '## ⚓ Anchored' heading)."""
    lines = set()
    for p in TEMPLATES.glob("*"):
        if p.is_file():
            lines.update(anchor_lines(read(p)))
    return lines


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
    if _decided.acquire(blocking=False):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }}), flush=True)
    return 0


def is_validator_command(command, cwd):
    """True only for: python3 <this plugin's validate-outline.py> --book <dir> [--json], with no shell syntax."""
    if SHELL_META.search(command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if len(argv) not in (4, 5) or argv[0] != "python3" or argv[2] != "--book" or argv[4:] not in ([], ["--json"]):
        return False
    script = Path(argv[1]) if os.path.isabs(argv[1]) else cwd / argv[1]
    try:
        return script.resolve().samefile(VALIDATOR)
    except OSError:
        return False


def is_simple_read(command):
    """A command from SAFE_READS with plain arguments: no globs, variables, redirections or chaining."""
    if SHELL_META.search(command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    return bool(argv) and argv[0] in SAFE_READS


def check_bash(command, agent, ours, short, cwd, book_root):
    if not agent:
        return 0  # the author's own shell: Claude Code's permission prompts apply
    if ours:
        if not is_validator_command(command, cwd):
            return decide("deny", f"novelsmith: {short} may run only the outline validator "
                                  f"(python3 \"{VALIDATOR}\" --book book [--json]) with no other shell syntax. "
                                  f"Use the Write and Edit tools for files.")
        return 0
    if book_root.is_dir() and not is_simple_read(command):
        return decide("deny", "novelsmith: in a book project, subagents may run only simple read-only commands "
                              f"({', '.join(sorted(SAFE_READS))}) without shell syntax; the canon guard cannot check "
                              "what other commands change. Use the Read, Write and Edit tools.")
    return 0


def strings_in(node, limit=10_000):
    """The short one-line strings anywhere in a tool input (where an MCP tool would name its paths)."""
    stack, out = [node], []
    while stack and len(out) < limit:
        x = stack.pop()
        if isinstance(x, dict):
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str) and 0 < len(x) <= MAX_PATH and "\n" not in x:
            out.append(x)
    return out


def check_mcp(tool, inp, agent, cwd, book_root):
    if not agent or not book_root.is_dir():
        return 0  # the author's own MCP calls: Claude Code's permission prompts apply
    root = book_root.resolve()
    for s in strings_in(inp):
        raw = s[len("file://"):] if s.startswith("file://") else s
        try:
            path = Path(raw) if os.path.isabs(raw) else cwd / raw
            rel = book_relative(path.resolve(), root)
        except (OSError, ValueError, RuntimeError):
            continue
        if rel is not None:
            return decide("deny", f"novelsmith: subagents may not use {tool} on book files ({s}); the canon guard "
                                  "cannot check what it changes. Use the Read, Glob, Grep, Write and Edit tools.")
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
    if tool.startswith("mcp__"):
        return check_mcp(tool, inp, agent, cwd, book_root)

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
    if agent and (new is None or too_big(old) or too_big(new)):
        return decide("deny", f"novelsmith: book/{rel} would be larger than the canon guard checks "
                              f"({MAX_CHARS:,} characters, lines up to {MAX_LINE:,}); split the content.")
    if agent and not exact:
        return decide("deny", f"novelsmith: an old_string does not match book/{rel} exactly (check quotes and "
                              f"spacing), so the change cannot be checked. Read the file and copy the text exactly.")

    if new is None:
        return decide("ask", f"novelsmith: this edit would make book/{rel} larger than the canon guard checks "
                             f"({MAX_CHARS:,} characters). Allow it only if you asked for this change.")

    problems = []
    if rel == SCENES:
        before, bad_old = waivers_of(old)
        after, bad_new = waivers_of(new)
        if bad_new:
            if agent:
                problems.append(f"book/{rel}, which {bad_new} after this change, so its waivers cannot be checked")
        elif bad_old:
            # An unreadable old file may be repaired, unless it has waivers: the repair could not be
            # compared with them, so it might drop or alter the author's.
            if after or "waivers" in old:
                problems.append(f"the book.waivers block of book/{rel} (the current file cannot be read, so the "
                                f"author's waivers in it cannot be compared; the author repairs this file)")
        elif before != after:
            problems.append(f"the book.waivers block of book/{rel}")
    old_anchors, new_anchors = anchors(old), anchors(new)
    old_lines, new_lines = anchor_lines(old), anchor_lines(new)
    lines_changed = old_lines != new_lines if exists else bool(set(new_lines) - template_anchor_lines())
    sections_changed = old_anchors != new_anchors or visible_anchors(old) != visible_anchors(new)
    if lines_changed or (sections_changed and (exists or has_content(new_anchors))):
        problems.append(f"⚓ text in book/{rel}")
    if rel == PREMISE:
        before_s, after_s = ns_book.book_settings(old), ns_book.book_settings(new)
        changed = [key for key in before_s if before_s[key] and before_s[key] != after_s[key]]
        if changed:
            problems.append(f"the {', '.join(changed)} setting of book/{rel}")
    protected = rel in (SCENES, PREMISE) or ns_book.ANCHOR in old or any(
        ns_book.ANCHOR in str(e.get("new_string", "")) for e in edits_of(tool, inp))
    if not exact and protected:
        problems.append(f"book/{rel} with an old_string that does not match the file exactly, so it cannot be checked")

    if not problems:
        return 0
    what = "; ".join(problems)
    if agent:
        hint = (" Agents never write the ⚓ symbol; refer to \"the anchored section\" in words."
                if any(p.startswith("⚓") for p in problems) else "")
        return decide("deny", f"novelsmith: this would change {what}. Those are the author's decisions; agents never "
                              f"change them. Report the tension or write the proposal in book/proposals/.{hint}")
    return decide("ask", f"novelsmith: this changes {what}, which holds your decisions as the author. "
                         f"Allow it only if you asked for this change.")


def run(payload):
    """main() on a watchdog: past DEADLINE the call counts as unchecked, on every platform."""
    result = {}

    def work():
        try:
            result["code"] = main(payload)
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(DEADLINE)
    if worker.is_alive():
        raise TimeoutError(f"took longer than {DEADLINE:g} s")
    if "error" in result:
        raise result["error"]
    return result["code"]


if __name__ == "__main__":
    payload = {}
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        code = run(payload)
    except Exception as exc:
        tool = payload.get("tool_name", "") if isinstance(payload, dict) else ""
        guarded = tool in WRITE_TOOLS + ("Bash",) or str(tool).startswith("mcp__")
        if isinstance(payload, dict) and payload.get("agent_type") and guarded:
            # A subagent's call that cannot be checked is denied, not waved through.
            decide("deny", f"novelsmith: the canon guard could not check this call ({type(exc).__name__}: {exc}), "
                           f"so it is denied for subagents.")
            os._exit(0)  # a worker still running must not print after this
        print(f"guard-canon: {exc}", file=sys.stderr, flush=True)  # the author's own call fails open
        os._exit(1)
    sys.exit(code)
