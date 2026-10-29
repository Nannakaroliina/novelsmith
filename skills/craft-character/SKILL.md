---
name: craft-character
description: Building and auditing novel characters — the arc engine (Want/Need, Lie/Truth, Ghost, misbelief), protagonist audit against the character sheets in book/bible/characters/, antagonist design, supporting-cast orchestration, agency and motivation, distinct dialogue voice with NEVER-SAYS lists, setting as pressure on character, and knowledge-ledger continuity. Use when creating or revising characters, character sheets, arcs, antagonists, cast lists, motivation, or dialogue voice, and when a reviewer checks whether a character is consistent, has agency, or earns their ending (stage 2 bible, stage 5 critique).
user-invocable: false
---

# Character craft

Characters are the argument of the book made flesh: the protagonist's Lie is the counter-idea, the Truth is the controlling idea, and the antagonist is the road the protagonist could take. Every rule below is a test you can run against `book/bible/characters/<slug>.md`, `book/outline/acts.md` or a scene file. Structure (where the beats sit and why) lives in `craft-structure`; this skill only names the 25/50/75/climax beats as the points where an arc attaches.

## 1. The arc engine

One vocabulary, four sources, same machine. Fill these for every POV character; fill Want, Lie and function for everyone else.

| Field | Definition | Test |
|---|---|---|
| **Want** | Conscious, external, concrete pursuit. Can be won or lost on the page. | Can you name the object/outcome in ≤ 6 words and the scene where it is decided? |
| **Need** | Unconscious inner change that would actually fix the character's life. | Is the Need the thing that makes the Want *hard* to get (Cron)? If the Want is easy, the Need is wrong. |
| **Lie** (Weiland) / **misbelief** (Cron) | A false belief about self or world, learned from the Ghost, that the character acts on as if true. | Can you write it as a sentence the character would never say aloud but always obeys? Does it equal the book's counter-idea in `premise.md`? |
| **Truth** | What the character learns (positive arc) or already holds and proves (flat arc). | Does it equal the controlling idea in `premise.md`? |
| **Ghost** / wound | The past event that taught the Lie. One event, specific, with a date. | Could you write Cron's **origin scene** (~2,000 words, first person): the healthy belief that existed *before*, the loss, and the meaning the character made of it? If not, the Ghost is a label, not a wound. |
| **Weakness and need** (Truby) | Split the Need in two: **psychological** need (hurts only the self) and **moral** need (hurts others). | Name at least one person the character damages because of the weakness in Act 1. A protagonist with only a psychological need reads as a victim; with neither, as perfect. |
| **Three dimensions** (Egri) | Physiological (body, age, health), sociological (class, work, money, family, faith), psychological (temperament, ambitions, frustrations, complexes). | Each dimension supplies at least one concrete detail that shows up on the page and at least one that constrains a choice. |

Cron's three **crossroads**: before drafting, list three past moments (post-Ghost, pre-story) where the misbelief was reinforced because obeying it seemed to work. These feed flashback-free backstory in dialogue and interiority.

Egri's **unity of opposites**: the protagonist and antagonist must be bound so tightly (blood, law, love, shared crime, same small town) that neither can walk away without destroying themselves. If either side could simply leave, the conflict is static. Write the bond in one line on both sheets.

### Arc types and attachment points

| Arc | Opening (0–5 %) | ~25 % (commitment) | ~50 % (midpoint) | ~75 % (low point) | Climax (~85–90 %) |
|---|---|---|---|---|---|
| **Positive change** | Lives under the Lie; it appears to work | Commits to the Want in a way that cannot be undone; the Lie is first challenged | Sees Lie and Truth side by side for the first time, often via a false victory | The Lie's last defence fails; "a cherished lie dies"; must choose | Acts on the Truth at cost; Want may be lost or transformed |
| **Flat** | Already holds the Truth; the world does not | Commits to the Want; world pushes the Lie at them | Tempted hardest to adopt the Lie | Holding the Truth costs the most it ever will | Proves the Truth; changes others (the arc belongs to the cast) |
| **Negative: disillusionment** | Believes a comforting Lie | Commits | Glimpses the harsh Truth | Truth confirmed; comfort gone | Accepts the Truth; ending sadder but wiser |
| **Negative: fall** | Believes a Lie; some Truth within reach | Commits to the wrong Want | Rejects the Truth when offered | Doubles down | Clings to the Lie; destroyed by it |
| **Negative: corruption** | Holds the Truth | Tempted; commits anyway | Trades Truth for a stronger Lie | Last chance to turn back, refused | Embraces the Lie; "wins" the Want, loses the self |

