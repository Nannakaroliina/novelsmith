# Turning novel-writing into a multi-agent Claude Code plugin: mechanics, prior systems, research, and a recommended architecture

Research date: 2026-10-29. All Claude Code mechanics below were verified against the live docs at code.claude.com (not memory); version-gated features are marked with the version number the docs give.

---

## Key Question A: What is the exact structure of a Claude Code plugin, skill, subagent, command, hook and marketplace as of late 2026?

### Takeaway
A plugin is a directory with an optional `.claude-plugin/plugin.json` manifest and conventional component folders (`skills/`, `agents/`, `commands/`, `hooks/hooks.json`, `workflows/`, `.mcp.json`, `bin/`, `settings.json`); everything is namespaced `<plugin>:<component>`. Skills (`SKILL.md`) have superseded commands, agents are `.md` files whose body is the system prompt, and a new `workflows/` component (JS scripts calling `agent()`/`pipeline()`/`parallel()`) now exists for codified orchestration. Marketplaces are a `.claude-plugin/marketplace.json` in any git repo.

### Cited Findings

**Plugin layout and manifest**
- The manifest is optional; without it Claude Code loads components found in the standard layout. "Save the manifest at `.claude-plugin/plugin.json` under the plugin root. Put every other plugin file at the plugin root, not inside `.claude-plugin/`." — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- Standard layout (default locations): Manifest `.claude-plugin/plugin.json`; Skills `skills/` ("One `<name>/SKILL.md` per skill"); Commands `commands/` ("Flat Markdown command files. Prefer `skills/` for new plugins"); Agents `agents/` ("Subfolders are part of the agent name"); Hooks `hooks/hooks.json`; MCP servers `.mcp.json`; LSP `.lsp.json`; Output styles `output-styles/`; Workflows `workflows/` (`.js` files); Themes `themes/`; Monitors `monitors/monitors.json`; Executables `bin/` (on Bash PATH while enabled; claude.ai/Cowork refuse plugins with this directory); Settings `settings.json` (only `agent` and `subagentStatusLine` take effect). — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- Full example tree from the docs:
  ```text
  deploy-tools/
  ├── .claude-plugin/plugin.json
  ├── skills/deploy/SKILL.md
  ├── commands/status.md
  ├── agents/reviewer.md
  ├── hooks/hooks.json
  ├── monitors/monitors.json
  ├── output-styles/terse.md
  ├── themes/dracula.json
  ├── workflows/release-audit.js
  ├── bin/deploy-tool
  ├── scripts/format.sh
  ├── settings.json
  ├── .mcp.json
  └── .lsp.json
  ```
  — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- `plugin.json` fields: `name` (required, kebab-case; everything namespaced under it), `displayName`, `version` (pins users until changed), `description`, `author {name, email, url}`, `homepage`, `repository`, `license`, `keywords`, `metadata`, `defaultEnabled`, `dependencies`, `settings`, `userConfig`, `skills` (adds to default scan), `commands` (replaces default scan; path, array, or object map with `source`/`content`/`description`/`argumentHint`/`model`/`allowedTools`), `agents` (`.md` files only; replaces default scan), `hooks` (merges with `hooks/hooks.json`), `mcpServers`, `lspServers`, `outputStyles`, `workflows`, `experimental.{themes,monitors,evals}`. — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- Every component path "must start with `./`" and resolve inside the plugin root. Validate with `claude plugin validate ./my-plugin` (`--strict` for CI). — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- A `CLAUDE.md` at the plugin root "isn't loaded as context, and `claude plugin validate` warns when it finds one. To include instructions that load into Claude's context, put them in a skill." — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- Reserved plugin names: anything starting with `claude-`, `anthropic-`, `anthropics-`, `cc-plugin-`, etc. is an error. — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- Environment variables available to plugin components: `${CLAUDE_PLUGIN_ROOT}` (install dir; changes on update, don't write state there), `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/<id>/`, persists across updates, for caches/deps), `${CLAUDE_PROJECT_DIR}` (project root). In skill/command/agent Markdown bodies the `${...}` reference is substituted inline. — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)
- `userConfig` lets a plugin prompt the user for typed values (`string|number|boolean|directory|file`, `sensitive`, `options` picker since v2.1.271) stored in `pluginConfigs`; referenced as `${user_config.KEY}` in skill/agent content (non-sensitive only). — [Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference)

**Skills (`SKILL.md`)**
- Skill = directory with required `SKILL.md` (YAML frontmatter must start on line 1) plus optional supporting files; example: `my-skill/SKILL.md`, `reference.md`, `examples.md`, `scripts/helper.py`. — [Skills](https://code.claude.com/docs/en/skills)
- Locations: Enterprise managed dir; Personal `~/.claude/skills/<name>/SKILL.md`; Project `.claude/skills/<name>/SKILL.md`; Nested `<subdir>/.claude/skills/`; `--add-dir`; Plugin `<plugin>/skills/<name>/SKILL.md` invoked as `/plugin-name:skill-name`. Plugin skills are namespaced so they don't collide. — [Skills](https://code.claude.com/docs/en/skills)
- Frontmatter fields (all optional, only `description` recommended): `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation` (true = only the user can run it; use for side-effect workflows), `user-invocable` (false = hidden from `/` menu, Claude-only background knowledge), `allowed-tools` (pre-approved for the invoking turn), `disallowed-tools`, `model`, `effort` (`low|medium|high|xhigh|max`), `context: fork` (run in a forked subagent), `agent` (subagent type when forked, default `general-purpose`), `background`, `hooks`, `paths` (glob-limited auto-activation), `shell`, plus informational `metadata`, `license`, `compatibility`. — [Skills](https://code.claude.com/docs/en/skills)
- Example from the docs:
  ```yaml
  ---
  name: deploy
  description: Deploy the application to production
  context: fork
  disable-model-invocation: true
  allowed-tools: Bash(git push *)
  ---
  ```
  — [Skills](https://code.claude.com/docs/en/skills)
- Substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`/`$N`, `$name` (named args), `${CLAUDE_SKILL_DIR}`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`. Dynamic context injection with `` !`command` `` runs before Claude sees the content. — [Skills](https://code.claude.com/docs/en/skills)
- Limits: "Keep `SKILL.md` under 500 lines (guidance, not enforced)"; `description` + `when_to_use` truncated at 1,536 characters in the listing; after auto-compaction skills are re-attached at the first 5,000 tokens per skill, 25,000 combined. — [Skills](https://code.claude.com/docs/en/skills)
- Skills vs commands: `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create `/deploy`; "If a skill and a command file share a name, the skill wins"; docs recommend skills for new work. — [Skills](https://code.claude.com/docs/en/skills)
- Portability: outside Claude Code (claude.ai uploads, Skills API) only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` are allowed; other keys hard-fail validation. — [Skills](https://code.claude.com/docs/en/skills)
- In plugins: `skills/review/SKILL.md` in `my-plugin` runs as `/my-plugin:review`; the `skills` manifest key adds directories rather than replacing. A single `SKILL.md` at the plugin root loads as one skill (set `name`). — [Plugin components](https://code.claude.com/docs/en/plugins/components)

**Subagents (`agents/*.md`)**
- Locations and priority: Managed settings (1), `--agents` CLI flag (2), `.claude/agents/` (3), `~/.claude/agents/` (4), plugin `agents/` (5, lowest). Body = system prompt. — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Only `name` and `description` are required. Fields: `name` (≤256 chars, no `:`), `description`, `tools` (allowlist; e.g. `Agent(worker, researcher), Read, Bash` restricts spawnable subagents), `disallowedTools`, `model` (`sonnet|opus|haiku|fable|<full id>|inherit`), `permissionMode`, `maxTurns`, `autoCompactWindow` (100000–1000000, v2.1.296+), `skills` (preloaded at startup, up to 32), `mcpServers`, `hooks`, `memory` (`user|project|local`), `background`, `omitClaudeMd`, `effort`, `isolation: worktree`, `color`, `initialPrompt`, `experimental.cacheTtl`. — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Plugin agents: supported fields are `name, description, model, effort, maxTurns, tools, disallowedTools, skills, memory, background, omitClaudeMd, isolation, color, experimental.cacheTtl`; **`permissionMode`, `hooks`, `mcpServers`, `initialPrompt` are ignored** in plugin agents (add hooks/MCP at plugin level instead). Name form `<plugin>:<name>`; subfolders join with colons (`agents/review/security.md` → `my-plugin:review:security`); user invokes with `@agent-my-plugin:security-reviewer`. — [Plugin components](https://code.claude.com/docs/en/plugins/components)
- Example agent file from the docs:
  ```markdown
  ---
  name: security-reviewer
  description: Reviews code changes for security issues. Use after edits to authentication or input handling.
  model: sonnet
  ---
  You are a security reviewer. Read the changed files and report injection, authentication, and secrets-handling risks.
  ```
  — [Plugin components](https://code.claude.com/docs/en/plugins/components)
- Context isolation: a fresh subagent sees its system prompt, the delegation message, CLAUDE.md (unless `omitClaudeMd`), a git status snapshot, preloaded skills, and "a roster of named sibling agents". It does not see the main conversation. It returns only its summary. — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Parallelism: 20 concurrent subagents by default (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`); nesting up to 3 layers (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`); omit `Agent` from `tools` to stop a subagent spawning. Combined descriptions over 15,000 tokens trigger a startup warning. — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Resuming: Claude gets the agent ID on completion; resume via `SendMessage` with the agent's ID or name; transcripts at `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`. Subagents auto-compact as their own window fills. — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Fork mode (default on from v2.1.302): a fork inherits the full conversation (same system prompt, tools, model, history, prompt cache) and only returns its result; start with `/subtask <task>`; `isolation: "worktree"` keeps edits in a separate git worktree; a fork can't fork. `CLAUDE_CODE_FORK_SUBAGENT=0` turns it off. — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Subagents can't use `AskUserQuestion`, `EnterPlanMode`, `ExitPlanMode`, or `Workflow`. Subagent output is scanned for instruction-like text (not blocking). — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Delegation patterns named in the docs: isolating high-volume work; parallel research ("works best when the paths are independent"); chaining ("Use the code-reviewer subagent to find performance issues, then use the optimizer subagent to fix them"). — [Subagents](https://code.claude.com/docs/en/sub-agents)

**Hooks**
- `hooks/hooks.json` wraps the event map in a top-level `"hooks"` key, same shape as `settings.json`. Example `PostToolUse` with `"matcher": "Write|Edit"` running `"${CLAUDE_PLUGIN_ROOT}/scripts/format.sh"`. Plugin hooks fire from session load, not only when the plugin's skills are used. — [Plugin components](https://code.claude.com/docs/en/plugins/components)
- Events (selection relevant to a writing pipeline): `SessionStart` (can return `additionalContext`, `initialUserMessage`, `watchPaths`); `UserPromptSubmit` (exit 2 blocks the prompt); `PreToolUse` (exit 2 blocks; JSON `permissionDecision allow/deny/ask/defer`, `updatedInput`); `PostToolUse` (`decision: block` + `reason`, `updatedToolOutput`); `SubagentStart` (`additionalContext`); `SubagentStop` (exit 2 "Prevents the subagent from stopping"); `Stop` (exit 2 prevents stopping; conversation continues); `TaskCreated`/`TaskCompleted` (exit 2 blocks); `TeammateIdle`; `PreCompact`/`PostCompact`; `FileChanged` (watched file changed); `SessionEnd`. — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Hook types: `command`, `http`, `mcp_tool`, `prompt` (sends `prompt` with `$ARGUMENTS` = hook input JSON to a model; default 30 s timeout), `agent` (experimental; spawns a subagent that can Read/Grep/Glob before deciding; default 60 s). Exit 0 = success (stdout parsed as JSON), exit 2 = block with stderr as reason. — [Hooks reference](https://code.claude.com/docs/en/hooks)

**Workflows (new component)**
- "A dynamic workflow is a JavaScript script that orchestrates many subagents at once ... a runtime executes it in the background while your session stays responsive." Available on paid plans; Pro turns it on in `/config`. — [Workflows](https://code.claude.com/docs/en/workflows)
- Comparison table: Subagents (Claude decides turn by turn; results in Claude's context), Skills (instructions Claude follows), Agent teams (lead supervising peer sessions; shared task list), Workflows (the script decides; intermediate results live in script variables; "Dozens to hundreds of agents per run"; resumable). — [Workflows](https://code.claude.com/docs/en/workflows)
- Script shape: `export const meta = { name, description }` first; body is plain JS with top-level `await`; `agent(prompt, { schema, label, stallMs })` spawns one subagent (returns JSON if `schema`), `pipeline(list, fn)` runs one per item, `parallel()` runs a set and waits, `phase(title)` groups agents in the progress view, `log()`, global `args`. `Date.now()`/`Math.random()` throw (so replays are deterministic). — [Workflows](https://code.claude.com/docs/en/workflows)
- Limits: "No mid-run user input ... For sign-off between stages, run each stage as its own workflow"; no `import()`; no direct FS/shell from the script (agents do that); 16 concurrent agents by default (`CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`, 1–256, v2.1.269+); 4,096 items per `parallel()`/`pipeline()`; 1,000 agents per run; "Large workflow" warning above 25 agents or 1.5M projected tokens. — [Workflows](https://code.claude.com/docs/en/workflows)
- Saved to `.claude/workflows/` (project) or `~/.claude/workflows/`; in a plugin, `workflows/` dir, namespaced `/acme-tools:release-audit`. Load `/workflow-authoring` bundled skill (v2.1.248+) before editing scripts. Trigger via the `ultracode` keyword or "use a workflow". — [Workflows](https://code.claude.com/docs/en/workflows)
- Example prompt pattern relevant to novels: "Keep fixing until a check passes: run a checker, fix what failed, and repeat until it passes or stops making progress", and "review every file ... then merge the per-file findings into one ranked summary". — [Workflows](https://code.claude.com/docs/en/workflows)

**Agent teams (experimental)**
- Enabled with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. Lead + teammates, each a full Claude Code session with its own context; shared task list (`~/.claude/tasks/{team}/`) and mailboxes (`~/.claude/teams/{team}/inboxes/{agent}.json`); teammates message each other; a teammate can be spawned from a subagent definition (`tools`, `model`, `disallowedTools`, body applied; `skills` NOT applied). Quality-gate hooks: `TeammateIdle`, `TaskCreated`, `TaskCompleted` (exit 2 sends feedback). Docs: "Start with 3-5 teammates"; "Two teammates editing the same file leads to overwrites"; "significantly more tokens than a single session"; no nested teams; no session resumption of in-process teammates. Not available with `-p`/SDK. — [Agent teams](https://code.claude.com/docs/en/agent-teams)

**Marketplaces and installation**
- `marketplace.json` lives at `.claude-plugin/marketplace.json` in the marketplace root. Required top-level: `name`, `owner {name}`, `plugins[]`. Optional: `description`, `version`, `metadata.pluginRoot`, `forceRemoveDeletedPlugins`, `renames`, `allowCrossMarketplaceDependenciesOn`. — [Marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference)
- Plugin entry: `name`, `source` (required), `description`, `version`, `category`, `tags`, `strict` (default true), `dependencies`, `defaultEnabled`, `displayName`, `metadata`. Source forms: relative path `"./plugins/formatter"`; `{"source":"github","repo":"owner/repo","ref","sha"}`; `url` (any git URL); `git-subdir` (`url`,`path`); `npm`; `archive` (`url`,`sha256`, v2.1.224+); `command`. — [Marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference)
- Minimal example from the docs: `{ "name": "formatter", "source": "./plugins/formatter" }`. — [Marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference)
- Install commands: `/plugin marketplace add owner/repo` (or `owner/repo#v1.2.0`, a git URL, `./local-dir`, or an https `marketplace.json` URL); `/plugin install name@marketplace` (opens details pane to pick scope); shell: `claude plugin install formatter@your-org --scope project`; one-step `claude plugin install deploy-helper --marketplace your-org/plugins` (v2.1.292+). Scopes: user (`~/.claude/settings.json`), project (`.claude/settings.json`, committed; collaborators still run install once), local (`.claude/settings.local.json`). Dev loop: `claude --plugin-dir ./my-plugin`. Manage: `claude plugin enable|disable|uninstall|update|list|details|validate|prune`, `/reload-plugins`. — [Install and manage plugins](https://code.claude.com/docs/en/plugins/install)
- Anthropic's official marketplace is auto-registered as `claude-plugins-official`; third-party marketplaces have auto-update off by default. Plugins enabled on a claude.ai account also sync into terminal sessions as `<name>@synced` (v2.1.273+). — [Install and manage plugins](https://code.claude.com/docs/en/plugins/install)
- The anthropics/skills repo (183.3k stars) holds `skills/`, `spec/` (Agent Skills specification), `template/`, and `.claude-plugin/` marketplace config. — [anthropics/skills](https://github.com/anthropics/skills)

### Inferences
- For a novel plugin, the modern layout is: `skills/` for every author-invocable workflow (plan, outline, draft, revise, continuity-pass) and for background craft knowledge (`user-invocable: false`), `agents/` for the specialist personas, `hooks/hooks.json` for mechanical guards (e.g., `PostToolUse` on `Write|Edit` to a `manuscript/` path running a lint/wordcount script; `PreToolUse` refusing writes to `bible/canon.md` unless a `/canon` skill is active), and optionally `workflows/` for codified fan-out stages (parallel scene drafting, parallel reader panel). `commands/` should be left empty.
- Plugin agents cannot carry their own `hooks` or `mcpServers`, so guardrails must be plugin-level hooks with matchers that target file paths, not per-agent hooks.
- Workflows cannot pause for user input, so each author checkpoint must be a stage boundary: one workflow per stage (`outline`, `draft-act-1`, `reader-panel`), with the author reviewing files between runs.

### Gaps
- The docs page on skills was truncated after ~100k characters (the skill-creator evaluation section); I did not read the remaining ~14k characters.
- I did not fetch the `spec/` directory of anthropics/skills, so the exact Agent Skills spec text for `compatibility`/`metadata` is not quoted here.

---

## Key Question B: Anthropic's published guidance on writing good skills and agents (progressive disclosure, triggering, subagent vs skill, context management, orchestration)

### Takeaway
Anthropic's guidance is consistent across the skills best-practices page, the skill-creator skill, the subagents docs and the multi-agent research blog: keep metadata always-on and bodies lazy (three-tier progressive disclosure), write pushy third-person trigger descriptions, prefer scripts for deterministic work, give each subagent one job with objective/output-format/boundaries, pass state via the filesystem rather than relaying it through context, and evaluate end state with a rubric-based LLM judge plus human spot checks.

### Cited Findings

**Skill authoring**
- "Only metadata (name and description) is pre-loaded at startup. Claude reads `SKILL.md` only when the Skill becomes relevant, and reads other files only as needed." Default assumption: "Claude is already very smart"; ask "Does this paragraph justify its token cost?" — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Degrees of freedom: high (text instructions) when multiple approaches are valid; medium (pseudocode/parameterized scripts); low (exact scripts) for fragile sequence-critical operations. — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Naming: `name` ≤64 chars, lowercase/hyphens, prefer gerunds (`processing-pdfs`); avoid `helper`, `utils`. Description: ≤1,024 chars, third person, "Be specific and include triggers" e.g. "Use when working with PDF files or when the user mentions PDFs, forms, or document extraction." — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- File organization: keep SKILL.md under 500 lines; "Keep references one level deep"; add a table of contents to reference files over 100 lines; organize by domain (e.g. `reference/finance.md`, `reference/sales.md`) so irrelevant context isn't loaded; forward slashes only. — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Scripts vs instructions: scripts when the operation is fragile/deterministic, consistency or efficiency matters, or validation must be objective; instructions when multiple approaches are valid and Claude's judgment adds value. Handle errors in scripts, no "voodoo constants". — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Workflow patterns: copyable task checklists; "Feedback loop pattern: run validator → fix errors → repeat"; "Plan-validate-execute: for batch or destructive operations, have Claude write a `changes.json` plan, validate it with a script, then apply it"; "Non-code validation works too: check output against a `STYLE_GUIDE.md` checklist." Examples convey style better than descriptions. — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- Testing: "Build at least three evaluations before extensive documentation"; develop with two Claude instances (A designs, B tests fresh); test with Haiku, Sonnet, and Opus; use "MUST" over "always" when rules are missed. — [Skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- skill-creator (anthropics/skills) layout: `SKILL.md`, `scripts/` (deterministic/repetitive), `references/` (docs loaded as needed; >300 lines need a TOC; "one reference file per variant, so only the relevant one is read"), `assets/` (templates for output). Description rule: "Make it 'pushy' to counter undertriggering." Process: capture intent → interview → draft → test with 2–3 eval prompts in `evals/evals.json` against a baseline → iterate → optimize description with ~20 should/should-not trigger queries. — [skill-creator SKILL.md](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md)
- Claude Code specifics: "Create a skill when you keep pasting the same instructions into chat, or when a CLAUDE.md section has become a procedure rather than a fact"; "Use `context: fork` only for task-oriented skills with explicit instructions. Guideline-only skills return little useful output in a subagent"; "Use `disable-model-invocation: true` for workflows with side effects"; `/skill-doctor` shows which skills cost context without being used. — [Skills](https://code.claude.com/docs/en/skills)

**Subagents and orchestration**
- When to use subagents vs main conversation: main for "iterative back-and-forth, phases that share a lot of context, quick targeted changes, or latency-sensitive work"; subagents for "verbose output you don't need, enforced tool restrictions, or self-contained work that returns a summary." — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Best practices box: "Design focused subagents: each subagent should excel at one specific task"; "Write descriptions that single out one subagent"; "Limit tool access"; "Check into version control". Example `code-reviewer` uses `tools: Read, Grep, Glob, Bash` and a priority-ordered output format (Critical/Warnings/Suggestions). — [Subagents](https://code.claude.com/docs/en/sub-agents)
- Anthropic's multi-agent research system: orchestrator-worker pattern; each subagent task should specify "Objective, Output format, Tools and sources, Boundaries"; "Vague instructions led subagents to duplicate searches or drift"; scale effort to complexity (simple: 1 agent, 3–10 calls; comparison: 2–4 subagents; complex: 10+). — [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Token economics: "Agents use roughly 4x the tokens of chat; multi-agent systems use roughly 15x"; token usage explained ~80% of performance variance; Opus lead + Sonnet subagents beat single Opus by 90.2% on internal evals; "Multi-agent systems only make economic sense when the task's value justifies the extra cost." — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Context management: "Agents summarize completed phases and store key information before moving on"; "Subagents can store results externally and pass lightweight references back, avoiding information loss from repeated relaying." — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Evaluation: evaluate outcome not process; ~20 realistic queries suffice at first; single-prompt LLM judge scoring factual accuracy, citation accuracy, completeness, source quality, tool efficiency on 0.0–1.0 plus pass/fail "was the most consistent and closest to human judgment"; human testers caught what automation missed. — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Failure modes: over-spawning for simple queries, endless searching, excessive status updates, continuing after sufficient results, wrong tools. Fixes: heuristics over rigid rules, explicit guardrails, let the model diagnose its own prompts. — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- When multi-agent is NOT a fit: tasks needing shared context, many inter-agent dependencies, few parallelizable steps, low-value tasks, real-time coordination. — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Agent teams docs reinforce file-based state and ownership: "Break the work so each teammate owns a different set of files"; adversarial debate ("Have them talk to each other to try to disprove each other's theories") counters anchoring. — [Agent teams](https://code.claude.com/docs/en/agent-teams)

### Inferences
- Genre craft and style guides are "guideline-only" content, so they belong in skills loaded into the drafting agent's context (via the agent's `skills:` preload or a `user-invocable: false` skill), not in forked skills.
- The "plan-validate-execute" pattern maps directly onto novel work: the outliner writes `outline.yaml`, a script validates it (every scene has POV, goal, conflict, outcome; every character referenced exists in the bible), and only then do drafters run.
- Per Anthropic's cost finding (15x tokens), a drafting pipeline should route cheap mechanical checks (word count, banned-word scan, bible-name match) to scripts and Haiku, and reserve Opus/Fable for prose drafting and the "overall quality" judge.

### Gaps
- No Anthropic document specifically addresses creative-writing agents; the guidance above is general.

---

## Key Question C: Existing multi-agent novel-writing systems (open-source and commercial) and what they learned

### Takeaway
Every surviving system converges on the same skeleton — structured planning files as source of truth, a chapter loop of plan→draft→extract facts→audit→revise, deterministic host control flow, and selective retrieval of context — and they report the same failure modes: continuity breaks, hook/thread accumulation, context bloat and cost, and "voice convergence"/AI-flavored prose after ~10k words.

### Cited Findings

**Claude Code-native projects**
- forsonny/Claude-Code-Novel-Writer v4.1 (141 stars, 25 forks): shared creative core `AGENTS.md` + `.agents/roles/` + `.agents/skills/` with thin adapters for Claude Code (`CLAUDE.md` imports `AGENTS.md`; `.claude/agents/*.md`; `.claude/skills/` slash commands `/plan-novel`, `/write-chapter`, `/continuity-pass`, `/revise-chapter`, `/finalize-manuscript`; hooks in `.claude/settings.json`; `.claude/output-styles/`). Seven roles: `chapter-writer`, `plot-architect`, `character-developer`, `worldbuilder`, `continuity-editor`, `smart-planner`, `error-recovery`. Layout: `manuscript/chapters/` (authoritative), `planning/`, `characters/`, `worldbuilding/`, `automation/`, `templates/`. "Tracking data is derived from the manuscript and can be rebuilt with `./sync-state.sh`." `quality-check.sh` records only mechanical signals (word count, paragraph length, dialogue share) and the README says they "do not measure literary quality." — [forsonny/Claude-Code-Novel-Writer](https://github.com/forsonny/Claude-Code-Novel-Writer)
- howells/fiction (15 stars; installs with `claude plugins:add howells/fiction`; has `.claude-plugin/` and `.codex-plugin/`): `agents/`, `commands/`, `skills/`, `templates/`. Commands `/fiction:go, new, plan, outline, character, review, critique, synopsis, edit, language, naming, cover, build, notes, reconcile, status, next`. 26 agents including `writer` (opus), `architect`, `outliner`, `character-developer`, `chapter-reviewer`, `editor`, `critique`, `continuity` (haiku), parallel reader agents, and four persona critics (`james-wood`, `stephen-king`, `ursula-le-guin`, `roxane-gay`). Project folder: `README.md`, `progress.md` (session tracking + continuity state), `themes.md`, `characters/`, `world/`, `craft/`, `chapters/`, `critiques/`, `synopses/`, `builds/`, `covers/`. Authors mark immutable decisions with a `## ⚓ Anchored` heading "which reviewers treat as non-negotiable." Workflow: Foundation → First draft (chapter → review → revise loop) → Polish → Manuscript review → Publishing prep. 23 craft references incl. `prose-style.md`, `anti-patterns.md`. — [howells/fiction](https://github.com/howells/fiction)
- "Genesis" 21-skill Claude Code pipeline (plain slash-command `.md` files, MIT): 17 phases — Premise Analysis, Deep Research, Character Architecture, Plot Engineering, Voice Calibration, First Draft, Anti-AI Scan (20 "AI fingerprint" patterns; ≥2 hits → constrained rewrite), Chaos Injection (bounded imperfections with narrative justification), Character Consistency Check, Beta Reader Panel (5 personas), Revision, Genesis Scoring (10 dimensions; final score = lowest dimension, not average), Deep Edit, Final Polish, Continuity Audit, Editorial Package, Publication Prep; three user approval checkpoints. Produced a 68k-word and a 97k-word book; "Both still needed human editing"; "The core problem was 'voice convergence,' where prose flattened after about 10,000 words." — [dev.to: I built 21 AI skills that write a full book](https://dev.to/philipstark/i-built-21-ai-skills-that-write-a-full-book-from-one-sentence-4lgd)

**Standalone open-source pipelines**
- InkOS (Narcooo/inkos, AGPL-3.0, ~10.2k stars; 2.0 runs on the pi-agent runtime): roles Radar (trends, optional), Planner (intent + focus + memory retrieval → chapter plan with must-keep/must-avoid), Composer (selects task-relevant context, records what entered the model with protection levels and compression), Architect (initial world/rules/characters/control files), Writer (word-count governed), Settler (structured state deltas via typed tools validated by the host), Auditor ("evidence-based qualitative observations"), Reviser (new version only on explicit revision target). Chapter run: working set → plan → write → state projection → observation → atomic commit; revision is a separate action. State: `story/state/*.json` (Zod-validated: current state, hooks, chapter summaries) with human-readable projections `current_state.md`, `pending_hooks.md`, `chapter_summaries.md`, `character_matrix.md`; `story/memory.db` is a rebuildable SQLite FTS5/BM25 index, "not a source of story facts"; control files `author_intent.md`, `current_focus.md`. Continuity audit dimensions: character memory, material/resource continuity, hook payoff, outline deviation, pacing, emotional arc; "Audits record observations rather than pass/fail verdicts." De-AI: `inkos-story-deslop` skill via `revise --mode anti-detect`; `inkos detect` flags overused words, monotonous sentence structures, excessive summarizing; "rewriting is not triggered automatically by a hidden word list." HITL: confirmation cards before heavy actions, daemon pauses on issues needing judgment. Design principle: "completion is judged by tool results and files on disk, not by the model's claims." Per-agent model routing. — [Narcooo/inkos](https://github.com/Narcooo/inkos)
- Earlier InkOS write-up (10-agent pipeline Radar→Planner→Composer→Architect→Writer→Observer→Reflector→Normalizer→Auditor→Reviser; Observer extracts nine fact categories; Auditor checks "seven truth files across 33 dimensions"; revise→re-audit loop until critical issues resolved). Failure modes: continuity breaks (characters knowing things they never witnessed, lost items reappearing); context bloat ("$200+" per chapter pre-v0.6; selective retrieval was "the single biggest improvement"); hook accumulation (40+ unresolved threads → `hookAgenda`, `analyzeHookHealth`, `evaluateHookAdmission` to block duplicates, `mention` semantics to prevent fake advancement); AI voice ("delve", "tapestry") → per-genre fatigue word lists, banned sentence patterns, style fingerprint injection. — [dev.to: Building an autonomous AI agent that writes novels](https://dev.to/dylan_brown_4c803aefcfe51/building-an-autonomous-ai-agent-that-writes-novels-architecture-of-a-10-agent-pipeline-59pf)
- voocel/ainovel-cli (Go, ~71 stars, Chinese docs): Coordinator, Architect (premise, outline, character files, world rules), Writer (tools `plan_chapter`, `draft_chapter`, `check_consistency`, `commit_chapter`), Editor (seven dimensions: setting consistency, character behavior, pacing, narrative coherence, foreshadowing, hooks, aesthetic quality; "Every critique must cite the original text as evidence"). Forward-only phase machine (init, premise, outline, writing, complete) + flow layer (writing, reviewing, rewriting, polishing, steering). "The LLM never controls the control flow." Lazy expansion: Architect plans a 2-arc skeleton plus detailed arc 1; later arcs expand from arc summaries and character snapshots. Per-chapter context pack: prior summaries, timelines, active foreshadowing, character state, style rules, next-chapter forecast, relevant historical chapters; strategy switches between full-context, sliding-window, hierarchical summarization by chapter count. Chapter-level checkpoints resume after crashes. Main lesson: "keep control flow deterministic and let only generation be non-deterministic." — [dev.to: This Go CLI turns one sentence into a 500-chapter novel](https://dev.to/teum/this-go-cli-turns-one-sentence-into-a-500-chapter-novel-no-babysitting-required-i5m)

**Commercial products**
- Sudowrite Story Bible: "a living knowledge base" with Braindump → Synopsis → Genre/Style → Characters → Worldbuilding → Outline → Scenes → Draft; outlining first not required; Write reads up to 20,000 words of preceding story plus the Bible; Draft turns Scenes into chapter prose using Muse ("trained specifically for fiction"); Chapter Continuity links up to 25 documents, "your best defense against continuity errors"; Style Examples teach the model your register; principle: the AI "should know your story and support your voice, not replace either." — [How Sudowrite works](https://sudowrite.com/blog/how-sudowrite-works/)
- Humanizer skill (blader/humanizer fork, Claude Code + OpenCode): 29 patterns from Wikipedia's "Signs of AI writing" (WikiProject AI Cleanup) in categories content (significance inflation, promotional language, vague attributions, formulaic challenges), word choice (AI vocabulary, copula avoidance, synonym cycling, rule of three, false ranges, negative parallelisms), style/formatting (em dash and boldface overuse, inline-header lists, emojis, curly quotes), communication (chatbot artifacts, sycophancy), filler/hedging. Invoked `/humanizer <text>`; accepts 2–3 paragraphs of the user's own writing for voice calibration; ends with an "obviously AI generated" audit pass and second rewrite. — [wey-gu/humanizer](https://github.com/wey-gu/humanizer)
- Generic Claude Code writing setups (newsletter author): generate `CLAUDE.md` with `/init` from a folder of past writing so it captures voice; custom commands like `/quick-edit`; output styles as system prompts per work type; sub-agents for research; `/compact` and sub-agent context windows to manage limits; pitfall: "Claude Code may start editing files without being asked. Plan mode (Shift+Tab) shows the intended steps for approval first." — [aimaker Substack](https://aimaker.substack.com/p/how-i-turned-claude-code-into-personal-ai-agent-operating-system-for-writing-research-complete-guide)

### Inferences
- Across InkOS, ainovel-cli and howells/fiction, the "audit as evidence-citing observations, not pass/fail" pattern recurs, consistent with the research finding (below) that LLM judges are unreliable on absolute creative quality; audits should surface quotes for a human.
- The two most-starred systems (InkOS 10k, ainovel-cli) both separate "state projection" (structured JSON validated by the host) from "narrative" (Markdown prose), and treat search indexes as rebuildable caches. A Claude Code plugin can replicate this with Markdown + YAML files validated by a script in a `PostToolUse` hook.
- "Voice convergence after ~10,000 words" (Genesis) and "prose flattened" is the practitioner-reported form of the homogenization finding in Q D; style-fingerprint injection and per-genre fatigue lists (InkOS) are the current mitigations, none with published evaluation.
- No source reports a formal evaluation of any of these open-source systems; quality claims are anecdotal.

### Gaps
- Star counts and activity dates come from page snapshots and may be stale.
- I could not retrieve NovelCrafter or Raptor Write product docs within the call budget; only Sudowrite is covered.
- No source quantifies output quality of Claude Code-native novel plugins.

---

## Key Question D: Academic research on long-form AI fiction quality (planning hierarchies, coherence, evaluation, homogenization)

### Takeaway
Hierarchical outline-then-draft (Re3 → DOC → Dramatron → Agents' Room → StoryWriter) consistently improves coherence and human preference, with the event/outline layer being the single most important component; but expert studies (TTCW, Agents' Room, Doshi & Hauser) show LLM fiction still fails on originality, endings, subtext and lexical/structural diversity, LLM-as-judge is weak for absolute creative quality (near-zero kappa on TTCW; ~73% pairwise on LitBench), and AI assistance homogenizes output across writers.

### Cited Findings

**Planning hierarchies and coherence**
- Re3 (Yang et al. 2022) introduced the Plan / Draft / Rewrite / Edit pipeline with structured prompting from plan and prior story, rerankers for outline relevance and coherence, and an editing step for entity consistency; DOC kept plan/draft/rerank but dropped the editing step "which the authors say did not significantly affect quality." — [DOC paper](https://ar5iv.labs.arxiv.org/html/2212.10077)
- DOC (Yang et al. 2023): hierarchical detailed outliner (breadth-first expansion to depth 3; each item gets setting and characters; candidates filtered and reranked), plus a FUDGE-style controller for outline faithfulness; stories ~3,500 words. Pairwise human wins vs Re3: plot coherence 67.6% vs 45.1%, outline relevance 65.3% vs 37.1%, interestingness 60.1% vs 39.4%. Limitations: outline errors cascade; only 58.5% of passages faithful to leaf outline items; "Factual consistency is a major open problem, with glaring errors such as inconsistent names or genders. Pacing and foreshadowing are not addressed"; "Stronger control produces repetitive, narrowly focused output at the expense of creativity." — [DOC paper](https://ar5iv.labs.arxiv.org/html/2212.10077)
- Dramatron (Mirowski et al. 2022): prompt-chained hierarchy log line → title → characters → plot outline (scene = location + narrative element + beat) → location descriptions → dialogue per scene; "Dialogue was originally generated in parallel for each scene, which Table 1 notes was changed after participant sessions" because participants "found inconsistencies between scenes, which the paper links to parallel dialogue generation." 15 professionals: 92% surprised by outputs, 84% found it helpful, 77% enjoyed it; valued seeing the shape of the arc and "editing at any level"; all noticed repetition and loops (a loop detector resamples repeated blocks); noted gender bias, ageism, predictable tropes, weak motivation, lack of subtext, characters stating goals outright; "Eight of fifteen mainly removed material"; plot outlines were the least edited; log line as seed was hard, writers suggested starting from characters or themes. — [Dramatron paper](https://arxiv.org/pdf/2209.14958v1)
- RecurrentGPT (2023): writes one paragraph per step and maintains natural-language long/short-term memory on disk included in the next prompt; memories are human-readable and editable mid-generation ("AI As Contents" interactive fiction). No evaluation of its unlimited-length claims appears on the abstract page. — [RecurrentGPT](https://arxiv.org/abs/2305.13304)
- Agents' Room (Huot et al., ICLR 2025): planning agents CONFLICT, CHARACTER, SETTING, PLOT write only to a shared scratchpad; writing agents EXPOSITION, RISING ACTION, CLIMAX, FALLING ACTION, RESOLUTION each write one section, concatenated; a deterministic orchestrator runs planners then writers; the scratchpad is updated after each call with the agent's label and output "so later agents can read earlier contributions and avoid repetition." Tell Me A Story dataset: 123/52/55 train/val/test from 28 writers. Human pairwise preferences on plot, creativity, development, language use, overall (Bradley-Terry; Fleiss κ = 0.46). Results: humans preferred overall, smallest gap on language use; Agents' Room with writing agents beat end-to-end baselines on all dimensions; fine-tuned > zero-shot; **planning-only variants performed poorly** ("the single finalizer agent being too simple to use the planned elements"); longer stories (~3,000 words vs ~1,200 baseline, 1,439 human) were not preferred for length (longer preferred only ~51%). LLM judge (Gemini 1.5 Pro) correlated ρ = 0.62 with humans across systems, ρ = 0.41 across items, 90.2% self-consistent under order swap. Failure modes: machine stories "more generic in sentence structure, with more sentences starting with an article or pronoun", "less lexically diverse, and the longest systems show the most trigram repetition", "still fall short on plot and originality." — [Agents' Room paper](https://arxiv.org/pdf/2410.02603v2)
- StoryWriter (Xia et al., Tsinghua, June 2025; AutoGen-based): Outline agents EventSeed (event tuples: time, location, relationships) + EventValidator; Planning agents SubTasker + Weaver (non-linear narration across chapters, flashbacks allowed if causal links preserved); Writing agents Coordinator + FinalWriter with ReIO (condense relevant history on input; rewrite drafts that drift from outline on output); sliding-window summarizer compressing the middle of history worked best. Human avg 4.2 vs 3.6–3.8 for DOC, Agents' Room, GPT-4o-mini; ~8,000-word outputs vs 1,000–3,100 for baselines; slightly behind Agents' Room on relevance/coherence, ahead on creativity/complexity. Ablation: removing the event-based outline caused the largest drop (4.3 → 2.5). Limitations: "Coherence tends to fall as length grows"; attention degradation beyond ~10,000 characters; "Common failures include repetition, hallucination, topic drift, and homogeneous plots." — [StoryWriter paper](https://web3.arxiv.org/pdf/2506.16445)
- Weaver (Jan 2024): family of writing-specialized LLMs (1.8B–34B) pre-trained on a writing corpus and aligned to professional writers' preferences; reported to beat generalist LLMs several times their size on a curated writing benchmark. — [Weaver](https://arxiv.org/abs/2401.17268)

**Expert evaluation of LLM fiction and the "sameness" problem**
- "Art or Artifice?" (Chakrabarty et al.): Torrance Test of Creative Writing = 14 binary tests (Fluency 5, Flexibility 3, Originality 3, Elaboration 3). 12 New Yorker stories vs 36 LLM stories (GPT-3.5, GPT-4, Claude v1.3) matched on plot and length. New Yorker passed ~84.7% of tests; GPT-3.5 8.7%, GPT-4 27.9%, Claude v1.3 30.0% → "three to ten times less likely to pass." Experts preferred the New Yorker story in 89% of rankings. Expert-named weaknesses: cliché and stereotyped characters, weak endings ("forestalling a resolution by expanding scope, or multiple disparate endings"), overtelling with expository dialogue and little subtext, muddled or simplistic metaphors, characters who appear and vanish, pacing loops or rapid time skips, repeated words/phrases across stories. **LLM judges had near-zero agreement with experts** (Cohen's κ ≈ 0.02 GPT-3.5, 0.04 GPT-4, −0.01 Claude); experts agreed moderately per test (Fleiss κ 0.41) and strongly on totals (r = 0.69). — [Art or Artifice?](https://ar5iv.labs.arxiv.org/html/2309.14556)
- Doshi & Hauser (Science Advances, 2024): 300 writers wrote 8-sentence micro-stories with no AI / one ChatGPT idea / up to five ideas; 600 raters. Most AI access raised novelty 8.1% and usefulness 9%; low-creativity (DAT) writers gained most (novelty +10.7%, usefulness +11.5%, up to 26.6% "better written"); AI "narrowed the gap" between writers. Stories from one-AI-idea writers were 10.7% more similar to each other than no-AI stories. Authors warn of a "social dilemma"/"downward spiral": individual incentive to use AI reduces collective novelty. — [University of Exeter summary](https://news.exeter.ac.uk/?p=13749)
- "Death of the Novel(ty)" (Sept 2025): 8,618 expert annotations; n-gram novelty is only weakly linked to expert-judged creativity ("About 91% of the top-quartile n-gram-novel expressions were not judged creative"); in open-source LLMs more novel phrasing correlated with less pragmatic text (not so for humans); frontier closed models produced fewer creative expressions than humans; LLM-as-judge novelty ratings matched expert preferences better than n-gram metrics, but models "struggle most with non-pragmatic expressions." — [Death of the Novel(ty)](https://arxiv.org/abs/2509.22641)
- Task-dependent homogenization taxonomy (Jain et al., Sept 2025, v3 Apr 2026): creative writing "should vary in key narrative components such as plot and setting, not just vocabulary"; proposes task-dependent sampling to increase diversity only where it is wanted and argues the diversity–quality trade-off is partly an artifact of task-agnostic measurement. — [arXiv 2509.21267](https://arxiv.org/abs/2509.21267)
- Genre-specific homogeneity in LLM Chinese web fiction (Mar 2026): LLM stories are "structurally homogeneous, reusing similar arrangements of plot events and stereotyped resolutions"; 34 Propp-style narrative functions defined; proposed cause: LLMs are "unable to correctly comprehend the meanings of narrative functions" and fall back on rigid patterns. — [arXiv 2603.14430](https://arxiv.org/abs/2603.14430)
- LitBench (2025): 2,480 held-out pairwise r/WritingPrompts comparisons. Zero-shot judges: Claude 3.7 Sonnet ~73% agreement with human preference, GPT-4.1/o4-mini/DeepSeek ~70–71%, Llama-3.1-8B 58%. Trained Bradley-Terry reward model (Llama-8B) 78%; chain-of-thought in generative reward models *lowered* accuracy to 72%. Length bias: 65% of preferred stories were longer in unfiltered data; unfiltered training plateaued ~70% and favored length. In a 46-person study the reward model's top pick was preferred 57% vs 41% for its bottom pick; the best LLM judge was at chance. Recommendations: use a strong proprietary judge if no training data; control length bias; consider rubric-based feedback. — [LitBench](https://arxiv.org/pdf/2507.00769v1)

### Inferences
- Outline-first is the evidence-backed default: the outline/event layer had the largest effect in both DOC and StoryWriter ablations, and Dramatron writers edited outlines least. A plugin should make the outline a validated, author-approved artifact before drafting.
- Planning agents are useless without capable writers (Agents' Room planning-only ablation); so the plugin's investment should go into the drafter and the handoff from outline to scene, not into ever-more-elaborate planning roles.
- Parallel scene drafting trades coherence for speed (Dramatron reverted to sequential). Parallelism is safe for *independent* work (per-scene audits, reader panel, research) but drafts within a chapter or POV thread should run sequentially with the previous scene's summary and the "last 2–3 pages" in context.
- Evaluators should be pairwise/comparative and rubric-anchored (where LLM judges reach ~70–78%), not absolute "is this creative?" judgments (near-zero kappa), and must be length-debiased (hold word counts fixed or penalize length). Scoring by the lowest dimension (Genesis) rather than the mean is a sensible guard.
- Homogenization evidence implies the plugin should (a) inject author-specific style fingerprints and voice samples, (b) check structural variety (sentence openers, trigram repetition, scene-shape variety) with scripts, and (c) have idea-generation stages produce many divergent options for the author to choose from rather than one "best" idea, since author selection is where diversity re-enters.

### Gaps
- Full texts of arXiv 2509.21267 and 2603.14430 were not read; only abstracts.
- No published study evaluates Claude 4.x/5.x-era models on TTCW; the kappa figures are from 2023 models and may have changed.
- I found no peer-reviewed evaluation of "de-AI"/humanizer passes on fiction quality.

---

## Key Question E: Recommended architecture for a novel-writing Claude Code plugin (orchestration, roles, state, loops, author control, genre packaging, cost)

### Takeaway
Build a file-first plugin: the book bible, outline and scene manifest are the only source of truth; a thin orchestrator skill sequences specialist subagents through outline-first stages with author checkpoints at every stage boundary; drafting is sequential per POV thread with retrieval-composed context packs; critique is a parallel panel of blind, evidence-citing evaluators whose findings are diffs the author accepts; genre knowledge ships as one-level-deep reference files inside skills; hooks enforce mechanical invariants.

### Cited Findings (design constraints drawn from the sources above)
- Plugin agents cannot define `hooks`/`mcpServers`/`permissionMode`; guardrails must be plugin-level hooks. — [Plugin components](https://code.claude.com/docs/en/plugins/components)
- Workflows cannot pause for user input; stages needing sign-off must be separate workflows. — [Workflows](https://code.claude.com/docs/en/workflows)
- Subagents return only a summary and don't share the main context; "Subagents can store results externally and pass lightweight references back." — [Subagents](https://code.claude.com/docs/en/sub-agents); [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Agent `skills:` preloads up to 32 skills' full content into a subagent at startup; the reference-file-per-variant pattern keeps only the relevant genre file in context. — [Subagents](https://code.claude.com/docs/en/sub-agents); [skill-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md)
- All current Claude models have a 1M-token context window and 128K max output; pricing per MTok input/output: Fable 5.1 $10/$50, Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 from $0.10/$0.50. — [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- Subagent prompt-cache TTL is 5 minutes by default; `subagentPromptCacheTtl: 1h` extends it; workflow fan-outs stagger agents to share a cached prefix. — [Agent teams](https://code.claude.com/docs/en/agent-teams); [Workflows](https://code.claude.com/docs/en/workflows)
- Hooks `Stop` and `SubagentStop` with exit 2 keep an agent working; `TaskCompleted` exit 2 blocks completion; `prompt`/`agent` hook types can run a model-based check. — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Evidence-citing audits ("Every critique must cite the original text"), anchored author decisions (`## ⚓ Anchored`), and state-as-validated-files are field-proven patterns. — [ainovel-cli](https://dev.to/teum/this-go-cli-turns-one-sentence-into-a-500-chapter-novel-no-babysitting-required-i5m); [howells/fiction](https://github.com/howells/fiction); [inkos](https://github.com/Narcooo/inkos)

### Inferences (the recommended design)

**1. Plugin file tree**
```text
novelsmith/                                  # plugin root (name is illustrative)
├── .claude-plugin/plugin.json               # name, version, userConfig (author_name, default_genre, target_words)
├── skills/
│   ├── novel-start/SKILL.md                 # /novelsmith:novel-start  — scaffolds book/ tree (disable-model-invocation: true)
│   ├── bible/SKILL.md                       # /novelsmith:bible — create/update characters, world, rules, timeline
│   ├── outline/SKILL.md                     # /novelsmith:outline — premise → acts → chapters → scene manifest (plan-validate loop)
│   ├── draft/SKILL.md                       # /novelsmith:draft <scene-id|chapter> — sequential scene drafting
│   ├── critique/SKILL.md                    # /novelsmith:critique <chapter> — parallel blind reader/editor panel
│   ├── revise/SKILL.md                      # /novelsmith:revise <chapter> — apply accepted notes as diffs
│   ├── continuity/SKILL.md                  # /novelsmith:continuity — bible-vs-manuscript audit, updates facts ledger
│   ├── status/SKILL.md                      # /novelsmith:status — progress, open threads, next action
│   ├── craft-prose/SKILL.md                 # user-invocable: false — line-level craft rules, examples, anti-patterns
│   ├── craft-structure/SKILL.md             # user-invocable: false — scene/sequel, beats, pacing, endings
│   ├── de-ai/SKILL.md                       # user-invocable: true — AI-tell catalogue + author voice calibration
│   └── genre/SKILL.md                       # one skill; references/<genre>.md one level deep (mystery.md, romance.md, …)
│       └── references/{mystery,thriller,romance,fantasy,literary}.md
├── agents/
│   ├── story-architect.md                   # premise, promise, theme, ending; model: opus/fable
│   ├── character-designer.md               # wants/needs/wounds/voice sheets → book/bible/characters/*.md
│   ├── worldbuilder.md                      # rules, places, timeline → book/bible/world/*.md
│   ├── outliner.md                          # scene manifest with POV/goal/conflict/turn/outcome; tools: Read, Write, Edit, Bash
│   ├── scene-drafter.md                     # prose only; skills: [craft-prose, craft-structure, genre, de-ai]; tools: Read, Write
│   ├── line-editor.md                       # sentence-level; outputs diff proposals, not rewrites
│   ├── continuity-editor.md                 # read-only + ledger write; model: haiku/sonnet; tools: Read, Grep, Glob, Edit(ledger only)
│   ├── genre-specialist.md                  # checks genre promises/beats; reads genre/references/<genre>.md
│   ├── de-ai-editor.md                      # scans for AI tells + homogenization metrics; proposes diffs
│   ├── reader-simulator.md                  # blind reader persona(s); experiences the text, reports confusion/boredom with quotes
│   └── judge.md                             # pairwise, rubric-anchored comparator for A/B drafts; never sees process notes
├── hooks/hooks.json                         # PostToolUse Write|Edit on book/manuscript/** → scripts/lint-scene.sh
│                                            # PreToolUse Write|Edit on book/bible/canon.md → deny unless CLAUDE_SKILL == bible
│                                            # SessionStart → scripts/status-summary.sh (additionalContext: open threads, next scene)
├── workflows/                               # optional codified fan-outs (no mid-run input)
│   ├── reader-panel.js                      # parallel(): N blind readers per chapter → ranked, deduped findings
│   └── continuity-sweep.js                  # pipeline(): per-chapter fact extraction → merge → diff vs bible
├── scripts/                                 # deterministic: validate-outline.py, lint-scene.sh (wordcount, banned words,
│                                            # sentence-opener variety, trigram repetition), extract-facts.py, build-context-pack.py
└── templates/                               # bible/character.md, scene-card.md, chapter-summary.md, critique-note.md
```
Rationale: skills over commands (docs), guideline skills marked `user-invocable: false` and preloaded via agent `skills:` (docs), one genre skill with per-variant reference files (skill-creator), hooks at plugin level because plugin agents ignore `hooks` (components doc), scripts for anything deterministic (best practices).

**2. Book state (the source of truth, in the author's repo, not the plugin)**
```text
book/
├── bible/
│   ├── premise.md            # logline, promise to reader, theme, ending (## ⚓ Anchored sections are immutable to agents)
│   ├── style.md              # voice fingerprint: 2–3 author sample passages, POV/tense, banned words, sentence-rhythm notes
│   ├── characters/<slug>.md  # want/need/wound/lie, voice tics, relationships, arc beats, what they KNOW (knowledge ledger)
│   ├── world/<topic>.md      # rules, places, tech/magic constraints
│   ├── timeline.md           # dated events; one line per fact with source scene id
│   └── facts-ledger.yaml     # machine-extracted facts per scene (who knows what, objects, injuries, locations) — rebuildable
├── outline/
│   ├── acts.md               # act-level structure and turning points
│   ├── chapters.md           # chapter goals, POV, word targets
│   └── scenes.yaml           # SCENE MANIFEST: id, chapter, pov, location, time, goal, conflict, turn, outcome, status, word_target
├── manuscript/
│   └── ch01/s01.md …         # one file per scene; frontmatter: scene id, status (draft|revised|locked), version
├── summaries/
│   ├── ch01.md …             # 150–300-word chapter summaries written after drafting (for context packs)
│   └── running.md            # "story so far" rolling summary, regenerated per act
├── critiques/
│   └── ch01/<agent>-<date>.md  # evidence-citing notes with quotes and proposed diffs
└── progress.md               # next action, open threads/hooks with admission dates, decisions log
```
Every file is Markdown/YAML so the author can edit it directly (Sudowrite's Story Bible, InkOS projections, RecurrentGPT's editable memory). `facts-ledger.yaml` and `summaries/` are derived and rebuildable (InkOS, forsonny), validated by `scripts/validate-outline.py` before drafting (plan-validate-execute).

**3. Orchestration loop (text diagram)**
```text
[author] /novel-start ─► scaffold book/, interview for premise/genre/voice samples
        │
        ▼
STAGE 1  story-architect ──► premise.md, acts.md        ── author checkpoint (edit, anchor) ──┐
STAGE 2  character-designer ∥ worldbuilder ──► bible/    ── author checkpoint ──────────────────┤ (parallel OK: independent files)
STAGE 3  outliner ──► chapters.md, scenes.yaml ──► validate-outline.py ──(fail)──► outliner fixes
                                                 └──(pass)── author checkpoint ───────────────┘
STAGE 4  per POV thread, SEQUENTIAL:
         build-context-pack.py(scene) = style.md + scene card + prev scene tail (~1.5k words)
                                       + running.md + relevant character sheets + facts for named entities
         scene-drafter ──► manuscript/chNN/sNN.md
         hook: lint-scene.sh (wordcount band, banned words, opener variety, trigram repeats) ──(fail)──► drafter revises once
         extract-facts.py ──► facts-ledger.yaml ; continuity-editor diff vs bible ──► critiques/ (observations, not blocks)
         after each chapter: chapter summary ──► summaries/chNN.md ; progress.md updated
         ── author checkpoint per chapter (or per act for autopilot) ──
STAGE 5  critique panel (PARALLEL, each agent BLIND to the others and to process notes):
         reader-simulator ×N (personas) ∥ line-editor ∥ genre-specialist ∥ de-ai-editor ∥ continuity-editor
         → each writes critiques/chNN/<agent>.md with quoted evidence + proposed diff hunks
         judge merges/dedupes/ranks; scoring = min over rubric dimensions, length-debiased
STAGE 6  revise: author accepts/rejects notes in critiques/ ; reviser applies ONLY accepted diffs; re-run lint + continuity
         loop STAGE 5–6 at most K times or until no critical findings (stop rule from Anthropic/workflow guidance)
STAGE 7  manuscript-level pass per act/book: structure, arcs, endings; then export
```
Author control mechanisms: every stage ends by writing files and stopping (subagents cannot `AskUserQuestion`; workflows cannot pause), `## ⚓ Anchored` headings reviewers must not contradict (howells), `disable-model-invocation: true` on all side-effecting skills, diff-style critique output so the author sees exactly what changes, and `progress.md` as the resumable checkpoint (ainovel-cli checkpointing; Anthropic "resume from checkpoints").

**4. Role list and model routing**
| Role | Job | Model | Tools |
|---|---|---|---|
| story-architect | premise, promise, theme, ending; divergent options (5+) for author pick | opus/fable | Read, Write |
| character-designer | character sheets, knowledge ledger seeds | opus | Read, Write |
| worldbuilder | rules/places/timeline | sonnet | Read, Write |
| outliner | scenes.yaml with goal/conflict/turn/outcome; runs validator | opus | Read, Write, Edit, Bash(validate script) |
| scene-drafter | prose for ONE scene from a context pack; no edits to bible | opus/fable | Read, Write |
| line-editor | sentence-level diffs | sonnet | Read |
| continuity-editor | facts vs bible, knowledge violations (who knows what) | haiku/sonnet | Read, Grep, Glob, Edit(ledger) |
| genre-specialist | genre promises/beats/clue fairness (mystery) | sonnet | Read |
| de-ai-editor | AI tells, opener/rhythm monotony, cliché density, voice drift vs style.md | sonnet | Read, Bash(metrics) |
| reader-simulator | blind read; confusion, boredom, predictions, emotional beats with quotes | sonnet (several personas) | Read only |
| judge | pairwise A/B with rubric; never sees drafts' provenance | opus | Read |
Rationale: Anthropic's cost finding (Opus lead + Sonnet workers), InkOS per-agent routing, read-only tool restriction for reviewers (subagent best practices), TTCW/LitBench (judges work pairwise, not absolute).

**5. Genre packaging**
One `genre` skill with `references/<genre>.md` (per-variant files, one level deep, TOC if >100 lines) is the Anthropic-recommended shape; the `genre-specialist` agent reads only the file named in `premise.md`. Separate per-genre *skills* would multiply always-on description tokens (every skill description sits in context; combined agent descriptions should stay under 15k tokens). Genre-as-agent-persona is unnecessary: the persona is a thin wrapper over the reference file.

**6. Context and cost for a 90k-word manuscript**
A 90k-word novel is roughly 120k tokens, which fits in the 1M window, but drafting with the full manuscript in context is wasteful and (per StoryWriter/Dramatron) degrades coherence; use retrieval-composed context packs (~8–15k tokens: style sample, scene card, previous scene tail, running summary, relevant sheets). Reviewers that need whole-book view (structure pass, continuity sweep) can load the full manuscript on Sonnet (~$0.25 input per pass at $2/MTok) or chunk by act. Keep style constant across sessions via `style.md` + 2–3 author sample passages injected into every drafter prompt and a `SessionStart` hook that surfaces `progress.md`; set `subagentPromptCacheTtl: 1h` during long drafting runs so the shared prefix (craft skills + style) stays cached. Expect the full pipeline to cost on the order of 10–15x a single-pass draft (Anthropic's multi-agent figure), so default to "draft one chapter, critique one chapter" rather than whole-book autopilot.

**7. Anti-homogenization measures (from Q D evidence)**
Author voice samples in every drafter prompt; scripts measuring sentence-opener distribution, trigram repetition, dialogue/narration ratio per scene (Agents' Room failure metrics); divergent-options stages (5 premises, 3 endings, 3 scene approaches) with author selection; scene manifest requiring a distinct "turn" per scene; a reader-simulator asked to predict the ending at the midpoint (predictability check); and a de-AI pass restricted to proposing diffs so it cannot flatten voice further.

### Gaps
- No empirical data exists on how any Claude Code novel plugin performs; the architecture is a synthesis, not a validated design.
- Hook matcher syntax for restricting `Write|Edit` by *file path* (vs tool name) was not verified on the hooks page within this research; the `PreToolUse` hook would need to inspect the tool input JSON in the script to enforce path rules.
- The `Workflow` tool is unavailable to subagents and absent in `-p`/SDK teammate spawning; whether a skill with `context: fork` can launch a plugin workflow was not verified.
