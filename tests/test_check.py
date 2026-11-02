import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check", ROOT / "scripts" / "check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ProjectFileChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_root, check.ROOT = check.ROOT, self.root

    def tearDown(self):
        check.ROOT = self.old_root
        self.tmp.cleanup()

    def file(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return p

    def test_clean_files_pass(self):
        files = [self.file("scripts/a.py", "x = '\\u200b'\n"), self.file("hooks/h.json", '{"a": 1}\n'),
                 self.file("README.md", "Two spaces end this line  \nfor a break.\n"),
                 self.file("assets/i.png", b"\x89PNG\r\n\x1a\n\0\0\0")]
        self.assertEqual(check.check_files(files), [])
        self.assertEqual(check.check_secrets(files), [])

    def test_hygiene_problems_are_named(self):
        cases = {
            "scripts/b.py": ("x = 1 \n", "trailing whitespace"),
            "scripts/c.py": ("name = 'Eli\u200bas'\n", "invisible character U+200B"),
            "skills/s/SKILL.md": ("line\r\n", "carriage return"),
            "templates/t.md": ("no end", "no newline at the end"),
            "hooks/bad.json": ("{'a': 1}\n", "invalid JSON"),
            "docs/latin.md": ("caf\xe9\n".encode("latin-1"), "not UTF-8"),
            "skills/.DS_Store": (b"\0\0", "OS metadata file"),
        }
        for rel, (data, expected) in cases.items():
            with self.subTest(rel=rel):
                problems = check.check_files([self.file(rel, data)])
                self.assertTrue(any(expected in p for p in problems), problems)

    def test_secrets_are_found_by_content_and_name(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"  # split so this file does not trip the check itself
        problems = check.check_secrets([self.file("docs/notes.md", f"one\naws: {key}\n"),
                                        self.file("scripts/server.key", "x\n")])
        self.assertIn("docs/notes.md:2: AWS access key (AKIAABCD…)", problems)
        self.assertIn("scripts/server.key: looks like a secret file", problems)
        self.assertEqual(check.check_secrets([self.file("README.md", "Set it to sk-ant-... from the console.\n")]), [])


if __name__ == "__main__":
    unittest.main()
