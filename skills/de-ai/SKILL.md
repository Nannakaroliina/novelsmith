---
name: de-ai
description: Fiction layer for detecting and removing "sounds AI-written" tells in a novel draft, at outline, scene, and dialogue level. Covers the measured structural fingerprint (stated themes, body-cue emotion, no subplots, tidy endings), always-fix craft failures, rate-limited tells counted per 1,000 words against the author's own baseline, outline-level checks, and over-correction traps. Use when drafting a scene (stage 4 self-check), critiquing or revising a chapter (stages 5–6), running the book pass (stage 7), or whenever the user says a passage "sounds like AI", "sounds generic", asks to humanize, de-slop, detect AI-isms, or scan a scene. Sits on top of the Anthropic avoid-ai-writing skill, which owns the business-prose vocabulary tiers.
user-invocable: true
argument-hint: "[scene or chapter path] [--detect|--rewrite]"
---

# De-AI: fiction layer

## Thesis

1. **Structure is the fingerprint, not vocabulary.** StoryScope (61,608 stories, 5 frontier models vs human): narrator states the theme 77% AI vs 52% human; emotion routed through bodily sensation 81% vs 38%; explicit emotion labels 8% vs 29%; no subplot 79% vs 57%; morally ambivalent protagonist 38% vs 59%. Narrative features alone reach 93% F1 as a detector. No word list comes close.
2. **Word lists age fast.** "Delve" faded within one model generation. Treat vocabulary as a floor, versioned by model era, never as the fix.
3. **Most tells are ordinary bad craft** that humans also produce (tidy plots, stated themes, flawless protagonists, body-cue emotion, dissolving conflict). Fixing craft fixes "AI-ness"; sanding surface tics does not.
4. **Density and co-occurrence are the signal.** One em dash, one clenched jaw, one "not X but Y" is nothing. Twenty per thousand words is a fingerprint. Count; do not ban.
5. **Over-correction creates a second fingerprint.** Experts beat detectors; detectors mislabel low-perplexity humans. Report counts and quoted evidence, never a verdict.

## Claude's own measured defaults (know what you drift toward)

Per StoryScope's per-model profile, Claude-written fiction shows: **notably flat event escalation**, the **most uniform narrative voice** across POV characters, a preference for **epilogues**, avoidance of dream sequences and non-linear moves, **tidy endings** of internal acceptance, and a "reverent, continuist" treatment of genre convention (62% vs 39–56%). In short-story tests Claude also gravitates to lighthouse/keeper settings and names like Elias and Mara. When drafting, assume you are doing all of this unless the outline forces otherwise.

## How to run

### Input
`$ARGUMENTS` = a path under `book/manuscript/chNN/` (one scene or a chapter folder) or `book/outline/`, plus an optional mode flag. No path: ask for one. No flag: default to `--detect`.

### Modes
| Mode | Does | Does not |
|---|---|---|
| `--detect` | Lists every finding with quoted evidence; per-1,000-word counts for every rate-limited item against the limits in `book/bible/style.md`; writes to `book/critiques/chNN/de-ai-<date>.md` | Edit the manuscript |
| `--rewrite` | Everything in detect, plus a proposed diff per P0/P1 finding | Apply any diff; the author accepts or rejects each one |

**NEVER** write to `book/manuscript/` in either mode. **NEVER** contradict a `## ⚓ Anchored` section in `book/bible/premise.md`; if a finding would, note it as "anchored, not proposed".

### Procedure
Every `references/` path below is in `${CLAUDE_SKILL_DIR}/references/`.

1. Read `book/bible/style.md`: POV/tense, voice notes, **author sample passages**, rate limits per 1,000 words, name list. Read `book/bible/characters/<slug>.md` for every POV character in scope (voice + NEVER-SAYS).
2. Compute the **author baseline** from the sample passages: em dashes, "not X but Y", fragments, one-line paragraphs, sentence-length coefficient of variation, said-only ratio. Record it at the top of the critique.
3. Run `references/always-fix.md` on every paragraph. These are P0/P1 regardless of counts.
4. Run `references/rate-limit.md`. Count per 1,000 words. A finding exists only when the count exceeds **the author's own rate** (from step 2) or the explicit limit in `style.md`, whichever the author set. **NEVER** compare to the default budgets in the reference when a baseline exists; the defaults are for books with no samples yet.
5. If scope includes `book/outline/`, run `references/outline-level.md`.
6. Before writing any diff, read `references/do-not-overcorrect.md` and check each proposal against it.
7. Write the critique in the output format below.

