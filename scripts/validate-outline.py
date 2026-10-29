#!/usr/bin/env python3
"""Validate book/outline/scenes.yaml against the bible before any drafting.

Plan-validate-execute: the outliner writes the manifest, this script judges it,
the outliner fixes what failed. Errors block drafting; warnings are findings the
outliner should address or explain. Checks are the deterministic half of
skills/craft-structure (beat map, scene test) and skills/de-ai/references/
outline-level.md (subplot, compromise, open thread, climax placement, valence,
chapter shapes, names); the judgement half stays with the agents.

Usage:
    validate-outline.py [--book PATH] [--json]

Exit codes: 0 pass (warnings allowed), 1 errors found, 2 cannot read the book.
Waivers: the AUTHOR may set book.waivers in scenes.yaml, e.g.
    waivers: {open_thread: "anchored: every thread closes"}
A waived check is reported but never fails the run. Agents must not add waivers.
"""

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ns_book  # noqa: E402
import ns_yaml  # noqa: E402
from ns_book import section, strip_html_comments  # noqa: E402

REQUIRED_FIELDS = ("id", "chapter", "pov", "goal", "conflict", "turn", "outcome", "value_shift", "word_target")
STATUSES = {"planned", "drafted", "revised", "locked"}
BEATS = {
    "hook", "theme_stated", "inciting", "b_story", "doorway", "pinch_1", "midpoint", "pinch_2",
    "all_is_lost", "dark_night", "break_into_three", "climax", "resolution",
    "inciting_crime", "false_solution", "collapse", "exposure", "denouement",
}
FLAGS = {"compromise", "non_protagonist_resolution", "open_thread", "nonlinear", "sequel"}

# Required arc beats in reading order, with the window (fraction of total words,
# measured at the END of the delivering scene) outside which placement is a warning.
ARC_BEATS = [
    ("inciting", 0.00, 0.15),
    ("doorway", 0.15, 0.35),
    ("pinch_1", 0.28, 0.47),
    ("midpoint", 0.40, 0.60),
    ("pinch_2", 0.53, 0.72),
    ("all_is_lost", 0.65, 0.85),
    ("climax", 0.80, 0.95),
]
# In a mystery these beats stand in for the general ones.
MYSTERY_ALIASES = {"inciting": {"inciting_crime"}, "climax": {"exposure"}}
MYSTERY_WORDS = ("mystery", "crime", "detective", "noir", "procedural", "whodunit", "cozy")
NORDIC_WORDS = ("nordic", "finnish", "scandi", "scandinavian")
NORDIC_SUBPLOTS = ("social", "criminal", "institution", "season")

DEFAULT_BANNED_NAMES = [
    "Elias", "Elara", "Mara", "Elena", "Kael", "Kaelen", "Lyra", "Aria", "Sera", "Seraphina",
    "Theron", "Orion", "Silas", "Aris", "Voss", "Vance", "Thorne", "Blackwood", "Marcus",
    "Sarah", "Chloe", "Lily",
]

ID_RE = re.compile(r"^ch(\d{2,3})-s(\d{2,3})$")
OUTCOME_RE = re.compile(r"^\s*(yes-but|no-and)\b", re.I)
SHIFT_RE = re.compile(r"\bfrom\b.+\bto\b", re.I)
DAY_RE = re.compile(r"\bday\s*(-?\d+)", re.I)
STRUCTURES = {"arc", "kishotenketsu", "alison"}
CLOCK_RE = re.compile(r"(\d{1,2}):(\d{2})")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    return [v]


def blank(v):
    return v is None or (isinstance(v, str) and not v.strip()) or v == []


def tag(v):
    return norm(v).replace("-", "_")


def read(path):
    """Read a bible file; a stray non-UTF-8 byte must not take down the run."""
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def suspicious_name(name):
    """Zero-width/format characters, or letters from more than one script (Latin 'E' vs Cyrillic 'Е')."""
    if any(unicodedata.category(ch) == "Cf" for ch in name):
        return "contains an invisible formatting character"
    scripts = set()
    for ch in name:
        if ch.isalpha():
            scripts.add(unicodedata.name(ch, "UNKNOWN").split()[0])
    if len(scripts) > 1:
        return f"mixes letters from {', '.join(sorted(scripts))} scripts"
    return ""


