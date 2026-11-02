#!/usr/bin/env python3
"""PreToolUse guard for Write/Edit/MultiEdit, Bash and MCP tools in a novelsmith book project.

Rules, enforced here because plugin agents cannot carry their own hooks:

1. Author-owned text: every heading containing ⚓ (with its body, HTML comments
   included) in any book file, every other line containing ⚓ (in its place:
   moving it, reordering it or hiding it in a comment is a change), ⚓ written
   as &#9875;, book.waivers in outline/scenes.yaml, and the genre/structure
   settings of bible/premise.md. A subagent changing one is denied; in the
   main conversation the author is asked to confirm. A new file may carry only
   the templates' own ⚓ lines and sections (NEW_FILE_ANCHOR_*).
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
4. MCP tools, for subagents in a book project: only tools whose names say they
   read (read_file, list_directory, search_issues) and name no change. A
   filesystem or shell server's other tools would bypass rules 1-3, and which
   paths a tool touches cannot be read reliably from its arguments. PowerShell
   and notebook edits under book/ are denied to subagents the same way.

A book project is a book/ folder holding progress.md or outline/scenes.yaml
(what novel-start writes); another tool's book/ folder is left alone. A path
reaches the book however it is spelled (case, symlinks, macOS firmlinks).

The checks run in a child process that is killed at DEADLINE seconds (below the
hook's 10 s timeout), because a hook that times out lets the call through and a
thread cannot interrupt one long C call; the author's own write to the book is
then asked about, never waved through. Size caps keep the work linear. Line
endings are normalised the way the readers see them; a subagent's edit whose
carriage returns could make the real tool match other text is denied. Paths are compared
case-insensitively, because macOS and Windows treat book/Bible and book/bible
as the same folder.

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
import stat
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ns_book  # noqa: E402

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
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
NOTEBOOK_TOOL = "NotebookEdit"
# Tools that only read, ask, plan or report back, which subagents may use freely. Any other tool a subagent
# calls in a book project, including ones Claude Code adds later (a scheduler whose prompt later runs as the
# author, say), is checked (rules 1-4) or denied, since the guard cannot see what it changes.
SAFE_TOOLS = {"Read", "Glob", "Grep", "LS", "LSP", "NotebookRead", "TodoWrite", "TodoRead", "TaskCreate",
              "TaskUpdate", "TaskList", "TaskGet", "WebFetch", "WebSearch", "Skill", "ToolSearch", "AskUserQuestion",
              "Agent", "Task", "TaskOutput", "BashOutput", "KillShell", "KillBash", "TaskStop", "SendMessage",
              "SubagentHandback", "StructuredOutput", "ListMcpResourcesTool", "ReadMcpResourceTool",
              "EnterPlanMode", "ExitPlanMode"}
YAML_BREAKS = re.compile("[\x85\u2028\u2029]")  # line breaks to YAML that the guard's line view does not split on
PYTHONS = {"python3", "python"}
DEADLINE = 6.0
MAX_CHARS = 1_000_000
MAX_LINE = 20_000
SHELL_META = re.compile(r"[;&|<>$`\\\n\r(){}\[\]*?!~#]")
SAFE_READS = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "stat", "file", "diff"}
VALIDATOR_COMMAND = re.compile(r"""(\S+)[ \t]+("[^"]*"|'[^']*'|[^\s"']+)[ \t]+--book[ \t]+("[^"]*"|'[^']*'|[^\s"']+)"""
                               r"""([ \t]+--json)?[ \t]*""")
LONE_CR = re.compile(r"\r(?!\n)")
MCP_READ_WORDS = {"read", "get", "list", "search", "find", "fetch", "view", "show", "describe", "status", "info",
                  "inspect", "count", "lookup"}
MCP_CHANGE_WORDS = {"write", "edit", "create", "update", "delete", "remove", "move", "rename", "copy", "set", "put",
                    "post", "patch", "replace", "append", "insert", "save", "upload", "import", "apply", "run",
                    "exec", "execute", "start", "kill", "send", "publish", "push", "commit", "modify", "change",
                    "add", "make", "mkdir", "touch", "interact", "eval", "shell", "command", "process", "script"}
# The ⚓ lines and sections a file copied from a template may start with; tests keep these in step with templates/.
NEW_FILE_ANCHOR_LINES = {
    "## ⚓ Anchored",
    '<!-- Everything under a "## ⚓ Anchored" heading is the author\'s decision. Agents MUST NOT change it or argue '
    "against it. -->",
    '<!-- Rules for critics: every finding quotes the manuscript as evidence. Findings are observations with a '
    'proposed change, not verdicts. Never contradict a "## ⚓ Anchored" decision. Severity: P0 = breaks the '
    "story/contract; P1 = weakens it; P2 = polish. -->",
}
NEW_FILE_ANCHOR_SECTIONS = {
    ("## ⚓ Anchored", ""),
    ("## ⚓ Anchored", "<!-- Move decisions here once made. Reviewers treat these as non-negotiable. -->"),
}
CHILD = [sys.executable, str(Path(__file__).resolve())]


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


def locate(path, book_root):
    """The path inside book/ (as book_relative gives it), or None. Also finds the book when the path names it
    another way, such as a macOS firmlink (/System/Volumes/Data/Users/…): an ancestor that is the same folder
    as book/ counts, whatever it is called."""
    root = book_root.resolve()
    rel = book_relative(path, root)
    if rel is not None:
        return rel
    try:
        st = root.stat()
    except OSError:
        return None
    if not st.st_ino:
        return None  # this file system gives no folder identity to compare
    for parent in (path, *path.parents):
        try:
            other = parent.stat()
        except OSError:
            continue
        if (other.st_dev, other.st_ino) == (st.st_dev, st.st_ino):
            inner = path.relative_to(parent).as_posix()
            return "" if inner == "." else fold(inner)
    return None


def target(raw, cwd, book_root, budget=3.0):
    """(resolved path, path inside book/, how) for a tool's file argument (~ expanded, normalised). A file inside
    book/ is judged by where it really is there, so a link between two book folders changes nothing (how is "").
    A file kept outside the book but reached through a symlink in book/ (a shared series bible) is linked: how is
    "through" when it was written by its path through that link, and "real" when it was written by its own location,
    which only a walk of book/'s links can tell; either may answer a CannotTell. The path is None outside the
    book. scenes.yaml and premise.md are known by what file they are, whatever path reaches them."""
    written = Path(os.path.normpath(os.path.join(str(cwd), os.path.expanduser(raw))))
    path = written.resolve()
    rel = locate(path, book_root)
    if rel is not None:
        return path, special(path, book_root) or rel, ""
    root = Path(os.path.normpath(str(book_root)))
    if book_relative(written, root) is not None:
        rel = leaving_link(written.parts[len(root.parts):], book_root)
        return path, special(path, book_root) or rel, "through"
    if not is_book_project(book_root):
        return path, None, ""
    found = through_link((path, written), book_root, budget=budget)
    if isinstance(found, CannotTell):
        return path, found, "real"
    return path, (strictest(found) if found else None), "real"


def leaving_link(parts, book_root):
    """The book path of a file written as book/<parts> that leaves the book through a symlink: the real place in
    book/ of the link that leads out, plus the rest of the path after it, so links between book folders on the way
    change nothing. Links (Windows junctions too) are resolved one part at a time, as the system does, so a file
    link, a link into a linked folder and a target relative to another link are all followed. A CannotTell when the
    links loop, when the path leaves the book some way no book path names (climbing back out of the linked folder,
    or through a link outside the book), or when it never leaves by the links this walk can follow."""
    shown = "book/" + "/".join(parts)
    cur = book_root.resolve()
    todo = [(name, None) for name in reversed(parts)]  # (part, the in-book link whose target it comes from)
    inside, out, hops = True, None, 0
    while todo:
        name, via = todo.pop()
        if name == "..":
            nxt = cur.parent
        elif is_link(cur / name):
            hops += 1
            if hops > 40:
                return CannotTell(f"the links on the way to {shown} loop", "remove the link that loops")
            try:
                link = Path(link_target(cur / name))
            except (OSError, ValueError):
                return CannotTell(f"it cannot read the link {cur / name}", f"make {cur / name} readable")
            if inside:
                base = locate(cur, book_root)
                via = (f"{base}/{fold(name)}" if base else fold(name), [n for n, _ in reversed(todo)])
            else:
                via = None
            todo.extend((n, via) for n in reversed(link.parts[1:] if link.is_absolute() else link.parts))
            nxt = Path(link.anchor) if link.is_absolute() else cur
        else:
            nxt = cur / name
        cur, was = nxt, inside
        inside = locate(cur, book_root) is not None
        if was and not inside:
            out = via
    fix = "point a link in book/ straight at the folder outside the book that holds the file"
    if inside:
        return CannotTell(f"{shown} leaves the book through a link the canon guard cannot follow",
                          "replace the links on that path with ordinary symbolic links")
    if out is None:
        return CannotTell(f"{shown} leaves the book only through a link outside it", fix)
    link_rel, rest = out
    if ".." in rest:
        return CannotTell(f"{shown} climbs back out of the folder the link book/{link_rel} leads to", fix)
    return "/".join([link_rel, *(fold(n) for n in rest)])


def is_link(path):
    """True for a symlink or a Windows directory junction: os.path.islink does not count a junction, yet the system
    follows it."""
    if os.path.islink(path):
        return True
    if hasattr(os.path, "isjunction"):
        return os.path.isjunction(path)
    try:  # Python before 3.12
        return os.lstat(path).st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    except (OSError, ValueError, AttributeError):
        return False


def link_target(path):
    """os.readlink, without the \\\\?\\ prefix Windows puts on a junction's target."""
    to = os.readlink(path)
    if to.startswith("\\\\?\\UNC\\"):
        return "\\\\" + to[8:]
    return to[4:] if to.startswith("\\\\?\\") else to


def special(path, book_root):
    """SCENES or PREMISE when `path` (resolved) is that very file, however it is reached (a link to a versioned
    copy), so its waivers and settings stay the author's; else None. Matched by where the link really leads, and by
    file identity where the file system gives one (os.path.samefile would match any two files where it gives none)."""
    for name in (SCENES, PREMISE):
        known = book_root / name
        try:
            if fold(known.resolve().as_posix()) == fold(path.as_posix()):
                return name
            mine, theirs = os.stat(path), os.stat(known)
        except (OSError, ValueError, RuntimeError):
            continue
        if mine.st_ino and (mine.st_dev, mine.st_ino) == (theirs.st_dev, theirs.st_ino):
            return name
    return None


def strictest(rels):
    """Of a file's book paths, the one the strictest rules see: scenes.yaml or premise.md, then canon, then the
    first."""
    special = [r for r in rels if r in (SCENES, PREMISE)]
    canon = [r for r in rels if any(fnmatch.fnmatchcase(r, g) for g in CANON)]
    return (special or canon or rels)[0]


class CannotTell(str):
    """through_link's answer when it could not look everywhere: `why` names the cause, `fix` what ends it."""

    def __new__(cls, why, fix):
        self = super().__new__(cls, "<cannot tell>")
        self.why, self.fix = why, fix
        return self


def identities(path):
    """{(st_dev, st_ino): the rest of `path` below that folder} for `path` and each of its folders that exists, so
    a file is found under a folder however either is spelled (a macOS /System/Volumes/Data/… path)."""
    ids = {}
    for parent in (path, *path.parents):
        try:
            st = parent.stat()
        except OSError:
            continue
        if st.st_ino:
            inner = path.relative_to(parent).as_posix()
            ids.setdefault((st.st_dev, st.st_ino), "" if inner == "." else fold(inner))
    return ids


def identity(path):
    """(st_dev, st_ino) of `path` itself (a link is not followed), or None when it is gone or the file system gives
    no identity. os.lstat, since os.DirEntry.stat on Windows always reports 0 for both."""
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino) if st.st_ino else None


