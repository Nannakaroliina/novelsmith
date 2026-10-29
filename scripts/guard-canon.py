#!/usr/bin/env python3
"""PreToolUse guard for Write/Edit/MultiEdit under book/.

Two rules, enforced here because plugin agents cannot carry their own hooks:

1. Author-owned regions: the "## ⚓ Anchored" section of any Markdown file and the
   book.waivers block of outline/scenes.yaml. A subagent changing one is denied;
   in the main conversation the author is asked to confirm.
2. Write scopes: each novelsmith agent may write only its own files (AGENT_SCOPES).
   Any other subagent may not write under book/bible/ (canon).

Reads the hook input JSON on stdin; prints a hookSpecificOutput decision or nothing.
Fails open (exit 1, non-blocking) on its own errors so a bug never locks the author out.
"""

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

AGENT_SCOPES = {
    "story-architect": ["bible/premise.md", "outline/acts.md", "proposals/*"],
    "character-designer": ["bible/characters/*", "proposals/*"],
    "worldbuilder": ["bible/world/*", "bible/timeline.md", "proposals/*"],
    "outliner": ["outline/*", "bible/clues.md", "bible/timeline.md", "proposals/*", "critiques/outline/*"],
}
CANON = ["bible/*"]

ANCHOR_RE = re.compile(r"^##\s.*⚓.*$", re.M)
WAIVERS_RE = re.compile(r"^(?P<indent>[ \t]*)waivers:.*$", re.M)


def anchored(text):
    m = ANCHOR_RE.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def waivers(text):
    m = WAIVERS_RE.search(text)
    if not m:
        return None
    indent = len(m.group("indent"))
    lines = [m.group(0)]
    for line in text[m.end():].splitlines()[1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        lines.append(line)
    return "\n".join(lines)


def canonical(region):
    if region is None:
        return ""
    region = re.sub(r"<!--.*?-->", "", region, flags=re.S)
    region = re.sub(r"#.*$", "", region, flags=re.M) if region.lstrip().startswith("waivers") else region
    return " ".join(region.split())


def apply_edits(old, tool, inp):
    if tool == "Write":
        return inp.get("content", "")
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    new = old
    for e in edits or []:
        a, b = e.get("old_string", ""), e.get("new_string", "")
        if a:
            new = new.replace(a, b) if e.get("replace_all") else new.replace(a, b, 1)
    return new


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))
    return 0


def main():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    if tool not in ("Write", "Edit", "MultiEdit"):
        return 0
    inp = data.get("tool_input") or {}
    raw = inp.get("file_path")
    if not raw:
        return 0
    cwd = Path(data.get("cwd") or os.getcwd())
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    path = (cwd / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    try:
        rel = path.relative_to((project / "book").resolve()).as_posix()
    except ValueError:
        return 0

    agent = (data.get("agent_type") or "").strip()
    short = agent.split(":")[-1] if agent else ""
    ours = agent.startswith("novelsmith:") or (short in AGENT_SCOPES and ":" not in agent)

    # Rule 2: write scopes for subagents.
    if agent:
        scopes = AGENT_SCOPES.get(short) if ours else None
        if scopes is not None and not any(fnmatch.fnmatch(rel, g) for g in scopes):
            return decide("deny", f"novelsmith: {short} may write only {', '.join('book/' + g for g in scopes)}; "
                                  f"book/{rel} belongs to another stage. Write a proposal in book/proposals/ instead.")
        if scopes is None and any(fnmatch.fnmatch(rel, g) for g in CANON):
            return decide("deny", f"novelsmith: book/{rel} is canon. Only the bible stage agents (or the author in the "
                                  f"main conversation) edit book/bible/. Propose the change in book/proposals/.")

    # Rule 1: author-owned regions.
    exists = path.is_file()
    old = path.read_text(encoding="utf-8") if exists else ""
    new = apply_edits(old, tool, inp)
    extract = waivers if rel == "outline/scenes.yaml" else anchored if rel.endswith(".md") else None
    if extract is None:
        return 0
    before, after = canonical(extract(old)), canonical(extract(new))
    label = "the book.waivers block" if extract is waivers else "the ## ⚓ Anchored section"
    if before == after or (not exists and not agent):
        return 0
    if before == "" and after in ("", "waivers: {}"):
        return 0
    if agent:
        return decide("deny", f"novelsmith: {label} of book/{rel} is the author's decision; agents never change it. "
                              f"Report the tension or write the proposal in book/proposals/ and let the author edit.")
    return decide("ask", f"novelsmith: this changes {label} of book/{rel}, which records the author's decisions. "
                         f"Allow only if the author asked for this change.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open: a guard bug must not lock the author out
        print(f"guard-canon: {exc}", file=sys.stderr)
        sys.exit(1)
