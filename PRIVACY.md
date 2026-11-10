# Privacy Policy

Last updated: 10 November 2026

novelsmith is a free, open-source plugin for Claude Code and Cowork, made by Nanna Setämaa ("I", "me"). This policy explains what happens to your data when you use it.

**Short version: novelsmith collects nothing. It has no server, no account, no analytics and no telemetry, and it contains no code that sends anything over the network. It runs on your machine, inside Claude Code or Cowork. Your book lives in a `book/` folder in your own project. What Claude reads and writes there goes to Anthropic like anything else you work on with Claude.**

## What novelsmith does with your data

novelsmith helps you plan a novel in a folder you choose. To do that it:

- asks for three settings: your name as the author, a default genre and a target length. Claude Code keeps them with your plugin settings on your machine. Cowork does not prompt for plugin settings, so `/novelsmith:novel-start` asks you in the conversation instead;
- writes your book as Markdown and YAML files in a `book/` folder in your project: the premise, characters, world, timeline, outline, proposals and `progress.md`. Your author name goes into `book/progress.md` and the premise byline. Nothing else is stored anywhere;
- runs a canon guard hook on Claude's tool calls. It reads the call and the book files involved to decide whether a write is allowed, then exits. It writes nothing and keeps no log;
- runs the outline validator (`scripts/validate-outline.py`) on `book/outline/scenes.yaml` when you build or check an outline. It only reads the book and prints a report;
- in `/novelsmith:doctor`, writes one test file, `book/outline/_novelsmith-guard-test.md`, to check that the guard blocks it, and removes it if it was written.

The planning agents can only read and write files; the outliner can also run the outline validator. None of them is told to search the web or use other services.

Outside your project, novelsmith writes only where you ask it to: `scripts/install.py` copies the plugin's own files to a folder of their own (see the README) and registers it with Claude Code; `--uninstall` removes them. Building the Cowork zip with `scripts/build_zip.py` writes it to the `dist/` folder of the plugin folder.

I never receive any of this. novelsmith contains no code that sends data to me or to any server I run.

## Where your data does go

novelsmith works through other software, and that software has its own terms:

- **Claude Code, Cowork and Anthropic.** The planning and writing are done by Claude. Your conversation, your settings and the book files Claude reads or writes are sent to Anthropic (or to the cloud provider you have configured for Claude Code) as part of your normal Claude Code or Cowork session, like anything else you ask Claude to work on. That is governed by your agreement with Anthropic and [Anthropic's Privacy Policy](https://www.anthropic.com/legal/privacy), not by novelsmith.
- **Other tools and connectors you use.** If you give Claude other tools in the same session (web search, MCP connectors), what Claude sends through them is up to you and those tools. The canon guard keeps novelsmith's agents and other subagents from changing the book through them, but novelsmith neither adds nor needs any.

## Personal data

The only personal data novelsmith asks for is your name as the author, which you can leave out or replace with a pen name.

Your book may contain personal data, for example if you base a character on a real person or note real places and events in your research. novelsmith treats it like any other text in the book: it stays in your `book/` folder, and whatever Claude reads is sent to Anthropic as described above.

## Deleting your data

- Delete the `book/` folder, or any file in it, to remove your book.
- Clear the author name in the plugin's settings in Claude Code.
- Run `scripts/install.py --uninstall` (or uninstall the plugin in Cowork) to remove the plugin itself. Uninstalling never touches your `book/`.

## Children

novelsmith is a writing tool for adults and is not directed at children.

## Changes

If this policy changes, the new version will be published in this file in the repository, with a new date at the top. The repository's history keeps every earlier version.

## Contact

Questions about this policy: open an issue at <https://github.com/Nannakaroliina/novelsmith/issues>.