def unreadable(path, via, error):
    """None when a folder that could not be listed can be passed over (it is gone, or a dot-folder such as a disk's
    .Spotlight-V100 or ~/.Trash, taken to hold no links), else the CannotTell naming it and the link it is behind."""
    if isinstance(error, (FileNotFoundError, NotADirectoryError)) or Path(path).name.startswith("."):
        return None
    if via:
        return CannotTell(f"it cannot read {path}, reached through the link {via}",
                          f"remove the link {via}, or make {path} readable")
    return CannotTell(f"it cannot read {path}", f"make {path} readable, or move it out of book/")


def through_link(paths, book_root, limit=5000, budget=3.0):
    """The book paths of a file (`paths`: its spellings) that reach it through a symlink in book/ (a shared series
    bible written to by its own location), as a sorted tuple, empty when there is none, or a CannotTell when the walk
    could not finish. What matters is whether there is any: a folder reached twice is walked once, so not every path
    is listed. A link's target is matched by identity as well as by text, and links inside a linked folder are
    followed too. Only folders and links count toward `limit`, so plain files never make the walk give up."""
    root = Path(os.path.normpath(str(book_root)))
    texts = {fold(p.as_posix()) for p in paths}
    ids = {}
    for p in paths:
        for key, inner in identities(p).items():
            ids.setdefault(key, inner)
    if not root.is_dir():
        return ()
    visited = {identity(root)} - {None}
    found, counted, start = set(), 0, time.monotonic()
    real_dirs, linked = [("", "book", root, None)], []
    while real_dirs or linked:
        if real_dirs:
            rel_dir, shown_dir, folder, via = real_dirs.pop()
        else:
            rel_dir, shown_dir, folder, via, key = linked.pop()
            if key in visited:
                continue  # a folder already walked by its own path
            visited.add(key)
        where = f" (in the folder the link {via} leads to)" if via else ""
        if time.monotonic() - start > budget:
            return CannotTell(f"looking through book/ and the folders it links to took over {budget:g} s{where}",
                              "if this keeps happening, remove links to large or slow (cloud or external) folders, "
                              "or move large folders out of book/")
        try:
            with os.scandir(folder) as listing:
                entries = list(listing)
        except OSError as error:
            problem = unreadable(folder, via, error)
            if problem is None:
                continue
            return problem
        for entry in entries:
            rel = f"{rel_dir}/{fold(entry.name)}" if rel_dir else fold(entry.name)
            shown = f"{shown_dir}/{entry.name}"
            try:
                linked_here = entry.is_symlink() or getattr(entry, "is_junction", lambda: False)()
                is_dir = not linked_here and entry.is_dir(follow_symlinks=False)
            except OSError as error:
                problem = unreadable(entry.path, via, error)
                if problem is None:
                    continue
                return problem
            if not (linked_here or is_dir):
                continue
            counted += 1
            if counted > limit:
                return CannotTell(f"book/ and the folders it links to hold over {limit:,} folders and links{where}",
                                  "remove links to large folders, or move large folders out of book/")
            if is_dir:
                key = identity(entry.path)
                if key is None or key not in visited:  # with no identity it is walked: real folders form a tree
                    visited.add(key)
                    real_dirs.append((rel, shown, Path(entry.path), via))
                continue
            try:
                real_path = Path(entry.path).resolve()
            except (OSError, RuntimeError):
                continue  # a link that loops: nothing can be written through it
            real = fold(real_path.as_posix()).rstrip("/")
            for text in texts:
                if text == real or text.startswith(real + "/"):
                    inner = text[len(real) + 1:]
                    found.add(f"{rel}/{inner}" if inner else rel)
            try:
                st = os.stat(real_path)
            except (OSError, ValueError):
                continue  # dangling: only its text can match
            key = (st.st_dev, st.st_ino) if st.st_ino else ("path", real)
            if key in ids:
                found.add(f"{rel}/{ids[key]}" if ids[key] else rel)
            if stat.S_ISDIR(st.st_mode) and key not in visited:
                linked.append((rel, shown, real_path, shown, key))
    return tuple(sorted(found))


