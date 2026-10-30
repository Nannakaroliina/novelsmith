import json
import os
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


def need_pyyaml(test):
    """Skip a PyYAML-only test, or fail it when NOVELSMITH_REQUIRE_PYYAML is set (the PyYAML check run)."""
    if ns_yaml._pyyaml is None:
        if os.environ.get("NOVELSMITH_REQUIRE_PYYAML"):
            test.fail("PyYAML is not installed, but NOVELSMITH_REQUIRE_PYYAML is set")
        test.skipTest("PyYAML not installed")


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

    def test_output_survives_a_windows_console(self):
        (self.book / "bible/characters/elias-koski.md").write_text("# Elias Koski\n", encoding="utf-8")
        p = subprocess.run([sys.executable, str(SCRIPT), "--book", str(self.book)], capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "cp1252"})
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("FAIL:", p.stdout)

    def test_genre_words_are_whole_and_the_last_names_the_base(self):
        premise = self.book / "bible/premise.md"
        for genre, mystery in (("cozy fantasy", False), ("historical (Crimean War)", False), ("cozy mystery", True),
                               ("crime fiction", True), ("crime thriller", False), ("cozy sci-fi", False),
                               ("cozy science fiction", False), ("fantasy (cozy)", False), ("Finnish crime", True)):
            with self.subTest(genre=genre):
                text = premise.read_text(encoding="utf-8")
                premise.write_text(re.sub(r"- Base genre: .*", f"- Base genre: {genre}", text), encoding="utf-8")
                self.replace(self.scenes, re.search(r"  base_genre: .*", self.scenes.read_text(encoding="utf-8"))
                             .group(), f'  base_genre: "{genre}"')
                code, out, err = run(self.book)
                self.assertEqual(out["stats"]["mystery"], mystery, err)

    def test_target_length_forms(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("validator", SCRIPT)
        v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v)
        for text, words in (("85,000 words", 85000), ("85 000", 85000), ("85.000 sanaa", 85000), ("85k", 85000),
                            ("1.5k", 1500), ("80–90k words", 90000), ("80-90,000 words", 90000),
                            ("80,000 to 90,000", 90000), ("85,000, 24 chapters", 85000), ("about a novel", None)):
            with self.subTest(text=text):
                self.assertEqual(v.premise_words(f"## Genre\n- Target length: {text}\n"), words)

    def test_value_shift_check_is_linear(self):
        import importlib.util
        import time
        spec = importlib.util.spec_from_file_location("validator", SCRIPT)
        v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(v)
        start = time.monotonic()
        self.assertFalse(v.is_shift("from " * 200_000))
        self.assertLess(time.monotonic() - start, 1)
        self.assertTrue(v.is_shift("from safety to exposure"))
        self.assertFalse(v.is_shift("to safety from exposure"))

    def test_banned_names_of_several_words(self):
        self.replace(self.book / "bible/style.md", "Elias, Mara, Elara", "Elias, Mara, Elara, O'Connor, Mary-Jane")
        (self.book / "bible/characters/siobhan.md").write_text("# Siobhan O'Connor\n", encoding="utf-8")
        out = self.assert_error("names")
        self.assertTrue(any("O'Connor" in f["message"] for f in out["findings"]))

    def test_target_length_in_the_premise_is_compared(self):
        premise = self.book / "bible/premise.md"
        self.replace(premise, "## Genre\n", "## Genre\n- Target length: 60,000 words\n")
        code, out, err = run(self.book)
        self.assertIn("length", checks(out, "warning"))
        self.replace(premise, "60,000 words", "27k")
        code, out, err = run(self.book)
        self.assertFalse([f for f in out["findings"] if "Target length" in f["message"]])

    def test_fixture_passes(self):
        code, out, err = run(self.book)
        self.assertEqual(code, 0, out and out["findings"] or err)
        self.assertEqual(out["stats"]["scenes"], 12)
        self.assertTrue(out["stats"]["nordic"])
        self.assertEqual(checks(out, "warning"), set())  # pin: a new warning on a good outline is a regression

    def test_non_mystery_uses_plain_beats(self):
        self.replace(self.book / "bible/premise.md", "- Base genre: mystery", "- Base genre: literary")
        self.replace(self.scenes, "base_genre: mystery", "base_genre: literary")
        code, out, _ = run(self.book)
        self.assertIn("beats", checks(out))  # inciting_crime / exposure do not count outside a mystery
        self.replace(self.scenes, 'beat: "inciting_crime"', 'beat: "inciting"')
        self.replace(self.scenes, "beat: [climax, exposure]", "beat: climax")
        self.replace(self.scenes, "clues_paid: [C01, C02]", "clues_paid: []")
        code, out, err = run(self.book)
        self.assertEqual(code, 0, out and out["findings"] or err)
        self.assertFalse(out["stats"]["mystery"])

    def test_clue_paid_in_the_scene_it_is_planted_fails(self):
        self.replace(self.scenes, "clues_paid: [C01, C02]", "clues_paid: [C01, C02]\n    # same-scene plant below")
        text = self.scenes.read_text(encoding="utf-8")
        idx = text.index("clues_paid: [C01, C02]")
        start = text.rindex("clues_planted:", 0, idx)
        end = text.index("\n", start)
        self.scenes.write_text(text[:start] + "clues_planted: [C03]" + text[end:]
                               .replace("clues_paid: [C01, C02]", "clues_paid: [C01, C02, C03]", 1), encoding="utf-8")
        clues = self.book / "bible/clues.md"
        self.replace(clues, "| C02 | wet boots |", "| C02 | wet boots |\n| C03 | the ferry ticket |")
        self.assert_error("fair_play")

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

    def test_anchored_settings_win_over_earlier_lines(self):
        premise = self.book / "bible/premise.md"
        self.replace(premise, "## ⚓ Anchored\n", "## ⚓ Anchored\n- Structural model: arc\n- Base genre: mystery\n")
        self.replace(premise, "- Base genre: mystery\n- Subgenre",
                     "- Base genre: literary\n<!--\n- Structural model: kishotenketsu\n-->\n- Subgenre")
        self.replace(self.scenes, "structure: arc", "structure: kishotenketsu")
        self.replace(self.scenes, 'beat: "pinch_2"', 'beat: ""')
        out = self.assert_error("book_meta")       # the manifest disagrees with the anchored model
        self.assertIn("beats", checks(out))        # arc checks still run
        self.assertTrue(out["stats"]["mystery"])   # the anchored genre, not the earlier line

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
        self.assertTrue(any("mixes look-alike letters" in f["message"] for f in out["findings"]))
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

    def test_non_finite_word_targets_cannot_silence_placement(self):
        self.replace(self.scenes, "beat: [climax, exposure]", 'beat: ""')
        self.replace(self.scenes, 'beat: "doorway"', "beat: [climax, exposure]")
        self.assert_error("climax_placement")
        for bad in (".nan", ".inf", "1e308", "1.0e+308", "2000000"):
            with self.subTest(bad=bad):
                text = self.scenes.read_text(encoding="utf-8")
                self.scenes.write_text(text.replace("word_target: 1500", f"word_target: {bad}", 1), encoding="utf-8")
                code, out, err = run(self.book)
                self.assertEqual(code, 1, err)
                self.assertIn("fields", checks(out))
                self.assertIn("climax_placement", checks(out))
                self.scenes.write_text(text, encoding="utf-8")

    def test_non_latin_names_must_have_sheets(self):
        (self.book / "bible/characters/ivan-petrov.md").write_text("# Иван Петров\n", encoding="utf-8")
        self.replace(self.scenes, "characters: [Häkkinen, Tuomas Lehto]", "characters: [Häkkinen, Иван Петров]")
        code, out, _ = run(self.book)
        self.assertNotIn("entities", checks(out))     # the real sheet matches
        self.replace(self.scenes, "characters: [Häkkinen, Иван Петров]", "characters: [Häkkinen, Пётр]")
        out = self.assert_error("entities")           # an unknown Cyrillic name no longer slips through
        self.assertTrue(any("Пётр" in f["message"] for f in out["findings"]))

    def test_normal_non_latin_names_are_not_suspicious(self):
        for name in ("田中さくら", "Kaʻiulani", "Ηλέκτρα", "Иван"):
            with self.subTest(name=name):
                slug = f"x{abs(hash(name)) % 1000}"
                (self.book / f"bible/characters/{slug}.md").write_text(f"# {name}\n", encoding="utf-8")
                code, out, _ = run(self.book)
                self.assertNotIn("names", checks(out))
                (self.book / f"bible/characters/{slug}.md").unlink()

    def test_names_keep_marks_outside_latin_greek_cyrillic(self):
        v = RulesStayInSync.load_validator()
        self.assertNotEqual(v.norm("राम"), v.norm("रीमा"))
        self.assertNotEqual(v.norm("だ"), v.norm("た"))
        self.assertNotEqual(v.norm("ガン"), v.norm("カン"))
        self.assertEqual(v.norm("Häkkinen"), "hakkinen")
        self.assertEqual(v.norm("Ηλέκτρα"), v.norm("Ηλεκτρα"))
        (self.book / "bible/characters/ram.md").write_text("# राम\n", encoding="utf-8")
        self.replace(self.scenes, "characters: [Häkkinen, Tuomas Lehto]", "characters: [Häkkinen, रीमा]")
        self.assert_error("entities")

    def test_status_of_the_wrong_type_is_a_field_error(self):
        self.replace(self.scenes, "status: planned", "status: [planned]")
        self.assert_error("fields")

    def test_unused_waiver_is_reported(self):
        self.replace(self.scenes, "  waivers: {}", '  waivers: {open_threads: "typo", compromise: "fine"}')
        code, out, _ = run(self.book)
        self.assertEqual(code, 0)
        msgs = [f["message"] for f in out["findings"] if f["check"] == "waivers"]
        self.assertEqual(len(msgs), 2)  # a typo'd id, and a check that passes anyway

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


