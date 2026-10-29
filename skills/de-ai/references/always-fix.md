Items that are wrong regardless of count: fix every instance at stage 4 self-check and flag as P0/P1 at stage 5, because each is a craft failure that humans and models both produce and readers key on.

Contents: 1 Explained subtext · 2 Theme stated in narration · 3 Emotion label on a body cue · 4 Scene-ending wisdom line · 5 Coda overreach · 6 Similes that do not map, stacked metaphors · 7 Chatbot and scaffolding artifacts · 8 Descriptor recycled verbatim · 9 Corporate lexicon in narration · 10 Therapy-speak and philosophical-debate dialogue · 11 Mic-drop closers · 12 Conflict dissolved in its own scene · 13 Default AI names and settings · 14 "As you know" exposition · Quick regex sweep

Rule of use: quote the line, name the item, propose one diff. Each example below is original. "Before" is the pattern; "after" is one acceptable fix, not the only one. Prefer cutting to replacing.

---

## 1. Explained subtext (narrator as therapist)

The narration glosses what a line of dialogue or action "really" means. If the subtext needs explaining, the scene has failed; the fix is in the action, not the gloss.

- [ ] After any line of dialogue, is there a sentence beginning "What she meant was", "He was really saying", "It was her way of", "which was as close as he came to"? Cut it.
- [ ] Does the narrator interpret a gesture ("a gesture that meant she forgave him")? Cut the interpretation; keep the gesture or sharpen it.

Before:
> "The soup's fine," she said, and pushed the bowl an inch away. It was her way of telling him she had already decided to leave.

After:
> "The soup's fine," she said, and pushed the bowl an inch away. He reached for the salt she had not asked for.

## 2. Theme stated in narration

Measured: 77% of AI stories state the theme outright vs 52% human. Any sentence that could be lifted and used as the book's blurb line is a theme statement.

- [ ] Search the scene's last 3 paragraphs and any paragraph following a quiet moment for abstract nouns in subject position (grief, forgiveness, home, memory, truth, love, loss) with a copula or a verb of realisation.
- [ ] If `book/bible/premise.md` lists a controlling idea, grep the manuscript for its key nouns. Any hit in narration is a finding.

Before:
> She understood, finally, that grief was not something you finished but something you carried, and that carrying it was a kind of love.

After:
> She put the second cup back in the cupboard. Then took it out again and used it.

## 3. Emotion label stacked on a body cue

Measured: AI routes emotion through bodily sensation 81% vs 38%, then labels it anyway. Show-then-tell is a two-step pattern: physical cliché, then the emotion noun within one sentence. Keep one half.

- [ ] Pattern: `(jaw|chest|stomach|throat|hands?|breath|heart|shoulders)\b[^.]{0,60}\.\s+[^.]{0,40}\b(anger|angry|fear|afraid|grief|relief|shame|panic|dread|rage|joy)`
- [ ] Decide which half the author would keep. Plain naming ("She was angry") is more human than another clenched jaw (humans name emotions 29% vs 8%). Cutting the cue and keeping the plain word is a valid fix.

Before:
> His stomach dropped. Panic surged through him, cold and absolute.

After (keep the action):
> He read the text again, then put the phone face down on the table.

After (keep the label, plainly):
> He was frightened. He read the text again.

## 4. Scene-ending wisdom line

The "for now, it would have to be enough" family. Practitioners report these "almost always" at section and chapter ends. The reader already has the meaning; the line packages it.

- [ ] Check the final sentence of every scene and every section break for: `(for now|it would have to be enough|would have to do|some (things|wounds|doors)|she (understood|knew|realized) (now|then)|and that was (enough|something)|maybe that was (enough|the point)|it was a start)`.
- [ ] Also flag any closing sentence with no concrete noun.
- [ ] Fix: end on the last concrete action or image. Delete the closer. If the scene then feels unfinished, that is the scene's problem, not the closer's job.

Before:
> He locked the shed and stood a moment in the dark. It wasn't forgiveness. But for now, it would have to be enough.

After:
> He locked the shed. The padlock was stiff and he had to try it twice.

## 5. Coda overreach

The scene reaches its natural end (the turn in `scenes.yaml`) and keeps going for one to four paragraphs explaining what the turn meant, how the character feels about it, and what it foreshadows.

- [ ] Find the sentence where the scene's `turn` lands. Count paragraphs after it. More than one paragraph of interiority with no new action or information is overreach.
- [ ] Fix: cut to the last concrete beat after the turn. Move any genuinely needed reflection to the opening of the next scene, where it can be interrupted.

Before:
> [turn: she finds the second key] She turned it over in her palm. So he had lied, then, about all of it. She thought of the summers at the lake, the way he had taught her to gut a fish, and wondered which of those memories were real. Perhaps none of them. Perhaps that was what it meant to love a liar.

After:
> [turn: she finds the second key] She turned it over in her palm. It was cut for the same lock as hers.

## 6. Similes that do not map; stacked metaphors