Rules:
- **MUST** mark which arc type each POV character runs in `characters/<slug>.md` before outlining. Reviewers test against the chosen type, not against positive change by default.
- A negative arc or flat arc is not a defect. A reviewer who flags "protagonist never changes" on a declared flat arc is wrong; the question is whether the *cast* changes around them.
- Seven-Point rule: the state at the hook is the opposite of the state at the resolution. Write both states in one line each on the sheet; if they match, there is no arc.
- Late Act 2 may include a **misleading victory** where Want and Need seem compatible; the 75 % beat proves they are not.

## 2. Protagonist audit (stage 2, re-run at stage 5)

Fill this table from `book/bible/characters/<slug>.md` and `book/outline/acts.md`. One line per cell. **Any blank is a structural gap, not a style note**: report it as P0 at stage 2, P1 at stage 5.

| Field | Source file | Value |
|---|---|---|
| Want | characters/<slug>.md | |
| Need | characters/<slug>.md | |
| Lie | characters/<slug>.md | |
| Truth | characters/<slug>.md | |
| Ghost (event + date) | characters/<slug>.md | |
| Moral need (who they hurt) | characters/<slug>.md | |
| Arc type | characters/<slug>.md | |
| Hook state → resolution state | characters/<slug>.md | |
| What they do at ~25 % that cannot be undone | acts.md | |
| What they see at ~50 % that separates Lie from Truth | acts.md | |
| What dies at ~75 % | acts.md | |
| The climax choice that proves the arc (and what it costs) | acts.md | |
| Unity of opposites with antagonist | characters/<slug>.md | |

Cross-checks:
- [ ] Lie == counter-idea in `premise.md`; Truth == controlling idea. If not, either the premise or the character is wrong. Say which and propose the smaller change.
- [ ] The climax choice is available *only* because of the Truth learned. If a character who had not changed could make the same choice, the arc is decorative.
- [ ] The climax choice costs something named. A choice with no price is not a choice.
- [ ] Cron's plot-test: does the central problem confront the misbelief head-on, create a real dilemma, matter emotionally, and support several escalating scenes? Four yeses or rework the problem.
- **NEVER** change fields under `## ⚓ Anchored` in `premise.md` or a character sheet. If an anchored field makes the audit fail, report the conflict and stop.

## 3. Antagonist design

The antagonist is a structural part, not a mood. Sheet fields and tests:

- [ ] **Same object.** Write the antagonist's Want. It must be the same object or outcome the protagonist wants, or mutually exclusive with it (Truby: find the opponent by asking who most wants to stop *this specific goal*). "Generally evil" or "wants chaos" fails.
- [ ] **Equal strength** (Egri). List the antagonist's resources (power, knowledge, allies, will) against the protagonist's. The antagonist must be ahead on at least two until the climax.
- [ ] **Mirror.** State in one line the comparable choice the antagonist faced earlier and the opposite answer they gave. The antagonist "represents the path the protagonist could take but must resist": they embody the Lie or its logical end. If the protagonist's Lie is "control keeps people safe", the antagonist is what total control looks like.
- [ ] **Articulate.** Write two to four lines of the antagonist's case in their own voice. A reader should be able to agree with it for a moment. If you cannot write it, the theme is one-sided.
- [ ] **On the page at the pinch points.** The antagonist's force must be *seen or felt* in a scene near ~37 % and in a full scene near ~62 %, not reported. A cutaway to the antagonist is acceptable at 37 %; at 62 % the reader must witness their "nature, power, and essence". Cite scene ids from `scenes.yaml`.
- [ ] **Not necessarily a villain.** A rival, a parent, an institution, or a well-meaning ally can be the antagonist if they compete for the object and force change.
- [ ] Mystery books: the antagonist is usually the culprit; their sheet also carries means/motive/opportunity/lie/secret and their entries in `clues.md` and the hidden crime timeline.

Two failure poles, both reportable:

| Pole | Symptom | Fix |
|---|---|---|
| **Misunderstood villain** | The antagonist's case is so sympathetic that the climax feels like bullying; their harm is explained away; the reader is told to pity them | Keep the case, restore the harm: show one irreversible thing they did to someone the reader cares about, before the climax |
| **Evil for its own sake** | Cruelty without a Want; monologues about power; no bond with the protagonist | Give them the same object, a Ghost of their own, and a unity-of-opposites bond |

## 4. Supporting cast

**Function first.** Every named character gets one primary function on the sheet:

| Function | What they do | Typical beat |
|---|---|---|
| **Mirror** | Faces the protagonist's dilemma and chooses differently (B-story partner, the friend who already learned the Truth, the one who already fell) | Carries Theme Stated near ~5 %; "helps the hero change" |
| **Contrast** (Egri orchestration) | Opposite temperament or dimension so each defines the other (reckless/cautious, believer/sceptic, local/outsider) | Every shared scene |
| **Pressure** | Fake-ally opponent; the ally who attacks; the mentor who is lost; the dependent who raises the cost | Truby's attack-by-ally; ~62 % pinch; ~75 % loss |

