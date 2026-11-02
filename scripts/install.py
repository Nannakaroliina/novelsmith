#!/usr/bin/env python3
"""Install novelsmith into Claude Code from this folder, or build the upload zip for Cowork.

    python3 scripts/install.py               install for Claude Code, in every project
    python3 scripts/install.py --cowork      build dist/novelsmith-<version>.zip for claude.ai / Cowork
    python3 scripts/install.py --uninstall   remove it from Claude Code again

Claude Code installs plugins from a marketplace. This script copies the plugin's
own files (the allowlist the Cowork zip uses: never book/, local settings or
anything uncommitted) to a folder of their own, registers that folder as the
local "novelsmith" marketplace and installs novelsmith from it, so the folder
you downloaded can be deleted afterwards. Run it again from a newer copy to
upgrade. Your book/ is never touched.

Exit codes: 0 done, 1 a step failed (the message names it).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_zip  # noqa: E402

NAME = "novelsmith"
PLUGIN_ID = f"{NAME}@{NAME}"  # the plugin, from the marketplace of the same name
MARKETPLACE = ".claude-plugin/marketplace.json"


def default_home():
    """Where the installed copy lives: the platform's per-user application data folder."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / NAME / "plugin"


def is_ours(folder):
    """True when folder holds a novelsmith plugin, so it is safe to replace or remove."""
    try:
        manifest = json.loads((folder / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(manifest, dict) and manifest.get("name") == NAME


def remove_copy(folder):
    if folder.exists() or folder.is_symlink():
        if folder.is_symlink() or not is_ours(folder):
            sys.exit(f"install: {folder} exists and is not a novelsmith install; choose another --dir")
        shutil.rmtree(folder)


def stage(dest):
    """Copy the plugin files and the marketplace manifest to dest, replacing an earlier copy."""
    files = build_zip.plugin_files() + [ROOT / MARKETPLACE]
    new = dest.with_name(dest.name + ".new")
    remove_copy(new)
    for p in files:
        target = new / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    remove_copy(dest)
    new.rename(dest)
    return len(files)


class Claude:
    def __init__(self, exe):
        self.exe = exe

    def run(self, *args):
        print(f"$ claude {' '.join(args)}", flush=True)
        if subprocess.run([self.exe, *args], timeout=300).returncode != 0:
            sys.exit(f"install: `claude {' '.join(args)}` failed (see above)")

    def json(self, *args):
        p = subprocess.run([self.exe, *args, "--json"], capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        if p.returncode != 0:
            sys.exit(f"install: `claude {' '.join(args)} --json` failed: {(p.stderr or p.stdout).strip()}")
        try:
            return json.loads(p.stdout)
        except ValueError:
            sys.exit(f"install: `claude {' '.join(args)} --json` printed something that is not JSON; "
                     "update Claude Code (claude update) and try again")

    def marketplace_path(self):
        for m in self.json("plugin", "marketplace", "list"):
            if m.get("name") == NAME:
                return m.get("path") or m.get("installLocation") or ""
        return None

    def installed_scopes(self):
        return {p.get("scope") for p in self.json("plugin", "list") if p.get("id") == PLUGIN_ID}


def find_claude():
    exe = shutil.which("claude")
    if not exe:
        sys.exit("install: the `claude` command was not found. Install Claude Code first "
                 "(https://claude.com/claude-code), open a new terminal and run this again.\n"
                 "For Cowork in claude.ai or the desktop app, run this with --cowork instead.")
    return Claude(exe)


def install(home, scope):
    claude = find_claude()
    count = stage(home)
    print(f"Copied {count} plugin files to {home}")
    registered = claude.marketplace_path()
    if registered is not None and Path(registered).resolve() != home.resolve():
        print(f"The {NAME} marketplace pointed at {registered}; pointing it at {home} instead.")
        claude.run("plugin", "marketplace", "remove", NAME)
        registered = None
    if registered is None:
        claude.run("plugin", "marketplace", "add", str(home))
    else:
        claude.run("plugin", "marketplace", "update", NAME)
    if scope in claude.installed_scopes():
        claude.run("plugin", "update", PLUGIN_ID, "--scope", scope)
    else:
        claude.run("plugin", "install", PLUGIN_ID, "--scope", scope)
    where = "every project" if scope == "user" else f"the project in {Path.cwd()}"
    print(f"\nNovelsmith is installed for {where}. Open a terminal in your writing folder (the one that holds or "
          f"will hold book/), start `claude`, and run /novelsmith:doctor, then /novelsmith:novel-start.\n"
          f"Already running Claude Code? Run /reload-plugins there or start a new session.")


def uninstall(home, scope):
    claude = find_claude()
    if scope in claude.installed_scopes():
        claude.run("plugin", "uninstall", PLUGIN_ID, "--scope", scope)
    else:
        print(f"{PLUGIN_ID} is not installed in {scope} scope.")
    if claude.marketplace_path() is not None:
        claude.run("plugin", "marketplace", "remove", NAME)
    remove_copy(home)
    print("Removed. Your book/ folders are untouched.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--cowork", action="store_true", help="build the upload zip for claude.ai / Cowork instead")
    mode.add_argument("--uninstall", action="store_true", help="remove novelsmith from Claude Code")
    ap.add_argument("--scope", choices=("user", "project", "local"), default="user",
                    help="user: every project (default); project or local: only the project in this folder")
    ap.add_argument("--dir", type=Path, default=None, help=f"where the installed copy lives (default: {default_home()})")
    args = ap.parse_args()
    if sys.version_info < (3, 9):
        sys.exit(f"install: novelsmith needs Python 3.9 or newer; this is {sys.version.split()[0]}")
    home = (args.dir or default_home()).expanduser().resolve()
    if args.cowork:
        build_zip.main()
        print("In claude.ai or the desktop app: Customize > Plugins > Add > Upload plugin, and pick that zip.")
    elif args.uninstall:
        uninstall(home, args.scope)
    else:
        install(home, args.scope)


if __name__ == "__main__":
    main()
