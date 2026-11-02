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

1. Get the plugin folder and Python 3 as in step 1 above (no zip needed), and install [Claude Code](https://claude.com/claude-code).
2. In a terminal in the plugin folder, run the installer (on Windows, `py scripts/install.py`):

   ```bash
   python3 scripts/install.py
   ```

   It copies the plugin's own files (the same ones the Cowork zip holds) to a folder of their own (`~/Library/Application Support/novelsmith/plugin` on a Mac, `%LOCALAPPDATA%\novelsmith\plugin` on Windows, `~/.local/share/novelsmith/plugin` on Linux), registers that folder as the `novelsmith` plugin marketplace and installs the plugin for every project. You can delete the downloaded folder afterwards. `--scope project` installs it only for the project in the folder you run it from; `--uninstall` removes it again.
3. Open a terminal in the folder that holds (or will hold) your `book/`, your writing project, not the plugin folder, start `claude`, and run `/novelsmith:doctor`, then `/novelsmith:novel-start`.

Or, without installing, start Claude Code with the plugin for one session: `claude --plugin-dir "/path/to/novelsmith"`.

To upgrade, in either app: get the new plugin folder, then run the installer from it again (for Cowork, build and upload the new zip over the old one). Your `book/` is not touched.

## Develop in Claude Code

```bash
claude --plugin-dir ./novelsmith
```

Before every push, run the quality and lint checks from the plugin folder:

```bash
python3 scripts/check.py
```

They check every tracked or new file for UTF-8, LF line ends, a final newline, trailing spaces and invisible characters in code, valid JSON and OS metadata files; scan for secret-looking files and credentials; check skill and agent frontmatter against the upload rules; lint the Python with `ruff` (settings in `ruff.toml`); `shellcheck` the hook command in `hooks/hooks.json`; and run `claude plugin validate --strict` on the plugin and its marketplace manifest (skipped where `claude` is not installed). They need `ruff` and `shellcheck` (`brew install ruff shellcheck`). `--all` also runs the tests and the self-check, which the `Check` GitHub Actions workflow does on every push, followed by the tests again with PyYAML:

```bash
python3 scripts/check.py --all
```

`tests/test_windows_junctions.py` checks the canon guard against real Windows junctions and is skipped elsewhere; the `Windows` GitHub Actions workflow runs it on Windows with Python 3.9 and the newest Python on every push.

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
| `scripts/install.py`, `.claude-plugin/marketplace.json` | by hand | Installs (or removes) the plugin in Claude Code from a clean copy of the plugin files |
| `scripts/check.py`, `ruff.toml` | before a push; CI | Quality and lint checks; not shipped in the plugin |
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
- A book project is a `book/` folder holding `progress.md` or `outline/scenes.yaml` (what novel-start writes); another tool's `book/` folder, such as mdBook's, is left alone. A path reaches the book however it is written, macOS `/System/Volumes/Data/…` paths included. A file inside `book/` is judged by where it really is there, so a link from one book folder to another (`bible/world/maps` to `research/maps`) does not make the files canon; keep canon under `bible/` itself. A file kept outside the book and reached through a symlink (or Windows junction) in `book/` (a series bible shared between books) is a linked file: subagents other than novelsmith's own may not write it, and novelsmith's agents write it only by its path inside `book/`, within their own folders, judged by the place in `book/` of the link that leads out of the book (a path it cannot name that way is asked about and denied to subagents); written by its real location, it is denied to subagents and checked as the book file for you. To recognise a linked file written by its real location, the guard looks through `book/` and the folders it links to on every write outside the book in a book project; if they hold more than 5,000 folders and links, take more than 3 seconds to look through, or include a folder it cannot read, it cannot tell, so subagents' writes outside `book/` are denied and yours are asked about, with the cause, the link involved and the fix named. Plain files never count toward the limit, and hidden folders it cannot read (a disk's `.Spotlight-V100`, `~/.Trash`) are passed over.
- A subagent's edit is checked on the text as Claude Code's tools see it. One whose old_string matches more than once, or that uses a carriage return that is not part of a Windows line break (in the edit or already in the file) or an invisible U+FEFF, is denied, since the guard could not tell which text the real edit changes.
- MCP tools, for subagents in a book project: only tools whose names say they read (`read_file`, `list_directory`, `search_issues`) and name no change. A filesystem or shell server's other tools would bypass these rules, and which files a tool touches cannot be read reliably from its arguments. PowerShell, notebook edits under `book/`, and any tool the guard does not know are denied to subagents there (reads, web search, planning and report-back tools pass); a bare agent name such as `outliner` counts as novelsmith's only in a book project. Your own MCP calls are left to Claude Code's permission prompts.
- Each novelsmith agent writes only its own files under `book/` (for example the worldbuilder writes `bible/world/`, `bible/timeline.md`, `proposals/`) and nothing outside `book/`; a novelsmith agent with no registered scope writes nothing. Other subagents cannot write under `book/bible/`. Paths are compared case-insensitively, as macOS and Windows treat `Bible/` and `bible/` as one folder.
- A subagent's edit of protected text must match it exactly (the Edit tool otherwise matches curly quotes loosely).
- Shell, for subagents in a book project: novelsmith agents may run exactly one command, the outline validator; other subagents may run only simple read-only commands (`ls`, `cat`, `head`, `tail`, `wc`, `grep`, `pwd`, `stat`, `file`, `diff`) with no shell syntax. Everything else is denied rather than guessed at, because what a shell command will change cannot be read reliably from its text. Your own shell commands in the main conversation are left to Claude Code's permission prompts.
- Book YAML may not use anchors or aliases, repeat keys (in block or `{ … }` form) or nest more than 64 levels; both parsers refuse them.
- The guard checks in a child process it stops after 6 seconds (a change of yours to the book that it cannot check in time is asked about, never waved through), and within size limits (1 MB per file, measured before an edit is applied, and 20,000 characters per line); a subagent call it cannot finish checking is denied. Where python3 is missing, the hook allows the write, so a broken environment never stops you writing; the agents' own instructions still keep them in scope. On a Mac without the developer tools, `python3` is a placeholder that offers to install them; the hook does not call it, so no dialog appears, but until you install them the guard is off. `/novelsmith:doctor` shows whether the guard is live.

