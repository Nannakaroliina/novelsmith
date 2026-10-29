---
name: craft-prose
description: Sentence- and paragraph-level craft for drafting and line editing fiction. Covers psychic distance (Gardner's five levels), filter words, head-hopping, show vs tell done right (R.U.E., Maass's inner/outer/other modes, emotion without stated-feeling flatness or body-cue cliché), specificity and detail selection, sentence rhythm and white space, dialogue subtext and beats, metaphor discipline, scene openings and closings at the line level, Browne & King's self-editing checks, and a line-editor checklist for stages 4 and 5. Use when drafting any scene, line editing, revising prose, or when a user asks about POV, show vs tell, dialogue, sentence rhythm, description, or voice. Does not own the AI-tell catalogue (see de-ai); this skill and de-ai are one layer and must not contradict each other.
user-invocable: false
---

# craft-prose

Applies at stage 4 (draft), stage 5 (critique, line-editor agent), stage 6 (revise). Before drafting, read `book/bible/style.md` for POV/tense, the author's sample passages, rate limits per 1,000 words, and the name list. Style rules in that file and anything under `## ⚓ Anchored` win over defaults here. Reviewers quote evidence and propose diffs; they do not rewrite silently.

## 1. POV and psychic distance

Psychic distance = how far the reader feels from the events. Gardner's ladder, far to close, with original examples:

| Level | Stance | Example |
|---|---|---|
| 1 | Camera far outside; time and place | It was late October in a mining town. A woman left the bus station on foot. |
| 2 | Named, lightly characterised | Marit Lehto had never been fond of bus stations. |
| 3 | Close third, plain feeling | Marit hated bus stations. |
| 4 | Character's own diction leaks in | God, these stations. The same wet-dog reek every single time. |
| 5 | Full immersion, syntax dissolves | Wet dog. Diesel. Somebody's chips going cold on the bench and her name, still, on that list. |

Rules:
- Pick a home level per scene from `style.md` (close third usually sits at 3–4). **MUST** move deliberately: open a scene one or two levels farther out than home, settle in, move closer at the turn, and never jump more than two levels in one sentence without a reason you could name.
- Distance should drift within a scene; a fixed level for pages reads flat. Darwin's test at any sentence: how far in are we, which words put us there, what effect does it have?
- **NEVER** head-hop. One POV character per scene. If another mind is needed, line space and new scene. Test: could this sentence be known by the POV character right now, from where they stand? If not, cut or re-anchor.
- The "camera" test: at level 4–5 the narration is the character's eyes and vocabulary; a sentence that could appear unchanged in another character's scene is not doing POV work.

Filter words (close POV): saw, heard, felt, knew, watched, noticed, realized, decided, wondered, thought, looked, seemed, could see/hear. They put an observer between reader and image.

> Before: She noticed the kitchen light was still on and felt a flicker of unease.
> After: The kitchen light was still on. She had switched it off. She was sure she had.

Filtering is fine when: the act of perceiving is the point ("He made himself look"); a scene-ending beat lands on a realisation; narration is level 1–2 by design; the borderline words (wondered, realized, decided) carry a real decision. Flag density, not single instances. Rate limit lives in `style.md`.

## 2. Show vs tell done right

The rule is not "never tell." Telling is correct for:
- Transitions and summary: leap over time that has no turn in it ("Three days of rain, then the call came").
- Pace: a tell keeps a fast scene fast; a dramatised beat would stall it.
- Emotion the character would plainly know: "She was angry" is honest when the character is; plain emotion naming is a human move, and rigid show-don't-tell produces body-cue clutter (see de-ai). Prefer plain naming over a third clenched jaw.
- Buffering extreme emotion (Maass outer mode): when the feeling is very painful, pull back to action and let the reader supply the feeling.
- Far psychic distance by design.

Flag telling only when it substitutes for a scene that should have been dramatised, or when it follows showing (R.U.E., resist the urge to explain):

> Before: He set the cup down without a word and left. He was furious with her.
> After: He set the cup down without a word and left.

Cron's version of show: show the cause-and-effect chain behind a feeling, not just the feeling. "She was afraid" is weak only if the reader cannot see what she expects to happen next.

Maass's three modes; use all three across a scene, not one:
- Inner: name or narrate the feeling. Works when fresh and when it is the character's own honest read ("She was not sad. She was relieved, and that was worse").
- Outer: imply the feeling through action and choice. Risk: small and "written." Best for extreme emotion.
- Other: provoke in the reader a feeling the character does not share (the character is cheerful while the reader sees the trap).

Core principle: readers feel their own emotions, not the character's. **Action is an opportunity to feel, not a cause of feeling.** Give the reader something to react to; do not instruct the reaction.

