---
name: outline
description: Run novelsmith's outline-first stages with author checkpoints — stage 1 (premise, theme, ending and act beats via the story-architect agent, starting from five or more divergent directions) and stage 3 (chapters and the scene manifest via the outliner agent, validated by scripts/validate-outline.py). Use when the author says "/novelsmith:outline", wants to shape the premise or ending, plan acts, chapters or scenes, build or fix scenes.yaml, or validate the outline before drafting.
disable-model-invocation: true
argument-hint: "[premise|scenes|check]"
allowed-tools: Read, Glob, Grep, Edit, Agent, AskUserQuestion
---

# Outline: premise → acts → scenes

You run a stage and stop. Agents do the writing in their own context and return file paths; you check the files on disk, put the decisions in front of the author, and update `book/progress.md`. Never let an agent's claim stand in for a file you have read.

**Plugin root** is `${CLAUDE_SKILL_DIR}/../..` (resolve it to an absolute path once). Begin every agent delegation message with the line `Plugin root: <that path>`, because agents cannot work it out themselves.

Validator command (used below):

```bash
python3 "<plugin root>/scripts/validate-outline.py" --book book
```

Run it exactly as written, with nothing added. The author may be asked to allow it (it is not pre-approved, so nothing else can ride on the permission); if they decline, say the validator did not run and offer the manual check below.

Exit codes: 0 PASS, 1 FAIL (findings to fix), 2 the book could not be read. On exit 2, show the author its stderr line word for word (it names the file, the line and the fix, such as quoting a value that contains `: `) and stop; this is neither a pass nor a fail. Only if the command itself cannot run (python3 or the script not found, exit 126 or 127) is the validator unavailable: then apply `${CLAUDE_SKILL_DIR}/references/validator-rules.md` by reading the files, and label the result "manual check" wherever you report it.

**Choices for the author.** `AskUserQuestion` shows at most four options. When a choice has more (five or more directions, five names per role), write every option as a numbered line in your message first, then ask the author to reply with a number, a combination ("2 with the ending of 4") or their own answer. Never drop an option to fit the tool.

## 0. Where are we?

- No `book/progress.md`: tell the author to run `/novelsmith:novel-start` first, and stop.
- Read `book/progress.md` and `book/bible/premise.md`.
- Stage from `$ARGUMENTS`: `premise`, `scenes` or `check`. With no argument: `premise` when the ending in `premise.md` is undecided or the beat table in `book/outline/acts.md` is empty; otherwise `scenes` if the character sheets exist; otherwise tell the author the bible comes next (`/novelsmith:bible`) and stop.

## 1. Stage `premise` (story-architect)

1. **Options.** Unless the author has already decided the ending (in `premise.md`, under `## ⚓ Anchored`, or in `$ARGUMENTS`), launch the `novelsmith:story-architect` agent with: "Mode: options. Book state is in book/. Today is <date>." Add anything the author said in this conversation about what they want or do not want.
2. Read the options file it wrote in `book/proposals/`. Give the author one numbered line per direction (arc shape, who resolves, what stays open) and ask which to develop, following **Choices for the author** above: every direction, plus "combine" and "none, regenerate". Do not recommend one. If they want a combination or a regeneration, collect their steer in their own words and run options again or pass the combination to develop.
3. **Develop.** Launch `novelsmith:story-architect` with: "Mode: develop. Develop direction <N> from book/proposals/<file>" plus the author's adjustments verbatim.
4. **Check the files**: read `premise.md` and `acts.md`. The ending, controlling idea, counter-idea and hook must be filled and the beat table's "What happens" column complete for the declared model. If anything is missing, send the agent back once with the specific gap.
5. **Checkpoint.** Tell the author, briefly: what is now in `premise.md` and `acts.md`, the open questions the agent listed, and that decisions they are sure of belong under `## ⚓ Anchored` (agents can never change those; offer to move named decisions there for them, and do it only on their yes). Update `book/progress.md`: current stage 2, next action `/novelsmith:bible`, and a decisions-log row for the direction chosen. Stop.

## 2. Stage `scenes` (outliner)

1. **Preconditions** (read the files): the ending is decided; the beat table is filled; `book/bible/characters/` holds at least the protagonist and antagonist sheets. If one is missing, name it and the command that fixes it, and stop.
2. Launch the `novelsmith:outliner` agent with: "Build (or repair) book/outline/scenes.yaml and chapters.md, validate, and write the de-AI outline check. Today is <date>." Add any author instructions verbatim (for example "keep chapters short", "no prologue").
3. **Verify yourself**: run the validator command. Read `book/critiques/outline/de-ai-outline-<date>.md`.
4. If the validator fails on something the outliner reported needing from the author (a missing character, an ending decision), say exactly what is needed. If it fails for any other reason, send the outliner back once with the validator output. Never edit `book.waivers` yourself; if the author wants to waive a check, they say so in their own words and you add the waiver with their reason, which the canon guard will ask them to confirm.
5. **Checkpoint.** Tell the author: the validator result (PASS/FAIL, error and warning counts), the de-AI outline score (three or more failed checks means revise the outline before drafting), the warnings worth their attention, and where the files are. Update `book/progress.md`: current stage 3 (or 4 once the author approves the outline), next action "review book/outline/scenes.yaml; approve or edit", and a decisions-log row. Drafting (`/novelsmith:draft`) arrives in Phase 3; say so if the author asks what is next. Stop.

## 3. Stage `check`

Run the validator command and report its result in a few lines: pass or fail, each error with its scene id, and the warning count. Change nothing.

## Rules

- Never decide the premise, ending, structure or names for the author. Present options; build their choice.
- Never edit anything under `## ⚓ Anchored` or `book.waivers` without the author's explicit request in this conversation.
- Launch one agent at a time in this skill; each stage ends at a checkpoint.
