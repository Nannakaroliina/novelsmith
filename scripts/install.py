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

The copy carries a marker file, and the script only ever deletes a folder that
has it: never the plugin folder you run it from, a writing project or a folder
--dir points at by mistake.

Exit codes: 0 done, 1 a step failed (the message names it).
"""

import argparse
import json
import os
import shutil
import stat
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
MARKER = ".novelsmith-installed-copy"


def default_home():
    """Where the installed copy lives: the platform's per-user application data folder."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / NAME / "plugin"


def check_home(home):
    """Refuse an installed-copy folder that is, holds or sits inside the plugin folder this runs from."""
    if home == ROOT or ROOT in home.parents or home in ROOT.parents:
        sys.exit(f"install: --dir {home} overlaps the plugin folder {ROOT}; the installed copy needs a folder "
                 f"of its own (leave out --dir to use {default_home()})")


def check_project_folder(scope, cwd):
    """--scope project/local installs for the folder this runs in, which must be the writing project."""
    if scope != "user" and (cwd == ROOT or ROOT in cwd.parents):
        sys.exit(f"install: --scope {scope} installs for the folder you run this in, and that is the plugin "
                 f"folder. Open a terminal in your writing folder and run:\n"
                 f"    python3 \"{ROOT / 'scripts' / 'install.py'}\" --scope {scope}")


def is_ours(folder):
    """True when folder is a copy this script made (it has the marker), so it may be replaced or removed."""
    return folder.is_dir() and not folder.is_symlink() and (folder / MARKER).is_file()