Emotion handling that avoids both failures:
- [ ] No "body cue then label" pairs (jaw tightened → "he was angry"). Keep one or the other.
- [ ] No stock body cues (heart pounding, breath held, stomach dropped, chills) unless `style.md` allows the rate.
- [ ] Prefer a specific, character-bound reaction: what she does, says, avoids, or misreads. One flat statement of feeling is better than a cliché.
- [ ] Mixed or contradictory feelings beat single clean ones (relief inside grief; irritation inside love).

## 3. Specificity

- Concrete nouns and specific verbs over generic ones: "a Toyota with one brake light" over "a car"; "limped" over "walked slowly."
- Sensory-oddity rule: one detail per scene the reader would not have predicted (the wrong smell, the thing out of place) does more than five expected ones. Reach beyond sight: temperature, smell, texture, sound.
- Detail must work: it reveals character (what this person notices), bears plot (a clue, a constraint), or applies pressure (the latch that sticks). A detail that does none of these is a list. Le Guin: listing is not describing; only the relevant belongs.
- Filter test: can each detail be justified by the POV character's current desire or fear?
- "3–5 details then move." After three to five, the reader has the room; further description is padding unless the scene is about the room.
- Blocking: keep space active (moving, touching, colliding) rather than inventorying it.

> Before: The office was cluttered, with papers everywhere, old furniture, a window, and a general air of neglect.
> After: Every surface held paper except the chair, which held a cat. The window had been painted shut.

## 4. Rhythm

- Vary sentence length. A run of same-length sentences reads mechanical, whether all short or all long. Read aloud; where the voice flattens, the rhythm has.
- Paragraph to the beat: new paragraph at a shift of speaker, action, or attention. Long narration blocks get broken with paragraphs and the occasional one-liner (Browne & King).
- One-line paragraphs and fragments are budgeted devices: they land only if rare. Default ceiling per 1,000 words comes from `style.md`; absent that, treat more than two one-liners or three fragments per 1,000 words as a flag.
- White space is pace: short paragraphs accelerate, long ones slow. Match the shape to the beat, not to habit.
- Le Guin, crowding and leaping: crowd the sentence with sensation and implication where the scene matters; leap over what does not. What you leave out is more than what you leave in. Cut anything that merely pads, repeats, slows, or impedes.
- King: second draft = first draft minus 10 percent. In stage 6, each scene file should shrink unless the author has asked for expansion. A second draft cannot fix dull storytelling; if the scene is dull, send it back to structure.
- Browne & King: find "as" and "-ing" constructions that yoke two actions ("Pulling on her coat, she opened the door") and rewrite unless simultaneity is real and matters.

## 5. Dialogue

- Subtext: characters rarely say what they mean. The on-the-nose test: if a line states the speaker's feeling, motive, or the scene's theme outright, cut it or bend it sideways (a character who wants to leave talks about the broken kettle).
- Cut-the-first-and-last-line test: remove the first and last line of each exchange. If nothing is lost, keep them cut; openings and closings of dialogue are where greetings, throat-clearing, and summary hide.
- Cut test for any line: remove it; does the scene still work? Necessity test: does it push the story and stay true to this character?
- Three-beat rule: prefer three sentences or fewer per speech. Longer speeches get interrupted, deflected, or broken by action.
- Tags: "said" and "asked," or none when the speaker is clear. **NEVER** stack -ly adverbs on tags or use tags that explain the line ("she snapped angrily"). Count beats around dialogue; cut if choppy.
- Action beats carry attribution and subtext: what the character does while speaking often says more than the line.
- Interruption, deflection, lies: people answer the question they wish they had been asked, change the subject, lie badly or well. A straight question followed by a straight answer is a flag unless the scene needs the information fast.
- **NEVER** stack vocatives. Characters do not use each other's names more than once per exchange, and rarely that.
- Dialect lightly: word choice and rhythm, not phonetic spelling. One or two markers per character, held consistently.
- Voice distinction: vary vocabulary, speed, and sentence shape by character; check against the character's voice and NEVER-SAYS fields in `book/bible/characters/<slug>.md`.
- Exposition in dialogue: hide it inside conflict (one character wants the information, the other withholds it), or start the scene after the news is delivered. "As you know, Bob" (characters telling each other what both know) is banned.

> Before: "As you know, Teemu, the mine closed in 2009 and Father lost his job."
> After: "Don't." / "I didn't say anything." / "You were about to say 2009."

## 6. Metaphor and simile discipline

- A figure must map: the two sides share the property being pointed at, and the property matters here. If the reader has to work out how a thing is like the other, cut it.
- Budget: roughly one figure per page unless `style.md` says otherwise. Stacking two figures in one sentence, or one per sentence in a paragraph, is a flag.
- No stacking: one image at a time. Resolve it before starting another.
- No mixed registers: a figure drawn from one domain (sea) does not get completed in another (machinery). Keep a scene's figures inside the POV character's world and knowledge.
- Literal first. Most sentences want the plain noun. Reserve figures for the moment the scene turns.

