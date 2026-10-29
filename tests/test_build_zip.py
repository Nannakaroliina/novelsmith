import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_zip", ROOT / "scripts" / "build_zip.py")
build_zip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_zip)


class SelectFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel in ("skills/s/SKILL.md", "agents/a.md", "scripts/x.py", "scripts/build_zip.py", "README.md",
                    ".claude-plugin/plugin.json", "tests/t.py", "docs/d.md", "book/bible/premise.md", ".env",
                    ".ravenwatch.md", "skills/.DS_Store", "scripts/__pycache__/x.pyc", "scripts/server.key",
                    ".claude/settings.local.json", "templates/.hidden"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text("x", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def rels(self, paths):
        return {p.relative_to(self.root).as_posix() for p in paths}

    def test_allowlist_only(self):
        files, secrets = build_zip.select_files(self.root, None)
        self.assertEqual(self.rels(files), {"skills/s/SKILL.md", "agents/a.md", "scripts/x.py", "README.md",
                                            ".claude-plugin/plugin.json"})
        self.assertEqual(self.rels(secrets), {"scripts/server.key"})

    def test_untracked_files_stay_out(self):
        files, _ = build_zip.select_files(self.root, {"skills/s/SKILL.md", "README.md"})
        self.assertEqual(self.rels(files), {"skills/s/SKILL.md", "README.md"})


class Frontmatter(unittest.TestCase):
    def check(self, text, folder="demo"):
        with tempfile.TemporaryDirectory() as tmp:
            old_root = build_zip.ROOT
            build_zip.ROOT = Path(tmp)
            try:
                p = Path(tmp) / "skills" / folder / "SKILL.md"
                p.parent.mkdir(parents=True)
                p.write_text(text, encoding="utf-8")
                return build_zip.frontmatter_problems(p, True)
            finally:
                build_zip.ROOT = old_root

    def test_clean(self):
        self.assertEqual(self.check("---\nname: demo\ndescription: Does a thing.\n---\nbody\n"), [])

    def test_rejects_angle_brackets_long_descriptions_and_wrong_names(self):
        self.assertTrue(self.check("---\nname: demo\ndescription: see <slug>.md\n---\n"))
        self.assertTrue(self.check("---\nname: demo\ndescription: " + "x" * 1025 + "\n---\n"))
        self.assertTrue(self.check("---\nname: other\ndescription: ok\n---\n"))
        self.assertTrue(self.check("no frontmatter\n"))

    def test_repo_skills_pass(self):
        problems = []
        for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
            problems += build_zip.frontmatter_problems(p, True)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
