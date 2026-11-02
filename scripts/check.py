#!/usr/bin/env python3
"""Quality and lint checks to run before every push; CI runs the same with --all.

    python3 scripts/check.py          files, secrets, frontmatter, lint, hook shell, plugin manifest
    python3 scripts/check.py --all    the same, then the test suite and the self-check

Needs ruff and shellcheck (brew install ruff shellcheck; pip install ruff; apt install shellcheck).
`claude plugin validate` runs when the claude command is on PATH and is skipped otherwise, as in CI.
Looks only at files git tracks or would track (not ignored), so book/, local settings and build output
are never read.
Prints one line per check; exits 0 when all pass, 1 otherwise.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_zip  # noqa: E402

CODE_SUFFIXES = {".py", ".json", ".toml", ".yml", ".yaml", ".sh", ".ps1"}
# Invisible or direction-changing characters: in code they hide what a line really says.
# Tests that need one spell it as an escape (\u200b).
INVISIBLE_RE = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")
SYSTEM_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
# Credentials by their published formats; a placeholder such as sk-ant-... does not match.
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{30,}")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
)


def project_files():
    """Tracked files plus new ones git does not ignore, so a file is checked before its first commit."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, check=True, timeout=30).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"check: git could not list the project's files ({exc}); run this in a git checkout")
    names = {n for n in out.decode("utf-8", errors="surrogateescape").split("\0") if n}
    return sorted(ROOT / n for n in names if (ROOT / n).is_file() and not (ROOT / n).is_symlink())


def rel(p):
    return p.relative_to(ROOT).as_posix()


def tool(name):
    """The tool's path, from PATH or the project's .venv."""
    for candidate in (shutil.which(name), ROOT / ".venv" / "bin" / name, ROOT / ".venv" / "Scripts" / f"{name}.exe"):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def run(args, **kw):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    return p.returncode, (p.stdout + p.stderr).strip()


def check_files(files):
    """Text hygiene on every tracked file: UTF-8, LF line ends, a final newline; code also without
    trailing spaces or invisible characters, and JSON that parses. No OS metadata files."""
    problems = []
    for p in files:
        name = rel(p)
        if p.name in SYSTEM_FILES:
            problems.append(f"{name}: OS metadata file; git rm --cached it")
            continue
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            continue  # binary (icons)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            problems.append(f"{name}: not UTF-8 ({exc.reason} at byte {exc.start})")
            continue
        if "\r" in text:
            problems.append(f"{name}: carriage return (CRLF line ends); save it with LF")
        if text and not text.endswith("\n"):
            problems.append(f"{name}: no newline at the end")
        if p.suffix not in CODE_SUFFIXES:
            continue
        for n, line in enumerate(text.split("\n"), 1):
            if line != line.rstrip(" \t"):
                problems.append(f"{name}:{n}: trailing whitespace")
            m = INVISIBLE_RE.search(line)
            if m:
                problems.append(f"{name}:{n}: invisible character U+{ord(m.group()):04X}; write it as an escape")
        if p.suffix == ".json":
            try:
                json.loads(text)
            except ValueError as exc:
                problems.append(f"{name}: invalid JSON ({exc})")
    return problems


def check_secrets(files):
    """Secret-looking file names (the zip's rule) and credentials in any tracked text."""
    problems = [f"{rel(p)}: looks like a secret file" for p in files if build_zip.SECRET_RE.search(rel(p))]
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{rel(p)}:{line}: {label} ({m.group()[:8]}…)")
    return problems


def check_frontmatter(_files):
    problems = []
    for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
        problems += build_zip.frontmatter_problems(p, True)
    for p in sorted((ROOT / "agents").rglob("*.md")):
        problems += build_zip.frontmatter_problems(p, False)
    return problems


def check_lint(_files):
    ruff = tool("ruff")
    if not ruff:
        return ["ruff not found; install it (brew install ruff, or pip install ruff)"]
    code, out = run([ruff, "check", "--no-cache", "--output-format", "concise", "."], timeout=120)
    return [] if code == 0 else out.splitlines()


def check_hook_shell(_files):
    """The hook commands in hooks/hooks.json are POSIX shell run by every Claude Code session; shellcheck them."""
    shellcheck = tool("shellcheck")
    if not shellcheck:
        return ["shellcheck not found; install it (brew install shellcheck, or apt install shellcheck)"]
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    problems = []
    for event, groups in hooks.items():
        for group in groups:
            for h in group.get("hooks", []):
                if h.get("type") != "command":
                    continue
                code, out = run([shellcheck, "--shell=sh", "-"], input=h["command"] + "\n", timeout=60)
                if code != 0:
                    problems.append(f"hooks/hooks.json {event} hook:\n{out}")
    return problems


def check_plugin(_files):
    claude = shutil.which("claude")
    if not claude:
        return None  # skipped
    problems = []
    for target in (".", ".claude-plugin/marketplace.json"):
        code, out = run([claude, "plugin", "validate", target, "--strict"], timeout=120)
        if code != 0:
            problems.append(f"claude plugin validate {target} --strict:\n{out}")
    return problems


def check_tests(_files):
    code, out = run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], timeout=600)
    return [] if code == 0 else [out]


def check_selfcheck(_files):
    code, out = run([sys.executable, "-B", str(HERE / "selfcheck.py")], timeout=120)
    return [] if code == 0 else [out]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--all", action="store_true", help="also run the test suite and the self-check")
    args = ap.parse_args()
    checks = [("files", check_files), ("secrets", check_secrets), ("frontmatter", check_frontmatter),
              ("lint", check_lint), ("hook shell", check_hook_shell), ("plugin manifest", check_plugin)]
    if args.all:
        checks += [("tests", check_tests), ("selfcheck", check_selfcheck)]
    files = project_files()
    failed = []
    for name, probe in checks:
        start = time.monotonic()
        problems = probe(files)
        took = f"{time.monotonic() - start:.1f} s"
        if problems is None:
            print(f"skip {name}: claude not on PATH", flush=True)
        elif problems:
            failed.append(name)
            print(f"FAIL {name} ({took})", flush=True)
            for line in problems:
                print("  " + line.replace("\n", "\n  "))
        else:
            print(f"ok   {name} ({took})", flush=True)
    if failed:
        print(f"\n{len(failed)} check(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