def is_book_project(book_root):
    """A novelsmith book: book/ holding a file novel-start writes. Another tool's book/ folder (mdBook,
    Jupyter Book) is not one, so subagents there keep their usual tools."""
    return (book_root / "progress.md").is_file() or (book_root / SCENES).is_file()


def read_raw(path):
    """The file exactly as the Edit tool sees it, line endings untouched."""
    if not path.is_file():
        return ""
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def line_ending_problem(tool, inp, raw_old, yaml=False):
    """Why line endings could make the real tool, or the YAML reader, see other text than the guard checks (the
    guard compares text with every line ending as a plain line break), or None."""
    if yaml:
        written = [inp.get("content")] if tool == "Write" else [
            x for e in ((inp.get("edits") if tool == "MultiEdit" else [inp]) or []) if isinstance(e, dict)
            for x in (e.get("old_string"), e.get("new_string"))]
        if YAML_BREAKS.search(raw_old) or any(isinstance(x, str) and YAML_BREAKS.search(x) for x in written):
            return "the text holds a line break that YAML counts and the guard does not (U+0085, U+2028 or U+2029)"
    edit_texts = [inp.get("content")] if tool == "Write" else [
        x for e in ((inp.get("edits") if tool == "MultiEdit" else [inp]) or []) if isinstance(e, dict)
        for x in (e.get("old_string"), e.get("new_string"))]
    if any(isinstance(x, str) and "\ufeff" in x for x in edit_texts):
        return "the text holds an invisible U+FEFF character (a byte-order mark or zero-width no-break space)"
    if tool == "Write":
        content = inp.get("content")
        return ("the new text holds a carriage return that is not part of a line break"
                if isinstance(content, str) and LONE_CR.search(content) else None)
    edits = (inp.get("edits") if tool == "MultiEdit" else [inp]) or []
    olds = [e.get("old_string") for e in edits if isinstance(e, dict)]
    texts = [x for e in edits if isinstance(e, dict) for x in (e.get("old_string"), e.get("new_string"))]
    if any(isinstance(x, str) and "\r" in x for x in texts):
        return "an old_string or new_string holds a carriage return"
    if LONE_CR.search(raw_old):
        return "the file holds a carriage return that is not part of a line break"
    if "\r" in raw_old and any(isinstance(x, str) and x.startswith("\n") for x in olds):
        return "an old_string starts with a line break in a file with Windows line endings"
    return None


