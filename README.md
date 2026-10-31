# Novelsmith

A Claude Code plugin for writing novels with a multi-agent, outline-first workflow. The book's state lives in a `book/` tree in your project; agents read and write files there, propose changes, and stop at every stage boundary so the author decides.

**Status: Phase 2 (outline-first core), MIT licence.** Phase 1's scaffolding, craft knowledge, de-AI taxonomy and mystery + Nordic/Finnish crime references, plus the four planning agents, the outline validator and the canon guard hook. Drafting, critique and revision arrive in Phases 3–4.

## Install in Cowork (where the writing happens)

1. Get the upload zip, `novelsmith-<version>.zip`. If someone gave you the file, skip to step 2. To build it yourself, first get the plugin folder: on the repository's page choose **Code > Download ZIP** and unzip it (or `git clone` it). You also need Python 3. On a Mac the first `python3` command offers to install the developer tools; let it finish, then run the command again. Open the Terminal app, go into the plugin folder (type `cd `, drag the folder onto the Terminal window, press Return), and run the command below. On Windows, install Python 3 from python.org (tick "Add python.exe to PATH"), open the plugin folder in File Explorer (the one that holds `README.md` and `scripts`; after **Extract All** that is the `novelsmith-main` folder inside the `novelsmith-main` folder), type `powershell` in the address bar and press Return, then run `py scripts/build_zip.py` instead:

   ```bash
   python3 scripts/build_zip.py
   ```

   It prints where the zip is (`dist/novelsmith-<version>.zip`). It packs only committed plugin files, never `book/` or local settings.

2. In claude.ai or the desktop app: **Customize > Plugins > Add > Upload plugin**, and pick `dist/novelsmith-<version>.zip`.
3. Start a Cowork task in the folder that holds (or will hold) your `book/`, and run `/novelsmith:doctor`. It reports whether the plugin files, python3, the four agents and the canon guard work in that session.

What Cowork changes:

- **Plugin settings are not prompted for.** `/novelsmith:novel-start` asks for your name, genre and length instead.
- **Paths.** Skills locate the plugin from their own folder (`${CLAUDE_SKILL_DIR}`, which Cowork documents) and pass the plugin root to each agent in its delegation message.
- **Python.** The validator and guard need only `python3` and the standard library (PyYAML is used if present; a built-in parser covers the manifest otherwise). Without python3 the outliner applies `skills/outline/references/validator-rules.md` by hand and labels the result "manual check", and the guard stays silent rather than blocking writes. `/novelsmith:doctor` tells you which case you are in.
- **Chat** (claude.ai without Cowork) ignores agents and hooks, so the staged workflow needs Cowork or Claude Code.

## Use in Claude Code

1. Get the plugin folder as in step 1 above (no zip needed).
2. Open a terminal in the folder that holds (or will hold) your `book/`, your writing project, not the plugin folder, and start Claude Code with the plugin:

   ```bash
   claude --plugin-dir "/path/to/novelsmith"
   ```

3. Run `/novelsmith:doctor`, then `/novelsmith:novel-start`.

To upgrade, in either app: get the new plugin folder (and, for Cowork, build and upload the new zip over the old one). Your `book/` is not touched.

## Develop in Claude Code

```bash
claude --plugin-dir ./novelsmith
```

Validate after edits, run the tests, and run the self-check:

```bash
claude plugin validate ./novelsmith --strict
```

```bash
python3 -m unittest discover -s tests
```

```bash
python3 scripts/selfcheck.py
```

## The workflow so far

| Stage | Invoke | Agent(s) | Writes | Checkpoint |
|---|---|---|---|---|
| 0 Start | `/novelsmith:novel-start [title]` | — | `book/` tree from `templates/` | Author fills what they know |
| 1 Premise | `/novelsmith:outline premise` | `story-architect` | 5+ divergent directions in `proposals/`, then `bible/premise.md`, `outline/acts.md` | Author picks a direction, anchors decisions |
| 2 Bible | `/novelsmith:bible [all\|characters\|world\|<name>]` | `character-designer` ∥ `worldbuilder` | Name candidates in `proposals/`, then `bible/characters/*.md`, `bible/world/*.md`, `bible/timeline.md` | Author picks names, checks `[verify]` facts |
| 3 Outline | `/novelsmith:outline scenes` | `outliner` | `outline/scenes.yaml`, `outline/chapters.md`, clue plants, `critiques/outline/de-ai-outline-<date>.md` | Validator passes; author approves |
| — | `/novelsmith:outline check` | — | nothing | Validator report only |

## Components

