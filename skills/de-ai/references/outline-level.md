Yes/no checks on `book/outline/acts.md` and `book/outline/scenes.yaml` that target the measured narrative-level gaps between AI and human fiction; run at stage 3 before drafting and again at stage 7 on the finished book.

Contents: Why outline first · The checks (1 subplot · 2 moral compromise · 3 non-protagonist resolution · 4 open thread · 5 non-linear move · 6 climax placement · 7 valence · 8 setback timing · 9 chapter shapes · 10 arc shape per thread · 11 epilogue · 12 voice divergence · 13 name list) · Output

## Why outline first

Narrative features alone identify AI fiction at 93% F1 (StoryScope). Every item below is a measured or well-attested gap, and none can be fixed by editing sentences. If the outline fails three or more of these, prose-level de-AI work on the draft is wasted until the outline changes. Agents **propose** outline changes in `book/critiques/`; the author edits `acts.md` and `scenes.yaml`. **NEVER** change a `## ⚓ Anchored` decision; if a check fails because of an anchored choice, report "fails, anchored" and move on.

For each check: answer from the files, quote the evidence (scene ids, beat rows), and if "no", propose the listed change.

## The checks

### 1. Is there at least one subplot with its own want, turn and outcome?
Measured: 79% of AI stories have no subplot vs 57% human.
- [ ] `scenes.yaml` has scenes whose `subplot` field is non-empty, and those scenes include at least one `turn` that is not the main plot's turn.
- [ ] The subplot touches the main plot at least once (a scene where both `beat` and `subplot` are set) and resolves or is deliberately left open on its own schedule, not in the same scene as the climax.
On "no": propose a subplot from the protagonist's Need/Lie in `characters/<slug>.md` or from a secondary character's own want; add 3–5 scenes to `scenes.yaml` spread across acts, with `subplot:` set.

### 2. Is the protagonist morally compromised at least once, without being redeemed in the same chapter?
Measured: morally ambivalent protagonist 38% AI vs 59% human. Claude in particular softens rivalries and resolves conflict early.
- [ ] At least one scene where the protagonist lies, betrays, chooses self-interest, or does harm, with a `value_shift` that goes negative for someone else.
- [ ] No apology or reconciliation scene within the same chapter.
- [ ] The compromise has a consequence later (a scene whose `conflict` references it).
On "no": pick the beat nearest 37% or 62% and have the protagonist take the selfish option; add the consequence scene in act 3.

### 3. Is at least one major resolution not driven by the protagonist?
Measured: protagonist-driven resolution 69% AI vs 46% human.
- [ ] At least one thread (main, subplot, or mystery line) whose resolving scene has a different `pov` or whose `outcome` is caused by another character, chance, institution, weather, or the antagonist's own error.
- [ ] For a mystery: at least one clue or confession arrives through someone other than the detective (`clues.md` "paid" column lists a non-protagonist source).
On "no": reassign one resolution to a secondary character who has their own reason to act; make the protagonist present but not decisive.

### 4. Is at least one thread left open or ambiguous at the end?
Measured: endings of internal understanding/acceptance 47% AI vs 27% human; humans leave more endings ambiguous.
- [ ] `acts.md` "open threads" section lists at least one thread with status `open at end` (not "to be resolved in ch NN").
- [ ] The final scene's `outcome` is not "yes" on every value line. At least one relationship, question, or cost stays unsettled.
- [ ] Genre check: the genre contract may require the central question answered (a mystery must name the killer); the open thread then belongs to a relationship or a cost, not the central question.
On "no": choose the subplot or a secondary relationship and remove its resolving scene; mark it open in `acts.md`.

### 5. Is there at least one non-linear move?
Measured: humans use more time jumps, flashbacks and framing devices; AI stories have tighter causal chains; Claude avoids dream sequences and non-linear structure.
- [ ] At least one scene in `scenes.yaml` whose `time` is earlier than the previous scene's, or a chapter that opens after a gap of weeks or more, or a framing device, or a document/letter/transcript scene.
- [ ] For a mystery: the hidden crime timeline in `timeline.md` surfaces at least once as a scene set in the past, not only as reconstruction in dialogue.
On "no": pick one scene currently told as backstory-in-dialogue and move it to a dramatized scene set at its real time; or open act 2 with a jump forward.

### 6. Does the climax land at or after ~80%?
Measured (Tian et al.): AI stories place the major setback and the climax noticeably earlier, so tension resolves too quickly; suspense gap vs human widens after the midpoint.
- [ ] Sum `word_target` in `scenes.yaml` up to the scene whose `beat` is the climax; divide by total. Target 0.80–0.90.
- [ ] Sum to the "all is lost" / major setback beat. Target around 0.75.
- [ ] Word count after the climax is under ~10% of the total.
On "no": move word budget from act 1 and early act 2 to the stretch between 62% and 85%; add a complication scene before the climax rather than denouement scenes after it.

### 7. Is the emotional valence not uniformly positive?
Measured: GPT-4 stories "homogeneously positive" with flatter arousal; reviewers describe "eerie placidity" in alarming moments.
- [ ] Read `value_shift` down the scene list. At least 40% of scenes end on a negative shift; at least two consecutive scenes end negative somewhere after the midpoint.
- [ ] No act ends on a reconciliation.
- [ ] At least one scene where the protagonist's plan works and the result is worse.
On "no": flip the `outcome` of two mid-act-2 scenes from "yes-but" to "no-and"; cut one consolation scene.

