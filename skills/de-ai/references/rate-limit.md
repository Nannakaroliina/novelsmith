Items that are ordinary craft once and a fingerprint in density: count them per 1,000 words, compare to the author's own baseline, and fix only the excess.

Contents: How budgets work · Table of budgets · Item notes with patterns and replacement sets (1 em dashes · 2 not-X-but-Y · 3 tricolons · 4 fragments · 5 one-line paragraphs · 6 reflective gerund openers · 7 participial tails · 8 un- adjective clusters · 9 "the kind of X that" · 10 synonym cycling · 11 metronomic sentence length · 12 body-cliché emotion · 13 "hung in the air" · 14 ozone and unnamed smells · 15 sensory checklists · 16 dialogue tags · 17 vocative stacking · 18 rhetorical questions · 19 "a beat" family · 20 anaphora) · Replacement discipline

## How budgets work

- **MUST** read the author's samples in `book/bible/style.md` first and compute the author's own rate for each row. That rate replaces the budget column. The budgets below are **practitioner defaults for a book with no samples yet**, assembled from the avoid-ai-writing skill, noslop, the agentic-novel ban list and r/aigamedev; none has been validated against a human-fiction corpus.
- A finding is the scene's count **above** the baseline, not the raw count. Report both.
- Severity: 1–2x over baseline = P2; more than 2x = P1. Zero over = no finding, even if the raw number looks high.
- Patterns are regex-friendly starting points for a first sweep; they over-match. Read before filing.
- "Replace with" entries are sets of 3–4. **Draw at random and vary across findings**; using the first entry every time builds a new fingerprint. Cutting the sentence is always in the set.

## Table of budgets (per 1,000 words of manuscript unless stated)

| # | Item | Default budget | Reported AI rate when unconstrained |
|---|---|---|---|
| 1 | Em dashes (— or --) | 1–2 | 20+ |
| 2 | "Not X but Y" and variants | 1 per scene | up to 20 |
| 3 | Tricolons (A, B, and C) | 1 per scene | default rhythm |
| 4 | Sentence fragments | 6 | stacked for drama |
| 5 | One-line paragraphs | 2–3 per page (~300 words) | every dramatic beat |
| 6 | Reflective gerund openers | 1 per scene | "suspicious frequency" |
| 7 | Participial tails ("…, reflecting…") | 2 | one per paragraph |
| 8 | un- adjectives (unspoken, unreadable…) | 1 | clustered on non-POV characters |
| 9 | "the kind of X that" / "the type of" | 1 per scene | frequent |
| 10 | Synonym cycling for one referent | 0 chains | thesaurus rotation |
| 11 | Sentence-length CV | ≥ 0.45 | ~0.3 (15–25 words each) |
| 12 | Body-cliché emotion phrases | 2 | 5–10 |
| 13 | "hung in the air" family | 0–1 per chapter | per scene |
| 14 | Ozone / unnamed smells | 0 ozone; smells named and local | 82% of AI stories use smell |
| 15 | Sensory checklist paragraphs | 0 | preset "vivid sensory detail" |
| 16 | Dialogue tags other than said/asked | ≤ 10% of tags; 0 adverb tags | murmured/breathed/rasped |
| 17 | Vocatives in dialogue | 1 per exchange | every line |
| 18 | Rhetorical questions in narration | 1 per scene | stacked ("And now? Now…") |
| 19 | "a beat" / "something shifted" / "let out a breath" | 0–1 per chapter | per scene |
| 20 | Anaphora runs (3+ sentences same opener) | 1 per chapter | per scene |

## Item notes

### 1. Em dashes
Pattern: `—|--|\s-\s`. Count spaced and closed forms separately; a mix in one manuscript is itself odd.
Caveat: in Russell et al.'s corpus AI text *avoided* dashes, so this is model-dependent; see `do-not-overcorrect.md`. If the author's samples are dash-heavy, the budget is the author's rate.
Replace with (pick one at random): comma; full stop and new sentence; parentheses; cut the aside entirely.

### 2. "Not X but Y" and its variants
Only a tell when the negated X was never a live possibility for the reader (AO3 test: "corrects no real assumption"). Variants to count together:
1. `not X, but Y` / `not X—Y`
2. `not only X but (also) Y`
3. `it's not (just|about) X, it's (about) Y`
4. `That's not X. That's Y.`
5. `no X, no Y, just Z`
6. `not because X, but because Y`
7. `not by X-ing, but by Y-ing`
8. `He didn't X. He Y-ed.` / `She doesn't X. No, she Y-s.`
9. `And the X? Y.` / `The result? Y.` (rhetorical echo)
10. `X rather than Y`
11. `less X than Y` / `more X than Y` used as a reframe
Pattern (first sweep): `\bnot\b[^.]{0,40}\b(but|just|—)\b|n't [^.]{0,30}\. (He|She|It|They) \w+ed\b|\? [A-Z]\w+\.`
Replace with: state Y directly; state X as true and let Y follow in a new sentence; cut X entirely; keep only when X was genuinely in play (then note "kept, assumption live").