def edits_of(tool, inp):
    if tool == "Write":
        return []
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    return [{k: ns_book.normalize_lines(v) if isinstance(v, str) else v for k, v in e.items()} for e in edits or []]


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
        count = new.count(a)
        if not count:
            exact = False  # the real tool may still match (it normalises curly quotes)
            continue
        if count > 1 and not e.get("replace_all"):
            exact, count = False, 1  # the real tool refuses an old_string that is not unique
        if len(new) + count * (len(b) - len(a)) > MAX_CHARS:
            return None, exact
        new = new.replace(a, b) if e.get("replace_all") else new.replace(a, b, 1)
    return new, exact


def too_big(text):
    return len(text) > MAX_CHARS or any(len(line) > MAX_LINE for line in text.split("\n"))


def anchors(text, markdown=True):
    """Comparable form of every ⚓ section: heading plus whitespace-normalised body, comments kept (none in YAML)."""
    if not markdown:
        return []
    return [(" ".join(h.split()), " ".join(body.split())) for h, body in ns_book.anchored_sections(text)]


def anchor_views(text, markdown=True):
    """(line views, section views): every ⚓ line in its place and every ⚓ section, each as written and, in
    Markdown, as the author sees it (comments removed, so a ⚓ line hidden in a comment drops out of that view)."""
    views = [text, ns_book.strip_html_comments(text)] if markdown else [text]
    return [ns_book.anchor_lines(v, markdown) for v in views], [anchors(v, markdown) for v in views]