- [ ] A character with no function is a merge candidate. Propose the merge; do not perform it on an anchored character.
- [ ] **Cast size discipline.** Count named characters. For each, state the scene where they are introduced and the scene where they last matter. Introduce characters gradually; **NEVER** more than ~3 named characters before the protagonist is anchored in the reader's mind. Readers list "too many characters" among the reasons they stop.
- [ ] Orchestration test: pick any two cast members who share scenes. If they would make the same decision under the same pressure, one is redundant or needs a dimension changed.
- [ ] No cast member exists to deliver exposition. If their only scenes are explanations, cut or merge.

### Voice per character

Each sheet carries a **Voice** block and a **NEVER-SAYS** list. Minimum content:

- Sentence length and rhythm (short and declarative / looping / fragments under stress).
- Vocabulary register and one or two idiolect markers (trade jargon, dialect, a verbal habit used at most once per scene).
- Speaks before thinking, or thinks before speaking.
- What they talk around rather than name (their subtext topic).
- **NEVER-SAYS**: five to ten words, phrases or constructions this character does not use (contractions, swearing, first names, "I feel", apology, the theme).

Tests:
- [ ] **Tag-strip test.** Take any dialogue exchange of six or more lines, remove all tags and beats, and ask whether the speaker of each line can be identified. If not, the voices are not distinct enough. Run at stage 5 on at least two scenes per chapter.
- [ ] **Swap test.** Give a line to a different character. If it needs no change, it belongs to nobody.
- [ ] NEVER-SAYS violations are P2 unless they occur at a beat where voice carries meaning (confession, climax), then P1.

Before / after (same content, two characters):

> Before, both characters: "I think we should wait until morning. It's too dangerous now."
> After, Hanna (ex-police, clipped, never says "I think"): "Morning. Not before."
> After, Olli (talks to fill silence, never gives a flat no): "I mean, we could go now, sure, if we wanted to find out what the ice does at night. I'm just saying morning has its points."

## 5. Agency and motivation

- [ ] **Characters cause events.** For each scene in `scenes.yaml`, the `turn` must be produced by a character's decision or action, not by weather, coincidence or a newly arrived stranger. Coincidence may start trouble (inciting incident), **NEVER** resolve it.
- [ ] **Midpoint shift.** Before ~50 % the protagonist may react; after it they must act. List the protagonist's decisions after the midpoint; if the list is short or they are still being pushed, agency is missing.
- [ ] **One resolution the protagonist does not cause.** "Protagonist resolves every thread personally" is itself a tell of a tidy, machine-shaped plot. Allow at least one subplot or thread whose resolution comes from another character's choice, a cost the protagonist cannot repair, or a thread deliberately left resonant rather than closed. Note which one in `acts.md` open threads.
- [ ] **Morally compromised beats.** The protagonist must, at least once before ~75 %, do something the reader would not do and the book does not excuse: lie to an ally, take the selfish option, hurt someone through the weakness. Record the scene id. A protagonist who is only ever right has no moral need and the climax cannot cost them anything.
- [ ] **Flaws that cost something.** Every flaw on the sheet must be traceable to a concrete loss on the page (a relationship, an opportunity, a clue missed). A flaw that only makes the character charming is a trait, not a flaw.
- [ ] **Don't protect the protagonist.** Something must contradict a belief they hold, and they must lose at least one try/fail cycle outright ("no, and").
- [ ] **Foreshadow out-of-character choices.** Any decision that breaks the sheet's pattern needs a planted cause earlier; otherwise it is a reviewer finding, not a surprise.
- [ ] Motivation must be legible without being stated. Readers drop books over "unclear motivation"; the fix is a visible Want in each scene (`goal` field), not a paragraph of explanation.

## 6. Setting as pressure on character

Setting earns its place only when it changes a decision. Worldbuilding lives in `book/bible/world/*.md`; what reaches the page is filtered through the POV character.

- [ ] **Pressure.** In each scene, name one environmental fact that forces or limits a choice (a room with one exit, cold that sets a deadline, a crowd that prevents a conversation). "If nothing in the environment forces a decision, the setting is a painted backdrop."
- [ ] **Filter.** Each setting detail must be justifiable by the POV character's current desire, fear or bias. "If a sentence could appear unchanged in another character's voice, it isn't doing POV work."
- [ ] **Three to five sensory details** per scene location, chosen to match the scene's emotional logic; draw on temperature, smell, texture and sound, not only sight. Listing is not describing.
- [ ] **Blindfold test.** Could a reader understand the pressures of the space without seeing it? If the scene only works as a picture, add friction (a stuck latch, a closing crowd) that acts on the body.
- [ ] **Exposition gates.** Any paragraph of world information must pass one of three: it changes a decision in this scene; the POV character would notice it right now; the reader needs it to understand the next action. Otherwise move it later or cut it.
- [ ] **Iceberg.** The author knows eight parts; the page shows one. Omit from knowledge, never from ignorance (hollow places show). Infodump detector: three or more consecutive sentences of narration with no character action, no sensory anchor and no present consequence.
- [ ] Recurring images attached to a character should change as the character changes; a static motif reads as decoration.