### 3. Tricolons
Pattern: `\w+, \w+,? and \w+` (adjective or noun triples); also three parallel short sentences or three fragments ("Focused. Aligned. Measurable.").
Replace with: two items; four items; one item expanded into a clause; cut to the strongest.

### 4. Sentence fragments
Count sentences with no finite verb. Fragments that override or correct the previous sentence are craft; stacks of two or more in a row for drama ("Waiting. Listening.") are the tell.
Pattern (rough): sentences under 4 words with no verb; consecutive fragments.
Replace with: join to the previous sentence; give it a verb; cut.

### 5. One-line paragraphs
Count paragraphs of one sentence. Human prose uses them; AI uses them at every dramatic beat and for every mic-drop. Also check that chapter endings are not *all* one-line paragraphs (see `outline-level.md`).
Replace with: merge into the preceding paragraph; expand with one concrete action; cut.

### 6. Reflective gerund openers
"Watching him leave, she realized…", "Turning from the window, he wondered…", "Standing there, she thought about…"
Pattern: `^(Watching|Turning|Standing|Looking|Sitting|Staring|Listening|Holding|Walking)[^,]{0,40}, (he|she|they) (realized|realised|wondered|thought|understood|knew|felt)`
Replace with: the action as its own sentence, then the thought as dialogue or omitted; the thought as a plain declarative; cut the thought and keep the action.

### 7. Participial tails
A sentence that ends with a present participle adding significance: "…, highlighting how far they had come." Stronger tell when the subject is inanimate ("The rain fell, mirroring her mood").
Pattern: `, (reflecting|highlighting|underscoring|mirroring|emphasizing|echoing|revealing|betraying|hinting|signalling|signaling)\b[^.]*\.$`
Replace with: full stop before the participle and cut it; new sentence with a concrete subject; cut.

### 8. un- adjective clusters
unspoken, unnameable, unreadable, undeniable, unnamed, unbidden, unfamiliar, unmistakable, unflinching. Often attached to a non-POV character's expression, which the POV character cannot read anyway.
Pattern: `\bun(spoken|nameable|readable|deniable|named|bidden|mistakable|flinching|familiar|settling)\b`
Replace with: name the thing; say what the POV character actually saw; cut the adjective.

### 9. "the kind of X that…"
Pattern: `the (kind|sort|type) of \w+ (that|who|which)`
Replace with: the specific X; cut the frame and keep the description; cut.

### 10. Synonym cycling
One referent rotated through synonyms to avoid repetition: "the detective… the investigator… the older woman… the veteran officer". Humans repeat the name or the clearest word.
Check: list the noun phrases used for each named character and each key object in the scene. A chain of three or more distinct epithets for one referent in one scene is a finding.
Replace with: the name; the pronoun; the one clear common noun. (Not a random pick: use the clearest.)

### 11. Metronomic sentence length
Compute mean and standard deviation of words per sentence over the scene; coefficient of variation = SD / mean. Human narrative prose typically lands above 0.45; unconstrained AI prose often sits near 0.3 with most sentences 15–25 words. Also check the paragraph level: paragraphs all 3–5 sentences is the same tell.
Fix: not word-swaps. Find the three longest sentences and let one run longer; find a 15-word sentence that carries a shock and cut it to four words; let one paragraph be a single line and one run half a page. Do not do this uniformly or you get a new metronome.

### 12. Body-cliché emotion phrases
Count hits on: jaw (clenched|tightened|set), fist(s) clenched, chest tightened, stomach (dropped|twisted|churned), heart (pounded|hammered|raced) in (his|her) chest, breath (hitched|caught), let out a breath (he|she) (didn't know|hadn't realized) (he|she) was holding, throat tightened, a chill (ran|crept) (up|down), hands trembled, gaze (flicked|shifted|softened), expression darkened, eyes widened, furrowed brow, squared (his|her) shoulders, the smile didn't reach (his|her) eyes, something cold (settled|crawled|spread), a wave of X washed over, a pang of, a flicker of X, a surge of, despite (herself|himself), the ghost of a smile.
Note: these are human clichés produced at above-human rates; Dreyer found the breath line in dozens of human books. The budget is the author's rate.
Replace with: a plain emotion word ("She was afraid", measured as *more* human); an action specific to this character and this room; a line of dialogue that deflects; cut.