## Upgrading

- **0.3.4 to 0.3.17:** a ⚓ anywhere on a line now locks that line, in its place, against agents; remove inline ⚓ marks you did not mean as decisions. A ⚓ on a scene field in `scenes.yaml` also fixes that scene's id, so the outliner asks you before renumbering it. Subagents in a book project may use only MCP tools whose names say they read; run other MCP tools from the main conversation. In 0.3.6 the built-in YAML reader treats a no-break space as text, as PyYAML does, and refuses invisible control characters. In 0.3.9 and 0.3.10 subagents in a book project may use only the tools the guard knows (run others, such as scheduling, from the main conversation), text holding an invisible U+FEFF is refused, and a book folder that is a symlink is guarded through its real location too. In 0.3.11 and 0.3.12 the search for links in `book/` counts folders and links only, looks in hidden folders too and stops after 3 seconds; when `book/` and the folders it links to hold more than 5,000 folders and links, take longer, or include a folder that cannot be read, writes outside the book ask you and are denied to subagents, and the prompt says why and what to change. In 0.3.13, files reached through a link in `book/` (a shared series bible) are written by subagents only through their path inside `book/`, and only by novelsmith's agents within their own folders; a link from one book folder to another no longer changes how its files are judged, so keep canon files in `bible/` rather than in another book folder linked into it (a shared series bible kept outside the book can still be linked under `bible/`), and change linked files from the main conversation or through the novelsmith agent whose folder they are in. In 0.3.14 and 0.3.15 a linked file is named by the place in `book/` of the link that leads out of the book, with links followed one part at a time as the system does, and `outline/scenes.yaml` and `bible/premise.md` keep their protection when they are links to another file, however they are reached; a path that leaves the book in a way no book path names (it climbs back out of the linked folder, or leaves through a link outside the book) asks you and is denied to subagents. In 0.3.16 a Windows directory junction (`mklink /J`) counts as a link, so a series bible linked that way works as a symbolic link does; from 0.3.17 that holds on Python versions before 3.12 too, also when a file is written by its real location. The built-in YAML parser (used without PyYAML) refuses `'…'` strings with a bare apostrophe (write `''` or use double quotes), empty `[x, , y]` items and an unquoted `?` inside `[ … ]` or `{ … }`; the validator names the line.

## Getting help

Run `/novelsmith:doctor` first and include its table. Report problems to the plugin's author (Nanna Setämaa) through the repository you got the plugin from.

## Roadmap

- **Phase 3** — `build-context-pack.py`, `scene-drafter`, `lint-scene.sh` with per-author baseline, `extract-facts.py`, `continuity-editor`, `SessionStart` status hook.
- **Phase 4** — blind critique panel (reader personas, line editor, genre specialist, de-AI editor), pairwise judge, `revise`, `SubagentStop` output check.
- **Phase 5** — remaining genre references, `book-metrics.py`, optional workflows, marketplace.json.
- **Phase 6** — calibrate on a Finnish crime novella; promote recurring hand-edits into rules.
