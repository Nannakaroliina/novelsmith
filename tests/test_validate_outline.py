import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-outline.py"
sys.path.insert(0, str(ROOT / "scripts"))
import fixture_book as fixture  # noqa: E402
import ns_yaml  # noqa: E402


def run(book):
    p = subprocess.run([sys.executable, str(SCRIPT), "--book", str(book), "--json"],
                       capture_output=True, text=True)
    out = json.loads(p.stdout) if p.stdout.strip() else None
    return p.returncode, out, p.stderr


def checks(out, level="error"):
    return {f["check"] for f in out["findings"] if f["level"] == level}


class ValidateOutline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = fixture.build(self.tmp.name)
        self.scenes = self.book / "outline" / "scenes.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def replace(self, path, old, new, count=1):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, count), encoding="utf-8")

    def assert_error(self, check):
        code, out, err = run(self.book)
        self.assertEqual(code, 1, err)
        self.assertIn(check, checks(out), out["findings"])
        return out

    def test_fixture_passes(self):
        code, out, err = run(self.book)
        self.assertEqual(code, 0, out and out["findings"] or err)
        self.assertEqual(out["stats"]["scenes"], 12)
        self.assertTrue(out["stats"]["nordic"])

    def test_missing_turn(self):
        self.replace(self.scenes, "    turn: turn 3\n", "    turn: \"\"\n")
        self.assert_error("fields")

    def test_plain_outcome(self):
        self.replace(self.scenes, "outcome: yes-but, something", "outcome: yes", 1)
        self.assert_error("outcome")

    def test_sequel_may_end_in_decision(self):
        self.replace(self.scenes, "outcome: yes-but, something\n    value_shift: from calm 2",
                     "outcome: she decides to call him\n    value_shift: from calm 2")
        self.replace(self.scenes, '    flags: []\n    word_target: 2200', '    flags: [sequel]\n    word_target: 2200')
        code, out, _ = run(self.book)
        self.assertNotIn("outcome", checks(out))

    def test_unknown_character(self):
        self.replace(self.scenes, "characters: [Häkkinen, Tuomas Lehto]", "characters: [Häkkinen, Pekka]")
        out = self.assert_error("entities")
        self.assertTrue(any("Pekka" in f["message"] for f in out["findings"]))

    def test_accents_and_aliases_match(self):
        # "Aino" (first name), "Häkkinen" (alias) and "Riikka Salo" (full) all resolve already.
        code, out, _ = run(self.book)
        self.assertNotIn("entities", checks(out))

    def test_banned_name(self):
        (self.book / "bible/characters/elias-koski.md").write_text("# Elias Koski\n", encoding="utf-8")
        self.assert_error("names")

    def test_anchored_name_is_allowed(self):
        (self.book / "bible/characters/elias-koski.md").write_text("# Elias Koski\n", encoding="utf-8")
        self.replace(self.book / "bible/premise.md", "## ⚓ Anchored\n", "## ⚓ Anchored\n- The brother is named Elias.\n")
        code, out, _ = run(self.book)
        self.assertNotIn("names", checks(out))

    def test_missing_beat(self):
        self.replace(self.scenes, 'beat: "pinch_2"', 'beat: ""')
        self.assert_error("beats")

    def test_early_climax(self):
        self.replace(self.scenes, "beat: [climax, exposure]", 'beat: ""')
        self.replace(self.scenes, 'beat: "all_is_lost"', "beat: [climax, exposure]")
        self.assert_error("climax_placement")

    def test_beats_out_of_order(self):
        self.replace(self.scenes, 'beat: "doorway"', 'beat: "__tmp"')
        self.replace(self.scenes, 'beat: "pinch_1"', 'beat: "doorway"')
        self.replace(self.scenes, 'beat: "__tmp"', 'beat: "pinch_1"')
        self.assert_error("beat_order")

    def test_no_subplot(self):
        text = self.scenes.read_text(encoding="utf-8")
        self.scenes.write_text(re.sub(r'subplot: "[a-z]*"', 'subplot: ""', text), encoding="utf-8")
        self.assert_error("subplot")

    def test_no_compromise(self):
        self.replace(self.scenes, "flags: [compromise]", "flags: []")
        self.assert_error("compromise")

    def test_no_open_thread(self):
        self.replace(self.scenes, "flags: [open_thread]", "flags: []")
        (self.book / "outline/acts.md").write_text("# Acts\n## Threads the book leaves open on purpose\n- \n",
                                                    encoding="utf-8")
        self.assert_error("open_thread")

    def test_open_thread_from_acts_alone(self):
        self.replace(self.scenes, "flags: [open_thread]", "flags: []")
        code, out, _ = run(self.book)
        self.assertNotIn("open_thread", checks(out))

    def test_paid_clue_never_planted(self):
        self.replace(self.scenes, "clues_paid: [C01, C02]", "clues_paid: [C01, C02, C99]")
        out = self.assert_error("fair_play")
        self.assertIn("clues", checks(out))  # C99 also missing from clues.md

    def test_clue_planted_after_payoff(self):
        # Move C02's only plant from scene 7 to scene 12, after the exposure in scene 11.
        self.replace(self.scenes, "    clues_planted: \n      - C02", "    clues_planted: []")
        text = self.scenes.read_text(encoding="utf-8")
        last = text.rindex("clues_planted: []")
        self.scenes.write_text(text[:last] + "clues_planted: [C02]" + text[last + len("clues_planted: []"):],
                               encoding="utf-8")
        self.assert_error("fair_play")

    def test_duplicate_and_malformed_ids(self):
        self.replace(self.scenes, "id: ch01-s02", "id: ch01-s01")
        self.replace(self.scenes, "id: ch02-s01", "id: chapter2")
        out = self.assert_error("ids")
        messages = " ".join(f["message"] for f in out["findings"])
        self.assertIn("duplicate", messages)
        self.assertIn("ch01-s01", messages)

    def test_waiver_downgrades_error(self):
        self.replace(self.scenes, "flags: [compromise]", "flags: []")
        self.replace(self.scenes, "  waivers: {}", '  waivers: {compromise: "anchored: she stays clean"}')
        code, out, _ = run(self.book)
        self.assertEqual(code, 0)
        self.assertIn("compromise", checks(out, "waived"))

    def test_non_arc_structure_skips_beats(self):
        self.replace(self.book / "bible/premise.md", "- Subgenre", "- Structural model: kishotenketsu\n- Subgenre")
        self.replace(self.scenes, "structure: arc", "structure: kishotenketsu")
        self.replace(self.scenes, 'beat: "pinch_2"', 'beat: ""')
        code, out, _ = run(self.book)
        self.assertNotIn("beats", checks(out))
        self.assertIn("structure", checks(out, "warning"))

    def test_structure_only_in_manifest_is_an_error(self):
        self.replace(self.scenes, "structure: arc", "structure: kishotenketsu")
        self.replace(self.scenes, 'beat: "pinch_2"', 'beat: ""')
        out = self.assert_error("book_meta")
        self.assertIn("beats", checks(out))  # arc checks still apply

    def test_manifest_genre_cannot_override_premise(self):
        self.replace(self.scenes, "base_genre: mystery", "base_genre: thriller")
        self.replace(self.scenes, "clues_paid: [C01, C02]", "clues_paid: [C01, C02, C99]")
        out = self.assert_error("book_meta")
        self.assertIn("fair_play", checks(out))  # mystery checks still run

    def test_genre_placeholders_and_empty_lines(self):
        premise = self.book / "bible/premise.md"
        self.replace(premise, "- Subgenre / variant: Finnish crime", "- Subgenre / variant: (e.g. Nordic noir, cozy, procedural)")
        code, out, _ = run(self.book)
        self.assertFalse(out["stats"]["nordic"])
        self.replace(premise, "- Base genre: mystery", "- Base genre:")
        self.replace(self.scenes, "base_genre: mystery", 'base_genre: ""')
        code, out, _ = run(self.book)
        self.assertFalse(out["stats"]["mystery"])

    def test_bad_shapes_exit_2_not_1(self):
        for old, new in (("  waivers: {}", "  waivers: [open_thread]"), ("  waivers: {}", "  waivers: open_thread")):
            with self.subTest(new=new):
                text = self.scenes.read_text(encoding="utf-8")
                self.scenes.write_text(text.replace(old, new), encoding="utf-8")
                code, out, err = run(self.book)
                self.assertEqual(code, 2, err)
                self.assertTrue(out["unreadable"])
                self.assertIn("waivers", err)
                self.scenes.write_text(text, encoding="utf-8")
        self.scenes.write_text("book: My Title\nscenes: []\n", encoding="utf-8")
        code, _, err = run(self.book)
        self.assertEqual(code, 2)
        self.assertIn("'book' must be a mapping", err)

    def test_duplicate_keys_refused(self):
        self.replace(self.scenes, "\nscenes:", '\n  waivers: {compromise: "x"}\nscenes:')
        code, _, err = run(self.book)
        self.assertEqual(code, 2)
        self.assertIn("duplicate key", err)

    def test_non_utf8_bible_file_does_not_crash(self):
        (self.book / "bible/characters/tuomas-lehto.md").write_bytes("# Tuomas Lehto\n- caf\xe9\n".encode("latin-1"))
        code, out, err = run(self.book)
        self.assertEqual(code, 0, err)

    def test_lookalike_letters_in_names(self):
        (self.book / "bible/characters/elias-koski.md").write_text("# Еlias Koski\n", encoding="utf-8")
        out = self.assert_error("names")
        self.assertTrue(any("mixes letters" in f["message"] for f in out["findings"]))
        (self.book / "bible/characters/elias-koski.md").write_text("# Eli​as Koski\n", encoding="utf-8")
        out = self.assert_error("names")
        self.assertTrue(any("invisible" in f["message"] for f in out["findings"]))

    def test_every_anchored_section_counts_but_comments_do_not(self):
        (self.book / "bible/characters/elias-koski.md").write_text("# Elias Koski\n", encoding="utf-8")
        premise = self.book / "bible/premise.md"
        self.replace(premise, "## ⚓ Anchored\n", "## ⚓ Anchored\n<!-- Elias approved -->\n")
        self.assert_error("names")
        premise.write_text(premise.read_text(encoding="utf-8") + "\n## ⚓ Anchored names\n- Elias stays.\n",
                           encoding="utf-8")
        code, out, _ = run(self.book)
        self.assertNotIn("names", checks(out))

    def test_late_compromise_ok_when_an_earlier_one_exists(self):
        self.replace(self.scenes, "flags: [open_thread]", "flags: [open_thread, compromise]")
        code, out, _ = run(self.book)
        self.assertNotIn("compromise", checks(out, "warning"))
        self.replace(self.scenes, "flags: [compromise]", "flags: []")
        code, out, _ = run(self.book)
        self.assertIn("compromise", checks(out, "warning"))

    def test_weekdays_are_not_story_days(self):
        text = self.scenes.read_text(encoding="utf-8")
        text = re.sub(r'time: "Day \d+, (07:\d\d)"', r'time: "Monday \1"', text)
        self.scenes.write_text(text.replace("flags: [nonlinear]", "flags: []"), encoding="utf-8")
        code, out, _ = run(self.book)
        self.assertIn("nonlinear", checks(out, "warning"))

    def test_uniform_chapters_warn(self):
        # Give every chapter the same total, whatever its scene count.
        per_chapter = {ch: fixture.CHAPTERS.count(ch) for ch in fixture.CHAPTERS}
        sizes = iter(4500 // per_chapter[ch] for ch in fixture.CHAPTERS)
        text = re.sub(r"word_target: \d+", lambda m: f"word_target: {next(sizes)}",
                      self.scenes.read_text(encoding="utf-8"))
        self.scenes.write_text(text, encoding="utf-8")
        code, out, _ = run(self.book)
        self.assertIn("chapter_shape", checks(out, "warning"))

    def test_missing_manifest_exits_2(self):
        self.scenes.unlink()
        code, out, err = run(self.book)
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)

    def test_bad_yaml_reports_line(self):
        self.scenes.write_text("book:\n  title: x\n    oops: 1\n", encoding="utf-8")
        code, _, err = run(self.book)
        self.assertEqual(code, 2)
        self.assertIn("line 3", err)