def _make_writable_and_retry(func, path, _exc):
    """rmtree error handler: a read-only file (common on Windows) is made writable and deleted again."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rmtree(path):
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def delete_copy(folder):
    """Delete a copy this script made, the marker last: a copy left half-deleted by an error is still
    recognised as ours, so the next run can finish the job."""
    for child in folder.iterdir():
        if child.name == MARKER:
            continue
        if child.is_dir() and not child.is_symlink():
            _rmtree(child)
        else:
            try:
                child.unlink()
            except PermissionError:
                os.chmod(child, stat.S_IWRITE)
                child.unlink()
    (folder / MARKER).unlink()
    folder.rmdir()


def remove_copy(folder):
    if folder.exists() or folder.is_symlink():
        if not is_ours(folder):
            sys.exit(f"install: {folder} exists and was not made by this installer (it has no {MARKER} file); "
                     "nothing was deleted. Choose another --dir.")
        delete_copy(folder)


def stage(dest):
    """Copy the plugin files and the marketplace manifest to dest. An earlier copy is moved aside first and
    deleted only once the new one is in place, so a failure never leaves dest half-deleted."""
    check_home(dest)
    if (dest.exists() or dest.is_symlink()) and not is_ours(dest):
        remove_copy(dest)  # exits with the reason, before anything is written
    files = build_zip.plugin_files() + [ROOT / MARKETPLACE]
    new, old = dest.with_name(dest.name + ".new"), dest.with_name(dest.name + ".old")
    remove_copy(new)  # left by an interrupted run
    remove_copy(old)
    new.mkdir(parents=True)
    (new / MARKER).write_text("Made by novelsmith's scripts/install.py; it may delete or replace this folder.\n",
                              encoding="utf-8")
    for p in files:
        target = new / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    if dest.exists():
        dest.rename(old)
    try:
        new.rename(dest)
    except OSError:
        if old.exists() and not dest.exists():
            old.rename(dest)  # put the working copy back
        raise
    try:
        remove_copy(old)
    except OSError as exc:
        print(f"Could not delete the previous copy {old} ({exc}); the next run deletes it, or delete it by hand.")
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
        """The scopes novelsmith is installed in, as Claude Code sees them from the current folder."""
        return {p.get("scope") for p in self.json("plugin", "list") if p.get("id") == PLUGIN_ID}


def find_claude():
    exe = shutil.which("claude")
    if not exe:
        sys.exit("install: the `claude` command was not found. Install Claude Code first "
                 "(https://claude.com/claude-code), open a new terminal and run this again.\n"
                 "For Cowork in claude.ai or the desktop app, run this with --cowork instead.")
    return Claude(exe)


def install(home, scope):
    check_home(home)
    check_project_folder(scope, Path.cwd().resolve())
    claude = find_claude()
    count = stage(home)
    print(f"Copied {count} plugin files to {home}")
    scopes = {scope}
    registered = claude.marketplace_path()
    if registered is not None and (not registered or Path(registered).resolve() != home):
        # Removing a marketplace uninstalls its plugins everywhere, so reinstall where it was.
        scopes |= claude.installed_scopes()
        print(f"The {NAME} marketplace pointed at {registered or 'another folder'}; pointing it at {home} instead "
              f"and reinstalling for: {', '.join(sorted(scopes))}.")
        claude.run("plugin", "marketplace", "remove", NAME)
        registered = None
    if registered is None:
        claude.run("plugin", "marketplace", "add", str(home))
    else:
        claude.run("plugin", "marketplace", "update", NAME)
    installed = claude.installed_scopes()
    for s in sorted(scopes):
        claude.run("plugin", "update" if s in installed else "install", PLUGIN_ID, "--scope", s)
    where = "every project" if scope == "user" else f"the project in {Path.cwd()}"
    print(f"\nNovelsmith is installed for {where}. Open a terminal in your writing folder (the one that holds or "
          f"will hold book/), start `claude`, and run /novelsmith:doctor, then /novelsmith:novel-start.\n"
          f"Already running Claude Code? Run /reload-plugins there or start a new session.")


def uninstall(home, scope):
    check_home(home)
    claude = find_claude()
    scopes = claude.installed_scopes()
    if scope in scopes:
        claude.run("plugin", "uninstall", PLUGIN_ID, "--scope", scope)
    elif scopes:
        sys.exit(f"install: {PLUGIN_ID} is not installed in {scope} scope (it is in: {', '.join(sorted(scopes))}); "
                 f"nothing was removed. Pass --scope to choose which one to uninstall.")
    remaining = claude.installed_scopes()
    if remaining:
        print(f"Uninstalled from {scope} scope. Still installed in: {', '.join(sorted(remaining))}, so the "
              f"{NAME} marketplace and {home} stay.")
        return
    if claude.marketplace_path() is not None:
        print(f"Removing the {NAME} marketplace; any other project that installed novelsmith with --scope project "
              "loses it too.")
        claude.run("plugin", "marketplace", "remove", NAME)
    remove_copy(home)
    print("Removed. Your book/ folders are untouched.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--cowork", action="store_true", help="build the upload zip for claude.ai / Cowork instead")
    mode.add_argument("--uninstall", action="store_true", help="remove novelsmith from Claude Code")
    ap.add_argument("--scope", choices=("user", "project", "local"), default="user",
                    help="user: every project (default); project or local: only the project in the current folder "
                         "(run this from your writing folder)")
    ap.add_argument("--dir", type=Path, default=None,
                    help=f"where the installed copy lives, a folder of its own (default: {default_home()})")
    args = ap.parse_args()
    if sys.version_info < (3, 9):
        sys.exit(f"install: novelsmith needs Python 3.9 or newer; this is {sys.version.split()[0]}")
    home = (args.dir or default_home()).expanduser().resolve()
    try:
        if args.cowork:
            build_zip.main()
            print("In claude.ai or the desktop app: Customize > Plugins > Add > Upload plugin, and pick that zip.")
        elif args.uninstall:
            uninstall(home, args.scope)
        else:
            install(home, args.scope)
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"install: {exc}\nNothing in your book/ was touched. Close Claude Code if it is running and run "
                 "this again.")


if __name__ == "__main__":
    main()
