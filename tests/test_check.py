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

    def test_every_credential_format_is_caught_and_a_near_miss_is_not(self):
        # Built from pieces so this file does not trip the check itself.
        cases = {
            "private key": ("-----BEGIN " + "RSA PRIVATE KEY-----", "-----BEGIN " + "PUBLIC KEY-----"),
            "AWS access key": ("AKIA" + "Q" * 16, "AKIA" + "Q" * 15),
            "GitHub token": ("gh" + "p_" + "A" * 36, "gh" + "p_" + "A" * 35),
            "Anthropic API key": ("sk-" + "ant-" + "a" * 30, "sk-" + "ant-" + "a" * 29),
            "OpenAI API key": ("sk-" + "proj-" + "a" * 40, "sk-" + "proj-" + "a" * 39),
            "Google API key": ("AI" + "za" + "A" * 35, "AI" + "za" + "A" * 34),
            "Slack token": ("xo" + "xb-" + "1" * 10, "xo" + "xb-" + "1" * 9),
        }
        for label, (real, near_miss) in cases.items():
            with self.subTest(label=label):
                found = check.check_secrets([self.file("docs/real.md", f"value: {real}\n")])
                self.assertTrue(any(f": {label} (" in p for p in found), found)
                self.assertEqual(check.check_secrets([self.file("docs/near.md", f"value: {near_miss} end\n")]), [])


if __name__ == "__main__":
    unittest.main()
