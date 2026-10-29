#!/usr/bin/env python3
"""Check that novelsmith's scripts work on this machine or in this Cowork VM.

Builds a throwaway fixture book in a temp folder (nothing in the project is
touched), runs the outline validator on a passing and a broken manifest, and
feeds the canon guard a subagent write and a main-session anchor edit.
Prints one line per check; exits 0 when all pass, 1 otherwise.
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixture_book  # noqa: E402
import ns_yaml  # noqa: E402


def run(args, stdin=None, env=None):
    return subprocess.run([sys.executable, *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def guard(project, agent, tool_input):
    payload = {"hook_event_name": "PreToolUse", "cwd": str(project), "tool_name": "Edit" if "old_string" in tool_input
               else "Write", "tool_input": tool_input}
    if agent:
        payload.update(agent_id="selfcheck", agent_type=agent)
    p = run([str(HERE / "guard-canon.py")], json.dumps(payload), {"CLAUDE_PROJECT_DIR": str(project)})
    if p.returncode != 0 or not p.stdout.strip():
        return f"none (exit {p.returncode}{', ' + p.stderr.strip() if p.stderr.strip() else ''})"
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]


def main():
    results = []

    def check(name, ok, detail):
        results.append(ok)
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")

    print(f"python {platform.python_version()} at {sys.executable}; "
          f"YAML: {'PyYAML' if ns_yaml._pyyaml else 'built-in fallback parser'}")
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp).resolve()
        book = fixture_book.build(project)
        validator = str(HERE / "validate-outline.py")

        p = run([validator, "--book", str(book)])
        check("validator passes a good outline", p.returncode == 0, p.stdout.strip().splitlines()[-1] if p.stdout
              else p.stderr.strip())

        scenes = book / "outline" / "scenes.yaml"
        scenes.write_text(scenes.read_text(encoding="utf-8").replace("flags: [compromise]", "flags: []"),
                          encoding="utf-8")
        p = run([validator, "--book", str(book), "--json"])
        failed = p.returncode == 1 and any(f["check"] == "compromise" for f in json.loads(p.stdout)["findings"])
        check("validator catches a missing compromise", failed, f"exit {p.returncode}")

        d = guard(project, "novelsmith:worldbuilder",
                  {"file_path": str(book / "outline" / "acts.md"), "content": "x"})
        check("guard denies an agent writing outside its files", d == "deny", d)

        d = guard(project, "novelsmith:worldbuilder",
                  {"file_path": str(book / "bible" / "world" / "harbour.md"), "content": "# Harbour\n"})
        check("guard allows an agent writing its own files", d.startswith("none (exit 0"), d)

        d = guard(project, None, {"file_path": str(book / "bible" / "premise.md"),
                                  "old_string": "harbour master's sister", "new_string": "harbour master"})
        check("guard asks before the author's anchored text changes", d == "ask", d)

    print("ALL OK" if all(results) else f"{results.count(False)} check(s) failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