class RulesStayInSync(unittest.TestCase):
    """The prose fallback and the templates restate the validator's vocabulary; keep them aligned."""

    @staticmethod
    def load_validator():
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate_outline", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def setUp(self):
        self.v = self.load_validator()

    def test_every_check_id_is_documented(self):
        code = SCRIPT.read_text(encoding="utf-8")
        ids = set(re.findall(r'rep\.(?:error|warn)\(\s*"([a-z_]+)"', code))
        rules = (ROOT / "skills/outline/references/validator-rules.md").read_text(encoding="utf-8")
        self.assertTrue(ids)
        self.assertEqual({i for i in ids if f"`{i}`" not in rules}, set())

    def test_vocabularies_in_template(self):
        template = (ROOT / "templates/scenes.yaml").read_text(encoding="utf-8")
        self.assertEqual({w for w in self.v.BEATS | self.v.FLAGS if w not in template}, set())

    def test_default_banned_names_in_style_template(self):
        style = (ROOT / "templates/style.md").read_text(encoding="utf-8")
        self.assertEqual({n for n in self.v.DEFAULT_BANNED_NAMES if n not in style}, set())


class MiniYaml(unittest.TestCase):
    def test_fallback_matches_pyyaml_on_fixture(self):
        text = fixture.scenes_yaml()
        mine = ns_yaml._Parser(text).parse()
        need_pyyaml(self)
        import yaml
        self.assertEqual(mine, yaml.safe_load(text))

    def test_template_parses(self):
        text = (ROOT / "templates" / "scenes.yaml").read_text(encoding="utf-8")
        data = ns_yaml._Parser(text).parse()
        self.assertEqual(data["book"]["waivers"], {})
        self.assertEqual(data["scenes"][0]["id"], "ch01-s01")
        self.assertEqual(data["scenes"][0]["characters"], [])

    # (text, what PyYAML's SafeLoader returns). Pinned so the fallback is checked on machines
    # without PyYAML too; with PyYAML installed the live comparison below also runs.
    PARITY_CASES = [
        ("characters: [Siobhan O'Brien, Aino]\n", {"characters": ["Siobhan O'Brien", "Aino"]}),
        ("subplot: Aino's debt   # B story\n", {"subplot": "Aino's debt"}),
        ("turn: Aino's plan fails   # note: revisit\n", {"turn": "Aino's plan fails"}),
        ("pov: O'Brien  # narrator\n", {"pov": "O'Brien"}),
        ("- 'quoted, with comma'\n- it's fine\n", ["quoted, with comma", "it's fine"]),
        ("a: ['x, y', \"z\"]\n", {"a": ["x, y", "z"]}),
        ("chapter: 08\n", {"chapter": "08"}), ("chapter: 010\n", {"chapter": 8}), ("chapter: 0\n", {"chapter": 0}),
        ("chapter: 1_000\n", {"chapter": 1000}), ("n: 0x1F\n", {"n": 31}), ("n: 0b101\n", {"n": 5}),
        ("t: 12:30\n", {"t": 750}), ("t: 1:20:30\n", {"t": 4830}), ("f: 1e4\n", {"f": "1e4"}),
        ("f: 1.5e+3\n", {"f": 1500.0}), ("f: .5\n", {"f": 0.5}), ("f: -.inf\n", {"f": float("-inf")}),
        ("f: 3.\n", {"f": 3.0}),
        ("b: no\n", {"b": False}), ("b: On\n", {"b": True}), ("b: YES\n", {"b": True}), ("b: off\n", {"b": False}),
        ("b: maybe\n", {"b": "maybe"}),
        ("n: -12\n", {"n": -12}), ("n: +7\n", {"n": 7}), ("s: 2026-10-29x\n", {"s": "2026-10-29x"}),
        ("a: |\n  one\n# comment\nb: 2\n", {"a": "one\n", "b": 2}),
        ("a: >\n  one\n  two\n\n  three\n", {"a": "one two\nthree\n"}),
        ("a: |\n  # heading\n  text\n", {"a": "# heading\ntext\n"}),
        ('s: "say \\"hi\\" #1"  # c\n', {"s": 'say "hi" #1'}),
        ("a: >-\n  x\n  y\n", {"a": "x y"}),
        ('"waivers": {a: 1}\n', {"waivers": {"a": 1}}),
        ("'it''s': 1\n", {"it's": 1}),
        ("title: 'a'' # b'' c'\n", {"title": "a' # b' c"}),
        ("tags: ['a'', b', c]\n", {"tags": ["a', b", "c"]}),
        ("characters: [mara, theo,]\n", {"characters": ["mara", "theo"]}),
        ("m: {a: 1, b: [x, {c: d}],}\n", {"m": {"a": 1, "b": ["x", {"c": "d"}]}}),
        ("q: {\"k\": v, 'j': [1, 2]}\n", {"q": {"k": "v", "j": [1, 2]}}), ("e: [ ]\n", {"e": []}),
        ("title: 'Don''t Look Back'\n", {"title": "Don't Look Back"}),
        ("a: {k: , j: 1}\n", {"a": {"k": None, "j": 1}}), ("a: {k:}\n", {"a": {"k": None}}),
        ("a: [\"who?\"]\n", {"a": ["who?"]}), ("a: who?\n", {"a": "who?"}),
        # a no-break or ideographic space is text to YAML, not indentation
        ("book:\n  title: X\n\u00a0\u00a0waivers: {open_thread: x}\n",
         {"book": {"title": "X"}, "\u00a0\u00a0waivers": {"open_thread": "x"}}),
        ("a: x\u00a0 # c\n", {"a": "x\u00a0"}), ("waivers\u00a0: 1\n", {"waivers\u00a0": 1}),
        ("a:\n\u3000b: 1\n", {"a": None, "\u3000b": 1}), ("a: |\n  \u00a0x\n", {"a": "\u00a0x\n"}),
        ("a: >\n  one\n\n  two\n  three\n", {"a": "one\ntwo three\n"}),
    ]

    # The fallback refuses these; PyYAML reads them, so they are not silent disagreements.
    FALLBACK_REFUSES = ['s: "\\x41"\n', 's: "\\e"\n', "- - a\n", "d: 2026-10-29\n", "a: |+\n  x\n",
                        "a: >\n  x\n    more\n", '"waiv\\x65rs": 1\n', "1: x\n", "yes: x\n",
                        "book: {?waivers: {open_thread: x}}\n", "a: [?a]\n"]

    # Both paths must refuse these with YAMLError (never another exception: the guard depends on it).
    BOTH_REFUSE = ["a: &x [1]\nb: *x\n", "x: 0x_\n", "x: 0b_\n", "d: 2026-02-30\n", "? [a]\n: b\n",
                   "x: " + "[" * 2000 + "]" * 2000 + "\n", "a: 1\na: 2\n",
                   "w: {a: 1, a: 2}\n", "book: {waivers: {x: y}, waivers: {}}\n", "x: " + "[" * 70 + "]" * 70 + "\n",
                   "a: [x, , y]\n", "a: [x] y\n", "title: 'Don't Look Back'\n", "'Don't': x\n",
                   "b:\n  <<: {t: X}\n", "a: [who?]\n", "a: {k?: v}\n", "a: [a?b]\n",
                   "a: x\x0cy\n", "a: 1\x1cb: 2\n", "a: x\x0b\n"]
    if hasattr(sys, "get_int_max_str_digits"):  # Python 3.11+ caps int() at 4,300 digits; 3.9 reads it
        BOTH_REFUSE.append("n: " + "9" * 5000 + "\n")

    def test_fallback_matches_pinned_pyyaml_results(self):
        for text, expected in self.PARITY_CASES:
            with self.subTest(text=text):
                self.assertEqual(ns_yaml._Parser(text).parse(), expected)

    def test_fallback_matches_live_pyyaml(self):
        need_pyyaml(self)
        import yaml
        for text, expected in self.PARITY_CASES:
            with self.subTest(text=text):
                self.assertEqual(yaml.safe_load(text), expected)

    def test_fallback_refuses_what_it_cannot_read(self):
        for text in self.FALLBACK_REFUSES:
            with self.subTest(text=text):
                with self.assertRaises(ns_yaml.YAMLError):
                    ns_yaml._Parser(text).parse()

    def test_load_refuses_with_yamlerror_only(self):
        need_pyyaml(self)
        for forced in (False, True):
            for text in self.BOTH_REFUSE:
                with self.subTest(fallback=forced, text=text[:30]):
                    old = ns_yaml._FORCE_FALLBACK
                    ns_yaml._FORCE_FALLBACK = forced
                    try:
                        with self.assertRaises(ns_yaml.YAMLError):
                            ns_yaml.load(text)
                    finally:
                        ns_yaml._FORCE_FALLBACK = old

    def test_byte_order_mark_is_skipped_like_pyyaml(self):
        for forced in (True, False):
            with self.subTest(fallback=forced):
                old = ns_yaml._FORCE_FALLBACK
                ns_yaml._FORCE_FALLBACK = forced
                try:
                    self.assertEqual(ns_yaml.load("\ufeffbook: 1\n"), {"book": 1})
                    self.assertEqual(ns_yaml.load("\ufeff# c\nbook: 1\n"), {"book": 1})
                finally:
                    ns_yaml._FORCE_FALLBACK = old

    def test_fallback_refuses_all(self):
        old = ns_yaml._FORCE_FALLBACK
        ns_yaml._FORCE_FALLBACK = True
        try:
            for text in self.BOTH_REFUSE:
                with self.subTest(text=text[:30]):
                    with self.assertRaises(ns_yaml.YAMLError):
                        ns_yaml.load(text)
        finally:
            ns_yaml._FORCE_FALLBACK = old

    def test_strict_loader(self):
        need_pyyaml(self)
        self.assertEqual(ns_yaml.load("a: 1\nb: [x, y]\n"), {"a": 1, "b": ["x", "y"]})
        for text in ("a: 1\na: 2\n", "a: &x 1\nb: *x\n", "? [a]\n: b\n"):
            with self.subTest(text=text):
                with self.assertRaises(ns_yaml.YAMLError):
                    ns_yaml.load(text)

    def test_pyyaml_errors_are_one_line_with_a_hint(self):
        need_pyyaml(self)
        with self.assertRaises(ns_yaml.YAMLError) as cm:
            ns_yaml.load("a: 1\nb: x: y\n")
        message = str(cm.exception)
        self.assertNotIn("\n", message)
        self.assertIn("line 2", message)
        self.assertIn("quote a value", message)

    def test_pyyaml_errors_name_the_line_to_fix(self):
        need_pyyaml(self)
        cases = {'a: 1\nb: 2\nc: "open\nd: 4\ne: 5\n': 3,  # unclosed quote: PyYAML gives up at the end
                 "a: 1\nb: 2\nc 3\nd: 4\n": 3,  # key without ':'
                 "a: 1\nb: [x, y\nc: 2\n": 2,  # unclosed [
                 "a: 1\ntitle: 'Don't Look'\nc: 2\n": 2,
                 "a: 1\nb: x: y\nc: 2\n": 2}
        for text, line in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(ns_yaml.YAMLError) as cm:
                    ns_yaml.load(text)
                self.assertEqual(cm.exception.line, line)

    def test_flow_parser_is_linear(self):
        import time
        text = "".join(f"k{n}: " + "[" * 60 + "]" * 60 + "\n" for n in range(2000))
        start = time.monotonic()
        ns_yaml._Parser(text).parse()
        self.assertLess(time.monotonic() - start, 2)

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
