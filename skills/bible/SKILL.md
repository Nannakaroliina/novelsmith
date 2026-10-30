---
name: bible
description: Run novelsmith's stage 2 with author checkpoints — the cast and character sheets via the character-designer agent and the places, institutions, rules and timeline via the worldbuilder agent, in parallel — or create or update one character or world entry. The only route besides the author's own edits for changing book/bible/. Use when the author says "/novelsmith:bible", wants characters, names, suspects, a setting, an institution, a timeline or the hidden crime timeline built or changed.
disable-model-invocation: true
argument-hint: "[all|characters|world|character or place name]"
allowed-tools: Read, Glob, Grep, Edit(book/**), Agent, AskUserQuestion
---

# Bible: characters, world, timeline

The bible is canon: every later stage plans, drafts and checks against it. You run the stage and stop. Agents write in their own context and return file paths; you check the files on disk, put the author's decisions in front of them, and update `book/progress.md`.

**Plugin root** is `${CLAUDE_SKILL_DIR}/../..` (resolve it to an absolute path once). Begin every agent delegation message with the line `Plugin root: <that path>`, because agents cannot work it out themselves.

## 0. Where are we?

- No `book/progress.md`: tell the author to run `/novelsmith:novel-start` first, and stop.
- Read `book/progress.md`, `book/bible/premise.md` and `book/outline/acts.md`. If the ending is undecided or the beat table is empty, say that characters built before the ending usually need rebuilding, suggest `/novelsmith:outline premise`, and continue only if the author says to.
- Scope from `$ARGUMENTS`: `all` (default), `characters`, `world`, or a name. A name that matches a sheet in `book/bible/characters/` or an entry in `book/bible/world/` updates that file; an unknown name asks the author whether it is a character or a place, then creates it.

## 1. Scope `all`, `characters` or `world`

1. **Launch the agents.** If the author has already named the characters, launch both in parallel (one message, two Agent calls; they write disjoint files). Otherwise launch only the character-designer now, and the worldbuilder after the names checkpoint (step 2), once the sheets exist: it places characters and checks the crime timeline against the suspects' sheets, so it must not run before them.
   - `novelsmith:character-designer` with "Mode: cast" if the author has not named the characters, otherwise "Mode: sheets" with the names. Include "Today is <date>." and any author instructions verbatim.
   - `novelsmith:worldbuilder` with "Build the world entries and timeline the acts need. Today is <date>." plus author instructions.
   Skip whichever the scope excludes.
2. **Names checkpoint** (cast mode only). Read the newest `book/proposals/cast-<date>*.md` (a regenerated set is `-2`, `-3`; earlier sets stay). List every role with all of its name candidates as numbered lines in your message (`AskUserQuestion` shows at most four options, so never use it to pick among five names), and ask the author to reply with a number or their own name for each role. Do not recommend. Check each chosen name against `book/bible/style.md` → "Banned names": if one matches, tell the author that the outline validator will block it unless it is anchored, and offer to add it under `## ⚓ Anchored` in `premise.md` now (only on their yes). Then launch `novelsmith:character-designer` with "Mode: sheets" and the chosen names verbatim, and when it returns, the `novelsmith:worldbuilder` (step 1), unless the scope excludes it.
3. **Check the files**: every named character has a sheet with the arc engine, voice block, NEVER-SAYS list and (for a mystery) suspect fields filled; the world entries say how each place presses on someone; `timeline.md` has its tables, and for a mystery the hidden crime timeline. Send an agent back once with any specific gap.
4. **Update `book/bible/style.md`** → "Name list" → "Protagonist and recurring names" with the chosen names. This is the one edit you make yourself.
5. **Checkpoint.** Tell the author, briefly: the sheets and entries created; the `[verify]` facts the worldbuilder flagged for them to check; any inconsistency either agent reported between the crime timeline and the suspects; and that they can edit any sheet directly. Update `book/progress.md`: current stage 3, next action `/novelsmith:outline scenes`, and a decisions-log row for the names chosen ("yes" or "no" under Anchored?, never the symbol). Stop.

## 2. Scope: one name

Launch the matching agent (`novelsmith:character-designer` in sheets mode, or `novelsmith:worldbuilder`) with the name, the file path if it exists, and the author's request verbatim. Check the file, report what changed in two or three lines, and note in `book/progress.md` if the change affects scenes already planned (the outline may need `/novelsmith:outline check`). Stop.

## Rules

- Never invent names, relationships or backstory the author has not approved; agents propose, the author picks.
- Never edit anything under `## ⚓ Anchored` without the author's explicit request in this conversation.
- If the outline already exists, say which scenes a bible change could affect rather than editing the outline.