def first_difference(old, new):
    """(old item, new item) where two lists first differ, None standing for a missing item; None if equal."""
    if old == new:
        return None
    for i in range(max(len(old), len(new))):
        a, b = old[i] if i < len(old) else None, new[i] if i < len(new) else None
        if a != b:
            return a, b


def quoted(text):
    return '"' + " ".join(text.split())[:120] + '"'


def anchor_change(old, new, exists, markdown=True):
    """What the change does to ⚓ text, in a few words for the message, or None. A new file may carry only the
    templates' own ⚓ lines and sections (an empty ⚓ section is fine)."""
    (old_lines, old_sections), (new_lines, new_sections) = anchor_views(old, markdown), anchor_views(new, markdown)
    if not exists:
        line = next((x for view in new_lines for x in view if x[1] not in NEW_FILE_ANCHOR_LINES), None)
        if line:
            return f"at {quoted(line[1])}"
        section = next((x for view in new_sections for x in view if x[1] and x not in NEW_FILE_ANCHOR_SECTIONS), None)
        return f"at {quoted(section[0])}" if section else None
    for before, after in zip(old_lines, new_lines):
        diff = first_difference(before, after)
        if diff:
            a, b = diff
            if a and b and a[1] == b[1]:
                return f"the line {quoted(a[1])} would move from under {quoted(a[0])} to under {quoted(b[0])}"
            return f"at {quoted((b if b and (not a or b not in before) else a)[1])}"
    for before, after in zip(old_sections, new_sections):
        diff = first_difference(before, after)
        if diff:
            a, b = diff
            return f"at {quoted((b if b and (not a or b not in before) else a)[0])}"
    return None


def waivers_doubt(text):
    """Why an unreadable scenes.yaml might hold the author's waivers, read from its text, or None: a 'waivers'
    entry with anything in or under it, or a backslash, which could spell the key in escapes."""
    if "\\" in text:
        return "it contains a backslash, which could spell the waivers key"
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "waivers" not in line.casefold() or line.lstrip().startswith("#"):
            continue
        s = line.split(" #", 1)[0].split("\t#", 1)[0].strip()
        if s in ("waivers:", "waivers: {}", "waivers: null", "waivers: ~"):
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("#")):
                j += 1  # YAML ignores blank and comment lines, wherever they are indented
            below = lines[j] if j < len(lines) else ""
            depth, below_depth = len(line) - len(line.lstrip()), len(below) - len(below.lstrip())
            if "\t" not in below[:below_depth] and (
                    below_depth < depth or (below_depth == depth and not below.lstrip().startswith("-"))):
                continue  # nothing nested under it, so the entry is empty
        return "its waivers entry is not empty"
    return None


def stray_waivers(node, where=()):
    """True if a 'waivers' key appears anywhere except book.waivers (a decoy for a human reader)."""
    if isinstance(node, dict):
        return any((k == "waivers" and where != ("book",)) or stray_waivers(v, where + (k,))
                   for k, v in node.items())
    if isinstance(node, list):
        return any(stray_waivers(x, where + ("[]",)) for x in node)
    return False


def waivers_of(text):
    """(waivers, problem, data): book.waivers and the whole manifest as parsed data, or a reason it cannot be
    read safely."""
    if not text.strip():
        return {}, None, {}
    import ns_yaml  # here, so the hook's other calls do not load PyYAML
    try:
        data = ns_yaml.load(text)
        if not isinstance(data, dict):
            return None, "is not a mapping", None
        if stray_waivers(data):
            return None, "has a 'waivers' key outside book", None
    except Exception as exc:  # any failure means the waivers cannot be checked
        return None, f"cannot be read safely ({exc})", None
    book = data.get("book") or {}
    if not isinstance(book, dict):
        return None, "has a 'book' that is not a mapping", None
    return book.get("waivers") or {}, None, data


