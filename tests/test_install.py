import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("install", ROOT / "scripts" / "install.py")
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class FakeClaude:
    """Stands in for the `claude` CLI as it behaves: every project's installs are listed wherever it runs,
    project and local ones with their folder; removing the marketplace uninstalls them all."""

    def __init__(self, installs=(), marketplace=None):
        self.installs_, self.marketplace, self.ran = set(installs), marketplace, []

    def here(self, scope):
        return (scope, None if scope == "user" else str(Path.cwd().resolve()))

    def run(self, *args):
        self.ran.append(args)
        if args[:2] == ("plugin", "uninstall"):
            self.installs_.discard(self.here(args[-1]))
        elif args[:2] == ("plugin", "install"):
            self.installs_.add(self.here(args[-1]))
        elif args[:3] == ("plugin", "marketplace", "add"):
            self.marketplace = args[3]
        elif args[:3] == ("plugin", "marketplace", "remove"):
            self.installs_, self.marketplace = set(), None

    def installs(self):
        return sorted(self.installs_, key=str)

    def marketplace_path(self):
        return self.marketplace


class InFolder(unittest.TestCase):
    """Runs each test in a fresh temp folder (the 'writing folder'), with an installed-copy home next to it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.writing, self.other = self.base / "writing", self.base / "other-book"
        self.writing.mkdir()
        self.other.mkdir()
        self.home = self.base / "plugin"
        old_cwd = os.getcwd()
        os.chdir(self.writing)
        self.addCleanup(os.chdir, old_cwd)
        self.addCleanup(self.tmp.cleanup)

    def call(self, fn, claude, *args):
        out = io.StringIO()
        with mock.patch.object(install, "find_claude", return_value=claude), redirect_stdout(out):
            fn(*args)
        return out.getvalue()


class InstalledCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.dest = self.base / "plugin"

    def tearDown(self):
        self.tmp.cleanup()

    def shipped(self):
        return {p.relative_to(ROOT).as_posix() for p in install.build_zip.plugin_files()} | {install.MARKETPLACE}

    def contents(self, folder):
        return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}

    def test_stage_twice_holds_exactly_the_plugin_files(self):
        for _ in range(2):
            install.stage(self.dest)
        self.assertEqual(self.contents(self.dest), self.shipped() | {install.MARKER})
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["plugin"])  # no .new or .old left
        self.assertFalse(any(name.startswith(("tests/", "book/", "docs/")) for name in self.contents(self.dest)))
        self.assertNotIn("scripts/install.py", self.contents(self.dest))

    def test_folders_it_did_not_make_are_never_deleted(self):
        clone = self.base / "novelsmith-main"  # a downloaded plugin folder: right plugin.json, no marker
        (clone / ".claude-plugin").mkdir(parents=True)
        (clone / ".claude-plugin/plugin.json").write_text(json.dumps({"name": "novelsmith"}), encoding="utf-8")
        (clone / "book").mkdir()
        (clone / "book/progress.md").write_text("my notes\n", encoding="utf-8")
        writing = self.base / "writing"
        writing.mkdir()
        (writing / "chapter.md").write_text("prose\n", encoding="utf-8")
        for folder in (clone, writing):
            with self.subTest(folder=folder.name):
                with self.assertRaises(SystemExit):
                    install.remove_copy(folder)
                with self.assertRaises(SystemExit):
                    install.stage(folder)
        self.assertEqual((clone / "book/progress.md").read_text(encoding="utf-8"), "my notes\n")
        self.assertEqual(self.contents(writing), {"chapter.md"})
        self.assertFalse((self.base / "writing.new").exists())

    @unittest.skipIf(os.name == "nt", "creating symlinks needs extra rights on Windows")
    def test_a_link_to_a_copy_is_refused_and_its_target_kept(self):
        install.stage(self.dest)
        link = self.base / "link"
        link.symlink_to(self.dest, target_is_directory=True)
        with self.assertRaises(SystemExit):
            install.remove_copy(link)
        self.assertTrue((self.dest / install.MARKER).is_file())

    def test_the_plugin_folder_and_its_relatives_are_refused(self):
        for home in (ROOT, ROOT / "plugin", ROOT.parent):
            with self.subTest(home=home):
                with self.assertRaises(SystemExit):
                    install.check_home(home)
        install.check_home(self.dest)  # an unrelated folder is fine

    def test_a_half_deleted_copy_is_still_recognised(self):
        install.stage(self.dest)
        with mock.patch.object(install.shutil, "rmtree", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                install.delete_copy(self.dest)
        self.assertTrue(install.is_ours(self.dest))
        install.remove_copy(self.dest)
        self.assertFalse(self.dest.exists())

    def test_an_empty_leftover_folder_does_not_block_the_next_run(self):
        (self.base / "plugin.old").mkdir()  # what a failed final rmdir leaves behind
        install.stage(self.dest)
        self.assertFalse((self.base / "plugin.old").exists())
        self.assertTrue(install.is_ours(self.dest))

    def test_project_scope_from_the_plugin_folder_is_refused(self):
        for cwd in (ROOT, ROOT / "scripts"):
            with self.subTest(cwd=cwd):
                with self.assertRaises(SystemExit):
                    install.check_project_folder("project", cwd)
        install.check_project_folder("user", ROOT)
        install.check_project_folder("project", self.base)


class Uninstall(InFolder):
    def setUp(self):
        super().setUp()
        install.stage(self.home)

    def uninstall(self, claude, scope):
        return self.call(install.uninstall, claude, self.home, scope)

    def test_other_scopes_keep_the_marketplace_and_copy(self):
        claude = FakeClaude({("user", None), ("project", str(self.writing))}, str(self.home))
        self.uninstall(claude, "project")
        self.assertEqual(claude.ran, [("plugin", "uninstall", install.PLUGIN_ID, "--scope", "project")])
        self.assertTrue(install.is_ours(self.home))

    def test_another_projects_install_is_left_alone_and_named(self):
        claude = FakeClaude({("project", str(self.other))}, str(self.home))
        with self.assertRaises(SystemExit) as stop:
            self.uninstall(claude, "project")
        self.assertIn(str(self.other), str(stop.exception.code))
        self.assertIn("--uninstall --scope project", str(stop.exception.code))
        self.assertEqual(claude.ran, [])
        self.assertTrue(install.is_ours(self.home))

    def test_project_scope_from_the_plugin_folder_is_refused_before_anything_runs(self):
        claude = FakeClaude({("project", str(self.writing))}, str(self.home))
        os.chdir(ROOT)
        with self.assertRaises(SystemExit) as stop:
            self.uninstall(claude, "project")
        self.assertIn("--uninstall --scope project", str(stop.exception.code))
        self.assertEqual(claude.ran, [])

    def test_the_last_scope_removes_marketplace_and_copy(self):
        claude = FakeClaude({("user", None)}, str(self.home))
        out = self.uninstall(claude, "user")
        self.assertEqual(claude.ran, [("plugin", "uninstall", install.PLUGIN_ID, "--scope", "user"),
                                      ("plugin", "marketplace", "remove", install.NAME)])
        self.assertFalse(self.home.exists())
        self.assertIn("Removed", out)

    def test_a_copy_made_with_dir_is_removed_too(self):
        elsewhere = self.base / "custom" / "plugin"
        install.stage(elsewhere)
        claude = FakeClaude({("user", None)}, str(elsewhere))
        self.uninstall(claude, "user")
        self.assertFalse(elsewhere.exists())
        self.assertFalse(self.home.exists())

    def test_nothing_installed_says_so(self):
        install.remove_copy(self.home)
        out = self.uninstall(FakeClaude(), "user")
        self.assertIn("nothing to remove", out)


class Install(InFolder):
    def install(self, claude, scope="user"):
        return self.call(install.install, claude, self.home, scope)

    def test_first_install_adds_the_marketplace(self):
        claude = FakeClaude()
        self.install(claude)
        self.assertEqual(claude.ran, [("plugin", "marketplace", "add", str(self.home)),
                                      ("plugin", "install", install.PLUGIN_ID, "--scope", "user")])

    def test_upgrade_in_place_updates(self):
        claude = FakeClaude({("user", None)}, str(self.home))
        install.stage(self.home)
        self.install(claude)
        self.assertEqual(claude.ran, [("plugin", "marketplace", "update", install.NAME),
                                      ("plugin", "update", install.PLUGIN_ID, "--scope", "user")])

    def test_repointing_reinstalls_this_folders_scopes_only_and_names_other_projects(self):
        old = self.base / "old" / "plugin"
        install.stage(old)
        claude = FakeClaude({("user", None), ("local", str(self.writing)), ("project", str(self.other))}, str(old))
        out = self.install(claude)
        self.assertEqual(claude.ran, [("plugin", "marketplace", "remove", install.NAME),
                                      ("plugin", "marketplace", "add", str(self.home)),
                                      ("plugin", "install", install.PLUGIN_ID, "--scope", "local"),
                                      ("plugin", "install", install.PLUGIN_ID, "--scope", "user")])
        self.assertNotIn(("project", str(self.writing)), claude.installs_)  # no project install made here
        self.assertIn(str(self.other), out)
        self.assertFalse(old.exists())  # the previous marked copy is cleaned up
        self.assertTrue(install.is_ours(self.home))

    def test_a_marketplace_at_a_plugin_clone_is_repointed_but_the_clone_kept(self):
        clone = self.base / "novelsmith-main"
        (clone / ".claude-plugin").mkdir(parents=True)
        (clone / ".claude-plugin/plugin.json").write_text(json.dumps({"name": "novelsmith"}), encoding="utf-8")
        claude = FakeClaude({("user", None)}, str(clone))
        self.install(claude)
        self.assertTrue((clone / ".claude-plugin/plugin.json").exists())
        self.assertEqual(claude.marketplace, str(self.home))


if __name__ == "__main__":
    unittest.main()
