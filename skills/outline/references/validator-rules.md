# Outline validator rules (manual fallback)

Use this only when `scripts/validate-outline.py` cannot run (no python3, no shell, file not found). It lists what the script checks, in the same order, so a manual pass reaches the same verdict. Label the result **manual check**, never PASS from the validator. When the script runs, it is the source of truth; if this file and the script disagree, the script wins and this file needs updating.

Read `book/outline/scenes.yaml`, `book/outline/acts.md`, `book/bible/premise.md`, `book/bible/style.md`, `book/bible/clues.md` and the headings of `book/bible/characters/*.md`. Positions are cumulative `word_target` through the **end** of a scene, divided by the total.

A check named in `book.waivers` (written by the author) is reported as waived and never fails.

The file cannot be checked at all (exit 2) when scenes.yaml is missing, is not UTF-8, does not parse, repeats a key, or `book` / `book.waivers` is not a mapping. Report that to the author with the line it names; it is not a FAIL and not a PASS.

## Errors (any one blocks drafting)

| Check id | Fails when |
|---|---|
| `book_meta` | `book.base_genre` in scenes.yaml differs from premise.md "Base genre" (premise settings are read from the ⚓ sections first, then the visible text; HTML comments never count); `book.structure` differs from premise.md "Structural model" (arc when premise.md declares none); or the premise names a model other than arc / kishotenketsu / alison. premise.md always decides genre and structure |
| `fields` | A scene is missing any of `id`, `chapter`, `pov`, `goal`, `conflict`, `turn`, `outcome`, `value_shift`, `word_target`; `chapter` is not a whole number; `word_target` is not a number of words between 1 and 1,000,000 (NaN and infinity are not numbers); `status` is not planned / drafted / revised / locked |
| `ids` | An id is not `chNN-sNN`, its chapter number differs from `chapter`, or two scenes share an id |
| `order` | A scene's chapter is lower than an earlier scene's (the manifest is reading order) |
| `outcome` | Outcome does not start with `yes-but` or `no-and` (scenes flagged `sequel` are exempt) |
| `entities` | A `pov` or `characters` entry matches no character sheet: not the file slug, the `#` heading, a listed `- Also known as:` alias, or an unambiguous first name (accents ignored: Häkkinen = hakkinen) |
| `names` | A character name contains a banned name from `style.md` → "Banned names" (or the default list: Elias, Elara, Mara, Elena, Kael, Kaelen, Lyra, Aria, Sera, Seraphina, Theron, Orion, Silas, Aris, Voss, Vance, Thorne, Blackwood, Marcus, Sarah, Chloe, Lily) and the name does not appear in any ⚓ section of `premise.md` (HTML comments do not count); or a name contains an invisible formatting character or mixes look-alike alphabets (Latin, Cyrillic, Greek, Armenian: a Cyrillic "Е" inside a Latin name). Kanji with kana, or letters like the ʻokina, are normal |
| `beats` | Arc structure only: no scene carries one of `inciting`, `doorway`, `pinch_1`, `midpoint`, `pinch_2`, `all_is_lost`, `climax` (in a mystery `inciting_crime` counts as inciting and `exposure` as climax) |
| `climax_placement` | Arc only: the first climax scene ends before 80% |
| `beat_order` | Arc only: those seven beats are not in that reading order |
| `subplot` | No scene has a non-empty `subplot` |
| `compromise` | No scene is flagged `compromise` |
| `non_protagonist_resolution` | No scene is flagged `non_protagonist_resolution` |
| `open_thread` | No scene is flagged `open_thread` and `acts.md` → "Threads the book leaves open on purpose" has no non-empty bullet |
| `clues` | Mystery only: a `clues_planted`, `clues_paid` or `red_herrings` id is not in the first column of a table in `clues.md` |
| `fair_play` | Mystery only: a clue in `clues_paid` has no `clues_planted` entry in an earlier scene |

## Warnings (findings to fix or explain; do not block)

- `beat_placement`: inciting after 15%; doorway outside 15–35%; pinch_1 outside 28–47%; midpoint outside 40–60%; pinch_2 outside 53–72%; all_is_lost outside 65–85%; climax after 95%. `beats`: two or more scenes claim midpoint or climax.
- `epilogue`: more than 12% of words after the climax; more than two scenes after it, or any with no conflict.
- `length`: total word targets more than 15% from `book.target_words`.
- `subplot`: a subplot in only one scene; no subplot scene also carries a beat.
- `compromise`: the only compromise is after 92%.
- `nonlinear`: no `nonlinear` flag and story time (`Day N, HH:MM`) never goes backwards.
- `valence`: under a third of non-sequel scenes end `no-and`. `setbacks`: a quarter of the book has no `no-and`. `polarity`: three identical outcomes in a row. `sequels`: two sequel scenes in a row.
- `chapter_shape` (four or more chapters): chapter word totals vary too little (standard deviation under 20% of the mean); every chapter has the same number of scenes.
- `mystery`: no `inciting_crime`, or it ends after 20%; no `false_solution`; more than two scenes after `exposure`. `clues`: a planted clue never paid off.
- `nordic` (mystery whose genre or variant names Nordic, Finnish or Scandinavian): no scene with subplot `social`, `criminal`, `institution` or `season`.
- `vocabulary`: a beat or flag outside the vocabulary in `templates/scenes.yaml`. `value_shift`: does not read "from X to Y". `structure`: a non-arc model, so beat checks were skipped.

## Report

Write the same shape the script prints: one line of totals (scenes, chapters, planned words, structure), then ERRORS, WARNINGS and WAIVED, each line `check [where]: message`, then `MANUAL CHECK — FAIL|PASS: N error(s), M warning(s), K waived`.