Expert judges on TTCW: figurative language "overwrought, confusing, nonsensical". Two tests: (a) can the reader picture the vehicle, and (b) does the vehicle share the property the sentence needs.

- [ ] For every `like a|like the|as if|as though`, state in one clause what property is being transferred. If you cannot, cut.
- [ ] Two metaphors in one sentence, or a metaphor whose vehicle is itself a metaphor ("shovelled dirt over its echo"), are stacked. Keep one.
- [ ] Concept-plus-sense pairings ("sorrow and the taste of metal", "silence like wet cloth") are the predictable version; prefer a comparison from the POV character's own metaphor domain in `characters/<slug>.md`.
- [ ] Similes should compare down (strange to ordinary), not up (ordinary to grand).

Before:
> The silence pressed on the room like wet cloth, a bruise of quiet that shovelled dirt over whatever he had meant to say.

After:
> Nobody said anything. The fridge clicked on.

## 7. Chatbot and scaffolding artifacts

Anything addressed to a user, or leaked from a prompt, outline or reasoning chain. Always P0.

- [ ] `(Certainly|Absolutely|Great question|I hope this helps|Let me know|Here is|Here's a|In this (scene|chapter)|As an AI|Note:|\[end here\]|\[beat\]|\[turn\]|TODO|placeholder)`.
- [ ] Outline vocabulary surfacing in prose: "the inciting incident", "her character arc", "the midpoint", "rising tension".
- [ ] Title inflation ("Dr.", "Prof.", "Detective Inspector" on every mention) is the same leak in miniature; humans drop titles after first use.

Before:
> Here is the revised scene. Elina stepped into the kitchen, her arc of reluctant trust beginning as she saw the note.

After:
> Elina stepped into the kitchen and saw the note.

## 8. Descriptor recycled verbatim

A trait restated word-for-word across scenes ("her too-careful hands", "the scar through his eyebrow") because the model is re-reading its own context. Humans vary or drop it; readers notice by the third repeat.

- [ ] Grep the chapter and the previous two for any 3+-word descriptive phrase attached to a named character. Two verbatim hits in one chapter, or three in the book, is a finding.
- [ ] Fix: cut all but the first. If the trait matters later, show it doing something (the scar catches the light when he lies), do not restate it.

Before (ch3 and ch5):
> Marja, with her too-careful hands, set the cup down.
> Marja set the cup down with her too-careful hands.

After (ch5):
> Marja set the cup down. It did not clink.

## 9. Corporate and business lexicon in narration

Two lexicons exist. The "delve / tapestry / testament / underscore / leverage / navigate the complexities / foster" set belongs to reports and press releases and is nearly always an error inside fiction narration. The full tiered tables live in the Anthropic `avoid-ai-writing` skill; do not reproduce them. Run its Tier 1 list over narration; in dialogue, treat a hit as a voice break unless the character's `voice` field says they talk like a consultant.

- [ ] Any Tier 1 hit in narration: P1.
- [ ] Also flag copula avoidance in narration ("the room boasted", "the window served as") and "-ing" participial pseudo-analysis ("highlighting her isolation").

Before:
> The kitchen was a testament to her mother's meticulous nature, showcasing decades of careful habit.

After:
> Her mother's kitchen. Every jar labelled in the same blue pen, forty years of it.

## 10. Therapy-speak and philosophical-debate dialogue

Measured: dialogue serves philosophical debate in 59% of AI stories vs 34% human. Characters diagnose their own emotions, name needs, validate each other, and reach clinical resolution. Real people talk around things, interrupt, deflect, lie.

- [ ] Dialogue regex: `I (feel|felt) (like|that|as if)|I (need|needed) you to|what I'm hearing|I (hear|see) (you|that)|that's (valid|fair)|I appreciate you|hold space|boundar(y|ies)|process(ing)? (this|that|it)|I'm not (ready|able) to|let me be honest|the truth is|at the end of the day`.
- [ ] Any exchange where both speakers state their feelings accurately and the other accepts the statement: rewrite so at least one party misreads, deflects, or withholds.
- [ ] Debates about meaning, memory, justice, or the nature of love that run more than four lines with no concrete stake in the scene: cut to the stake or move to subtext.
- [ ] Check each speaker against `characters/<slug>.md` NEVER-SAYS.

Before:
> "I think what I'm feeling is abandonment," she said. "And I need you to hear that without getting defensive."
> "I hear you. That's valid. I was scared too."

After:
> "You could have called."
> "The reception's bad up there."
> "It's a landline, Jussi."

## 11. Mic-drop closers

A character ends the exchange with a sweeping, quotable line that nobody answers, and the scene cuts. Nearly every AI scene ends this way; human scenes let the other person roll their eyes, change the subject, or get the last word by accident.

- [ ] If the last line of dialogue in a scene is a complete aphorism (no proper noun, no concrete object, present tense, under 15 words), it is a mic-drop.
- [ ] Fix: give the other character a reply that deflates or ignores it, or end on an action instead.