class Report:
    def __init__(self, waivers):
        self.items = []
        self.waivers = {tag(k): v for k, v in (waivers or {}).items()}

    def add(self, level, check, message, where="", fix=""):
        check = tag(check)
        if level == "error" and check in self.waivers:
            level = "waived"
            message += f" [waived by author: {self.waivers[check]}]"
        self.items.append({"level": level, "check": check, "where": where, "message": message, "fix": fix})

    def error(self, *a, **k):
        self.add("error", *a, **k)

    def warn(self, *a, **k):
        self.add("warning", *a, **k)

    def count(self, level):
        return sum(1 for i in self.items if i["level"] == level)


def load_characters(bible):
    """Map every accepted spelling of a character to its sheet's slug."""
    names, headings = {}, {}
    cdir = bible / "characters"
    if not cdir.is_dir():
        return names, headings
    firsts = {}
    for f in sorted(cdir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        slug = f.stem
        text = read(f)
        m = re.search(r"^#\s+(.+)$", text, re.M)
        heading = m.group(1).strip() if m and "{{" not in m.group(1) else ""
        headings[slug] = heading
        spellings = {norm(slug)}
        if heading:
            spellings.add(norm(heading))
            firsts.setdefault(norm(heading.split()[0]), set()).add(slug)
        aka = re.search(r"^-\s*Also known as:\s*(.+)$", text, re.M | re.I)
        if aka:
            spellings.update(norm(a) for a in aka.group(1).split(",") if a.strip())
        for s in spellings:
            names[s] = slug
    for first, slugs in firsts.items():
        if len(slugs) == 1 and first not in names:
            names[first] = next(iter(slugs))
    return names, headings


def table_first_column(md):
    ids = set()
    for line in md.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first = cells[0] if cells else ""
        if not first or set(first) <= set("-: ") or first.lower() in ("clue id", "id", "suspect"):
            continue
        ids.add(first)
    return ids


def banned_names(bible):
    style = bible / "style.md"
    if style.is_file():
        m = re.search(r"Banned names[^:\n]*:[ \t]*(\S.*)$", read(style), re.M | re.I)
        if m:
            return [n.strip() for n in m.group(1).split(",") if n.strip()]
    return DEFAULT_BANNED_NAMES


def story_minutes(t):
    """Rough story-time ordering key from 'Day 3, 14:20'; None if unparseable."""
    if not isinstance(t, str):
        return None
    d = DAY_RE.search(t)
    if not d:
        return None
    c = CLOCK_RE.search(t)
    return int(d.group(1)) * 1440 + (int(c.group(1)) * 60 + int(c.group(2)) if c else 0)


def validate(book):
    manifest_path = book / "outline" / "scenes.yaml"
    try:
        data = ns_yaml.load(manifest_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise SystemExit(f"cannot read {manifest_path}: no such file")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"{manifest_path}: not UTF-8 text ({exc.reason} at byte {exc.start}); re-save it as UTF-8")
    except ns_yaml.YAMLError as exc:
        raise SystemExit(f"{manifest_path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"{manifest_path}: top level must be a mapping with 'book' and 'scenes'")

    meta = data.get("book") or {}
    if not isinstance(meta, dict):
        raise SystemExit(f"{manifest_path}: 'book' must be a mapping (title, target_words, base_genre, structure, waivers)")
    waivers = meta.get("waivers") or {}
    if not isinstance(waivers, dict):
        raise SystemExit(f"{manifest_path}: book.waivers must be a mapping of check-id: \"reason\", e.g. {{open_thread: \"…\"}}")
    scenes = data.get("scenes") or []
    rep = Report(waivers)
    bible = book / "bible"

    # premise.md is the source of truth for genre and structure; scenes.yaml only mirrors them.
    premise = read(bible / "premise.md")
    anchored = ns_book.anchored_text(premise)
    premise_genre = ns_book.field(premise, "Base genre").lower()
    variant = ns_book.field(premise, "Subgenre / variant").lower()
    manifest_genre = str(meta.get("base_genre") or "").strip().lower()
    if premise_genre and manifest_genre and manifest_genre != premise_genre:
        rep.error("book_meta", f"scenes.yaml base_genre {manifest_genre!r} differs from premise.md {premise_genre!r}", "book",
                  "premise.md decides the genre; copy it into scenes.yaml or ask the author to change the premise.")
    genre = premise_genre or manifest_genre
    is_mystery = any(w in genre for w in MYSTERY_WORDS)
    is_nordic = is_mystery and any(w in genre + " " + variant for w in NORDIC_WORDS)
    premise_structure = tag(ns_book.field(premise, "Structural model").split(" ")[0]) if ns_book.field(
        premise, "Structural model") else ""
    manifest_structure = tag(meta.get("structure") or "")
    structure = premise_structure or "arc"
    if premise_structure and premise_structure not in STRUCTURES:
        rep.error("book_meta", f"premise.md structural model {premise_structure!r} is not one of {', '.join(sorted(STRUCTURES))}",
                  "premise.md")
    if manifest_structure and manifest_structure != structure:
        rep.error("book_meta", f"scenes.yaml structure {manifest_structure!r} differs from premise.md ({structure})", "book",
                  "Only the author changes the structural model, in premise.md → Genre → Structural model.")

    if not isinstance(scenes, list) or not scenes:
        rep.error("fields", "scenes.yaml has no scenes", "scenes")
        return rep, {}

    # ---- per-scene fields -------------------------------------------------
    names, headings = load_characters(bible)
    seen, prev_ch = {}, 0
    total = 0
    for idx, s in enumerate(scenes):
        if not isinstance(s, dict):
            rep.error("fields", f"scene #{idx + 1} is not a mapping", f"scenes[{idx}]")
            scenes[idx] = s = {}
        sid = str(s.get("id") or f"scenes[{idx}]")
        missing = [f for f in REQUIRED_FIELDS if blank(s.get(f))]
        if missing:
            rep.error("fields", f"missing {', '.join(missing)}", sid,
                      "Every scene needs a statable goal, opposition, turn, yes-but/no-and outcome and 'from X to Y' shift.")
        if sid in seen:
            rep.error("ids", f"duplicate id (also scene #{seen[sid] + 1})", sid)
        seen[sid] = idx
        m = ID_RE.match(sid)
        ch = s.get("chapter")
        if not m:
            rep.error("ids", "id must look like ch01-s01 (manuscript files are chNN/sNN.md)", sid)
        elif isinstance(ch, int) and int(m.group(1)) != ch:
            rep.error("ids", f"id says chapter {int(m.group(1))} but chapter is {ch}", sid)
        if isinstance(ch, int):
            if ch < prev_ch:
                rep.error("order", f"chapter {ch} comes after chapter {prev_ch}; the manifest is in reading order", sid)
            prev_ch = max(prev_ch, ch)
        elif ch is not None:
            rep.error("fields", f"chapter must be a whole number, got {ch!r}", sid)
        wt = s.get("word_target")
        if isinstance(wt, bool) or not isinstance(wt, (int, float)) or wt <= 0:
            if wt is not None:
                rep.error("fields", f"word_target must be a positive number, got {wt!r}", sid)
            wt = 0
        s["_wt"] = wt
        total += wt
        status = s.get("status", "planned")
        if status not in STATUSES:
            rep.error("fields", f"status {status!r} is not one of {', '.join(sorted(STATUSES))}", sid)
        flags = {tag(f) for f in as_list(s.get("flags"))}
        s["_flags"] = flags
        for f in flags - FLAGS:
            rep.warn("vocabulary", f"unknown flag {f!r}", sid, f"Use one of: {', '.join(sorted(FLAGS))}.")
        beats = {tag(b) for b in as_list(s.get("beat"))}
        s["_beats"] = beats
        for b in beats - BEATS:
            rep.warn("vocabulary", f"unknown beat {b!r}", sid, "See the beat vocabulary at the top of templates/scenes.yaml.")
        outcome = s.get("outcome")
        if not blank(outcome) and "sequel" not in flags and not OUTCOME_RE.match(str(outcome)):
            rep.error("outcome", f"outcome must start with yes-but or no-and, got {str(outcome)[:60]!r}", sid,
                      "A plain yes or no ends the tension; add the 'but' or the 'and'. Flag reaction scenes as sequel.")
        s["_outcome"] = (OUTCOME_RE.match(str(outcome or "")) or [None, ""])[1].lower()
        vs = s.get("value_shift")
        if not blank(vs) and not SHIFT_RE.search(str(vs)):
            rep.warn("value_shift", f"value_shift should read 'from X to Y', got {str(vs)[:60]!r}", sid)

    # ---- entities -----------------------------------------------------------
    unknown = {}
    for s in scenes:
        people = as_list(s.get("characters")) + as_list(s.get("pov"))
        for p in people:
            ids = unknown.setdefault(str(p), []) if norm(p) not in names else None
            if ids is not None and str(s.get("id")) not in ids:
                ids.append(str(s.get("id")))
    for p, ids in sorted(unknown.items()):
        rep.error("entities", f"{p!r} has no sheet in bible/characters/", ", ".join(ids[:6]) + (" …" if len(ids) > 6 else ""),
                  "Create the sheet (character-designer) or fix the spelling; add aliases with '- Also known as:'.")

    banned = banned_names(bible)
    anchored_n = norm(anchored)
    used = set(unknown) | set(headings.values()) | set(headings)
    for s in scenes:
        used.update(str(p) for p in as_list(s.get("characters")) + as_list(s.get("pov")))
    hits = set()
    for name in used:
        tokens = set(norm(name).split("-"))
        for b in banned:
            if norm(b) in tokens and norm(b) not in anchored_n.split("-"):
                hits.add((b, name))
    for b, name in sorted(hits):
        rep.error("names", f"{name!r} uses the model-default name {b!r}", "characters",
                  "Draw names from the setting's real naming data; anchor the name in premise.md if it is deliberate.")
    for name in sorted(used):
        why = suspicious_name(name)
        if why:
            rep.error("names", f"{name!r} {why}", "characters",
                      "Retype the name in plain letters of one alphabet; look-alike characters hide default names.")

    # ---- positions -----------------------------------------------------------
    cum = 0
    for s in scenes:
        cum += s["_wt"]
        s["_pos"] = cum / total if total else 0

    def scenes_with(*beats):
        return [s for s in scenes if s["_beats"] & set(beats)]

    target = meta.get("target_words")
    if isinstance(target, (int, float)) and target > 0 and total:
        drift = (total - target) / target
        if abs(drift) > 0.15:
            rep.warn("length", f"scene word targets sum to {total:,} vs book target {int(target):,} ({drift:+.0%})", "book")

    climax_pos = None
    if structure == "arc":
        last_pos, last_beat = -1, None
        for beat, lo, hi in ARC_BEATS:
            accepted = {beat} | (MYSTERY_ALIASES.get(beat, set()) if is_mystery else set())
            hit = scenes_with(*accepted)
            if not hit:
                rep.error("beats", f"no scene delivers the {beat} beat", "beat",
                          "Assign the beat to an existing scene or add one; see craft-structure §1 for what it must accomplish.")
                continue
            if beat in ("midpoint", "climax") and len(hit) > 1:
                rep.warn("beats", f"{len(hit)} scenes claim the {beat} beat", ", ".join(str(s.get("id")) for s in hit))
            s = hit[0]
            pos = s["_pos"]
            where = f"{s.get('id')} at {pos:.0%}"
            if beat == "climax":
                climax_pos = pos
                if pos < 0.80:
                    rep.error("climax_placement", f"climax lands at {pos:.0%}; it must land at or after 80%", where,
                              "Move word budget from act 1 / early act 2 into 62–85%; add a complication before the climax.")
                elif pos > hi:
                    rep.warn("beat_placement", f"climax lands at {pos:.0%}, after {hi:.0%}", where)
            elif not lo <= pos <= hi:
                rep.warn("beat_placement", f"{beat} lands at {pos:.0%}; expected {lo:.0%}–{hi:.0%}", where)
            if pos < last_pos:
                rep.error("beat_order", f"{beat} comes before {last_beat} in reading order", where)
            last_pos, last_beat = pos, beat
        if climax_pos is not None:
            after = 1 - climax_pos
            if after > 0.12:
                rep.warn("epilogue", f"{after:.0%} of the words come after the climax", "resolution",
                         "Cut the denouement until it no longer works one scene shorter.")
    else:
        rep.warn("structure", f"structure is {structure}; arc beat checks skipped", "book",
                 "craft-structure §0: test the declared pattern's integrity instead.")

    # ---- anti-homogenisation (de-ai outline-level checks) -----------------------
    sub = [s for s in scenes if not blank(s.get("subplot"))]
    if not sub:
        rep.error("subplot", "no scene carries a subplot", "subplot",
                  "Build one from the protagonist's Need/Lie or a secondary character's want; 3–5 scenes spread across acts.")
    else:
        threads = {}
        for s in sub:
            threads.setdefault(tag(s["subplot"]), []).append(s)
        for name, ss in threads.items():
            if len(ss) < 2:
                rep.warn("subplot", f"subplot {name!r} appears in only one scene", str(ss[0].get("id")))
        if not any(s["_beats"] for s in sub):
            rep.warn("subplot", "no subplot scene also carries a main-plot beat; the threads never touch", "subplot")

    all_flags = set().union(*(s["_flags"] for s in scenes))
    if "compromise" not in all_flags:
        rep.error("compromise", "no scene is flagged compromise: the protagonist is never morally compromised", "flags",
                  "Pick the beat nearest 37% or 62% and have the protagonist take the selfish option; plan the consequence in act 3.")
    else:
        compromises = [s for s in scenes if "compromise" in s["_flags"]]
        if min(s["_pos"] for s in compromises) > 0.92:
            rep.warn("compromise", "the only compromise is this late, leaving no room for consequence",
                     ", ".join(str(s.get("id")) for s in compromises))
    if "non_protagonist_resolution" not in all_flags:
        rep.error("non_protagonist_resolution", "every resolution is driven by the protagonist", "flags",
                  "Give one thread's resolution to another character, chance, an institution, weather, or the antagonist's error.")

    acts_path = book / "outline" / "acts.md"
    acts = strip_html_comments(read(acts_path))
    open_md = section(acts, r"Threads the book leaves open")
    open_items = [l for l in open_md.splitlines() if re.match(r"^\s*[-*]\s+\S", l)]
    if "open_thread" not in all_flags and not open_items:
        rep.error("open_thread", "no thread is left open at the end", "acts.md / flags",
                  "Choose a subplot or secondary relationship, remove its resolving scene, and list it in acts.md.")

    times = [story_minutes(s.get("time")) for s in scenes]
    backwards = any(a is not None and b is not None and b < a for a, b in zip(times, times[1:]))
    if "nonlinear" not in all_flags and not backwards:
        rep.warn("nonlinear", "no flashback, time jump, framing device or document scene", "flags",
                 "Dramatize one backstory-in-dialogue scene at its real time, or open act 2 after a jump.")

    outcomes = [s["_outcome"] for s in scenes if "sequel" not in s["_flags"]]
    if outcomes:
        neg = outcomes.count("no-and") / len(outcomes)
        if neg < 1 / 3:
            rep.warn("valence", f"only {neg:.0%} of scenes end no-and; the book reads uniformly positive", "outcome",
                     "Flip two mid-act-2 yes-but outcomes to no-and; cut a consolation scene.")
        for q in range(4):
            lo, hi = q / 4, (q + 1) / 4
            if not any(lo < s["_pos"] <= hi and s["_outcome"] == "no-and" for s in scenes):
                rep.warn("setbacks", f"no no-and setback in quarter {q + 1}", f"{lo:.0%}–{hi:.0%}")
        run = 1
        for a, b in zip(scenes, scenes[1:]):
            run = run + 1 if a["_outcome"] and a["_outcome"] == b["_outcome"] else 1
            if run == 3:
                rep.warn("polarity", f"three {b['_outcome']} outcomes in a row", f"ending at {b.get('id')}")
    prev_sequel = False
    for s in scenes:
        if "sequel" in s["_flags"] and prev_sequel:
            rep.warn("sequels", "two consecutive sequel scenes with no goal-driven scene between", str(s.get("id")))
        prev_sequel = "sequel" in s["_flags"]

    if climax_pos is not None:
        late = [s for s in scenes if s["_pos"] > climax_pos]
        idle = [s for s in late if blank(s.get("conflict"))]
        if len(late) > 2 or idle:
            rep.warn("epilogue", f"{len(late)} scene(s) after the climax" + (", some with no conflict" if idle else ""),
                     ", ".join(str(s.get("id")) for s in late[:5]),
                     "Epilogues need an anchored decision or a new cost; otherwise fold the fact into the last real scene.")

    chapters = {}
    for s in scenes:
        if isinstance(s.get("chapter"), int):
            chapters.setdefault(s["chapter"], []).append(s)
    if len(chapters) >= 4:
        words = [sum(x["_wt"] for x in ss) for ss in chapters.values()]
        mean = statistics.mean(words)
        cv = statistics.pstdev(words) / mean if mean else 0
        if cv < 0.20:
            rep.warn("chapter_shape", f"chapter lengths vary too little (CV {cv:.2f} < 0.20)", "chapters",
                     "Plan at least one chapter under 60% of the mean and one over 140%.")
        if len({len(ss) for ss in chapters.values()}) == 1:
            rep.warn("chapter_shape", f"every chapter has {len(next(iter(chapters.values())))} scenes", "chapters")

    # ---- mystery ------------------------------------------------------------
    if is_mystery:
        clue_md = read(bible / "clues.md")
        known = table_first_column(clue_md)
        planted_at = {}
        for s in scenes:
            for c in as_list(s.get("clues_planted")):
                planted_at.setdefault(str(c), s["_pos"])
        for s in scenes:
            sid = str(s.get("id"))
            for field in ("clues_planted", "clues_paid", "red_herrings"):
                for c in as_list(s.get(field)):
                    if str(c) not in known:
                        rep.error("clues", f"{field} names {c!r}, which is not in bible/clues.md", sid)
            for c in as_list(s.get("clues_paid")):
                if str(c) not in planted_at or planted_at[str(c)] >= s["_pos"]:
                    rep.error("fair_play", f"clue {c!r} is paid off here but never planted earlier", sid,
                              "Plant it up to three times before the exposure (subtle → clearer → obvious in hindsight).")
        paid = {str(c) for s in scenes for c in as_list(s.get("clues_paid"))}
        for c in sorted(set(planted_at) - paid):
            rep.warn("clues", f"clue {c!r} is planted but never paid off", "clues_planted")
        crime = scenes_with("inciting_crime")
        if not crime:
            rep.warn("mystery", "no scene carries beat inciting_crime", "beat")
        elif crime[0]["_pos"] > 0.20:
            rep.warn("mystery", f"the crime reaches the page at {crime[0]['_pos']:.0%}; aim for ≤ 20%", str(crime[0].get("id")))
        false = scenes_with("false_solution")
        if not false:
            rep.warn("mystery", "no false_solution beat; the first solution should be confident and wrong near 50%", "beat")
        exposure = scenes_with("exposure")
        if exposure and len([s for s in scenes if s["_pos"] > exposure[0]["_pos"]]) > 2:
            rep.warn("mystery", "more than two scenes after the exposure", str(exposure[0].get("id")))
        if is_nordic:
            tags = {tag(s.get("subplot")) for s in sub}
            for t in NORDIC_SUBPLOTS:
                if t not in tags:
                    rep.warn("nordic", f"no scene with subplot: {t} (mystery-nordic-finnish.md §4)", "subplot")

    stats = {"scenes": len(scenes), "chapters": len(chapters), "words": total,
             "structure": structure, "mystery": is_mystery, "nordic": is_nordic}
    return rep, stats


def find_book(arg):
    if arg:
        return Path(arg)
    for base in (Path.cwd(), Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))):
        if (base / "book").is_dir():
            return base / "book"
    return Path("book")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--book", help="path to the book/ directory (default: ./book)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    book = find_book(args.book)
    try:
        rep, stats = validate(book)
    except (SystemExit, Exception) as exc:  # exit 1 means "outline has errors"; anything that stops the check is 2
        reason = str(exc) if isinstance(exc, SystemExit) else f"{type(exc).__name__}: {exc}"
        print(f"validate-outline: {reason}", file=sys.stderr)
        if args.json:
            print(json.dumps({"pass": False, "unreadable": True, "error": reason}, ensure_ascii=False))
        return 2

    errors, warnings = rep.count("error"), rep.count("warning")
    if args.json:
        print(json.dumps({"pass": errors == 0, "errors": errors, "warnings": warnings,
                          "stats": stats, "findings": rep.items}, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    print(f"Outline check: {book / 'outline' / 'scenes.yaml'}")
    if stats:
        print(f"{stats['scenes']} scenes, {stats['chapters']} chapters, {stats['words']:,} planned words, "
              f"structure {stats['structure']}" + (", mystery" if stats["mystery"] else "")
              + (" (Nordic/Finnish)" if stats["nordic"] else ""))
    for level, title in (("error", "ERRORS (block drafting)"), ("warning", "WARNINGS"), ("waived", "WAIVED BY AUTHOR")):
        items = [i for i in rep.items if i["level"] == level]
        if not items:
            continue
        print(f"\n{title}")
        for i in items:
            where = f" [{i['where']}]" if i["where"] else ""
            print(f"- {i['check']}{where}: {i['message']}")
            if i["fix"]:
                print(f"    fix: {i['fix']}")
    print(f"\n{'FAIL' if errors else 'PASS'}: {errors} error(s), {warnings} warning(s), {rep.count('waived')} waived")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