| Component | Invoke | Purpose |
|---|---|---|
| `skills/novel-start` | `/novelsmith:novel-start [title]` | Interviews you and scaffolds `book/` from `templates/` |
| `skills/outline` | `/novelsmith:outline [premise\|scenes\|check]` | Stages 1 and 3 with author checkpoints |
| `skills/bible` | `/novelsmith:bible [scope]` | Stage 2 with author checkpoints; the route for changing canon |
| `skills/doctor` | `/novelsmith:doctor` | Checks plugin files, settings, python3, agents and a live guard test in this environment |
| `skills/genre` | `/novelsmith:genre [genre]` or auto | Loads one genre contract; `references/mystery.md`, `references/mystery-nordic-finnish.md` |
| `skills/de-ai` | `/novelsmith:de-ai <path> [--detect\|--rewrite]` | Fiction-specific AI-tell audit; four reference tiers |
| `skills/craft-structure`, `craft-character`, `craft-prose` | auto | Beat map and scene test; arc engine and voice; line-level craft |
| `agents/story-architect` | via `outline` | Divergent premises and endings, then premise + beat table (Opus) |
| `agents/character-designer` | via `bible` | Cast roles, name candidates, character sheets with voice and knowledge ledger (Opus) |
| `agents/worldbuilder` | via `bible` | Places and institutions as pressure; backstory and hidden crime timeline (Sonnet) |
| `agents/outliner` | via `outline` | Scene manifest, chapters, clue plants; validate-fix loop; de-AI outline check (Opus) |
| `scripts/validate-outline.py` | outliner, `outline check` | Deterministic manifest checks (below) |
| `scripts/guard-canon.py` + `hooks/hooks.json` | automatic | Protects anchored decisions and per-agent write scopes |
| `scripts/selfcheck.py`, `scripts/build_zip.py` | doctor; by hand | Script self-test on a throwaway fixture book; upload zip for Cowork |
| `templates/` | — | Premise, style sheet, character, world, timeline, acts, scene manifest, clue ledger, summaries, critique note, progress |

## The book tree

```text
book/
├── bible/        premise.md · style.md · timeline.md · clues.md · characters/ · world/
├── outline/      acts.md · chapters.md · scenes.yaml
├── manuscript/   chNN/sNN.md
├── summaries/    chNN.md · running.md
├── critiques/    outline/ · chNN/<agent>-<date>.md
├── proposals/    divergent options and proposed changes awaiting the author
└── progress.md
```

## The outline validator

`scripts/validate-outline.py --book book [--json]` exits 0 on pass, 1 on errors, 2 when the book cannot be read.

- **Cannot read (exit 2):** scenes.yaml missing, not UTF-8, not valid YAML, a repeated key, or `book` / `book.waivers` not a mapping. The message names the line.
- **Errors (block drafting):** `base_genre` or `structure` in scenes.yaml differing from premise.md; missing goal/conflict/turn/outcome/value shift; outcome not `yes-but`/`no-and` (sequels excepted); malformed or duplicate ids, chapters out of order; a POV or character with no sheet; a model-default name (Elias, Mara, Elara…) not anchored by the author, or a name with invisible characters or mixed alphabets; for the arc model, a missing inciting/doorway/pinch/midpoint/all-is-lost/climax beat, beats out of order, or a climax before 80%; no subplot; no `compromise`, `non_protagonist_resolution` or open thread; for mysteries, unknown clue ids and any clue paid off before it is planted.
- **Warnings:** beat placement outside its window, long tail after the climax, uniform chapter lengths or scene counts, too few `no-and` setbacks or none in a quarter, runs of three identical outcomes, consecutive sequels, no non-linear move, length drift, mystery placement (crime by 20%, false solution, short denouement), and the four Nordic/Finnish subplot tags.
- **Waivers** live in `book.waivers` in `scenes.yaml` and belong to the author: a waived error is reported but does not fail. The guard denies agents any change to waivers.

## The canon guard

