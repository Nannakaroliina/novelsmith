#!/usr/bin/env python3
"""Build dist/novelsmith-<version>.zip for Customize > Plugins > Upload plugin (claude.ai / Cowork).

The archive holds one top-level novelsmith/ folder with only what the plugin
loads: committed files under the plugin's own folders (INCLUDE). Untracked
and git-ignored files, research docs, tests, the review brief and this script
stay out, and a file that looks like a secret stops the build.

Before zipping it checks skill and agent frontmatter against the rules the
claude.ai upload enforces (Agent Skills spec): a parseable frontmatter block,
a text description of at most 1,024 characters, a name that matches its folder,
and no angle brackets in any frontmatter value (read as XML tags). It refuses
to build when any check fails.
"""

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ns_yaml  # noqa: E402

INCLUDE_DIRS = (".claude-plugin", "agents", "assets", "hooks", "scripts", "skills", "templates")
INCLUDE_FILES = ("README.md", "LICENSE")
EXCLUDE_FILES = {"scripts/build_zip.py"}
SECRET_RE = re.compile(r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx|keystore)|id_(rsa|dsa|ed25519)(\..*)?|"
                       r"credentials\.json|secrets?\.ya?ml|\.netrc|\.npmrc)$", re.I)
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")


def frontmatter_problems(path, is_skill):
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return [f"{rel}: no frontmatter block starting on line 1"]
    try:
        fm = ns_yaml.load(m.group(1)) or {}
    except ns_yaml.YAMLError as exc:
        return [f"{rel}: frontmatter does not parse ({exc})"]
    problems = []
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        problems.append(f"{rel}: description missing or not text")
    elif len(desc) > 1024:
        problems.append(f"{rel}: description is {len(desc)} characters (max 1024)")
    name = fm.get("name")
    if is_skill and name is not None and (name != path.parent.name or not NAME_RE.match(str(name))):
        problems.append(f"{rel}: name {name!r} must be lowercase/hyphens and match its folder {path.parent.name!r}")
    values = [v for v in fm.values() if isinstance(v, str)] + [
        x for v in fm.values() if isinstance(v, list) for x in v if isinstance(x, str)]
    for v in values:
        if re.search(r"[<>]", v):
            problems.append(f"{rel}: angle brackets in frontmatter read as XML tags: {v[:60]!r}")
    return problems


def tracked_files(root):
    """Files git tracks under root, or None when root is not a git checkout."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {name for name in out.decode("utf-8").split("\0") if name}


def select_files(root, tracked):
    """(files to ship, secret-looking paths) from the allowlist, limited to tracked files when known."""
    candidates = [root / name for name in INCLUDE_FILES if (root / name).is_file()]
    for d in INCLUDE_DIRS:
        candidates += [p for p in (root / d).rglob("*") if p.is_file()] if (root / d).is_dir() else []
    files, secrets = [], []
    for p in sorted(candidates):
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        if rel in EXCLUDE_FILES or p.suffix == ".pyc" or "__pycache__" in parts:
            continue
        if any(part.startswith(".") for part in parts if part != ".claude-plugin"):
            continue
        if tracked is not None and rel not in tracked:
            continue
        (secrets if SECRET_RE.search(rel) else files).append(p)
    return files, secrets


def main():
    problems = []
    for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
        problems += frontmatter_problems(p, True)
    for p in sorted((ROOT / "agents").rglob("*.md")):
        problems += frontmatter_problems(p, False)
    if (ROOT / "bin").exists():
        problems.append("bin/ present: claude.ai and Cowork refuse plugins with a top-level bin/ directory")
    files, secrets = select_files(ROOT, tracked_files(ROOT))
    problems += [f"{p.relative_to(ROOT).as_posix()}: looks like a secret; remove it from the plugin" for p in secrets]
    if problems:
        sys.exit("refusing to build:\n" + "\n".join(f"- {x}" for x in problems))

    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    out = ROOT / "dist" / f"{manifest['name']}-{manifest['version']}.zip"
    out.parent.mkdir(exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, f"{manifest['name']}/{p.relative_to(ROOT).as_posix()}")
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None or len(z.namelist()) != len(files):
                raise RuntimeError("the written zip does not match the file list")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"{out} ({len(files)} files, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
