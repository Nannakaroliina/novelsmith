---
name: novel-start
description: Scaffold a new novel project (book/ tree, premise, style sheet, progress checkpoint) by interviewing the author. Use when the user wants to start a new novel, set up a book project, or says "new book" or "/novelsmith:novel-start".
disable-model-invocation: true
argument-hint: "[working title]"
allowed-tools: Read, Write, Glob, AskUserQuestion
---

# Start a new novel

You are setting up the file-first state for a novel. The `book/` tree in the project root is the only source of truth for every later stage; agents read and write files there and never rely on conversation memory.

## Steps

1. **Check for an existing project.** If `book/progress.md` exists, stop and tell the author: this project is already started; read `book/progress.md` and continue from "Next action" instead.

2. **Interview the author** with `AskUserQuestion` (or plain questions if the tool is unavailable). Ask only what the templates need; take the working title from `$ARGUMENTS` if given. Ask, in two short rounds at most:
   - Your name as the author, working title, base genre, subgenre/variant (e.g. Nordic noir, cozy, police procedural), secondary genre if any, target length. Offer the plugin settings as defaults: author `${user_config.author_name}`, genre `${user_config.default_genre}`, length `${user_config.target_words}`. A setting that is empty or still reads as a `${…}` placeholder is unset (Cowork does not prompt for plugin settings): then default to genre mystery and 85000 words, and ask for the author's name.
   - POV and tense; the one-sentence premise if they have it; comparable titles.
   - Whether they have 2–3 samples of their own prose to paste into the style sheet (strongly encourage this: the samples calibrate voice and the de-AI baseline). If not now, leave the slots and note it in progress.md.

3. **Create the tree** from the plugin's templates in `${CLAUDE_SKILL_DIR}/../../templates/`, filling `{{title}}`, `{{genre}}`, `{{target_words}}`, `{{author}}` with the interview answers:

   ```text
   book/
   ├── bible/
   │   ├── premise.md          ← templates/premise.md
   │   ├── style.md            ← templates/style.md
   │   ├── timeline.md         ← templates/timeline.md
   │   ├── characters/         (empty; one file per character from templates/character.md)
   │   ├── world/              (empty; templates/world-entry.md)
   │   └── clues.md            ← templates/clues.md   (mystery, thriller, or any book with a secret)
   ├── outline/
   │   ├── acts.md             ← templates/acts.md
   │   ├── chapters.md         (empty)
   │   └── scenes.yaml         ← templates/scenes.yaml
   ├── manuscript/             (empty; chNN/sNN.md later)
   ├── summaries/
   │   └── running.md          (empty)
   ├── critiques/              (empty)
   ├── proposals/              (empty; agents' divergent options and proposed changes for the author)
   └── progress.md             ← templates/progress.md
   ```

   Fill in `premise.md` with whatever the author gave (logline, genre, length, comps). Leave the rest of the template prompts in place for the author to complete. Put any decisions the author stated firmly under `## ⚓ Anchored`.

4. **Load the genre contract.** Read `${CLAUDE_SKILL_DIR}/../genre/SKILL.md` and the one reference file that matches the base genre (and the variant file if one exists, e.g. `mystery-nordic-finnish.md`). Copy the genre's *reader promise* into `premise.md` under "The promise to the reader", and its *obligatory scenes* into `acts.md` as rows the outline must deliver.

5. **Write `progress.md`** with stage 1, next action "Run /novelsmith:outline premise (divergent directions, then premise.md and acts.md)", and a note of what the author still owes (prose samples, ending decision).

6. **Report** in five lines or fewer: what was created, what the author should fill in next, and that `premise.md` → `## The ending` should be decided before outlining (hook is the mirror of the ending).

## Rules
- Never invent the premise, ending, or character names for the author. Offer options only if asked, and then offer at least five divergent ones.
- Never use the default-AI names listed in `style.md`.
- Do not create `commands/` or write anything outside `book/`.