## 7. Scene openings and closings, line level

Open on something happening or seen, in the POV character's perception, at a point of change. First sentence should name or imply the POV character, the place, and a want or wrongness within the first paragraph. **NEVER** open on weather, waking, a mirror, a dream, or a block of backstory. Test: delete the first paragraph; if the scene still works, delete it.

Close on action, dialogue, or image. The last line is the line that resonates, so it should be concrete. **NEVER** close on a moral, a summary of what the scene meant, a stated feeling, or a "for now it would have to be enough" cadence. Leave as soon as the scene's goal is reached or lost; unless it is the final scene, leave a question open. Test: delete the last paragraph; if the ending gets stronger, keep it deleted.

> Before (closing): She realised then that trust, once broken, could never be fully mended, and that she would have to live with that.
> After (closing): She put the key back under the mat where he would find it.

## 8. Browne & King self-editing checks (compact)

1. Find sentences that state a trait or emotion; ask whether action already conveys it. Keep one, not both.
2. Scan tags for -ly adverbs and verbs other than "said"; cut dialogue that explains itself.
3. Read aloud; note where the voice changes.
4. Count beats around dialogue; cut if choppy.
5. Interior monologue: is it explanation in disguise? Remove stage directions.
6. Find "as" and "-ing" yokes; rewrite if unneeded.
7. Break long narration with paragraphs and the occasional one-liner.
8. No POV shifts mid-scene; line space and new scene if needed.
9. Repetition: keep the stronger version, cut the weaker.
10. Voice: revise weak passages toward the strong ones in the same chapter.
11. Proportion: is the rest really needed?
12. Introduce characters gradually.
13. Flag "very," "rather," "suddenly," adjective strings, fancy imagery, italics, exclamation points.
14. Condense blow-by-blow description.

## 9. Line-editor checklist

Stage 4: drafter applies to each paragraph before marking a scene `drafted` in `book/outline/scenes.yaml`. Stage 5: line-editor agent applies to `book/manuscript/chNN/sNN.md`, writes findings to `book/critiques/chNN/line-<date>.md` with quoted evidence, proposed diff, severity (P0 breaks POV or sense; P1 weakens the scene; P2 polish). Line findings wait until structural and character critiques for the chapter are resolved. Do not report items that `style.md` explicitly permits.

- [ ] POV: every sentence is knowable by the POV character from where they stand now.
- [ ] Distance: the paragraph's psychic level is nameable, and no sentence jumps more than two levels without reason.
- [ ] Filters: fewer than the `style.md` rate; none where a direct image would do.
- [ ] Explained showing: no sentence restates a feeling or meaning the previous sentence already showed.
- [ ] Emotion: no body-cue-then-label pair; no stock body cue; at least one feeling in the scene is mixed or contradicted.
- [ ] Telling that should be a scene: no summarised event that the outline marks as a turn.
- [ ] Specificity: no generic noun where a specific one would reveal character or bear plot.
- [ ] Detail budget: no more than five descriptive details before an action or line of dialogue.
- [ ] Detail filter: each detail is justified by the POV character's desire, fear, or task.
- [ ] Rhythm: sentence lengths vary within the paragraph; read aloud without flattening.
- [ ] Devices: one-liners and fragments within the `style.md` budget.
- [ ] Dialogue: no line states the speaker's feeling or the theme outright; no greetings or recaps; first and last lines of each exchange survive the cut test.
- [ ] Dialogue mechanics: tags are "said"/"asked"/none; no -ly adverbs; speeches of three beats or fewer unless broken by action.
- [ ] Vocatives and exposition: no repeated names in address; no "As you know" information transfer.
- [ ] Figures: every metaphor or simile maps; at most one per page; no mixed registers.
- [ ] Yokes and fillers: no needless "as"/"-ing" simultaneity; no "very," "rather," "suddenly," exclamation points.
- [ ] Opening: first paragraph cannot be deleted without loss; something is happening or seen.
- [ ] Closing: last line is action, dialogue, or image; nothing moral or summarising after it.
- [ ] Repetition: no word, image, or descriptor recycled within the scene unless deliberate.
- [ ] Length: the revised paragraph is not longer than the draft paragraph unless the author asked for expansion.

Sources: Gardner, The Art of Fiction (psychic distance, filtering); Emma Darwin on psychic distance; Writers in the Storm on filter words; Browne & King, Self-Editing for Fiction Writers; Donald Maass, inner/outer/other modes (Jane Friedman); Lisa Cron, Wired for Story; Palomar Pressbooks on dialogue; Kirkus editors' most common mistakes; Stephen King, On Writing; Le Guin, Steering the Craft (crowding and leaping); Not MFA on setting that drives story; Renée Fountain on agent rejection triggers; StoryScope emotion-naming data via the de-ai research notes.
