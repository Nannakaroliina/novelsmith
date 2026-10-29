"""A small Finnish-mystery book/ tree that passes validate-outline.py.

Tests and scripts/selfcheck.py copy it, break one thing, and check that the matching check fires.
"""

from pathlib import Path

PREMISE = """# Premise
## Genre
- Base genre: mystery
- Subgenre / variant: Finnish crime

## The ending (decide this first)
- Outcome of the climax: exposure on the ice road

## ⚓ Anchored
- The culprit is the harbour master's sister.
"""

STYLE = "## Name list\n- Banned names (model defaults): Elias, Mara, Elara\n"

CLUES = """| Clue id | What it is |
|---|---|
| C01 | the second key |
| C02 | wet boots |

## Red herrings
| Id | What |
|---|---|
| R01 | the Estonian van |
"""

ACTS = """# Acts
## Threads the book leaves open on purpose
<!-- comment -->
- Aino's brother's debt
"""

CHARACTERS = [("aino-hakkinen", "Aino Häkkinen", "Häkkinen"), ("tuomas-lehto", "Tuomas Lehto", ""),
              ("riikka-salo", "Riikka Salo", "")]

BEATS = {1: "inciting_crime", 3: "doorway", 4: "pinch_1", 6: ["midpoint", "false_solution"], 7: "pinch_2",
         9: "all_is_lost", 11: ["climax", "exposure"]}
SUBPLOTS = {2: "social", 5: "criminal", 6: "institution", 8: "season", 10: "social", 12: "criminal",
            3: "institution", 9: "season"}
FLAGS = {4: ["compromise"], 8: ["nonlinear"], 10: ["non_protagonist_resolution"], 12: ["open_thread"]}
OUTCOMES = ["no-and", "yes-but", "no-and", "yes-but", "no-and", "yes-but",
            "no-and", "no-and", "yes-but", "no-and", "yes-but", "no-and"]
SIZES = [1500, 2200, 2600, 1800, 3000, 2400, 2000, 3400, 1700, 2600, 2400, 1400]
CHAPTERS = [1, 1, 2, 2, 3, 3, 3, 4, 5, 5, 6, 6]
PLANTED = {2: "[C01]", 5: "[C01]", 7: "\n      - C02"}


def scenes_yaml():
    lines = ["# fixture", "book:", '  title: "Jäänlähtö"', "  target_words: 27000", "  base_genre: mystery",
             "  structure: arc", "  waivers: {}", "", "scenes:"]
    counter = {}
    for i in range(1, 13):
        ch = CHAPTERS[i - 1]
        counter[ch] = counter.get(ch, 0) + 1
        beat = BEATS.get(i, "")
        beat_s = "[" + ", ".join(beat) + "]" if isinstance(beat, list) else f'"{beat}"'
        lines += [
            f"  - id: ch{ch:02d}-s{counter[ch]:02d}",
            f"    chapter: {ch}",
            "    pov: Riikka Salo" if i == 5 else "    pov: Aino",
            f'    time: "Day {1 if i == 8 else i}, 07:{i:02d}"',
            "    characters: [Häkkinen, Tuomas Lehto]",
            f'    goal: "goal {i}"   # trailing comment',
            "    conflict: 'the sergeant''s silence'",
            f"    turn: turn {i}",
            f"    outcome: {OUTCOMES[i - 1]}, something",
            f"    value_shift: from calm {i} to dread",
            f"    beat: {beat_s}",
            f'    subplot: "{SUBPLOTS.get(i, "")}"',
            f"    flags: [{', '.join(FLAGS.get(i, []))}]",
            f"    word_target: {SIZES[i - 1]}",
            "    status: planned",
            f"    clues_planted: {PLANTED.get(i, '[]')}",
            "    clues_paid: [C01, C02]" if i == 11 else "    clues_paid: []",
            "    red_herrings: [R01]" if i == 3 else "    red_herrings: []",
            "    notes: |",
            "      multi-line note",
            "      second line",
        ]
    return "\n".join(lines) + "\n"


def build(root):
    """Write the fixture under root/book and return the book path."""
    b = Path(root) / "book"
    for d in ("bible/characters", "bible/world", "outline", "manuscript", "summaries", "critiques", "proposals"):
        (b / d).mkdir(parents=True, exist_ok=True)
    (b / "bible/premise.md").write_text(PREMISE, encoding="utf-8")
    (b / "bible/style.md").write_text(STYLE, encoding="utf-8")
    (b / "bible/clues.md").write_text(CLUES, encoding="utf-8")
    for slug, name, aka in CHARACTERS:
        extra = f"- Also known as: {aka}\n" if aka else ""
        (b / f"bible/characters/{slug}.md").write_text(f"# {name}\n{extra}", encoding="utf-8")
    (b / "outline/acts.md").write_text(ACTS, encoding="utf-8")
    (b / "outline/scenes.yaml").write_text(scenes_yaml(), encoding="utf-8")
    return b
