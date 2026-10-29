What a de-AI pass must leave alone, how de-AI passes go wrong, and why no detector score is evidence; read at stage 6 before applying any proposed diff.

Contents: Human signals to leave alone · Over-correction failure modes · Em dashes are model-dependent · Detector caveats · Pre-apply checklist

## Human signals to leave alone

Every source that engages seriously (Wikipedia's "Signs of AI writing", the AO3 guide, Dreyer, the Anthropic avoid-ai-writing skill, Rob Burke) says the same thing: the markers are statistical, not diagnostic, and sanding them all off pushes human prose *toward* the AI profile. Over-polishing is itself the most reliable way to make a manuscript read as machine-made.

| Leave alone | Why |
|---|---|
| **Plain emotion words** ("She was angry." "He was frightened of the dark.") | Humans label emotions in 29% of stories, AI in 8%. Replacing a plain word with a clenched jaw moves the text toward the AI profile. |
| **Comma splices, run-ons, sentences starting with And/But** | Natural disfluency; detectors key on regularity. If the author's samples have them, the draft should too. |
| **Digressions, tangents, a character wandering off-topic** | "Nobody does anything surprising in an AI story"; "characters never get distracted". A digression is evidence of a person. |
| **Repeating the clear word** | Synonym cycling is the tell. Three "said", three "door", three "Pekka" in one paragraph are fine if that is the word. |
| **Genuine colon-triples and "turns out"** | Burke found both in his own pre-2023 prose. If the author's samples have the pattern, it is theirs. |
| **Idiosyncratic punctuation in the author's samples** | Dash-heavy, semicolon-heavy, ellipsis-heavy, no-quotation-marks: if `style.md` samples show it, the budget is the sample rate, not a universal cap. |
| **One cliché** | Dreyer: a cliché once is "honest (if tired) prose". Flag it only when it recurs in the manuscript. |
| **An em dash or a fragment that does work** | "Deliberate fragments… if the natural voice uses them, keep them" (avoid-ai-writing). A fragment that overrides the previous sentence is craft. |
| **Sarcasm, understatement, irony, lines read literally** | AI flattens these; a line that only works if read against its surface is a human signal. Do not "clarify" it. |
| **Uneven pacing, a scene that runs long, a short chapter** | Uniformity is the tell. Do not even out chapter lengths for tidiness. |
| **Specific named references** (a real book, song, brand, street) | Humans name real things 47% vs 24%; AI makes vague allusions 72% vs 50%. Never replace a real name with "a song she half remembered". |
| **A strong passage** | "If the original writing is already strong, say so and make only the necessary cuts." Zero findings is a valid result. |

**NEVER** apply a rate-limit fix to a passage that is at or below the author's baseline. **NEVER** replace a plain emotion statement with a body cue.

## Over-correction failure modes

These are the tells of a de-AI pass that went too far (named by noslop as its own over-application failures, plus patterns observed in humanized drafts). A reviewer at stage 6 checks the *revised* text for them.

| Failure mode | What it looks like | Fix |
|---|---|---|
| **Anchor stuffing** | Every sentence crammed with a concrete noun, brand, time stamp, or measurement because "be specific" was over-applied: "At 7:42 on the Fazer-blue kitchen clock she lifted the 1.5-litre Arabia kettle." | Specificity serves the POV character's attention. One anchor per beat; the rest can be plain. |
| **Fragment cosplay** | Fragments. Everywhere. For rhythm. Because long sentences were flagged. | Fragments earn their place by overriding or cutting against the previous sentence. Restore full sentences; vary length through clause structure, not amputation. |
| **Signature closers** | Every scene now ends on a terse concrete image ("The kettle clicked off.") because wisdom lines were cut. The new ending is as uniform as the old one. | Vary ending type across chapters: mid-dialogue, mid-action, a question nobody answers, a plain statement of fact, an image. Check the run of three. |
| **Punchy one-line morals** | The theme statement was cut and replaced with a four-word aphorism in its own paragraph. Still a moral, now shorter. | Cut it. End on the last concrete beat. |
| **Every sentence "ugly"** | Comma splices, typos and awkwardness inserted on purpose to defeat detectors. Reads as a different kind of fake. | Disfluency only where the author's samples have it. Never add errors the author would not make. |
| **Synonym-cycling the fixes** | The reviewer replaced seven "hung in the air" with seven different silence clichés from another row. | Cut, do not swap. When swapping, the replacement sets in `rate-limit.md` include "cut" as an option; use it most. |
| **Dash-to-semicolon transfer** | Em dashes went from 9 to 0; semicolons went from 0 to 9. | Recount all punctuation after the pass; semicolons in dialogue are their own finding. |
| **Body-cue purge** | Every physical reaction deleted, so characters have no bodies at all and the scene is talking heads. | Keep physical action that is specific to the character and the room. Only the stock cue-plus-label pairs go. |
| **Voice flattening** | A character who talks in corporate jargon (by design, per `characters/<slug>.md`) had their vocabulary "fixed". | Vocabulary rules apply to narration. Dialogue follows the character's voice block. Check NEVER-SAYS, not the Tier 1 table. |
| **Removing the surprise** | A deliberate "not X but Y" where X really was the reader's assumption got rewritten as a flat statement, losing the turn. | The AO3 test: if X was live in the reader's mind, the construction is doing work. Keep it and note "kept, assumption live". |

## Em dashes are model-dependent

Russell, Karpinska & Iyyer (2025) found that in their corpus AI text tended to **avoid** dashes and ellipses; the UWA commentary calls em dashes "unreliable" because chatbots differ; a widely shared Tumblr thread says outright that em dashes and repeated words are not the signal. Other practitioners report drafts at 20+ per 1,000 words. Both are true of different models and eras.

- Count em dashes against the author's samples, never against folklore.
- An author whose samples run at 5 per 1,000 words keeps 5 per 1,000 words.
- Do not tell an author "em dashes mean AI". Tell them "this scene has 4x your own rate".

## Detector caveats

A detector score is a number, not a finding. **NEVER** cite a detector percentage as evidence in a critique; quote text.

- Early detectors flagged **61% of essays by non-native English writers** as AI (Liang et al. 2023), nearly 20% of them unanimously; the cause was low perplexity from limited vocabulary variation. The same mechanism flags formulaic genre prose, prolific fanfic writers, and anyone writing plainly.
- Non-expert readers score at chance (true-positive ~57%, false-positive ~52%) with high confidence; Mark Lawrence's blind-test readers were a coin toss and a majority thought a human author's story was AI. Expert heavy-LLM-users reach ~90–99%, by reading structure, not by counting words.
- Perplexity/burstiness scoring is historical; GPTZero abandoned it in 2023 and says "a person could easily write an AI-like sentence by accident".
- Modern detectors (Pangram, GPTZero) report very low false-positive rates on long creative prose, but independent testers see a 2,000-word score jump from 5% to 21% after one sentence change, worse under 2,000 words, and OCR noise producing flags. Vendors advise against scoring short passages at all.
- Style-mimicry (feeding the model the author's samples, which this pipeline does) cuts detection; fiction miss rates of 1–5% in one test. So a low score on a draft from this pipeline is not proof of anything either.
- The Wikipedia AI-cleanup guide: detectors "have high false-positive rates and should never be the sole evidence". The AO3 guide: "unreliable for creative writing"; prolific writers and non-native writers "should not be shamed".
- Surface word-swaps fool neither experts nor modern detectors; structure does both. That is the reason this skill spends most of its checks at outline level.

If an author runs a detector and brings the score: treat it as a prompt to run `--detect`, report density and co-occurrence with quotes, and say explicitly that the score is not a verdict.

## Pre-apply checklist (stage 6, per proposed diff)

- [ ] Is the original at or below the author's baseline for this item? If yes, drop the diff.
- [ ] Does the diff replace a plain emotion word with a body cue? Drop it.
- [ ] Does the diff add a concrete anchor where the POV character would not notice one? Drop it.
- [ ] Does the diff turn a sentence into a fragment for rhythm alone? Drop it.
- [ ] Does the diff change a line of dialogue in a way that breaks the character's voice block or NEVER-SAYS? Drop it.
- [ ] Does the diff replace one cliché with another from the same or a neighbouring row? Cut instead.
- [ ] After all diffs: do three or more consecutive scenes now end the same way? Vary one.
- [ ] After all diffs: recount em dashes, semicolons, fragments, one-line paragraphs. Did a count move from one column to another?
- [ ] Is the passage strong as written? Say so and apply nothing.

Sources: Wikipedia "Signs of AI writing"; AO3 "Spotting AI-Written Fanfiction"; Dreyer "Only shifters pad"; Anthropic avoid-ai-writing skill; Rob Burke; noslop README (over-application modes); Russell, Karpinska & Iyyer 2025; UWA commentary; Liang et al. 2023; GPTZero on perplexity/burstiness; Pangram false-positive notes; Very Fine Print detector test; Epoch AI style-mimicry test; Mark Lawrence blind test; WikiProject AI Cleanup guide; StoryScope (emotion-label and named-reference figures).
