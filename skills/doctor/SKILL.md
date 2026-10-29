---
name: doctor
description: Check that novelsmith works in this environment (especially Cowork) — plugin files found, settings, python3 for the outline validator and canon guard, the four planning agents, and a live test that the canon guard hook blocks an out-of-scope agent write. Use when the author says "/novelsmith:doctor", after installing or updating the plugin, or when the validator or guard seems not to work.
disable-model-invocation: true
allowed-tools: Read, Glob, Agent, Bash(rm book/outline/_novelsmith-guard-test.md)
---

# Novelsmith doctor

Run every check, then report one table. Change nothing in `book/` except the single test file in check 5, which you remove again if it was written.

**Plugin root** is `${CLAUDE_SKILL_DIR}/../..`. Resolve it to an absolute path.

1. **Plugin files.** Confirm these exist under the plugin root: `templates/scenes.yaml`, `scripts/validate-outline.py`, `scripts/guard-canon.py`, `scripts/selfcheck.py`, `skills/outline/references/validator-rules.md`. If any is missing, the skills cannot hand agents the plugin root; report the path you resolved.
2. **Settings.** Author `${user_config.author_name}`, genre `${user_config.default_genre}`, length `${user_config.target_words}`. A value that is empty or still reads as a `${…}` placeholder is unset; that is expected in Cowork, which does not prompt for plugin settings, and `/novelsmith:novel-start` asks instead.
3. **Scripts.** Run `python3 "<plugin root>/scripts/selfcheck.py"` exactly as written and keep its output (the author may be asked to allow it; if they decline, mark this check "not run"). If python3 is missing or the command cannot run, the outline validator falls back to the manual rules and the canon guard is inactive (writes are not blocked, only the agents' instructions keep them in scope).
4. **Agents.** Check that `novelsmith:story-architect`, `novelsmith:character-designer`, `novelsmith:worldbuilder` and `novelsmith:outliner` are available to the Agent tool.
5. **Live guard test** (only if a `book/` folder exists in the project; otherwise mark it "skipped: run again after /novelsmith:novel-start"). Launch `novelsmith:worldbuilder` with:
   > Plugin root: <plugin root>
   > Permissions test only. Use the Write tool once to write the text `guard test` to book/outline/_novelsmith-guard-test.md. Report verbatim what the tool returned. Do nothing else.

   Expected: the write is denied with a message starting "novelsmith: worldbuilder may write only". Then check whether `book/outline/_novelsmith-guard-test.md` exists. If it does, the hook did not fire: remove that file with `rm book/outline/_novelsmith-guard-test.md` and report the guard as inactive.

## Report

| Check | Result | What it means for writing |
|---|---|---|
| Plugin files | found at `<path>` / missing: … | |
| Settings | set / unset (asked at novel-start) | |
| python3 + scripts | selfcheck ALL OK / n failed / python3 unavailable | validator automatic, or manual fallback |
| Agents | 4 of 4 / missing: … | |
| Canon guard (live) | blocks out-of-scope writes / inactive / skipped | |

End with one line: "Ready" if checks 1, 3 and 4 passed and check 5 passed or was skipped (then add "(the live guard test runs after /novelsmith:novel-start)"); otherwise the single most important problem and its consequence. Do not offer fixes that need changing the plugin; say the author can report them to the plugin's author (see the README).