Before / after:

> Before: "The kitchen was small, with a wooden table, two chairs, a window facing the lake and an old stove."
> After (POV: Hanna, who needs to leave before he returns): "One door. The window over the sink did not open; she had checked. The stove ticked as it cooled, which meant he had been here within the hour."

## 7. Knowledge ledger and continuity

Each `characters/<slug>.md` carries a **Knowledge ledger**: a table of facts this character knows, the scene id where they learned it, and from whom. Mystery books also log each lie told and each secret kept (the sheet's lie/secret fields).

| Fact | Learned in | From | Acted on in |
|---|---|---|---|

Rules:
- [ ] **NEVER** let a character use information before the ledger says they have it. Dramatic irony (reader knows, character does not) is deliberate; a character knowing what only the reader has seen is a continuity error, P1.
- [ ] When the ledger says a character knows something, they must act consistently with it; a character who ignores known facts to keep the plot alive is the "idiot plot", P1.
- [ ] Update the ledger after every drafted scene that reveals, overhears or deduces. The drafting agent writes the entry; the reviewer checks it.
- [ ] **Physical facts** (eye colour, injuries, scars, who holds the keys, what was broken, which hand) are logged once on the sheet and checked at stage 5 against the scene files. Injuries persist until a scene heals them.
- [ ] Emotional continuity: the state a character leaves a scene in is the state they enter the next scene in, unless off-page time is shown to pass. Skipped transitional steps between emotional states are Egri's "jumping conflict", reportable.
- [ ] Timeline: the ledger's scene ids must be consistent with `book/bible/timeline.md`; a character cannot learn a fact before it happens.

## 8. Character reviewer checklist

Run at **stage 2** (bible: sheets and outline exist, no prose) and **stage 5** (critique: against drafted scenes, citing quoted evidence and scene ids). Findings go to `book/critiques/chNN/<agent>-<date>.md` with severity. Never contradict `## ⚓ Anchored`.

- [ ] 1. Protagonist audit table (section 2) has no blank cell. *(2, 5)*
- [ ] 2. Lie == counter-idea; Truth == controlling idea in `premise.md`. *(2)*
- [ ] 3. Arc type is declared and the 25/50/75/climax beats in `acts.md` match that type's row. *(2, 5)*
- [ ] 4. Hook state and resolution state are opposites (or, for a flat arc, the cast's states are). *(2, 5)*
- [ ] 5. Ghost is a specific dated event; the origin scene could be written from the sheet. *(2)*
- [ ] 6. Antagonist wants the same object, is at least equal in strength, mirrors a choice, and can argue their case in their own voice. *(2)*
- [ ] 7. Antagonist's force is on the page in scenes near ~37 % and ~62 % (cite scene ids; at stage 5, quote the lines). *(2, 5)*
- [ ] 8. Neither failure pole: not misunderstood-villain, not evil-for-its-own-sake. *(2, 5)*
- [ ] 9. Every named character has a declared function (mirror/contrast/pressure) and an introduction and exit scene; merge candidates named. *(2)*
- [ ] 10. Tag-strip test passes on at least two exchanges per chapter; NEVER-SAYS lists are respected. *(5)*
- [ ] 11. Scene turns are caused by character decisions; coincidence never resolves. *(5)*
- [ ] 12. At least one morally compromised protagonist beat before ~75 %, and at least one thread the protagonist does not personally resolve. *(2, 5)*
- [ ] 13. Each flaw has a traceable cost on the page. *(5)*
- [ ] 14. Knowledge ledger is current; no character acts on unlearned information; physical facts and injuries are consistent across scenes. *(5)*
- [ ] 15. Climax choice depends on the Truth learned and costs something named; the ending is earned, not granted. *(2, 5)*

Severity guide: 1, 2, 3, 6, 15 are P0 at stage 2 (fix before outlining continues). 7, 11, 12, 14 are P1 at stage 5. Voice and flaw-cost findings (10, 13) are P2 unless they land on a structural beat.

Sources: Creating Character Arcs (Weiland); Structuring Your Novel (Weiland); The Anatomy of Story (Truby); Story Genius and Wired for Story (Cron); The Art of Dramatic Writing (Egri); Story Grid on protagonist/antagonist and the Editor's Six Core Questions; Writing Excuses on Seven-Point Structure; Writers Helping Writers on pinch points; Self-Editing for Fiction Writers (Browne & King); Not MFA on setting that drives story; Hemingway's iceberg; Palomar dialogue chapter; TCK Publishing on why readers drop books.
