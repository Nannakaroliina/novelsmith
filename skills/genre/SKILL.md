---
name: genre
description: Genre contracts, obligatory scenes and reader expectations for novels (mystery and Nordic/Finnish crime in depth; thriller, romance, fantasy, SF, horror, literary, historical, kidlit, erotica planned). Use when outlining, drafting, or reviewing any fiction, when the user names a genre or subgenre, asks whether a book "delivers" for its genre, or asks about fair play, clues, suspects, beats, tropes or word counts.
user-invocable: true
argument-hint: "[genre or subgenre]"
---

# Genre knowledge

A genre is a contract with the reader: a core value at stake, an emotion promised, an ending shape, and a set of obligatory scenes the reader will feel cheated without. This skill tells you which contract applies and loads only the reference file for it.

## How to use

1. Find the base genre in `book/bible/premise.md` (field "Base genre"), or from `$ARGUMENTS`, or from the user's words. If none is stated, ask once.
2. Read exactly one base reference from `${CLAUDE_SKILL_DIR}/references/` (table below; every `references/` path in this skill is under that folder). Read a variant file too only when the premise names that variant. Do not read other genres.
3. For a blend ("romantic suspense", "cozy fantasy", "mystery with a romance subplot"):
   - The **second word** of a compound label names the base genre; load its full file.
   - From the secondary genre load only its non-negotiables (listed at the top of each file under "Non-negotiables when secondary").
   - Conflicts resolve in favour of the base, **except** recognised two-contract labels (romantasy, romantic suspense, erotic romance), where both full lists are mandatory.
4. Apply the file's checklists at the stage you are in: *Contract* and *Obligatory scenes* when outlining; *Drafting rules* when drafting; *Reader complaints* and *Fairness audit* when reviewing.

## Reference files

| Base genre | File | Variants with their own file |
|---|---|---|
| Mystery / crime | `references/mystery.md` | `references/mystery-nordic-finnish.md` (Nordic noir, Finnish crime) |
| Thriller / suspense | `references/thriller.md` (Phase 5) | |
| Romance | `references/romance.md` (Phase 5) | romantic suspense, dark romance, romantasy |
| Fantasy | `references/fantasy.md` (Phase 5) | cozy, grimdark, urban, romantasy |
| Science fiction | `references/science-fiction.md` (Phase 5) | |
| Horror | `references/horror.md` (Phase 5) | |
| Literary / upmarket | `references/literary.md` (Phase 5) | |
| Historical | `references/historical.md` (Phase 5) | |
| YA / MG / picture book | `references/kidlit.md` (Phase 5) | |
| Erotica | `references/erotica.md` (Phase 5) | |
| Blends | `references/blends.md` (Phase 5) | |

If the file for a genre does not exist yet, say so and work from the general craft skills (`craft-structure`, `craft-character`, `craft-prose`) plus the contract the author states in `premise.md`.

## Word-count anchors (adult trade fiction unless noted)

| Category | Typical | Notes |
|---|---|---|
| Mystery, crime, thriller | 70–90k | Cozy 60–75k; debut ceiling ~100k |
| Romance | 70–100k | Category romance 50–60k |
| Fantasy, SF | 90–120k | Epic debut: sources disagree (90k to 160k); stay under ~120k unless the author decides otherwise |
| Horror | 70–90k | |
| Literary / upmarket | 70–100k | |
| Historical | 90–110k | |
| YA | 55–80k | SF/F YA up to ~90k |
| Middle grade | 20–55k | |
| Picture book | 400–800 words | 32 pages, 14 spreads |

## The one rule that overrides genre
Every genre convention is subordinate to the author's `## ⚓ Anchored` decisions in `premise.md`. If an anchored decision breaks a convention, note the trade-off once and move on.