### Rules that models skip
- **Generate with positive constraints, revise with negative constraints.** At stage 4 the drafter works from `style.md` voice rules, the character's metaphor domain, and the scene's goal/conflict/turn; it does not draft from a ban list (negative prompting alone does not reduce homogeneity). The ban lists are for stage 5–6 revision and the stage 4 *self-check* after the draft exists.
- **Per-author baseline, never a universal threshold.** A writer whose samples show 4 em dashes per 1,000 words gets a limit near 4, not 1. If `style.md` has no samples, say so and ask for 1,500+ words of the author's own prose before any rate-limit finding is more than provisional.
- **Rewrite from scratch, do not patch,** when a passage hits the avoid-ai-writing trigger (5+ vocabulary hits across 3+ pattern categories plus uniform rhythm) **or** the fiction equivalent: 3+ always-fix items in one scene, **or** every paragraph ends on a reflective line, **or** the scene ends with its own conflict resolved. Propose a one-line restatement of the scene's turn and a from-scratch draft; patched prose keeps the skeleton that caused the problem.
- **Replacement clichés come from randomized sets.** When a diff replaces a stock phrase, draw from a set of 3–4 alternatives in `rate-limit.md` and vary the pick across findings. A fixed replacement table is a new fingerprint. Prefer cutting over replacing.
- **Never over-correct.** Plain emotion words, comma splices, digressions, and repeated clear words are human signals (`references/do-not-overcorrect.md`). If the original passage is strong, say so and propose nothing.
- **Continuity drift is a pipeline problem.** Eye colour changes, re-described rooms, a character knowing something too early: do not propose prose patches. File it as a P0 against the **knowledge ledger** in `book/bible/characters/<slug>.md` and `book/bible/timeline.md`, and point the author to the book-bible skill. Most such errors cluster mid-narrative in high-entropy passages; check chapter middles first.
- **Business-prose vocabulary** (delve, tapestry, testament, underscore, leverage, robust…) is owned by the Anthropic `avoid-ai-writing` skill, Tier 1–3 tables. Run that skill's Tier 1 list over narration and flag any hit as P1; do not reproduce the tables here. In dialogue, corporate lexicon is a voice finding (see always-fix).

## Which reference, which stage

| File | Job | Stage |
|---|---|---|
| `references/outline-level.md` | Yes/no checks on `book/outline/acts.md` and `scenes.yaml` for the measured narrative gaps (subplot, moral compromise, open thread, non-linear move, climax placement, chapter shape, names) | 3 (before drafting) and 7 (book pass) |
| `references/always-fix.md` | Wrong regardless of count: explained subtext, stated theme, label-on-cue, wisdom closers, coda overreach, broken similes, chatbot artifacts, recycled descriptors, corporate lexicon, therapy-speak, mic-drops, dissolving conflict, default names, "as you know" | 4 self-check, 5 critique |
| `references/rate-limit.md` | Tells only in excess: budgets per 1,000 words, regex where one exists, replacement sets | 4 self-check, 5 critique |
| `references/do-not-overcorrect.md` | Human signals to leave alone, over-correction failure modes, detector caveats | 6 revise (read before applying any diff) |
| Anthropic `avoid-ai-writing` SKILL.md | Vocabulary tiers, severity model, rewrite-from-scratch trigger | 5, as a sub-check |

Open one reference at a time. Do not load all four for a single scene.

## De-AI reviewer output format

Write to `book/critiques/chNN/de-ai-<YYYY-MM-DD>.md`:

```markdown
# De-AI review: ch07/s02 (--detect)
Baseline: book/bible/style.md samples, 2,140 words. Em dash 2.3/1k; not-X-but-Y 0.5/1k;
fragments 6/1k; one-line paras 9%; sentence-length CV 0.52; said-only 91%.
Scene: 1,870 words.

## Counts (per 1,000 words)
| Item | Scene | Baseline/limit | Flag |
|---|---|---|---|
| Em dashes | 9.1 | 2.3 | over |
| Not X but Y (all variants) | 3.7 | 0.5 | over |
| Reflective gerund openers | 2.1 | 0 | over |
| Body-cue emotion phrases | 5.9 | 1.4 | over |
| Said-only ratio | 62% | 91% | over-varied |
| Sentence-length CV | 0.31 | 0.52 | metronomic |
| Dialogue tag adverbs | 0 | 0 | ok |

## Findings
### P0
**[always-fix / label-on-cue] s02 ¶14**
> "Her jaw tightened. She was furious, and underneath the fury, afraid."
Problem: body cue followed by two stacked emotion labels; the cue was doing the work.
Diff: `- Her jaw tightened. She was furious, and underneath the fury, afraid.` /
`+ Her jaw tightened. She counted the tiles behind his head.`

### P1
**[rate-limit / not-X-but-Y] s02 ¶3, ¶9, ¶17, ¶22, ¶31, ¶40, ¶44**
> "It wasn't anger. It was something older."
Problem: 7 in 1,870 words; the negated X was never in play.
Diff (¶3 only; cut the rest): `+ Something older than anger.`

### P2
...

## Verdict
Rewrite from scratch: NO (2 always-fix items, rhythm varies in ¶20–35).
Anchored items not proposed: none.
Continuity (not prose): ¶28 Pekka knows about the ledger; per characters/pekka.md he learns it in ch09.
```

Severity: **P0** = always-fix items, continuity contradictions, conflict dissolved in its own scene, chatbot artifacts. **P1** = rate-limit items more than 2x over baseline, default names, voice bleed between POV characters, corporate Tier 1 vocabulary in narration. **P2** = rate-limit items 1–2x over baseline, sensory monoculture, tag variety. Quote every finding. One diff per finding, proposed, not applied.

Sources: StoryScope (Russell et al. 2026); Tian et al. 2024; Hamilton & Mimno 2026 (name/setting collapse); Russell, Karpinska & Iyyer 2025 (expert detection); TTCW (Chakrabarty et al.); Thennal & Hatzel 2026; Li et al. 2026 (ConStory-Bench); Anthropic avoid-ai-writing skill; Jason Craft "Style Engineering"; noslop; SleuthSayers; AO3 "Spotting AI-Written Fanfiction"; Dreyer; r/aigamedev randomized-replacement note.