### 8. Are the setbacks not all early?
Same source as check 6; also StoryScope's "flat event escalation" for Claude.
- [ ] List scenes with `outcome: no-and`. At least one falls in each quarter of the book, and the largest (by `value_shift` magnitude) is in the last 25%.
- [ ] Setback magnitude rises: the setback at ~75% costs more than the one at ~37%.
On "no": escalate the late setbacks (raise stakes to the character's Need, not just the Want) and demote an early one to a "yes-but".

### 9. Are chapter shapes not identical?
Practitioner heuristic (no corpus study): AI chapters converge on one length and one shape (scene chunk → reflective coda → one-line ending).
- [ ] Compute the coefficient of variation of chapter word targets (SD / mean) from `scenes.yaml`. Below 0.20 is suspicious; propose at least one chapter under 60% of the mean and one over 140%.
- [ ] Count scenes per chapter. Not all chapters should have the same number.
- [ ] At stage 7, from the manuscript: fraction of chapters ending on a one-sentence paragraph. Above 50% is a finding. Fraction of chapters ending on a sentence with no concrete noun: above 30% is a finding.
- [ ] Not every chapter opens in-scene with weather or a character waking; not every chapter ends on a hook of the same type (question / reveal / threat). List the ending type per chapter and check for runs of three identical.
On "no": merge two short chapters; split one long one at a mid-scene cliff; rewrite three chapter endings to end mid-action or on dialogue.

### 10. Is "Man in Hole" not the default arc shape of every thread?
Measured (Tian et al.): GPT-4 uses "Man in Hole" (fall then rise) in over half its stories; Riches to Rags 1.3% vs 14.6% human; Oedipus (rise–fall–rise–fall) 1.7% vs 9.3%; Rags to Riches 13.0% vs 4.4%.
- [ ] For the main plot and each subplot, sketch the fortune curve from `value_shift`. Name the shape.
- [ ] At least one thread (main or sub) is a fall-ending shape (Riches to Rags, Icarus, or Oedipus), unless the genre contract forbids it.
- [ ] The main plot and the subplot do not have the same shape.
On "no": give the subplot a downward ending; or have the main plot's rise cost the subplot its resolution.

### 11. Is there no epilogue by default?
Measured: Claude "favours epilogues"; Gemini "extended denouements". Human endings cut sooner.
- [ ] `scenes.yaml` has no scene after the climax whose `goal` is "show how everyone is doing" or whose `conflict` is empty.
- [ ] If an epilogue exists, it is anchored by the author in `premise.md` or it introduces a new fact (a cost, an open thread) rather than confirming the ending.
On "no": cut the epilogue; move any needed fact into the last real scene as a single line of dialogue.

### 12. Do POV characters diverge in voice on paper?
Measured: Claude has the most uniform voice across characters; readers of blind tests reported dialogue "indistinguishable between characters".
- [ ] For each `pov` value in `scenes.yaml`, `characters/<slug>.md` has a filled voice block: sentence-length tendency, metaphor domain, 2–3 verbal tics, education/register, NEVER-SAYS list. Two POV characters sharing a metaphor domain is a finding.
- [ ] `style.md` states how narration shifts per POV (tense, distance, vocabulary band), not just dialogue.
- [ ] At stage 7, from the manuscript: take 300 words of narration from each POV character with names removed; the critic agent must be able to assign them. If it cannot, voice has converged.
On "no": fill the voice blocks before drafting; at stage 7, flag the chapters where the assignment failed for a voice-only revision pass.

### 13. Does the name list exist and is it clean?
Measured: Elias 26.5%, Mara 16.7%, Elara 13.1% of 20,000 AI stories; "lighthouse" 51.2%, "keeper" 48.1%; Elias ~900x over contemporary-novel frequency.
- [ ] `style.md` has a name list, and every named character in `scenes.yaml` and `characters/` is on it.
- [ ] No name from the measured or community clusters (Elias, Elara, Mara, Elena, Voss, Vance, Thorne, Aris, Silas, Kael/Kaelen, Seraphina, Blackwood, Marcus, Sarah, Chloe, Lily, Lyra, Aria, Sera, Theron, Orion, Priya-in-London; the validator's list is in `book/bible/style.md`) unless the author anchored it.
- [ ] Names fit the setting's naming conventions and era (`world/*.md`); no two major characters share a first initial; no trade-name characters (the baker, the clockmaker, the keeper) without a name.
- [ ] No place called Eldora, Whispering Woods, or any unplaced "village by the sea".
On "no": generate names from the setting's real naming data (parish records, population registers, the author's own list), not from the model's defaults; replace in `scenes.yaml` and `characters/` before drafting.

## Output

Write to `book/critiques/outline/de-ai-outline-<date>.md`:

```markdown
# De-AI outline check (stage 3)
| # | Check | Yes/No | Evidence | Proposal |
|---|---|---|---|---|
| 1 | Subplot present | No | scenes.yaml: subplot field empty in all 42 scenes | Add Liisa's custody thread, 4 scenes, ch4/9/15/21 |
| 2 | Moral compromise | Yes | s17 Anneli hides the second key; consequence s31 | — |
| ... |
Fails: 5 of 13. Rewrite outline before drafting: YES (3+ fails).
Anchored fails not proposed: #11 (author anchored the epilogue).
```

Three or more "no" at stage 3: recommend revising the outline before any drafting. At stage 7, each "no" becomes a P0 or P1 in `book/critiques/book-pass-<date>.md` with the affected chapters listed.

Sources: StoryScope (Russell et al. 2026) incl. per-model profiles; Tian et al. 2024 (turning points, arc shapes); Hamilton & Mimno 2026 (names); TTCW; Thennal & Hatzel 2026 (homogeneity); Mark Lawrence blind test; practitioner notes on chapter uniformity (AO3 guide, noslop, Anthropic avoid-ai-writing skill).