class MiniYaml(unittest.TestCase):
    def test_fallback_matches_pyyaml_on_fixture(self):
        text = fixture.scenes_yaml()
        mine = ns_yaml._Parser(text).parse()
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        self.assertEqual(mine, yaml.safe_load(text))

    def test_template_parses(self):
        text = (ROOT / "templates" / "scenes.yaml").read_text(encoding="utf-8")
        data = ns_yaml._Parser(text).parse()
        self.assertEqual(data["book"]["waivers"], {})
        self.assertEqual(data["scenes"][0]["id"], "ch01-s01")
        self.assertEqual(data["scenes"][0]["characters"], [])

    PARITY_CASES = [
        "characters: [Siobhan O'Brien, Aino]\n",
        "subplot: Aino's debt   # B story\n",
        "turn: Aino's plan fails   # note: revisit\n",
        "pov: O'Brien  # narrator\n",
        "- 'quoted, with comma'\n- it's fine\n",
        "a: ['x, y', \"z\"]\n",
        "chapter: 08\n", "chapter: 010\n", "chapter: 0\n", "chapter: 1_000\n", "n: 0x1F\n", "n: 0b101\n",
        "t: 12:30\n", "t: 1:20:30\n", "f: 1e4\n", "f: 1.5e+3\n", "f: .5\n", "f: -.inf\n", "f: 3.\n",
        "b: no\n", "b: On\n", "b: YES\n", "b: off\n", "b: maybe\n",
        "n: -12\n", "n: +7\n", "s: 2026-10-29x\n",
    ]

    def test_fallback_matches_pyyaml_on_tricky_scalars(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        for text in self.PARITY_CASES:
            with self.subTest(text=text):
                self.assertEqual(ns_yaml._Parser(text).parse(), yaml.safe_load(text))

    def test_apostrophes_without_pyyaml(self):
        p = lambda t: ns_yaml._Parser(t).parse()  # noqa: E731
        self.assertEqual(p("characters: [Siobhan O'Brien, Aino]\n"), {"characters": ["Siobhan O'Brien", "Aino"]})
        self.assertEqual(p("subplot: Aino's debt   # B story\n"), {"subplot": "Aino's debt"})
        self.assertEqual(p("chapter: 08\n"), {"chapter": "08"})
        self.assertEqual(p("b: no\n"), {"b": False})

    def test_unquoted_colon_rejected_like_pyyaml(self):
        with self.assertRaises(ns_yaml.YAMLError) as cm:
            ns_yaml._Parser("outcome: no-and: the key is gone\n").parse()
        self.assertIn("quote", str(cm.exception))
        self.assertEqual(ns_yaml._Parser('outcome: "no-and: the key is gone"\n').parse(),
                         {"outcome": "no-and: the key is gone"})

    def test_block_scalars_and_quotes(self):
        data = ns_yaml._Parser("a: |\n  one\n  two\nb: >-\n  x\n  y\nc: 'it''s'\nd: \"q # not comment\"\n").parse()
        self.assertEqual(data, {"a": "one\ntwo\n", "b": "x y", "c": "it's", "d": "q # not comment"})


if __name__ == "__main__":
    unittest.main()
