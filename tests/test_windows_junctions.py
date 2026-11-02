"""Windows directory junctions against the canon guard, on a real NTFS folder. Skipped elsewhere.

Run on a Windows machine (no administrator rights needed):  python -m unittest tests.test_windows_junctions -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fixture_book as fixture  # noqa: E402

SCRIPT = ROOT / "scripts" / "guard-canon.py"
HARBOUR = "# Harbour\n## ⚓ Anchored\n- The harbour freezes in March.\n"


def guard_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("guard", SCRIPT)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard


def junction(link, target):
    """mklink /J, which needs no administrator rights or Developer Mode."""
    p = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    if p.returncode != 0:
        raise unittest.SkipTest(f"cannot make a junction here: {p.stdout.strip()} {p.stderr.strip()}")


@unittest.skipUnless(os.name == "nt", "Windows junctions only")
class WindowsJunctions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        self.book = fixture.build(self.project)
        self.series = self.project / "series-bible"
        self.series.mkdir()
        (self.series / "harbour.md").write_text(HARBOUR, encoding="utf-8")
        self.shared = self.book / "bible/world/shared"
        junction(self.shared, self.series)
        self.addCleanup(os.rmdir, self.shared)  # the junction only, before the folder behind it is cleaned up
        self.guard = guard_module()

    def hook(self, path, agent=None, content=HARBOUR.replace("# Harbour", "# Harbour\nFerries run twice a day.")):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": "Write",
                   "tool_input": {"file_path": str(path), "content": content}}
        if agent:
            payload["agent_id"], payload["agent_type"] = "a1", agent
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True, text=True,
                           encoding="utf-8", env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] if p.stdout.strip() else None

    def test_the_listing_marks_a_junction(self):
        # what the link walk reads: no extra system call, the same answer DirEntry.is_junction gives from 3.12
        with os.scandir(self.shared.parent) as listing:
            entries = {e.name: e for e in listing}
        entry = entries["shared"]
        self.assertFalse(entry.is_symlink())
        self.assertTrue(entry.is_dir(follow_symlinks=False))
        self.assertEqual(entry.stat(follow_symlinks=False).st_reparse_tag, self.guard.JUNCTION_TAG)
        self.assertTrue(self.guard.is_junction_entry(entry))
        if hasattr(entry, "is_junction"):
            self.assertTrue(entry.is_junction())
        with os.scandir(self.book / "bible") as listing:
            plain = next(e for e in listing if e.name == "characters")
        self.assertFalse(self.guard.is_junction_entry(plain))

    def test_the_path_walk_follows_a_junction(self):
        self.assertTrue(self.guard.is_link(self.shared))
        self.assertEqual(os.path.normcase(self.guard.link_target(self.shared)), os.path.normcase(str(self.series)))
        # the fallback for Python before 3.12, which has no os.path.isjunction
        saved = getattr(os.path, "isjunction", None)
        if saved is not None:
            del os.path.isjunction
        try:
            self.assertTrue(self.guard.is_link(self.shared))
        finally:
            if saved is not None:
                os.path.isjunction = saved
        self.assertEqual(self.guard.leaving_link(("bible", "world", "shared", "harbour.md"), self.book),
                         "bible/world/shared/harbour.md")

    def test_a_series_bible_behind_a_junction_is_guarded(self):
        real, through = self.series / "harbour.md", self.book / "bible/world/shared/harbour.md"
        self.assertEqual(self.guard.target(str(real), self.project, self.book)[1:],
                         ("bible/world/shared/harbour.md", "real"))
        self.assertEqual(self.guard.target(str(through), self.project, self.book)[1:],
                         ("bible/world/shared/harbour.md", "through"))
        # by its real location: denied to every subagent, the shared canon checked for the author
        self.assertEqual(self.hook(real, agent="general-purpose"), "deny")
        self.assertEqual(self.hook(real, agent="novelsmith:worldbuilder"), "deny")
        self.assertEqual(self.hook(real, content="# Harbour\n- The harbour never freezes.\n"), "ask")
        # by its path in book/: only the stage whose folder it is
        self.assertEqual(self.hook(through, agent="general-purpose"), "deny")
        self.assertEqual(self.hook(through, agent="novelsmith:story-architect"), "deny")
        self.assertIsNone(self.hook(through, agent="novelsmith:worldbuilder"))


if __name__ == "__main__":
    unittest.main()
