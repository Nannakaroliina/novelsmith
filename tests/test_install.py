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
    """Stands in for the `claude` CLI: scopes it reports, and every command run."""

    def __init__(self, scopes, marketplace="somewhere"):
        self.scopes, self.marketplace, self.ran = set(scopes), marketplace, []

    def run(self, *args):
        self.ran.append(args)
        if args[:2] == ("plugin", "uninstall"):
            self.scopes.discard(args[-1])
        if args[:3] == ("plugin", "marketplace", "remove"):
            self.scopes, self.marketplace = set(), None

    def installed_scopes(self):
        return set(self.scopes)

    def marketplace_path(self):
        return self.marketplace


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

    def test_project_scope_from_the_plugin_folder_is_refused(self):
        for cwd in (ROOT, ROOT / "scripts"):
            with self.subTest(cwd=cwd):
                with self.assertRaises(SystemExit):
                    install.check_project_folder("project", cwd)
        install.check_project_folder("user", ROOT)
        install.check_project_folder("project", self.base)


class Uninstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve() / "plugin"
        install.stage(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def uninstall(self, claude, scope):
        with mock.patch.object(install, "find_claude", return_value=claude), redirect_stdout(io.StringIO()):
            install.uninstall(self.home, scope)

    def test_other_scopes_keep_the_marketplace_and_copy(self):
        claude = FakeClaude({"user", "project"})
        self.uninstall(claude, "project")
        self.assertEqual(claude.ran, [("plugin", "uninstall", install.PLUGIN_ID, "--scope", "project")])
        self.assertTrue(install.is_ours(self.home))

    def test_a_scope_it_is_not_in_removes_nothing(self):
        claude = FakeClaude({"user"})
        with self.assertRaises(SystemExit):
            self.uninstall(claude, "project")
        self.assertEqual(claude.ran, [])
        self.assertTrue(install.is_ours(self.home))

    def test_the_last_scope_removes_marketplace_and_copy(self):
        claude = FakeClaude({"user"})
        self.uninstall(claude, "user")
        self.assertEqual(claude.ran, [("plugin", "uninstall", install.PLUGIN_ID, "--scope", "user"),
                                      ("plugin", "marketplace", "remove", install.NAME)])
        self.assertFalse(self.home.exists())


if __name__ == "__main__":
    unittest.main()