A `PreToolUse` hook on every tool call (it returns at once for anything but a file write or a subagent's call):

- Every heading containing ⚓ (with its body, HTML comments included; indented, underlined and quoted headings count) and every other line containing ⚓ in any `book/` file, `book.waivers` in `scenes.yaml`, and the genre, variant and structural-model settings of `premise.md` are the author's. `&#9875;` and `:anchor:` count as ⚓. A ⚓ section runs to the next heading every Markdown reader shows (a `#` heading at the margin, or an underlined one after a blank line); text inside code fences is never a heading, and in YAML files `#` lines are comments. A ⚓ line's place is the line it sits under (a scene's `- id:` line in `scenes.yaml`, or the heading above it), so renaming that line counts as moving it. Only the ⚓ line itself is locked: keep a free-standing decision on one line, or put a longer one under `## ⚓ Anchored`. A subagent changing one, adding, moving or reordering a ⚓ line, hiding one in a comment (an unclosed `<!--` hides the rest of the file), or leaving `scenes.yaml` unreadable is denied, and the denial names the line; in the main conversation you are asked to confirm. A new file may carry only the templates' own ⚓ lines and sections, such as an empty `## ⚓ Anchored` heading. Agents may fill a setting that is still empty. If `scenes.yaml` cannot be read and its `waivers` entry is not empty, only you repair it (Claude offers to, and the guard asks you), since the guard cannot compare the waivers; with the template's empty `waivers: {}` the outliner repairs it.
- A book project is a `book/` folder holding `progress.md` or `outline/scenes.yaml` (what novel-start writes); another tool's `book/` folder, such as mdBook's, is left alone. A path reaches the book however it is written, macOS `/System/Volumes/Data/…` paths included, and so does a file reached through a symlink in `book/` (a series bible shared between books), by its real location too. To find those links the guard looks through `book/` and the folders it links to on every write outside the book in a book project; if they hold more than 5,000 folders and links, take more than 3 seconds to look through, or include a folder it cannot read, it cannot tell, so subagents' writes outside `book/` are denied and yours are asked about, with the cause and the fix named. Plain files never count toward the limit.
- A subagent's edit is checked on the text as Claude Code's tools see it. One whose old_string matches more than once, or that uses a carriage return that is not part of a Windows line break (in the edit or already in the file) or an invisible U+FEFF, is denied, since the guard could not tell which text the real edit changes.
- MCP tools, for subagents in a book project: only tools whose names say they read (`read_file`, `list_directory`, `search_issues`) and name no change. A filesystem or shell server's other tools would bypass these rules, and which files a tool touches cannot be read reliably from its arguments. PowerShell, notebook edits under `book/`, and any tool the guard does not know are denied to subagents there (reads, web search, planning and report-back tools pass); a bare agent name such as `outliner` counts as novelsmith's only in a book project. Your own MCP calls are left to Claude Code's permission prompts.
- Each novelsmith agent writes only its own files under `book/` (for example the worldbuilder writes `bible/world/`, `bible/timeline.md`, `proposals/`) and nothing outside `book/`; a novelsmith agent with no registered scope writes nothing. Other subagents cannot write under `book/bible/`. Paths are compared case-insensitively, as macOS and Windows treat `Bible/` and `bible/` as one folder.
- A subagent's edit of protected text must match it exactly (the Edit tool otherwise matches curly quotes loosely).
- Shell, for subagents in a book project: novelsmith agents may run exactly one command, the outline validator; other subagents may run only simple read-only commands (`ls`, `cat`, `head`, `tail`, `wc`, `grep`, `pwd`, `stat`, `file`, `diff`) with no shell syntax. Everything else is denied rather than guessed at, because what a shell command will change cannot be read reliably from its text. Your own shell commands in the main conversation are left to Claude Code's permission prompts.
- Book YAML may not use anchors or aliases, repeat keys (in block or `{ … }` form) or nest more than 64 levels; both parsers refuse them.
- The guard checks in a child process it stops after 6 seconds (a change of yours to the book that it cannot check in time is asked about, never waved through), and within size limits (1 MB per file, measured before an edit is applied, and 20,000 characters per line); a subagent call it cannot finish checking is denied. Where python3 is missing, the hook allows the write, so a broken environment never stops you writing; the agents' own instructions still keep them in scope. On a Mac without the developer tools, `python3` is a placeholder that offers to install them; the hook does not call it, so no dialog appears, but until you install them the guard is off. `/novelsmith:doctor` shows whether the guard is live.

## Upgrading

- **0.3.4 to 0.3.11:** a ⚓ anywhere on a line now locks that line, in its place, against agents; remove inline ⚓ marks you did not mean as decisions. A ⚓ on a scene field in `scenes.yaml` also fixes that scene's id, so the outliner asks you before renumbering it. Subagents in a book project may use only MCP tools whose names say they read; run other MCP tools from the main conversation. In 0.3.6 the built-in YAML reader treats a no-break space as text, as PyYAML does, and refuses invisible control characters. In 0.3.9 and 0.3.10 subagents in a book project may use only the tools the guard knows (run others, such as scheduling, from the main conversation), text holding an invisible U+FEFF is refused, and a book folder that is a symlink is guarded through its real location too. In 0.3.11 a `book/` with more than 5,000 folders and links (or one you cannot read) makes writes outside the book ask you, and deny subagents; the prompt says why. The built-in YAML parser (used without PyYAML) refuses `'…'` strings with a bare apostrophe (write `''` or use double quotes), empty `[x, , y]` items and an unquoted `?` inside `[ … ]` or `{ … }`; the validator names the line.

## Getting help

Run `/novelsmith:doctor` first and include its table. Report problems to the plugin's author (Nanna Setämaa) through the repository you got the plugin from.

## Roadmap

- **Phase 3** — `build-context-pack.py`, `scene-drafter`, `lint-scene.sh` with per-author baseline, `extract-facts.py`, `continuity-editor`, `SessionStart` status hook.
- **Phase 4** — blind critique panel (reader personas, line editor, genre specialist, de-AI editor), pairwise judge, `revise`, `SubagentStop` output check.
- **Phase 5** — remaining genre references, `book-metrics.py`, optional workflows, marketplace.json.
- **Phase 6** — calibrate on a Finnish crime novella; promote recurring hand-edits into rules.