Before:
> "Some debts aren't paid in money, Anneli. They're paid in who you become."
> He left. She did not follow.

After:
> "Some debts aren't paid in money, Anneli."
> "Lock the door on your way out. It sticks."

## 12. Conflict dissolved in the scene that introduced it

The argument resolves, the rival softens, the misunderstanding clears, all before the scene ends. Measured: AI setbacks and climaxes land early and tension resolves too quickly; practitioners had to instruct the model explicitly not to resolve conflicts. **NEVER** resolve tension in the scene that raised it unless `scenes.yaml` outcome for that scene is an unqualified "yes".

- [ ] Compare the scene's `conflict` and `outcome` in `scenes.yaml`. If the outcome is "yes-but" or "no-and", check the last 20% of the scene for apology, reconciliation, mutual understanding, or the problem turning out to be minor.
- [ ] Fix: cut the reconciliation. Let the scene end with the conflict live. Carry it to the open-threads list in `acts.md`.

Before:
> "You went through my desk."
> "I was looking for the invoice. I'm sorry, I should have asked." She exhaled. "It's fine. I overreacted."

After:
> "You went through my desk."
> "I was looking for the invoice."
> She picked up her keys. The invoice had been on the fridge for a week.

## 13. Default AI names and settings

Measured across 20,000 stories from four models: Elias 26.5%, Mara 16.7%, Elara 13.1%; "lighthouse" in 51.2% and "keeper" in 48.1%; clockmaker, baker, fisherman, librarian, mayor, conductor each 1.9–6.6%; 56% of Claude's stories were titled "The Lighthouse Keeper's Secret". Elias is roughly 900x more frequent than in contemporary novels. Community-reported clusters: Elara/Elena Voss, Elias Vance/Thorne, Aris Thorne, Silas, Kael/Kaelen, Seraphina, Blackwood, Chloe, Lily, Marcus, Sarah, Priya (London), "Whispering Woods", "Eldora", Erebus (as an AI or project name).

- [ ] Every named character must appear in the name list in `book/bible/style.md`. A name not on the list is a P1 regardless of what it is.
- [ ] Any name from the measured or community lists above, in any spelling, is P1 even if on the list; ask the author to confirm it is deliberate.
- [ ] Two characters sharing a name "by family tradition" is a model artifact; flag.
- [ ] Settings and trades: lighthouse, keeper, clockmaker, blacksmith, innkeeper, "vaguely pre-contemporary" village with no year, no brand, no phone. Flag unless the premise is historical.
- [ ] "Light" as a recurring noun (measured 3.2 uses per story): count per scene.

Before:
> Elias Thorne had kept the lighthouse at Eldora for eleven years.

After:
> Teuvo had run the pumping station at Kuolio since the co-op sold it in 2009.

## 14. "As you know" exposition

Characters tell each other things both already know so the reader can hear it.

- [ ] Dialogue regex: `as you (know|remember|recall|well know)|you know as well as I|need I remind you|as I('ve| have) (told|said)|you'll recall`.
- [ ] Also flag any speech over 60 words that summarises past events to someone who was present.
- [ ] Fix: cut, or give one party a reason not to know (new arrival, memory loss, lying), or move to narration in the POV character's voice.

Before:
> "As you know, Father left the farm to both of us when he died in the spring of 2019, on condition we never sell."

After:
> "Read the will again. The bit about selling."

---

## Quick regex sweep (run first, then read by hand)

| Item | Pattern (case-insensitive) |
|---|---|
| Wisdom closer | `(for now|would have to be enough|would have to do|understood now|knew then|maybe that was enough|it was a start)\.?$` |
| Label on cue | `(jaw|chest|stomach|throat|breath|heart)[^.]{0,60}\.\s+[^.]{0,40}(anger|angry|fear|afraid|grief|relief|shame|panic|dread|rage)` |
| Therapy-speak | `I (feel|felt) (like|that)|I need you to|what I'm hearing|that's (valid|fair)|hold space|process (this|that)` |
| As-you-know | `as you (know|remember|recall)|need I remind you|you'll recall` |
| Chatbot | `(certainly|absolutely|great question|I hope this helps|here is the|in this scene)` |
| Default names | `\b(Elias|Elara|Mara|Voss|Thorne|Vance|Kael|Kaelen|Seraphina|Blackwood|Silas|Eldora)\b|lighthouse|keeper` |
| Scaffolding | `\[(beat|turn|end here|todo)\]|inciting incident|character arc|midpoint` |

A regex hit is evidence to quote, not a finding by itself; read the paragraph before filing.

Sources: StoryScope; TTCW; Hamilton & Mimno 2026; Read Max "Who is Elara Voss"; SleuthSayers; Jason Craft "Style Engineering"; Dan Guru; Wayline; AO3 guide; agentic-novel ban list; LessWrong "AI can't write good fiction"; Anthropic avoid-ai-writing skill.
