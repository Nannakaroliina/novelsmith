#!/usr/bin/env python3
"""Build dist/novelsmith-<version>.zip for Customize > Plugins > Upload plugin (claude.ai / Cowork).

The archive holds one top-level novelsmith/ folder with only what the plugin
loads: research docs, tests, git metadata and this script stay out.

Before zipping it checks skill and agent frontmatter against the rules the
claude.ai upload enforces (Agent Skills spec): a parseable frontmatter block,
a text description of at most 1,024 characters, a name that matches its folder,
and no angle brackets in any frontmatter value (read as XML tags). It refuses
to build when any check fails.
"""

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ns_yaml  # noqa: E402

SKIP_DIRS = {".git", "dist", "docs", "tests", "__pycache__"}
SKIP_FILES = {".DS_Store", ".gitignore", "build_zip.py"}
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


def main():
    problems = []
    for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
        problems += frontmatter_problems(p, True)
    for p in sorted((ROOT / "agents").rglob("*.md")):
        problems += frontmatter_problems(p, False)
    if problems:
        sys.exit("refusing to build:\n" + "\n".join(f"- {x}" for x in problems))

    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    out = ROOT / "dist" / f"{manifest['name']}-{manifest['version']}.zip"
    out.parent.mkdir(exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and not SKIP_DIRS & set(p.relative_to(ROOT).parts)
                   and p.name not in SKIP_FILES and p.suffix != ".pyc")
    if (ROOT / "bin").exists():
        sys.exit("bin/ present: claude.ai and Cowork refuse plugins with a top-level bin/ directory")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, f"{manifest['name']}/{p.relative_to(ROOT).as_posix()}")
    print(f"{out} ({len(files)} files, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