### 13. "hung in the air" family
"the words hung in the air", "the question sat between them", "silence stretched", "the silence was thick/heavy", "the air was thick with", "hit like a physical blow", "landed like".
Pattern: `(hung|sat|lingered) (in the air|between them)|silence (stretched|hung|settled|was (thick|heavy))|the air was thick|like a (physical )?blow|landed like`
Replace with: "Silence." as its own line; the next concrete thing anyone did; the next line of dialogue with no gap described; cut.

### 14. Ozone and unnamed smells
Ozone as the default smell of magic, storms, electricity, danger; "it smelled of [real thing] and [abstraction]" ("of woodsmoke and regret"). AI stories use smell imagery in 82% of cases vs 57% human, so smell is not a free authenticity token.
Pattern: `ozone|smell(ed|s)? of [^.]* and (something|regret|loss|memory|fear|hope|home)`
Replace with: one smell named from the actual location in `book/bible/world/` (hot solder, wet concrete, diesel, reindeer hide, cold coffee); no smell at all; a sound instead.

### 15. Sensory checklists
A paragraph that ticks sight, sound, smell, touch, taste in order because a prompt said "vivid sensory detail". Reads as inventory.
Check: any paragraph with three or more senses and no character action.
Replace with: one or two senses per scene, chosen for what this POV character would notice; one concrete non-visual detail drawn from the location; cut the catalogue.

### 16. Dialogue tags
Count tag verbs. Tags other than said/asked (murmured, breathed, exhaled, rasped, offered, mused, pondered, growled) above ~10% of all tags is over-variation; any adverb on a tag (angrily, softly, nervously, bitterly, wearily) is a finding.
Pattern: `" (he|she|they|\w+) (murmured|breathed|exhaled|rasped|offered|mused|pondered|growled|hissed|purred|intoned)|" (he|she|they|\w+) \w+ed \w+ly\b`
Replace with: said; an action beat and no tag; no tag (two-person exchange already established); cut the line.

### 17. Vocative stacking
Characters say each other's names in nearly every line ("I know, Anneli." "Do you, Jussi?"). Humans use a name in dialogue to get attention, to threaten, or to be tender, roughly once per exchange.
Pattern: count `, [A-Z]\w+[.?!"]` and `"[A-Z]\w+,` inside quoted lines.
Replace with: cut the name; replace with "you" or nothing; keep only the one use that carries pressure.

### 18. Rhetorical questions in narration
"What had she expected?", "And now? Now there was nothing.", "Wasn't that the point?" Stall before the point, or stage interiority.
Pattern: `\?\s*(And|Now|Maybe|Perhaps|Or)\b|^(What|Why|How|Wasn't|Hadn't|Didn't) [^?]{0,60}\?$` in non-dialogue lines.
Replace with: the answer as a statement; cut; move to dialogue where another character can refuse to answer.

### 19. "a beat" / "something shifted" / "let out a breath" family
"A beat passed." "Something shifted in his expression." "Something unreadable crossed her face." "He let out a breath." "For what felt like an eternity." "A long moment."
Pattern: `a beat( passed)?|something (shifted|changed|unreadable|flickered)|let out a (breath|sigh)|for what felt like|a long moment|the moment stretched`
Replace with: the specific thing that changed (he put the cup down); a line of dialogue; nothing (cut the pause and let the next line follow); a concrete time ("She counted to four").

### 20. Anaphora runs
Three or more consecutive sentences or clauses opening with the same word for rhythm ("She had loved him. She had waited. She had…"). Fine once per chapter as a deliberate device; a tell as a default.
Pattern: three consecutive sentences with identical first two words.
Replace with: vary two of the three openers; collapse into one sentence with a list; keep one and cut two.

## Replacement discipline

1. Before replacing, try cutting. Most rate-limited items are padding.
2. When replacing, pick from the item's set at random and record which option you used in the critique, so the author can see you did not use the same fix seven times.
3. Never replace a cliché with a cliché from another row (e.g. "hung in the air" → "a beat passed").
4. After the pass, recount. A scene can go from 9 em dashes to 0 em dashes and 9 semicolons; semicolons in dialogue are a finding of their own.
5. If the scene is more than 2x over baseline on four or more rows, stop patching and recommend a rewrite from scratch (see SKILL.md).

Sources: Anthropic avoid-ai-writing skill; noslop; agentic-novel ban list; r/aigamedev prompt notes; Jason Craft "Style Engineering"; AO3 "Spotting AI-Written Fanfiction"; SleuthSayers; Wikipedia "Signs of AI writing"; humanize DETAILED_PATTERNS negation catalogue; Dreyer; Rob Burke (per-author baseline); r/SillyTavernAI ozone thread; StoryScope smell figures.