def anchored_values(node, where=()):
    """Every key or text value holding ⚓ in parsed YAML, with where it sits (a scene by its id, not its place in
    the list): a value swallowed into another field's quoted text, or moved to another scene, changes this."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if ns_book.ANCHOR in ns_book.decode_anchor(str(k)):
                out.append((where, str(k)))
            out.extend(anchored_values(v, where + (str(k),)))
    elif isinstance(node, list):
        for i, x in enumerate(node):
            out.extend(anchored_values(x, where + (f"id {x['id']}" if isinstance(x, dict) and "id" in x else str(i),)))
    elif isinstance(node, str) and ns_book.ANCHOR in ns_book.decode_anchor(node):
        out.append((where, node))
    return sorted(out)


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}), flush=True)
    return 0


def subagent_of(payload):
    """The subagent's name, or "" for the main conversation. Claude Code sends agent_id only from a subagent;
    a main conversation started as an agent (claude --agent) sends agent_type alone and is still the author."""
    if not isinstance(payload, dict) or not payload.get("agent_id"):
        return ""
    return str(payload.get("agent_type") or "subagent").strip()


def is_validator_command(command, cwd):
    """True only for: python3 <this plugin's validate-outline.py> --book <dir> [--json]. Either path may be
    quoted, since a plugin folder can hold ~, ( ) or Windows backslashes; no shell syntax outside the quotes,
    no $, backquote or line break inside double quotes, and no backslash there that the shell would read as an
    escape (before ", \\, $ or a backquote). The shell's own split of the command must agree, word for word."""
    m = VALIDATOR_COMMAND.fullmatch(command)
    if not m or m.group(1) not in PYTHONS:
        return False
    args = []
    for arg in (m.group(2), m.group(3)):
        if arg[0] == "'":
            bad = "\n" in arg or "\r" in arg
        elif arg[0] == '"':
            bad = bool(re.search(r'[$`\n\r]|\\(?=["\\$`])', arg))
        else:
            bad = bool(SHELL_META.search(arg))
        if bad:
            return False
        args.append(arg[1:-1] if arg[0] in "\"'" else arg)
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if words != [m.group(1), args[0], "--book", args[1]] + (["--json"] if m.group(4) else []):
        return False  # the shell would read other words than the guard checked
    script = Path(args[0]) if os.path.isabs(args[0]) else cwd / args[0]
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
    if is_book_project(book_root) and not is_simple_read(command):
        return decide("deny", "novelsmith: in a book project, subagents may run only simple read-only commands "
                              f"({', '.join(sorted(SAFE_READS))}) without shell syntax; the canon guard cannot check "
                              "what other commands change. Use the Read, Write and Edit tools.")
    return 0


def needs_check(tool, agent):
    """Whether the hook must run the checks: every file write, and any subagent call but a known read."""
    tool = str(tool)
    return tool in WRITE_TOOLS or (bool(agent) and tool not in SAFE_TOOLS)


def mcp_reads_only(tool):
    """True if an MCP tool's own name says it reads (read_file, listDirectory) and names no change. The guard
    cannot see what a server does with its arguments, only what the tool is called."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", tool.split("__", 2)[-1]).casefold()
    words = set(re.split(r"[^a-z0-9]+", name))
    return bool(words & MCP_READ_WORDS) and not words & MCP_CHANGE_WORDS


def check_mcp(tool, agent, book_root):
    if not agent or not is_book_project(book_root):
        return 0  # the author's own MCP calls: Claude Code's permission prompts apply
    if not mcp_reads_only(tool):
        return decide("deny", f"novelsmith: in a book project, subagents may use only MCP tools whose names say they "
                              f"read (read, get, list, search …); {tool} could change book files the canon guard "
                              "cannot check. Use the Read, Write and Edit tools, or report what you need.")
    return 0


def main(data):
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    book_root = project / "book"

    agent = subagent_of(data)
    short = agent.split(":")[-1] if agent else ""
    # A bare name ("outliner") is taken as novelsmith's only in a book project: elsewhere it is someone else's.
    ours = agent.startswith("novelsmith:") or (short in AGENT_SCOPES and ":" not in agent
                                               and is_book_project(book_root))

    # Rule 3: the shell.
    if tool == "Bash":
        return check_bash(inp.get("command", ""), agent, ours, short, cwd, book_root)
    if tool == "PowerShell":
        if agent and (ours or is_book_project(book_root)):
            return decide("deny", "novelsmith: in a book project, subagents do not use PowerShell; the canon guard "
                                  "cannot check what it changes. Use the Read, Write and Edit tools.")
        return 0
    if tool.startswith("mcp__"):
        return check_mcp(tool, agent, book_root)

    if tool not in WRITE_TOOLS + (NOTEBOOK_TOOL,):
        if agent and tool not in SAFE_TOOLS and (ours or is_book_project(book_root)):
            return decide("deny", f"novelsmith: in a book project, subagents may use only tools the canon guard "
                                  f"knows; {tool} could change book files or act as the author where the guard cannot "
                                  f"check it. Use the Read, Write and Edit tools, or report what you need.")
        return 0
    raw = inp.get("notebook_path" if tool == NOTEBOOK_TOOL else "file_path")
    if not raw:
        return 0
    path, rel, how = target(raw, cwd, book_root)
    if isinstance(rel, CannotTell):
        if how == "through":
            what = (f"novelsmith: {raw} leaves the book through a link, and the canon guard cannot tell which book "
                    f"file it is ({rel.why}).")
            if agent:
                return decide("deny", f"{what} Subagents may not write it. Report it to the author, with the fix: "
                                      f"{rel.fix}.")
            return decide("ask", f"{what} Allow it only if you asked for this change. To end these prompts, "
                                 f"{rel.fix}.")
        if ours:
            return decide("deny", f"novelsmith: {short} writes only under book/. If {raw} is a book file reached "
                                  f"through a link, write it by its path inside book/.")
        if agent:
            return decide("deny", f"novelsmith: the canon guard cannot tell whether {raw} is a book file reached "
                                  f"through a link in book/ ({rel.why}), so subagents' writes outside book/ are "
                                  f"denied in this project until the author fixes that. Report it to the author, with "
                                  f"the fix: {rel.fix}.")
        return decide("ask", f"novelsmith: the canon guard cannot tell whether {raw} is a book file reached through "
                             f"a link in book/ ({rel.why}). Allow it only if you asked for this change. To end these "
                             f"prompts, {rel.fix}.")
    if rel is None:
        if ours:
            return decide("deny", f"novelsmith: {short} writes only under book/; {raw} is outside the book.")
        return 0
    if not ours and not is_book_project(book_root):
        return 0  # another tool's book/ folder
    if how and agent and not ours:
        return decide("deny", f"novelsmith: book/{rel} is kept outside the book and reached through a link in book/ "
                              f"(such as a shared series bible). Only novelsmith's agents, each in its own folders, "
                              f"and the author in the main conversation change linked files. Report what you need "
                              f"instead.")
    if how == "real" and agent:
        return decide("deny", f"novelsmith: {raw} is the book file book/{rel}, reached through a link in book/. "
                              f"Write it by that path, so the canon guard can check it.")
    if tool == NOTEBOOK_TOOL:
        if agent:
            return decide("deny", f"novelsmith: subagents may not edit notebooks under book/ ({raw}); book files "
                                  f"are Markdown and YAML, written with the Write and Edit tools.")
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
    raw_old = read_raw(path)
    old = ns_book.normalize(raw_old)
    new, exact = apply_edits(old, tool, inp)
    endings = line_ending_problem(tool, inp, raw_old, yaml=rel.endswith((".yaml", ".yml")))
    if endings and agent:
        advice = ("Leave that character out (retype the passage without it), or report it to the author."
                  if "U+FEFF" in endings else "Use plain line breaks and copy the text exactly.")
        return decide("deny", f"novelsmith: {endings} in book/{rel}, so the canon guard cannot tell which text the "
                              f"real edit changes. {advice}")
    exact = exact and not endings
    if not exists and not agent:
        return 0  # the author creating a file (novel-start) owns everything in it
    if agent and (new is None or too_big(old) or too_big(new)):
        return decide("deny", f"novelsmith: book/{rel} would be larger than the canon guard checks "
                              f"({MAX_CHARS:,} characters, lines up to {MAX_LINE:,}); split the content.")
    if agent and not exact:
        return decide("deny", f"novelsmith: an old_string does not match book/{rel} exactly, or matches it more "
                              f"than once, so the change cannot be checked. Read the file and copy the text exactly, "
                              f"with enough context to be unique.")

    if new is None:
        return decide("ask", f"novelsmith: this edit would make book/{rel} larger than the canon guard checks "
                             f"({MAX_CHARS:,} characters). Allow it only if you asked for this change.")

    problems, anchored_value = [], None
    if rel == SCENES:
        before, bad_old, old_data = waivers_of(old)
        after, bad_new, new_data = waivers_of(new)
        if not bad_old and not bad_new:
            diff = first_difference(anchored_values(old_data), anchored_values(new_data))
            if diff:
                where, value = diff[1] or diff[0]
                anchored_value = f"⚓ text in book/{rel} (the value at {quoted(' > '.join(where))}, {quoted(value)})"
        if bad_new:
            if agent or before or (bad_old and waivers_doubt(old)):
                problems.append(f"book/{rel}, which {bad_new} after this change, so its waivers cannot be checked")
        elif bad_old:
            # An unreadable old file may be repaired, unless it may hold waivers: the repair could not be
            # compared with them, so it might drop or alter the author's.
            if after:
                problems.append(f"the book.waivers block of book/{rel}")
            elif waivers_doubt(old):
                problems.append(f"book/{rel} while it cannot be read ({waivers_doubt(old)}, so the canon guard "
                                f"cannot check that the waivers survive the repair)")
        elif before != after:
            problems.append(f"the book.waivers block of book/{rel}")
    changed_anchor = anchor_change(old, new, exists, markdown=not rel.endswith((".yaml", ".yml")))
    if changed_anchor is not None:
        problems.append(f"⚓ text in book/{rel} ({changed_anchor})")
    elif anchored_value:
        problems.append(anchored_value)
    if rel == PREMISE:
        before_s, after_s = ns_book.book_settings(old), ns_book.book_settings(new)
        changed = [key for key in before_s if before_s[key] and before_s[key] != after_s[key]]
        if changed:
            problems.append(f"the {', '.join(changed)} setting of book/{rel}")
    protected = rel in (SCENES, PREMISE) or ns_book.ANCHOR in ns_book.decode_anchor(old) or any(
        ns_book.ANCHOR in ns_book.decode_anchor(str(e.get("new_string", ""))) for e in edits_of(tool, inp))
    if not exact and protected:
        problems.append(f"book/{rel} with an old_string that does not match the file exactly, so it cannot be checked")

    if not problems:
        return 0
    what = "; ".join(problems)
    if agent:
        hint = (" Keep every existing ⚓ line exactly as it is and where it is (rewriting the line it sits under "
                "counts as moving it), add none, and refer to \"the anchored section\" in words."
                if changed_anchor is not None or anchored_value else "")
        return decide("deny", f"novelsmith: this would change {what}. Those are the author's decisions; agents never "
                              f"change them. Report the tension or write the proposal in book/proposals/.{hint}")
    return decide("ask", f"novelsmith: this changes {what}, which holds your decisions as the author. "
                         f"Allow it only if you asked for this change.")


def run(raw):
    """main() in a child process, killed at DEADLINE: a thread cannot stop one long C call (substring search
    on Python 3.9 is quadratic on some input), and a hook that times out lets the call through."""
    try:
        p = subprocess.run(CHILD + ["--check"], input=raw, capture_output=True, timeout=DEADLINE)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"took longer than {DEADLINE:g} s") from None
    if p.returncode != 0:
        lines = p.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"exit {p.returncode}")
    return p.stdout


def writes_book(payload):
    """True if the call is a write to a file under the project's book/ (decided cheaply, in the parent)."""
    inp = payload.get("tool_input")
    raw = inp.get("file_path") if isinstance(inp, dict) else None
    if not isinstance(raw, str) or not raw:
        return False  # no file the real tool could write either
    try:
        cwd = Path(payload.get("cwd") or os.getcwd())
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
        # a short walk, so the hook still answers before its timeout; a CannotTell counts as the book
        return target(raw, cwd, project / "book", budget=1.0)[1] is not None
    except Exception:  # cannot tell: treat it as the book's
        return True


def cli(raw):
    """The hook: the checks run in a child process and its decision is passed on. Returns the exit code."""
    payload, parsed = {}, False
    try:
        payload = json.loads(raw.decode("utf-8"))
        parsed = True
        if needs_check(payload.get("tool_name", ""), subagent_of(payload)):
            sys.stdout.buffer.write(run(raw))  # the author's own shell and MCP calls need no check
        return 0
    except Exception as exc:
        if not isinstance(payload, dict):
            payload = {}
        tool, agent = payload.get("tool_name", ""), subagent_of(payload)
        why = f"{type(exc).__name__}: {exc}"
        if not parsed:  # nothing could be read (too deeply nested, not UTF-8): go by the raw text
            agent = agent or b'"agent_id"' in raw
            if not agent and b'"file_path"' in raw:
                decide("ask", f"novelsmith: the canon guard could not read this call ({why}). Allow it only if "
                              f"you asked for this change.")
                return 0
        if agent and needs_check(tool, agent):
            # A subagent's call that cannot be checked is denied, not waved through.
            decide("deny", f"novelsmith: the canon guard could not check this call ({why}), so it is denied for "
                           f"subagents.")
            return 0
        if tool in WRITE_TOOLS and writes_book(payload):
            # The author's own write to the book is asked about, never blocked and never waved through unseen.
            decide("ask", f"novelsmith: the canon guard could not check this change to the book ({why}), so it "
                          f"cannot tell whether it touches your ⚓ text, waivers or premise settings. Allow it only "
                          f"if you asked for this change.")
            return 0
        print(f"guard-canon: {exc}", file=sys.stderr, flush=True)  # anything else of the author's fails open
        return 1


if __name__ == "__main__":
    raw = sys.stdin.buffer.read()
    if sys.argv[1:] == ["--check"]:
        sys.exit(main(json.loads(raw.decode("utf-8"))))
    sys.exit(cli(raw))
