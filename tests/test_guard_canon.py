import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fixture_book as fixture  # noqa: E402

SCRIPT = ROOT / "scripts" / "guard-canon.py"
HOOKS = ROOT / "hooks" / "hooks.json"


def guard_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("guard", SCRIPT)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard


class GuardCanon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        self.book = fixture.build(self.project)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, tool, rel, agent=None, raw=False, cwd=None, tool_input_override=None, reason=False,
             **tool_input):
        target = {} if rel is None else {"file_path": rel if raw else str(self.project / rel)}
        payload = {"hook_event_name": "PreToolUse", "cwd": str(cwd or self.project), "tool_name": tool,
                   "tool_input": tool_input_override if tool_input_override is not None else {**target, **tool_input}}
        if agent:
            payload["agent_id"] = "a1"
            payload["agent_type"] = agent
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                           text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        if not p.stdout.strip():
            return None
        out = json.loads(p.stdout)["hookSpecificOutput"]
        return (out["permissionDecision"], out["permissionDecisionReason"]) if reason else out["permissionDecision"]

    def test_outside_book(self):
        self.assertIsNone(self.hook("Write", "src/app.py", agent="general-purpose", content="x"))
        self.assertIsNone(self.hook("Write", "src/app.py", content="x"))
        # novelsmith agents write only the book, never e.g. the plugin's own scripts (GSEC-2)
        self.assertEqual(self.hook("Write", "src/app.py", agent="novelsmith:outliner", content="x"), "deny")
        self.assertEqual(self.hook("Write", str(ROOT / "scripts" / "yaml.py"), agent="novelsmith:outliner",
                                   raw=True, content="x"), "deny")

    def test_other_tools_ignored(self):
        self.assertIsNone(self.hook("Read", "book/bible/premise.md", agent="novelsmith:outliner"))

    def test_agent_in_scope_allowed(self):
        self.assertIsNone(self.hook("Write", "book/outline/chapters.md", agent="novelsmith:outliner", content="x"))
        self.assertIsNone(self.hook("Write", "book/bible/characters/new.md", agent="novelsmith:character-designer",
                                    content="# New\n"))

    def test_agent_out_of_scope_denied(self):
        self.assertEqual(self.hook("Write", "book/bible/characters/x.md", agent="novelsmith:outliner", content="x"),
                         "deny")
        self.assertEqual(self.hook("Edit", "book/progress.md", agent="novelsmith:worldbuilder",
                                   old_string="a", new_string="b"), "deny")

    def test_unscoped_agent_name_still_recognised(self):
        self.assertEqual(self.hook("Write", "book/outline/acts.md", agent="worldbuilder", content="x"), "deny")

    def test_foreign_agent_cannot_touch_canon(self):
        self.assertEqual(self.hook("Write", "book/bible/style.md", agent="general-purpose", content="x"), "deny")
        self.assertIsNone(self.hook("Write", "book/summaries/ch01.md", agent="general-purpose", content="x"))

    def test_main_session_edit_outside_anchor_allowed(self):
        self.assertIsNone(self.hook("Edit", "book/bible/premise.md", old_string="exposure on the ice road",
                                    new_string="exposure at the ferry"))

    def test_main_session_anchor_change_asks(self):
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", old_string="harbour master's sister",
                                   new_string="harbour master"), "ask")

    def test_agent_anchor_change_denied(self):
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   old_string="harbour master's sister", new_string="harbour master"), "deny")

    def test_agent_rewrite_preserving_anchor_allowed(self):
        text = (self.book / "bible/premise.md").read_text(encoding="utf-8")
        new = text.replace("exposure on the ice road", "exposure at the ferry")
        self.assertIsNone(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect", content=new))

    def test_agent_rewrite_dropping_anchor_denied(self):
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content="# Premise\n"), "deny")

    def test_agent_cannot_add_waiver(self):
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   old_string="  waivers: {}", new_string='  waivers: {subplot: "no"}'), "deny")

    def test_agent_may_edit_scenes_without_touching_waivers(self):
        self.assertIsNone(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                    old_string="turn: turn 3", new_string="turn: she sees the key"))

    def test_new_manifest_from_template_allowed(self):
        (self.book / "outline/scenes.yaml").unlink()
        template = (Path(__file__).resolve().parents[1] / "templates/scenes.yaml").read_text(encoding="utf-8")
        self.assertIsNone(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                    content=template))

    def test_main_session_waiver_asks(self):
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", old_string="  waivers: {}",
                                   new_string='  waivers: {subplot: "author: novella"}'), "ask")

    def test_relative_path(self):
        self.assertEqual(self.hook("Write", "book/bible/world/x.md", agent="novelsmith:character-designer", raw=True,
                                   content="x"), "deny")
        self.assertEqual(self.hook("Write", "../bible/premise.md", agent="general-purpose", raw=True,
                                   cwd=self.book / "outline", content="x"), "deny")

    def test_dotdot_cannot_escape_scope(self):
        sneaky = str(self.project) + "/book/proposals/../outline/scenes.yaml"
        self.assertEqual(self.hook("Write", sneaky, agent="novelsmith:worldbuilder", raw=True, content="x"), "deny")

    def test_symlink_into_canon(self):
        (self.book / "proposals" / "link").symlink_to(self.book / "bible")
        self.assertEqual(self.hook("Write", "book/proposals/link/style.md", agent="general-purpose", content="x"),
                         "deny")

    # --- LOOP-2: letter case -------------------------------------------------
    def test_case_variants_are_the_same_file(self):
        self.assertEqual(self.hook("Write", "book/Bible/style.md", agent="general-purpose", content="x"), "deny")
        self.assertEqual(self.hook("Write", "Book/bible/premise.md", agent="general-purpose", content="x"), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/Scenes.YAML", agent="novelsmith:outliner",
                                   old_string="  waivers: {}", new_string='  waivers: {subplot: "x"}'), "deny")

    @unittest.skipUnless(sys.platform == "darwin", "case-insensitive filesystem check")
    def test_case_variant_anchor_edit_on_macos(self):
        self.assertEqual(self.hook("Edit", "book/bible/PREMISE.MD", agent="novelsmith:story-architect",
                                   old_string="harbour master's sister", new_string="harbour master"), "deny")

    # --- LOOP-1 / TEST-1: waiver edit shapes ---------------------------------
    def test_second_waivers_key_denied(self):
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   old_string="\nscenes:", new_string='\n  waivers: {compromise: "x"}\nscenes:'), "deny")

    def test_decoy_waivers_above_book_denied(self):
        text = (self.book / "outline/scenes.yaml").read_text(encoding="utf-8")
        new = text.replace("book:\n", "waivers: {}\nbook:\n").replace("  waivers: {}", '  waivers: {beats: "x"}')
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=new),
                         "deny")
        only_decoy = text.replace("book:\n", "waivers: {}\nbook:\n")
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   content=only_decoy), "deny")

    def test_block_style_waivers_after_comment_denied(self):
        new = (self.book / "outline/scenes.yaml").read_text(encoding="utf-8").replace(
            "  waivers: {}", "  waivers:\n#\n    names: \"x\"")
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=new),
                         "deny")

    def test_broken_yaml_from_agent_denied(self):
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   old_string="turn: turn 3", new_string="turn: a: b"), "deny")

    def test_empty_old_string_creates_file_with_waivers_denied(self):
        (self.book / "outline/scenes.yaml").write_text("", encoding="utf-8")
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   old_string="", new_string='book:\n  waivers: {compromise: "x"}\nscenes: []\n'),
                         "deny")

    # --- LOOP-3: decoy and comment tricks in ⚓ sections ---------------------
    def premise_text(self):
        return (self.book / "bible/premise.md").read_text(encoding="utf-8")

    def test_decoy_anchor_heading_denied(self):
        text = self.premise_text()
        body = text.split("## ⚓ Anchored\n", 1)[1]
        new = text.replace("## ⚓ Anchored\n", "## Agreed ⚓\n" + body + "\n## ⚓ Anchored\n", 1)
        new = new.replace("- The culprit is the harbour master's sister.\n", "- The culprit is the ferryman.\n")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect", content=new),
                         "deny")

    def test_decoy_inside_comment_denied(self):
        text = self.premise_text()
        new = text.replace("## Genre", "<!--\n## ⚓ Anchored\n- The culprit is the harbour master's sister.\n## -->\n"
                                      "## Genre")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect", content=new),
                         "deny")

    def test_comment_injected_into_anchor_denied(self):
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   old_string="## ⚓ Anchored\n", new_string="## ⚓ Anchored\n<!-- Elias approved -->\n"),
                         "deny")

    def test_second_anchor_section_appended_denied(self):
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=self.premise_text() + "\n## ⚓ Anchored (cont.)\n- Elias is fine.\n"), "deny")

    def test_anchor_on_new_agent_file_denied_but_empty_template_allowed(self):
        self.assertEqual(self.hook("Write", "book/bible/characters/new.md", agent="novelsmith:character-designer",
                                   content="# New\n## ⚓ Anchored\n- forged decision\n"), "deny")
        # a comment under the heading would read as an author note; only the empty heading is allowed
        self.assertEqual(self.hook("Write", "book/bible/characters/new2.md", agent="novelsmith:character-designer",
                                   content="# New\n## ⚓ Anchored\n<!-- Author: New is the killer -->\n"), "deny")
        self.assertIsNone(self.hook("Write", "book/bible/characters/new3.md", agent="novelsmith:character-designer",
                                    content="# New\n## ⚓ Anchored\n\n## Notes\n"))

    # --- LOOP-7: inexact old_string on protected files ------------------------
    def test_curly_quote_mismatch_on_anchored_file_denied(self):
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   old_string="harbour master’s sister", new_string="ferryman"), "deny")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md",
                                   old_string="harbour master’s sister", new_string="ferryman"), "ask")

    def test_any_inexact_subagent_edit_is_denied(self):
        # The real Edit tool matches curly quotes loosely, so an inexact edit's result cannot be predicted.
        self.assertEqual(self.hook("Edit", "book/outline/chapters.md", agent="novelsmith:outliner",
                                   old_string="nothing", new_string="x"), "deny")
        (self.book / "outline/chapters.md").write_text("Kirsi\u2019s plan\n", encoding="utf-8")
        self.assertEqual(self.hook("Edit", "book/outline/chapters.md", agent="novelsmith:outliner",
                                   old_string="Kirsi's plan", new_string="x"), "deny")
        self.assertIsNone(self.hook("Edit", "book/outline/chapters.md", agent="novelsmith:outliner",
                                    old_string="Kirsi\u2019s plan", new_string="x"))

    def test_inexact_edit_turning_plain_anchor_text_into_a_heading(self):
        acts = self.book / "outline/acts.md"
        acts.write_text(acts.read_text(encoding="utf-8") + "\u201cNote\u201d \u2693 Decision: culprit X\n",
                        encoding="utf-8")
        self.assertEqual(self.hook("Edit", "book/outline/acts.md", agent="novelsmith:story-architect",
                                   old_string='"Note" ', new_string="## "), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/acts.md", old_string='"Note" ', new_string="## "), "ask")

    # --- TEST-3: MultiEdit and replace_all ----------------------------------
    def test_multiedit(self):
        edits = [{"old_string": "exposure on the ice road", "new_string": "at the ferry"},
                 {"old_string": "harbour master's sister", "new_string": "harbour master"}]
        self.assertEqual(self.hook("MultiEdit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   edits=edits), "deny")
        self.assertEqual(self.hook("MultiEdit", "book/bible/premise.md", edits=edits), "ask")
        self.assertIsNone(self.hook("MultiEdit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                    edits=edits[:1]))

    def test_replace_all_reaching_anchor_denied(self):
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   old_string="harbour", new_string="ferry", replace_all=True), "deny")

    # --- DES-1 / TEST-6: agent identity ---------------------------------------
    def test_unregistered_novelsmith_agent_denied(self):
        self.assertEqual(self.hook("Write", "book/manuscript/ch01/s01.md", agent="novelsmith:scene-drafter",
                                   content="x"), "deny")

    def test_other_plugins_same_name_gets_no_scope(self):
        self.assertEqual(self.hook("Write", "book/bible/world/x.md", agent="otherplugin:worldbuilder", content="x"),
                         "deny")

    def test_scopes_match_agent_files(self):
        self.assertEqual(set(guard_module().AGENT_SCOPES), {p.stem for p in (ROOT / "agents").glob("*.md")})

    # --- LOOP-4: shell --------------------------------------------------------
    def bash(self, command, agent="novelsmith:outliner"):
        return self.hook("Bash", None, agent=agent, command=command)

    def test_outliner_may_run_only_the_validator(self):
        v = ROOT / "scripts" / "validate-outline.py"
        self.assertIsNone(self.bash(f'python3 "{v}" --book book'))
        self.assertIsNone(self.bash(f"python3 {v} --book book --json"))
        for cmd in (f'python3 "{v}" --book book; rm -rf book',
                    f'python3 "{v}" --book book && sed -i s/a/b/ book/outline/scenes.yaml',
                    "sed -i 's/waivers: {}/waivers: {x: y}/' book/outline/scenes.yaml",
                    'python3 -c "open(\'book/bible/premise.md\',\'w\')"',
                    f'python3 "{v}" --book book > book/bible/premise.md',
                    'python3 /tmp/validate-outline.py --book book',
                    f'python3 "{v}" --book $(touch x)'):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), "deny")

    # --- Shell for other subagents: an allowlist, not a guess ---------------------
    def test_other_subagents_get_only_simple_reads(self):
        for cmd in ("ls book", "cat book/bible/premise.md", "grep -rn Aino book", "wc -l book/outline/acts.md",
                    "head -5 book/bible/style.md", "ls /tmp"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.bash(cmd, agent="general-purpose"))
        bypasses = ("sed -i s/a/b/ book/bible/premise.md", "cd book && cat bible/premise.md",
                    "cp x BOOK/bible/style.md", "sed -i s/A/B/ */bible/premise.md", "rm -rf bo?k/bible",
                    "find . -path '*bible*' -delete", "git checkout -- .", "git clean -fd", 'rm -rf "$D/bible"',
                    "B=bo; cp x ${B}ok/bible/x", "cp x $'\\x62ook'/bible/x", "python3 /tmp/x.py", "sh x.sh",
                    "cat book/x\nrm book/bible/style.md", "ls book&&(rm -rf book/bible)", "ls book |& rm x",
                    "git diff --output=book/bible/premise.md", "tree book -o book/x", "rg --pre ./x pat book",
                    "bash -lc ls", "python3 -Bc 1", "env python3 -c 1", "printf x | python3",
                    "grep x book > book/bible/premise.md", "cat b[o]ok/x")
        for cmd in bypasses:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd, agent="general-purpose"), "deny")

    # --- The author's own shell is left to Claude Code's permission prompts --------
    def test_main_session_shell_is_not_classified(self):
        for cmd in ("ls book", "sed -i s/a/b/ book/bible/premise.md", "python3 -c 'print(1)'", "rm -rf book"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.bash(cmd, agent=None))

    def test_shell_rules_need_a_book(self):
        import shutil
        shutil.rmtree(self.book)
        self.assertIsNone(self.bash("sed -i s/a/b/ notes.txt", agent="general-purpose"))
        self.assertEqual(self.bash("sed -i s/a/b/ notes.txt"), "deny")  # novelsmith agents: validator only

    # --- GBUG-1 / GSEC-1 / RES-1 / VSEC-1: crafted YAML ---------------------------
    def test_crashing_or_aliased_yaml_is_denied_not_waved_through(self):
        base = (self.book / "outline/scenes.yaml").read_text(encoding="utf-8")
        forged = base.replace("  waivers: {}", '  waivers: {compromise: "x"}')
        bomb = "".join(f"l{i}: &a{i} [" + ", ".join([f"*a{i - 1}"] * 9 if i else ["1"] * 9) + "]\n"
                       for i in range(9))
        for poison in ("x: 0x_\n", "d: 2026-02-30\n", "? [a]\n: b\n", "a: &x [*x]\n",
                       "x: " + "[" * 2000 + "]" * 2000 + "\n", "n: " + "9" * 5000 + "\n", bomb):
            with self.subTest(poison=poison[:20]):
                self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                           content=forged + poison), "deny")

    def test_poisoned_file_on_disk_cannot_be_used_to_launder_waivers(self):
        scenes = self.book / "outline/scenes.yaml"
        clean = scenes.read_text(encoding="utf-8")
        scenes.write_text(clean.replace("  waivers: {}", '  waivers: {compromise: "x"}') + "x: 0x_\n",
                          encoding="utf-8")
        laundered = clean.replace("  waivers: {}", '  waivers: {compromise: "x"}')
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   content=laundered), "deny")

    # --- TEST-2: repairing an unreadable manifest ---------------------------------
    def test_repair_of_unreadable_manifest(self):
        scenes = self.book / "outline/scenes.yaml"
        good = scenes.read_text(encoding="utf-8")
        scenes.write_text("book:\n  title: x\n    oops: 1\n", encoding="utf-8")
        self.assertIsNone(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=good))
        forged = good.replace("  waivers: {}", '  waivers: {compromise: "x"}')
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   content=forged), "deny")
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", content=forged), "ask")

    def test_guard_failure_denies_subagents_but_not_the_author(self):
        self.assertEqual(self.hook("Write", None, agent="novelsmith:outliner", tool_input_override="x"), "deny")

    # --- GBUG-3 / LOOP-3: inexact edit that plants a ⚓ section --------------------
    def test_inexact_edit_adding_an_anchor_denied(self):
        acts = self.book / "outline/acts.md"
        acts.write_text(acts.read_text(encoding="utf-8") + "Kirsi’s note\n", encoding="utf-8")
        # straight quotes do not match the file exactly, but the real Edit tool would apply this
        self.assertEqual(self.hook("Edit", "book/outline/acts.md", agent="novelsmith:story-architect",
                                   old_string="Kirsi's note", new_string="## ⚓ Anchored\n- forged"), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/acts.md", agent="novelsmith:story-architect",
                                   old_string="Kirsi’s note", new_string="## ⚓ Anchored\n- forged"), "deny")

    # --- GSEC-3: hiding a ⚓ section inside a comment ------------------------------
    def test_wrapping_an_anchor_in_a_comment_denied(self):
        text = (self.book / "bible/premise.md").read_text(encoding="utf-8")
        hidden = text.replace("## ⚓ Anchored", "<!--\n## ⚓ Anchored") + "\n-->\n## Notes\n"
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=hidden), "deny")

    # --- LOOP-2: genre and structure settings ------------------------------------
    def test_premise_settings_are_author_owned(self):
        premise = self.book / "bible/premise.md"
        text = premise.read_text(encoding="utf-8")
        for old, new in (("- Base genre: mystery", "- Base genre: literary"),
                         ("- Subgenre / variant: Finnish crime", "- Subgenre / variant: cozy")):
            with self.subTest(new=new):
                self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                           content=text.replace(old, new)), "deny")
        # A commented-out decoy changes nothing the validator reads, so it is harmless.
        self.assertIsNone(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                    content=text.replace("# Premise\n", "# Premise\n<!--\n- Base genre: literary\n-->\n")))
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", old_string="- Base genre: mystery",
                                   new_string="- Base genre: literary"), "ask")

    def test_anchored_structure_beats_a_decoy_line(self):
        premise = self.book / "bible/premise.md"
        premise.write_text(premise.read_text(encoding="utf-8").replace(
            "## ⚓ Anchored\n", "## ⚓ Anchored\n- Structural model: arc\n"), encoding="utf-8")
        decoy = premise.read_text(encoding="utf-8").replace(
            "- Base genre: mystery", "- Base genre: mystery\n- Structural model: kishotenketsu")
        # The guard has nothing to protect (the anchored value still decides) ...
        self.assertIsNone(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                    content=decoy))
        # ... because the shared reader takes the ⚓ value first.
        self.assertEqual(guard_module().ns_book.book_setting(decoy, "Structural model"), "arc")

    def test_premise_settings_may_be_filled_when_empty(self):
        premise = self.book / "bible/premise.md"
        premise.write_text(premise.read_text(encoding="utf-8").replace(
            "- Subgenre / variant: Finnish crime", "- Subgenre / variant: (e.g. Nordic noir, cozy)"), encoding="utf-8")
        self.assertIsNone(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                    old_string="(e.g. Nordic noir, cozy)", new_string="Finnish crime"))

    def test_bad_input_fails_open(self):
        p = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, "")


    # --- GSEC-1: the guard decides fast on adversarial text, or denies ------------
    def test_pathological_heading_is_decided_quickly(self):
        import time
        text = (self.book / "bible/premise.md").read_text(encoding="utf-8")
        poison = "# a" + " " * 20000 + "x\n"
        start = time.monotonic()
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=text.replace("harbour master's sister", "ferryman") + poison), "deny")
        self.assertLess(time.monotonic() - start, 3)
        scenes = (self.book / "outline/scenes.yaml").read_text(encoding="utf-8")
        start = time.monotonic()
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   content=scenes.replace("  waivers: {}", '  waivers: {beats: "x"}')
                                   + "#" + " " * 15000 + "x\n" + "<!--" * 40000 + "\n"), "deny")
        self.assertLess(time.monotonic() - start, 3)

    def test_oversized_subagent_content_denied(self):
        self.assertEqual(self.hook("Write", "book/outline/chapters.md", agent="novelsmith:outliner",
                                   content="x" * 1_000_001), "deny")
        self.assertEqual(self.hook("Write", "book/outline/chapters.md", agent="novelsmith:outliner",
                                   content="ok\n" + "y" * 20_001 + "\n"), "deny")
        self.assertIsNone(self.hook("Write", "book/outline/chapters.md", agent="novelsmith:outliner",
                                    content="ok\n" * 1000))

    # --- GSEC-2: line endings are seen the way the readers see them --------------------
    def test_lone_carriage_returns_cannot_hide_a_section(self):
        text = (self.book / "bible/premise.md").read_text(encoding="utf-8")
        sneaky = text.replace("## Genre\n", "## Genre\n\r## \u2693 Note\r- Base genre: romance\r")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=sneaky), "deny")
        crlf = text.replace("\n", "\r\n")  # Windows line endings alone change nothing
        self.assertIsNone(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                    content=crlf))

    # --- DES-1: guard and validator read settings through one normaliser -------------
    def test_lookalike_genre_spelling_counts_as_a_change(self):
        text = (self.book / "bible/premise.md").read_text(encoding="utf-8")
        for spelling in ("my\u017ftery", "MYSTERY", "Mystery"):
            with self.subTest(spelling=spelling):
                # long-s folds to "mystery" for both guard and validator, so it is no change either way
                self.assertIsNone(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                            content=text.replace("- Base genre: mystery", f"- Base genre: {spelling}")))
        g = guard_module()
        self.assertEqual(g.ns_book.book_settings(text.replace("mystery", "my\u017ftery"))["genre"], "mystery")

    # --- GBUG-8: UTF-8 in, ASCII out, whatever the console encoding -------------------
    def test_windows_console_encoding(self):
        payload = json.dumps({"hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": "Write",
                              "agent_id": "a1", "agent_type": "novelsmith:story-architect",
                              "tool_input": {"file_path": str(self.book / "outline/acts.md"),
                                             "content": "# Acts\n## \u2693 Anchored\n- forged\n"}},
                             ensure_ascii=False).encode("utf-8")
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project), "PYTHONIOENCODING": "cp1252"}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        main = json.dumps({"hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": "Edit",
                           "tool_input": {"file_path": str(self.book / "bible/premise.md"),
                                          "old_string": "harbour master's sister", "new_string": "x"}}).encode()
        p = subprocess.run([sys.executable, str(SCRIPT)], input=main, capture_output=True, env=env)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    # --- TEST-1: Rule 1 for subagents from other plugins -----------------------------
    def test_other_subagents_are_held_to_rule_one(self):
        g = "general-purpose"
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent=g, old_string="  waivers: {}",
                                   new_string='  waivers: {subplot: "x"}'), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent=g, old_string="turn: turn 3",
                                   new_string="turn: a: b"), "deny")
        self.assertEqual(self.hook("Write", "book/outline/acts.md", agent=g,
                                   content="# Acts\n## \u2693 Anchored\n- forged\n"), "deny")
        self.assertIsNone(self.hook("Edit", "book/outline/scenes.yaml", agent=g, old_string="turn: turn 3",
                                    new_string="turn: she sees the key"))

    # --- Round 4 LOOP-1 / LOOP-2: every ⚓ line is author text ---------------------
    def test_anchor_headings_the_reader_does_not_parse_are_still_anchor_text(self):
        text = self.premise_text()
        for form in ("   ## ⚓ Anchored\n", "⚓ Anchored\n---\n", "> ## ⚓ Anchored\n", "- ⚓ the author decided:\n"):
            forged = text.replace("## Genre\n", form + "- Ending: the ferryman did it.\n\n## Genre\n")
            with self.subTest(form=form):
                self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                           content=forged), "deny")
                self.assertEqual(self.hook("Write", "book/bible/premise.md", content=forged), "ask")

    def test_new_files_carry_only_template_anchor_lines(self):
        for rel, agent in (("book/proposals/x.md", "novelsmith:story-architect"),
                           ("book/bible/characters/new.md", "novelsmith:character-designer"),
                           ("book/summaries/ch01.md", "general-purpose")):
            with self.subTest(rel=rel):
                self.assertEqual(self.hook("Write", rel, agent=agent,
                                           content="# New\n## ⚓ Anchored: New is the killer\n"), "deny")
        self.assertIsNone(self.hook("Write", "book/critiques/outline/note.md", agent="novelsmith:outliner",
                                    content=(ROOT / "templates/critique-note.md").read_text(encoding="utf-8")))

    # --- Round 4 LOOP-3: MCP tools that name book files ---------------------------
    def mcp(self, tool_input, agent="general-purpose", tool="mcp__filesystem__write_file"):
        return self.hook(tool, None, agent=agent, tool_input_override=tool_input)

    def test_subagent_mcp_calls_must_be_read_only_tools(self):
        book_file = {"path": str(self.book / "bible/premise.md"), "content": "x"}
        for tool in ("mcp__filesystem__write_file", "mcp__filesystem__edit_file",
                     "mcp__desktop-commander__start_process", "mcp__shell__execute", "mcp__fs__writeFile",
                     "mcp__notes__get_or_create_note", "mcp__computer-use__app_click", "mcp__duckdb__query",
                     "mcp__search__click", "mcp__readonly-files__overwrite", "mcp__fs__getHTTPAndWrite"):
            with self.subTest(tool=tool):
                # the arguments do not matter: padding, ~ paths or a command string cannot hide a book path
                for inp in (book_file, {"command": "sed -i x book/bible/premise.md"},
                            {"path": "~/x/book/bible/premise.md", "pad": ["x"] * 10_001}, {}):
                    self.assertEqual(self.mcp(inp, tool=tool), "deny")
                self.assertEqual(self.mcp(book_file, tool=tool, agent="novelsmith:outliner"), "deny")
                self.assertIsNone(self.mcp(book_file, tool=tool, agent=None))  # the author's own call
        for tool in ("mcp__filesystem__read_text_file", "mcp__filesystem__list_directory", "mcp__github__search_issues",
                     "mcp__fs__readFile", "mcp__d1__d1_databases_list"):
            with self.subTest(tool=tool):
                self.assertIsNone(self.mcp(book_file, tool=tool))

    def test_mcp_rule_needs_a_book(self):
        import shutil
        shutil.rmtree(self.book)
        self.assertIsNone(self.mcp({"path": "book/bible/premise.md", "content": "x"}))

    # --- Round 4 G-BUG-1: waivers in an unreadable manifest -----------------------
    def test_unreadable_manifest_with_waivers_is_the_authors_to_repair(self):
        scenes = self.book / "outline/scenes.yaml"
        good = scenes.read_text(encoding="utf-8")
        waived = good.replace("  waivers: {}", '  waivers: {open_thread: "left open on purpose"}')
        scenes.write_text(waived.replace("book:\n", "book:\n\ttab: 1\n", 1), encoding="utf-8")
        for content in (good, waived):
            with self.subTest(keeps_waivers=content == waived):
                self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                           content=content), "deny")
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", content=waived), "ask")

    # --- Round 4 G-SEC-1 / G-BUG-4: deep or duplicated flow YAML -------------------
    def test_deep_flow_yaml_is_decided_quickly(self):
        import time
        base = (self.book / "outline/scenes.yaml").read_text(encoding="utf-8")
        forged = base.replace("  waivers: {}", '  waivers: {open_thread: "x"}')
        deep = "".join(f"k{n}: " + "[" * 300 + "]" * 300 + "\n" for n in range(50))
        start = time.monotonic()
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   content=forged + deep), "deny")
        self.assertLess(time.monotonic() - start, 3)

    def test_flow_map_duplicate_waivers_denied(self):
        text = (self.book / "outline/scenes.yaml").read_text(encoding="utf-8")
        decoy = text.replace("book:\n", 'book2: {waivers: {open_thread: "author agreed"}, waivers: {}}\nbook:\n')
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=decoy),
                         "deny")

    def test_deadline_kills_a_slow_check(self):
        import time
        g = guard_module()
        g.DEADLINE = 0.2
        g.CHILD = [sys.executable, "-c", "import time; time.sleep(5)"]  # stands in for one long C call
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            g.run(b"{}")
        self.assertLess(time.monotonic() - start, 2)

    # --- Round 4 RES-2: growth is measured before an edit is applied --------------
    def test_replace_all_growth_past_the_cap_denied(self):
        (self.book / "outline/chapters.md").write_text("a\n" * 1000, encoding="utf-8")
        self.assertEqual(self.hook("Edit", "book/outline/chapters.md", agent="novelsmith:outliner",
                                   old_string="a", new_string="b" * 2000, replace_all=True), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/chapters.md",
                                   old_string="a", new_string="b" * 2000, replace_all=True), "ask")

    # --- Round 5: ⚓ forms, places and comments ---------------------------------------
    def test_anchor_written_as_a_character_reference_is_anchor_text(self):
        forged = self.premise_text().replace("## Genre\n", "## &#9875; Anchored\n- Ending: the ferryman did it.\n\n"
                                             "## Genre\n")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=forged), "deny")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", content=forged), "ask")
        self.assertEqual(self.hook("Write", "book/bible/characters/x.md", agent="novelsmith:character-designer",
                                   content="# X\n## &#x2693; Anchored\n- X is the killer\n"), "deny")

    def test_bodies_under_commonmark_anchor_headings_are_protected(self):
        premise = self.book / "bible/premise.md"
        for heading in ("   ## ⚓ Ending", "⚓ Ending\n--------", "> ## ⚓ Ending"):
            with self.subTest(heading=heading):
                text = self.premise_text().split("## ⚓ Anchored")[0] + heading + "\n- the ferryman did it\n"
                premise.write_text(text, encoding="utf-8")
                self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                           old_string="- the ferryman did it", new_string="- the sister did it"),
                                 "deny")

    def test_empty_heading_does_not_end_an_anchor_section(self):
        for split in ("## \n", "##\n", "## <!-- -->\n", "## \u200b\n"):
            with self.subTest(split=repr(split)):
                self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                           old_string="- The culprit is the harbour master's sister.\n",
                                           new_string="- The culprit is the harbour master's sister.\n" + split
                                           + "- Ending: Riikka walks free.\n"), "deny")

    def test_anchor_lines_cannot_be_moved_hidden_or_dropped(self):
        premise = self.book / "bible/premise.md"
        text = self.premise_text().replace("- Outcome of the climax: exposure on the ice road",
                                           "- Outcome of the climax: ⚓ exposure on the ice road")
        premise.write_text(text, encoding="utf-8")
        line = "- Outcome of the climax: ⚓ exposure on the ice road\n"
        for new in (text.replace(line, "<!--\n" + line + "-->\n- Outcome of the climax: a quiet arrest\n"),
                    text.replace(line, "").replace("## Genre\n", "## Genre\n" + line),
                    text.replace(line, ""),
                    text.replace("## ⚓ Anchored", "<!--\n## ⚓ Anchored")):  # an unclosed comment hides the rest
            with self.subTest(new=new):
                self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                           content=new), "deny")
                self.assertEqual(self.hook("Write", "book/bible/premise.md", content=new), "ask")
        scenes = self.book / "outline/scenes.yaml"
        yaml_text = scenes.read_text(encoding="utf-8")
        first, second = [p for p in yaml_text.split("  - id: ") if p.startswith("ch")][:2]
        marked = yaml_text.replace(first, first.replace("    pov: ", "    pov: Aino  # ⚓\n    old_pov: ", 1), 1)
        scenes.write_text(marked, encoding="utf-8")
        moved = marked.replace("    pov: Aino  # ⚓\n    old_pov: ", "    pov: ", 1).replace(
            "  - id: " + second, "  - id: " + second.replace("    pov: ", "    pov: Aino  # ⚓\n    old_pov: ", 1), 1)
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=moved),
                         "deny")

    def test_anchor_denial_names_the_line(self):
        text = self.premise_text()
        decision, why = self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                  content=text.replace("## ⚓ Anchored", "## ⚓ Anchored decisions"), reason=True)
        self.assertEqual(decision, "deny")
        self.assertIn('"## ⚓ Anchored decisions"', why)
        self.assertIn("Keep every existing ⚓ line exactly as it is", why)

    def test_new_file_anchor_allowlist_matches_the_templates(self):
        g = guard_module()
        for path in sorted((ROOT / "templates").glob("*")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(template=path.name):
                self.assertIsNone(g.anchor_change("", text, exists=False))
        # and every allowed entry still comes from a template, so a reworded template leaves no stale entry
        lines, sections = set(), set()
        for path in (ROOT / "templates").glob("*.md"):
            line_views, section_views = g.anchor_views(path.read_text(encoding="utf-8"))
            lines |= {line for _, line in line_views[0]}
            sections |= {s for view in section_views for s in view}
        self.assertEqual(lines, g.NEW_FILE_ANCHOR_LINES)
        self.assertEqual(sections | {("## ⚓ Anchored", "")}, g.NEW_FILE_ANCHOR_SECTIONS)

    # --- Round 5: repairing a template-based manifest ------------------------------------
    def test_outliner_may_repair_a_manifest_whose_waivers_are_empty(self):
        scenes = self.book / "outline/scenes.yaml"
        good = scenes.read_text(encoding="utf-8")
        self.assertIn("  waivers: {}", good)
        broken = good.replace("turn: turn 3", "turn: a: b")
        for empty in ("  waivers: {}", "  waivers: {}   # AUTHOR ONLY", "  waivers:"):
            with self.subTest(empty=empty):
                scenes.write_text(broken.replace("  waivers: {}", empty), encoding="utf-8")
                self.assertIsNone(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                            content=good))
                self.assertIsNone(self.hook("Write", "book/outline/scenes.yaml", content=good))
        for held in ("  waivers:\n    open_thread: x", '  "waiv\\x65rs": {open_thread: x}\n  waivers: {}',
                     "  waivers:\n  # approved after the March draft\n    open_thread: x",
                     "  waivers:\n# keep until draft 2\n    open_thread: x",
                     "  waivers:\n\topen_thread: x", "  waivers: {}\n    open_thread: x"):
            with self.subTest(held=held):
                scenes.write_text(broken.replace("  waivers: {}", held), encoding="utf-8")
                self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                           content=good), "deny")
                self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", content=good), "ask")

    def test_repair_denial_says_why_the_waivers_are_in_doubt(self):
        scenes = self.book / "outline/scenes.yaml"
        good = scenes.read_text(encoding="utf-8")
        scenes.write_text(good.replace("turn: turn 3", 'turn: a: b "she said \\"no\\""'), encoding="utf-8")
        decision, why = self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=good,
                                  reason=True)
        self.assertEqual(decision, "deny")
        self.assertIn("backslash", why)

    # --- Round 6: forged ⚓ text appended after a copy of the last one ------------------
    def test_copy_of_the_last_anchor_then_a_forged_one_is_denied(self):
        text = (ROOT / "templates/premise.md").read_text(encoding="utf-8")
        premise = self.book / "bible/premise.md"
        premise.write_text(text, encoding="utf-8")
        tail = text[text.index("## Open questions for the author"):]
        forged = text + "\n" + tail + "\n## ⚓ Anchored\n- Protagonist: Elara\n- Ending: forged\n"
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=forged), "deny")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", content=forged), "ask")
        sheet = self.book / "bible/characters/aino-hakkinen.md"
        sheet.write_text(sheet.read_text(encoding="utf-8") + "- a ⚓ keep\n", encoding="utf-8")
        self.assertEqual(self.hook("Write", "book/bible/characters/aino-hakkinen.md",
                                   agent="novelsmith:character-designer",
                                   content=sheet.read_text(encoding="utf-8") + "- a ⚓ keep\n- b ⚓ forged\n"), "deny")

    def test_anchor_lines_cannot_be_swapped(self):
        premise = self.book / "bible/premise.md"
        text = self.premise_text().replace("## ⚓ Anchored\n", "## Decided\n- ⚓ one\n- ⚓ two\n\n## ⚓ Anchored\n")
        premise.write_text(text, encoding="utf-8")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                   content=text.replace("- ⚓ one\n- ⚓ two", "- ⚓ two\n- ⚓ one")), "deny")

    # --- Round 6: only a clear heading ends a ⚓ section ---------------------------------
    def test_text_that_only_looks_like_a_heading_keeps_the_anchor_section_open(self):
        premise = self.book / "bible/premise.md"
        base = self.premise_text()
        culprit = "- The culprit is the harbour master's sister.\n"
        for split in ("- a wrapped decision,\n  and its second line.\n---\n",
                      "- Ending: Riikka walks free, and the town\nnever learns why.\n---\n",
                      "> ## Riikka's letter\n", "```\nnot a heading\n---\n## x\n```\n", "    ## indented code\n",
                      "> quoted\nlazy line\n===\n"):
            with self.subTest(split=split):
                premise.write_text(base.replace(culprit, split + culprit), encoding="utf-8")
                self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                           old_string=culprit, new_string="- The culprit is the ferryman.\n"), "deny")
        # a heading every reader sees still ends the section
        for clear in ("\n## Notes\n", "\nNotes\n-----\n"):
            with self.subTest(clear=clear):
                premise.write_text(base + clear + "- free text\n", encoding="utf-8")
                self.assertIsNone(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                            old_string="- free text", new_string="- other text"))

    def test_yaml_comments_are_not_headings(self):
        scenes = self.book / "outline/scenes.yaml"
        text = scenes.read_text(encoding="utf-8")
        marked = text.replace("  - id: ", "  # ⚓ keep this scene\n  - id: ", 1)
        scenes.write_text(marked, encoding="utf-8")
        self.assertIsNone(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                    content=marked.replace("word_target: 1800", "word_target: 2000")))

    # --- Round 6: a ⚓ line's place ----------------------------------------------------------
    def test_sections_may_be_added_around_an_anchor_heading(self):
        text = self.premise_text()
        for added in ("### Notes\n- a note\n\n", "## Extra\n- more\n\n"):
            with self.subTest(added=added):
                self.assertIsNone(self.hook("Write", "book/bible/premise.md", agent="novelsmith:story-architect",
                                            content=text.replace("## ⚓ Anchored", added + "## ⚓ Anchored")))

    def test_moving_an_anchor_line_is_named_as_a_move(self):
        scenes = self.book / "outline/scenes.yaml"
        text = scenes.read_text(encoding="utf-8")
        marked = text.replace("    pov: Aino\n", "    pov: Aino  # ⚓\n", 1)
        scenes.write_text(marked, encoding="utf-8")
        renamed = marked.replace("  - id: ch01-s01", "  - id: ch01-s09", 1)
        decision, why = self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner", content=renamed,
                                  reason=True)
        self.assertEqual(decision, "deny")
        self.assertIn('would move from under "- id: ch01-s01" to under "- id: ch01-s09"', why)
        # a comment above it is not its place
        self.assertIsNone(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                    content=marked.replace("    pov: Aino  # ⚓", "    # POV fixed\n    pov: Aino  # ⚓")))

    def test_anchor_shortcode_counts_as_anchor(self):
        self.assertEqual(self.hook("Write", "book/bible/characters/x.md", agent="novelsmith:character-designer",
                                   content="# X\n## :anchor: Anchored\n- X is the killer\n"), "deny")

    def test_author_call_fails_open_when_the_check_crashes(self):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": "Write",
                   "tool_input": "x"}
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True, text=True,
                           env=env)
        self.assertEqual((p.returncode, p.stdout), (1, ""))
        self.assertTrue(p.stderr.startswith("guard-canon:"), p.stderr)

    # --- Round 7: line endings the guard cannot see ------------------------------------
    def test_carriage_returns_that_could_move_an_edit_are_denied(self):
        culprit = "the harbour master's sister."
        planted = self.premise_text().replace("# Premise\n", f"# Premise\nnote: {culprit}\r")
        a = "novelsmith:story-architect"
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent=a, content=planted), "deny")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent=a, old_string="# Premise\n",
                                   new_string="# Premise\rnote\n"), "deny")
        premise = self.book / "bible/premise.md"
        premise.write_bytes(planted.encode("utf-8"))  # a lone \r already in the file
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent=a, old_string=culprit + "\n",
                                   new_string="the ferryman.\n"), "deny")
        scenes = self.book / "outline/scenes.yaml"
        crlf = scenes.read_text(encoding="utf-8").replace("\n", "\r\n")
        scenes.write_bytes(crlf.encode("utf-8"))
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   old_string="\n  target_words", new_string="  waivers: {open_thread: x}\n  target_words"),
                         "deny")
        # an ordinary edit of a Windows-line-ending file is fine
        self.assertIsNone(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                    old_string="word_target: 1800", new_string="word_target: 2000"))

    def test_an_old_string_that_matches_twice_is_not_checked_as_once(self):
        premise = self.book / "bible/premise.md"
        text = self.premise_text().replace("# Premise\n", "# Premise\nThe culprit is the harbour master's sister.\n")
        premise.write_text(text, encoding="utf-8")
        edit = dict(old_string="The culprit is the harbour master's sister.", new_string="The culprit is the ferryman.")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect", **edit), "deny")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", **edit), "ask")

    # --- Round 7: other ways in ----------------------------------------------------------
    @unittest.skipUnless(Path("/System/Volumes/Data").is_dir(), "macOS firmlinks only")
    def test_firmlink_path_reaches_the_book(self):
        firm = "/System/Volumes/Data" + str(self.book / "bible/premise.md")
        if not Path(firm).exists():
            self.skipTest("the temp folder is not on the data volume")
        forged = self.premise_text().replace("harbour master's sister", "ferryman")
        self.assertEqual(self.hook("Write", firm, agent="general-purpose", raw=True, content=forged), "deny")
        self.assertEqual(self.hook("Write", firm, raw=True, content=forged), "ask")

    def test_powershell_and_notebooks_are_held_to_the_rules(self):
        self.assertEqual(self.hook("PowerShell", None, agent="general-purpose",
                                   tool_input_override={"command": "Set-Content book/bible/premise.md x"}), "deny")
        self.assertIsNone(self.hook("PowerShell", None, tool_input_override={"command": "Get-ChildItem"}))
        self.assertEqual(self.hook("NotebookEdit", None, agent="general-purpose",
                                   tool_input_override={"notebook_path": str(self.book / "outline/x.ipynb"),
                                                        "new_source": "x"}), "deny")
        self.assertIsNone(self.hook("NotebookEdit", None, agent="general-purpose",
                                    tool_input_override={"notebook_path": str(self.project / "src/x.ipynb"),
                                                         "new_source": "x"}))

    def test_another_tools_book_folder_is_not_a_book_project(self):
        import shutil
        shutil.rmtree(self.book)
        (self.project / "book/html").mkdir(parents=True)  # e.g. mdBook's output
        self.assertIsNone(self.bash("git status", agent="general-purpose"))
        self.assertIsNone(self.mcp({"path": "x"}, tool="mcp__filesystem__write_file"))
        self.assertIsNone(self.hook("Write", "book/html/index.html", agent="general-purpose", content="<p>x</p>"))

    def test_validator_runs_from_a_plugin_folder_with_shell_characters(self):
        odd = self.project / "Writing (2026)" / "com~apple~CloudDocs"
        odd.mkdir(parents=True)
        (odd / "novelsmith").symlink_to(ROOT)
        script = odd / "novelsmith/scripts/validate-outline.py"
        self.assertIsNone(self.bash(f'python3 "{script}" --book book'))
        self.assertIsNone(self.bash(f"python3 '{script}' --book book --json"))
        for bad in (f'python3 "{script}$(id)" --book book', f'python3 "{script}" --book book; rm -rf book',
                    f'python3 {script} --book book', f'python3 "{script}" --book "book`id`"'):
            with self.subTest(bad=bad):
                self.assertEqual(self.bash(bad), "deny")

    def test_a_check_that_cannot_finish_is_denied_or_asked_never_waved_through(self):
        import contextlib
        import io
        g = guard_module()

        def too_slow(raw):
            raise TimeoutError("took longer than 6 s")

        g.run = too_slow
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.project)
        try:
            for agent, rel, decision, code in (("novelsmith:outliner", "book/outline/chapters.md", "deny", 0),
                                               (None, "book/bible/premise.md", "ask", 0),
                                               (None, "src/app.py", None, 1)):
                payload = {"cwd": str(self.project), "tool_name": "Write",
                           "tool_input": {"file_path": str(self.project / rel), "content": "x"}}
                if agent:
                    payload.update(agent_id="a1", agent_type=agent)
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    got = g.cli(json.dumps(payload).encode())
                with self.subTest(agent=agent, rel=rel):
                    self.assertEqual(got, code)
                    printed = json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"] \
                        if out.getvalue() else None
                    self.assertEqual(printed, decision)
        finally:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)

    # --- Round 8 -------------------------------------------------------------------------------
    def test_validator_path_may_not_end_in_an_escaping_backslash(self):
        twin = self.project / "plugin/scripts"
        twin.mkdir(parents=True)
        try:
            os.link(ROOT / "scripts/validate-outline.py", twin / "validate-outline.py\\")
        except OSError:
            self.skipTest("cannot hard-link here")
        # Bash reads \" as a quote inside the string, so the rest would run as a second command
        self.assertEqual(self.bash(f'python3 "{twin}/validate-outline.py\\" --book "; echo INJECTED #"'), "deny")
        self.assertEqual(self.bash(f'python3 "{twin}/validate-outline.py\\\\" --book book'), "deny")

    def test_tools_the_guard_does_not_know_are_denied_to_subagents(self):
        monitor = {"command": "until false; do sed -i x book/bible/premise.md; done"}
        self.assertEqual(self.hook("Monitor", None, agent="general-purpose", tool_input_override=monitor), "deny")
        self.assertEqual(self.hook("Monitor", None, agent="novelsmith:outliner", tool_input_override=monitor), "deny")
        self.assertIsNone(self.hook("Monitor", None, tool_input_override=monitor))  # the author's own
        for tool in ("Read", "Grep", "WebSearch", "TodoWrite"):
            with self.subTest(tool=tool):
                self.assertIsNone(self.hook(tool, None, agent="general-purpose", tool_input_override={"x": "y"}))
        import shutil
        shutil.rmtree(self.book)
        self.assertIsNone(self.hook("Monitor", None, agent="general-purpose", tool_input_override=monitor))

    def test_a_bare_agent_name_is_novelsmiths_only_in_a_book_project(self):
        import shutil
        shutil.rmtree(self.book)
        self.assertIsNone(self.hook("Write", "src/app.py", agent="outliner", content="x"))
        self.assertIsNone(self.bash("git status", agent="outliner"))
        self.assertEqual(self.hook("Write", "src/app.py", agent="novelsmith:outliner", content="x"), "deny")

    def test_input_that_cannot_be_read_is_judged_by_its_text(self):
        deep = "[" * 200_000 + "]" * 200_000
        for raw, decision, code in (
                ('{"tool_name": "mcp__fs__write_file", "agent_id": "a1", "agent_type": "general-purpose", '
                 '"tool_input": {"x": %s}}' % deep, "deny", 0),
                (b'{"tool_name": "Write", "agent_id": "a1", "agent_type": "general-purpose", "tool_input": '
                 b'{"x": "\xff"}}', "deny", 0),
                ('{"tool_name": "Write", "tool_input": {"file_path": "book/bible/premise.md", "x": %s}}' % deep,
                 "ask", 0),
                ("not json", None, 1)):
            with self.subTest(raw=raw[:60]):
                data = raw if isinstance(raw, bytes) else raw.encode()
                p = subprocess.run([sys.executable, str(SCRIPT)], input=data, capture_output=True,
                                   env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)})
                self.assertEqual(p.returncode, code, p.stderr)
                got = json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] if p.stdout.strip() else None
                self.assertEqual(got, decision)

    def test_authors_unreadable_rewrite_that_drops_waivers_is_asked_about(self):
        scenes = self.book / "outline/scenes.yaml"
        good = scenes.read_text(encoding="utf-8")
        waived = good.replace("  waivers: {}", '  waivers: {open_thread: "left open"}')
        scenes.write_text(waived, encoding="utf-8")
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml",
                                   content=good.replace("turn: turn 3", "turn: a: b")), "ask")

    def test_line_ending_tricks_reach_the_author_and_multiedit(self):
        scenes = self.book / "outline/scenes.yaml"
        scenes.write_bytes(scenes.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
        plant = dict(old_string="\n  target_words", new_string="  waivers: {open_thread: x}\n  target_words")
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", **plant), "ask")
        self.assertEqual(self.hook("MultiEdit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   edits=[plant]), "deny")
        self.assertEqual(self.hook("MultiEdit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   edits=[{"old_string": "word_target: 1800", "new_string": "word_target: 1\r"}]),
                         "deny")
        premise = self.book / "bible/premise.md"
        culprit = "the harbour master's sister."
        premise.write_bytes(self.premise_text().replace("# Premise\n", f"# Premise\nnote: {culprit}\r")
                            .encode("utf-8"))
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", old_string=culprit + "\n",
                                   new_string="the ferryman.\n"), "ask")

    # --- Round 9 -------------------------------------------------------------------------------
    def test_subagents_can_report_back_and_plan(self):
        for agent in ("novelsmith:outliner", "general-purpose"):
            for tool, inp in (("SubagentHandback", {"message": "done"}), ("TaskCreate", {"subject": "x"}),
                              ("TaskUpdate", {"taskId": "1", "status": "completed"}), ("LSP", {"operation": "x"}),
                              ("StructuredOutput", {"result": "x"})):
                with self.subTest(agent=agent, tool=tool):
                    self.assertIsNone(self.hook(tool, None, agent=agent, tool_input_override=inp))
        # any tool the guard does not know is denied, whatever its arguments are called
        for tool, inp in (("SomeNewTool", {"query": "x"}), ("SomeNewTool", {"filePath": "book/bible/premise.md"}),
                          ("CronCreate", {"cron": "*/5 * * * *", "prompt": "rewrite book/bible/premise.md"})):
            with self.subTest(tool=tool, inp=inp):
                self.assertEqual(self.hook(tool, None, agent="general-purpose", tool_input_override=inp), "deny")
                self.assertIsNone(self.hook(tool, None, tool_input_override=inp))  # the author's own

    def test_a_main_conversation_run_as_an_agent_is_the_author(self):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": "Write",
                   "agent_type": "my-main-agent",
                   "tool_input": {"file_path": str(self.book / "bible/style.md"), "content": "# Style\n"}}
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True, text=True,
                           env=env)
        self.assertEqual((p.returncode, p.stdout), (0, ""), p.stderr)
        payload["tool_name"], payload["tool_input"] = "Bash", {"command": "git status"}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True, text=True,
                           env=env)
        self.assertEqual((p.returncode, p.stdout), (0, ""), p.stderr)

    def test_a_home_relative_path_reaches_the_book(self):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.project / "src"), "tool_name": "Write",
                   "agent_id": "a1", "agent_type": "general-purpose",
                   "tool_input": {"file_path": "~/book/bible/premise.md", "content": "x"}}
        p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True, text=True,
                           env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.project), "HOME": str(self.project)})
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_folder_in_the_book_that_links_elsewhere_is_still_the_book(self):
        import shutil
        series = self.project / "series-world"
        shutil.move(str(self.book / "bible/world"), str(series)) if (self.book / "bible/world").exists() \
            else series.mkdir()
        (series / "harbour.md").write_text("# Harbour\n## ⚓ Anchored\n- The harbour freezes in March.\n",
                                          encoding="utf-8")
        (self.book / "bible/world").symlink_to(series)
        wipe = "# Harbour\n- The harbour never freezes.\n"
        self.assertEqual(self.hook("Write", "book/bible/world/harbour.md", agent="general-purpose", content=wipe),
                         "deny")
        self.assertEqual(self.hook("Write", "book/bible/world/harbour.md", agent="novelsmith:worldbuilder",
                                   content=wipe), "deny")  # the ⚓ section, not the scope, stops it
        self.assertEqual(self.hook("Write", "book/bible/world/harbour.md", content=wipe), "ask")
        self.assertIsNone(self.hook("Write", "book/bible/world/port.md", agent="novelsmith:worldbuilder",
                                    content="# Port\n"))

    def test_yaml_line_breaks_the_guard_cannot_see_are_refused(self):
        scenes = self.book / "outline/scenes.yaml"
        text = scenes.read_text(encoding="utf-8")
        scenes.write_text(text.replace("    pov: Aino\n", "    pov: Aino\n    goal_note: ⚓ Ann must leave\n", 1),
                          encoding="utf-8")
        for brk in ("\u2028", "\x85", "\u2029"):
            with self.subTest(brk=repr(brk)):
                edit = dict(old_string="    pov: Aino\n    goal_note:",
                            new_string=f"    pov: Aino{brk}  - id: ch99-s01\n    goal_note:")
                self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner", **edit),
                                 "deny")
                self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", **edit), "ask")

    def test_an_anchored_yaml_value_cannot_be_swallowed_by_a_quote(self):
        scenes = self.book / "outline/scenes.yaml"
        text = scenes.read_text(encoding="utf-8")
        marked = text.replace("    pov: Aino\n", "    pov: Aino\n    goal_note: ⚓ Ann must leave\n    mood: calm\n", 1)
        scenes.write_text(marked, encoding="utf-8")
        swallowed = marked.replace("    pov: Aino\n    goal_note:", "    pov: 'Aino\n    goal_note:", 1).replace(
            "    mood: calm\n", "    mood: calm'\n", 1)
        self.assertEqual(self.hook("Write", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                   content=swallowed), "deny")
        g = guard_module()
        self.assertNotEqual(g.anchored_values({"scenes": [{"id": "s1", "goal": "⚓ x"}]}),
                            g.anchored_values({"scenes": [{"id": "s1", "pov": "Ann goal: ⚓ x"}]}))
        self.assertEqual(g.anchored_values({"scenes": [{"id": "s1", "goal": "⚓ x"}, {"id": "s2"}]}),
                         g.anchored_values({"scenes": [{"id": "s2"}, {"id": "s1", "goal": "⚓ x"}]}))

    # --- Round 10 ------------------------------------------------------------------------------
    def test_a_byte_order_mark_cannot_slip_a_setting_or_hide_a_heading(self):
        a = "novelsmith:story-architect"
        forged = dict(old_string="# Premise", new_string="\ufeff- Base genre: romance\n# Premise")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent=a, **forged), "deny")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent=a,
                                   content="\ufeff- Base genre: romance\n" + self.premise_text()), "deny")
        # a file the author saved with a BOM: its first-line ⚓ heading still protects its body
        sheet = self.book / "bible/characters/anna.md"
        sheet.write_bytes("\ufeff# ⚓ Anna Virtanen\n- Anna never lies to Aino.\n".encode("utf-8"))
        self.assertEqual(self.hook("Edit", "book/bible/characters/anna.md", agent="novelsmith:character-designer",
                                   old_string="- Anna never lies to Aino.", new_string="- Anna lies to everyone."),
                         "deny")
        g = guard_module()
        text = g.ns_book.normalize("\ufeff- Base genre: romance\n## Genre\n- Base genre: mystery\n")
        self.assertEqual(g.ns_book.book_settings(text)["genre"], "romance")  # the first line, as the validator reads it

    def test_a_symlinked_book_folder_written_through_its_real_location(self):
        series = self.project / "series-bible"
        series.mkdir()
        (series / "harbour.md").write_text("# Harbour\n## ⚓ Anchored\n- The harbour freezes in March.\n",
                                          encoding="utf-8")
        (self.book / "bible/world").mkdir(parents=True, exist_ok=True)
        (self.book / "bible/world/shared").symlink_to(series)
        real = str(series / "harbour.md")
        wipe = "# Harbour\n- The harbour never freezes.\n"
        self.assertEqual(self.hook("Write", real, agent="general-purpose", raw=True, content=wipe), "deny")
        self.assertEqual(self.hook("Write", real, raw=True, content=wipe), "ask")
        decision, why = self.hook("Write", str(series / "port.md"), agent="novelsmith:worldbuilder", raw=True,
                                  reason=True, content="# Port\n")
        self.assertEqual(decision, "deny")
        self.assertIn("Write it by that path", why)
        self.assertIn("book/bible/world/shared/port.md", why)
        self.assertIsNone(self.hook("Write", "book/bible/world/shared/port.md", agent="novelsmith:worldbuilder",
                                    content="# Port\n"))

    def test_subagent_identity_comes_from_agent_id(self):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)}

        def decide(**fields):
            payload = {"hook_event_name": "PreToolUse", "cwd": str(self.project), **fields}
            p = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                               text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] if p.stdout.strip() else None

        write = dict(tool_name="Write", tool_input={"file_path": str(self.book / "bible/style.md"), "content": "x"})
        sed = dict(tool_name="Bash", tool_input={"command": "sed -i x book/bible/premise.md"})
        mcp = dict(tool_name="mcp__fs__write_file", tool_input={"path": "x"})
        for who in ({"agent_id": "a1"}, {"agent_id": "a1", "agent_type": ""}):
            with self.subTest(who=who):
                for call in (write, sed, mcp):
                    self.assertEqual(decide(**who, **call), "deny")
        self.assertIsNone(decide(agent_id="", agent_type="general-purpose", **write))  # no id: the author

    def test_progress_md_alone_marks_a_book_project(self):
        (self.book / "outline/scenes.yaml").unlink()
        (self.book / "progress.md").write_text("# Progress\n", encoding="utf-8")
        self.assertEqual(self.hook("Write", "book/bible/premise.md", agent="general-purpose", content="# P\n"),
                         "deny")
        self.assertEqual(self.bash("sed -i s/a/b/ notes.txt", agent="general-purpose"), "deny")
        (self.book / "progress.md").unlink()
        self.assertIsNone(self.bash("sed -i s/a/b/ notes.txt", agent="general-purpose"))

    # --- Round 11 ------------------------------------------------------------------------------
    def test_an_invisible_ufeff_in_an_edit_is_refused(self):
        a = "novelsmith:story-architect"
        # only the U+FEFF check catches this: the heading line would stop being a heading
        unmake = dict(old_string="## ⚓ Anchored", new_string="\ufeff## ⚓ Anchored")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent=a, **unmake), "deny")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", **unmake), "ask")
        self.assertEqual(self.hook("MultiEdit", "book/bible/premise.md", agent=a, edits=[
            {"old_string": "## Genre", "new_string": "## Genre"}, unmake]), "deny")
        # a zero-width no-break space in the middle of a file: an old_string of just that character
        sheet = self.book / "bible/characters/anna.md"
        sheet.write_text("# Anna\n## ⚓ Anchored\n- Anna never\ufeff lies.\n", encoding="utf-8")
        target = dict(old_string="\ufeff", new_string=" lies to everyone; she")
        self.assertEqual(self.hook("Edit", "book/bible/characters/anna.md", agent="novelsmith:character-designer",
                                   **target), "deny")
        self.assertEqual(self.hook("Edit", "book/bible/characters/anna.md", **target), "ask")
        decision, why = self.hook("Edit", "book/bible/premise.md", agent=a, reason=True, **unmake)
        self.assertIn("Leave that character out", why)

    def _shared_bible(self):
        series = self.project / "series-bible"
        series.mkdir()
        (series / "harbour.md").write_text("# Harbour\n## ⚓ Anchored\n- The harbour freezes in March.\n",
                                          encoding="utf-8")
        (self.book / "bible/world").mkdir(parents=True, exist_ok=True)
        (self.book / "bible/world/shared").symlink_to(series)
        return series

    def _folders(self, parent, n=5_100):
        for i in range(n):
            (parent / f"d{i:04}").mkdir(parents=True)

    def test_plain_files_never_make_the_symlink_walk_give_up(self):
        series = self._shared_bible()
        for n in range(5_100):
            (self.book / f"n{n:04}.md").write_text("x", encoding="utf-8")
        self.assertEqual(self.hook("Write", str(series / "harbour.md"), agent="general-purpose", raw=True,
                                   content="# Harbour\n- The harbour never freezes.\n"), "deny")
        (self.book / "bible/world/shared").unlink()
        self.assertIsNone(self.hook("Write", "src/app.py", agent="general-purpose", content="x"))
        self.assertIsNone(self.hook("Write", "src/app.py", content="x"))

    def test_a_symlink_walk_over_too_many_folders_cannot_tell(self):
        self._shared_bible()
        self._folders(self.book / "research")
        guard = guard_module()
        rel = guard.through_link((self.project / "src/app.py",), self.book)
        self.assertIsInstance(rel, guard.CannotTell)
        self.assertIn("over 5,000 folders and links", rel.why)
        decision, why = self.hook("Write", "src/app.py", agent="general-purpose", reason=True, content="x")
        self.assertEqual(decision, "deny")
        self.assertIn("over 5,000 folders and links", why)
        self.assertIn("the fix: remove links to large folders", why)
        decision, why = self.hook("Write", "src/app.py", reason=True, content="x")
        self.assertEqual(decision, "ask")
        self.assertIn("move large folders out of book/", why)

    def test_a_symlink_walk_over_its_time_budget_cannot_tell(self):
        self._shared_bible()
        guard = guard_module()
        self.assertEqual(guard.through_link((self.project / "src/app.py",), self.book), ())
        rel = guard.through_link((self.project / "src/app.py",), self.book, budget=-1)
        self.assertIsInstance(rel, guard.CannotTell)
        self.assertIn("took over", rel.why)

    def test_a_symlink_walk_that_cannot_read_a_folder_cannot_tell(self):
        series = self._shared_bible()
        (self.book / "bible/world/shared").unlink()
        locked = self.book / "locked"
        locked.mkdir()
        (locked / "shared").symlink_to(series)
        locked.chmod(0)
        try:
            if os.access(locked, os.R_OK):
                self.skipTest("running with permissions that read any folder")
            decision, why = self.hook("Write", str(series / "harbour.md"), agent="general-purpose", raw=True,
                                      reason=True, content="x")
            self.assertEqual(decision, "deny")
            self.assertIn(f"cannot read {locked}", why)
            self.assertIn("move it out of book/", why)
            self.assertEqual(self.hook("Write", str(series / "harbour.md"), raw=True, content="x"), "ask")
        finally:
            locked.chmod(0o755)

    def test_an_unreadable_folder_behind_a_link_names_the_link(self):
        series = self._shared_bible()
        private = series / "drafts"
        private.mkdir()
        private.chmod(0)
        try:
            if os.access(private, os.R_OK):
                self.skipTest("running with permissions that read any folder")
            decision, why = self.hook("Write", "src/app.py", reason=True, content="x")
            self.assertEqual(decision, "ask")
            self.assertIn(f"cannot read {private.resolve()}, reached through the link book/bible/world/shared", why)
            self.assertIn("remove the link book/bible/world/shared", why)
            self.assertNotIn("move it out of book/", why)
        finally:
            private.chmod(0o755)

    def test_an_unreadable_dot_folder_holds_no_links(self):
        series = self._shared_bible()
        trash = series / ".Trashes"
        trash.mkdir()
        trash.chmod(0)
        try:
            if os.access(trash, os.R_OK):
                self.skipTest("running with permissions that read any folder")
            self.assertIsNone(self.hook("Write", "src/app.py", agent="general-purpose", content="x"))
            self.assertIsNone(self.hook("Write", "src/app.py", content="x"))
            self.assertEqual(self.hook("Write", str(series / "harbour.md"), agent="general-purpose", raw=True,
                                       content="# Harbour\n- The harbour never freezes.\n"), "deny")
        finally:
            trash.chmod(0o755)

    def test_links_in_dot_folders_are_found_and_their_files_do_not_count(self):
        series = self._shared_bible()
        (self.book / "bible/world/shared").unlink()
        vault = self.book / ".vault"
        vault.mkdir()
        for n in range(5_100):
            (vault / f"o{n:04}").write_text("x", encoding="utf-8")
        (vault / "series").symlink_to(series)
        self.assertEqual(guard_module().through_link((series / "harbour.md",), self.book),
                         (".vault/series/harbour.md",))
        self.assertIsNone(self.hook("Write", "src/app.py", agent="general-purpose", content="x"))

    def test_a_link_target_spelled_through_a_firmlink_is_still_the_book(self):
        series = self._shared_bible()
        spelled = Path("/System/Volumes/Data" + str(series / "harbour.md"))
        if not spelled.exists():
            self.skipTest("no /System/Volumes/Data firmlink for this folder")
        self.assertEqual(guard_module().through_link((spelled,), self.book), ("bible/world/shared/harbour.md",))
        self.assertEqual(self.hook("Write", str(spelled), agent="general-purpose", raw=True,
                                   content="# Harbour\n- The harbour never freezes.\n"), "deny")

    def test_folders_with_no_identity_are_still_walked(self):
        # Windows: os.DirEntry.stat reports st_dev and st_ino as 0, and FAT drives give no identity at all
        series = self._shared_bible()
        guard = guard_module()

        class Zeroed:
            def __init__(self, entry):
                self._entry = entry

            def __getattr__(self, name):
                return getattr(self._entry, name)

            def stat(self, follow_symlinks=True):
                st = self._entry.stat(follow_symlinks=follow_symlinks)
                return os.stat_result((st.st_mode, 0, 0) + tuple(st)[3:])

        class Listing:
            def __init__(self, folder):
                self._entries = [Zeroed(e) for e in real_scandir(folder)]

            def __enter__(self):
                return iter(self._entries)

            def __exit__(self, *exc):
                return False

        real_scandir = os.scandir
        guard.os.scandir = Listing
        guard.identity = lambda path: None
        try:
            self.assertEqual(guard.through_link((series / "harbour.md",), self.book),
                             ("bible/world/shared/harbour.md",))
        finally:
            guard.os.scandir = real_scandir

    def test_a_shortcut_inside_the_book_does_not_rename_canon(self):
        series = self._shared_bible()
        (self.book / "world").symlink_to(self.book / "bible/world")
        edit = "# Harbour\nFerries run twice a day.\n## ⚓ Anchored\n- The harbour freezes in March.\n"
        # book/world/... is judged where it really is: bible/world/...
        self.assertEqual(self.hook("Write", "book/world/inn.md", agent="general-purpose", content="# Inn\n"), "deny")
        self.assertIsNone(self.hook("Write", "book/world/inn.md", agent="novelsmith:worldbuilder", content="# Inn\n"))
        self.assertEqual(self.hook("Write", str(series / "harbour.md"), agent="general-purpose", raw=True,
                                   content=edit), "deny")
        self.assertIsNone(self.hook("Write", "book/bible/world/shared/harbour.md", agent="novelsmith:worldbuilder",
                                    content=edit))

    def test_a_file_in_the_book_is_judged_where_it_really_is(self):
        # a link between two book folders changes nothing: research/maps stays research, however it is written
        maps = self.book / "research/maps"
        maps.mkdir(parents=True)
        (self.book / "bible/world").mkdir(parents=True, exist_ok=True)
        (self.book / "bible/world/maps").symlink_to(maps)
        for spelled in ("book/research/maps/harbour.md", "book/bible/world/maps/harbour.md"):
            self.assertIsNone(self.hook("Write", spelled, agent="general-purpose", content="# Harbour\n"))
        self.assertEqual(self.hook("Write", "book/bible/world/maps/harbour.md", agent="novelsmith:worldbuilder",
                                   content="# Harbour\n"), "deny")

    def test_linked_files_are_for_novelsmith_agents_by_their_book_path(self):
        series = self._shared_bible()
        (self.book / "series").symlink_to(self.project)  # the whole series folder, linked for reference
        edit = "# Harbour\nFerries run twice a day.\n## ⚓ Anchored\n- The harbour freezes in March.\n"
        wb = "novelsmith:worldbuilder"
        self.assertIsNone(self.hook("Write", "book/bible/world/shared/harbour.md", agent=wb, content=edit))
        decision, why = self.hook("Write", "book/series/series-bible/harbour.md", agent=wb, reason=True, content=edit)
        self.assertEqual(decision, "deny")
        self.assertIn("book/series/series-bible/harbour.md belongs to another stage", why)
        for spelled in ("book/bible/world/shared/harbour.md", "book/series/series-bible/harbour.md",
                        "series-bible/harbour.md"):
            decision, why = self.hook("Write", spelled, agent="general-purpose", reason=True, content=edit)
            self.assertEqual(decision, "deny")
        self.assertIn("reached through a link in book/", why)
        self.assertIsNone(self.hook("Write", "book/bible/world/shared/harbour.md", content=edit))
        self.assertEqual(self.hook("Write", "series-bible/harbour.md", content="# Harbour\n"), "ask")

    def test_a_series_file_behind_a_link_in_an_in_book_folder_is_found(self):
        series = self._shared_bible()
        (self.book / "bible/world/shared").unlink()
        maps = self.book / "research/maps"
        maps.mkdir(parents=True)
        (self.book / "bible/world/maps").symlink_to(maps)
        (maps / "shared").symlink_to(series)
        self.assertEqual(self.hook("Write", str(series / "harbour.md"), agent="general-purpose", raw=True,
                                   content="# Harbour\n"), "deny")
        self.assertEqual(self.hook("Write", str(series / "harbour.md"), raw=True, content="# Harbour\n"), "ask")

    def test_a_known_book_path_never_waits_for_the_walk(self):
        self._shared_bible()
        self._folders(self.book / "research")  # the walk would answer "cannot tell"
        edit = "# Harbour\nFerries run twice a day.\n## ⚓ Anchored\n- The harbour freezes in March.\n"
        self.assertIsNone(self.hook("Write", "book/bible/world/shared/harbour.md", agent="novelsmith:worldbuilder",
                                    content=edit))
        self.assertIsNone(self.hook("Write", "book/bible/world/shared/harbour.md", content=edit))

    def test_a_linked_file_is_named_by_the_link_that_leaves_the_book(self):
        series = self._shared_bible()
        edit = "# Harbour\nFerries run twice a day.\n## ⚓ Anchored\n- The harbour freezes in March.\n"
        wb, sa = "novelsmith:worldbuilder", "novelsmith:story-architect"
        # the series bible linked under research/, reached from bible/world/maps -> research/maps
        (self.book / "bible/world/shared").unlink()
        maps = self.book / "research/maps"
        maps.mkdir(parents=True)
        (self.book / "bible/world/maps").symlink_to(maps)
        (maps / "shared").symlink_to(series)
        decision, why = self.hook("Write", "book/bible/world/maps/shared/harbour.md", agent=wb, reason=True,
                                  content=edit)
        self.assertEqual(decision, "deny")
        self.assertIn("book/research/maps/shared/harbour.md belongs to another stage", why)
        # an in-book link from proposals/ into bible/world, where the series bible is linked
        (self.book / "bible/world/shared").symlink_to(series)
        (self.book / "proposals").mkdir(exist_ok=True)
        (self.book / "proposals/world").symlink_to(Path("../bible/world"))
        decision, why = self.hook("Write", "book/proposals/world/shared/harbour.md", agent=sa, reason=True,
                                  content=edit)
        self.assertEqual(decision, "deny")
        self.assertIn("book/bible/world/shared/harbour.md belongs to another stage", why)
        self.assertIsNone(self.hook("Write", "book/proposals/world/shared/harbour.md", agent=wb, content=edit))
        # a link to a link: proposals/series -> bible/world/shared -> the series bible
        (self.book / "proposals/series").symlink_to(Path("../bible/world/shared"))
        decision, why = self.hook("Write", "book/proposals/series/harbour.md", agent=sa, reason=True, content=edit)
        self.assertEqual(decision, "deny")
        self.assertIn("book/bible/world/shared/harbour.md belongs to another stage", why)

    def test_premise_and_scenes_behind_links_keep_their_protection(self):
        import shutil
        genre = dict(old_string="- Base genre: mystery", new_string="- Base genre: literary")
        waiver = dict(old_string="  waivers: {}", new_string='  waivers: {subplot: "x"}')
        (self.book / "proposals").mkdir(exist_ok=True)
        # the whole bible and outline kept outside the book, each also linked from proposals/
        for folder in ("bible", "outline"):
            shutil.move(str(self.book / folder), str(self.project / f"series-{folder}"))
            (self.book / folder).symlink_to(self.project / f"series-{folder}")
            (self.book / "proposals" / folder).symlink_to(Path("..") / folder)
        for agent in ("novelsmith:story-architect", "novelsmith:worldbuilder"):
            with self.subTest(agent=agent):
                self.assertEqual(self.hook("Edit", "book/proposals/bible/premise.md", agent=agent, **genre), "deny")
        self.assertEqual(self.hook("Edit", "book/proposals/bible/premise.md", **genre), "ask")
        self.assertEqual(self.hook("Edit", "book/proposals/outline/scenes.yaml", agent="novelsmith:outliner",
                                   **waiver), "deny")
        self.assertEqual(self.hook("Edit", "book/proposals/outline/scenes.yaml", **waiver), "ask")

    def test_versioned_scenes_and_premise_links_are_still_scenes_and_premise(self):
        import shutil
        waiver = dict(old_string="  waivers: {}", new_string='  waivers: {subplot: "x"}')
        genre = dict(old_string="- Base genre: mystery", new_string="- Base genre: literary")
        outline = self.book / "outline"
        (outline / "scenes.yaml").rename(outline / "scenes-v3.yaml")
        (outline / "scenes.yaml").symlink_to("scenes-v3.yaml")
        for spelled in ("book/outline/scenes.yaml", "book/outline/scenes-v3.yaml"):
            for agent in ("general-purpose", "novelsmith:outliner"):
                with self.subTest(spelled=spelled, agent=agent):
                    self.assertEqual(self.hook("Edit", spelled, agent=agent, **waiver), "deny")
            self.assertEqual(self.hook("Edit", spelled, **waiver), "ask")
        # the whole outline folder a link to a draft inside the book
        (outline / "scenes.yaml").unlink()
        (outline / "scenes-v3.yaml").rename(outline / "scenes.yaml")
        (self.book / "drafts").mkdir()
        shutil.move(str(outline), str(self.book / "drafts/outline-v2"))
        outline.symlink_to(Path("drafts/outline-v2"))
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", agent="general-purpose", **waiver), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/scenes.yaml", **waiver), "ask")
        self.assertIsNone(self.hook("Edit", "book/outline/scenes.yaml", agent="novelsmith:outliner",
                                    old_string='  title: "Jäänlähtö"', new_string='  title: "Jäänlähtö II"'))
        # premise.md a link to a later version
        bible = self.book / "bible"
        (bible / "premise.md").rename(bible / "premise-v2.md")
        (bible / "premise.md").symlink_to("premise-v2.md")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", **genre), "ask")
        self.assertEqual(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect", **genre),
                         "deny")
        self.assertIsNone(self.hook("Edit", "book/bible/premise.md", agent="novelsmith:story-architect",
                                    old_string="- Outcome of the climax: exposure on the ice road",
                                    new_string="- Outcome of the climax: exposure on the frozen ice road"))

    def test_links_are_followed_part_by_part(self):
        series = self._shared_bible()
        (series / "towns").mkdir()
        (series / "towns/harbour.md").write_text((series / "harbour.md").read_text(encoding="utf-8"),
                                                encoding="utf-8")
        edit = "# Harbour\nFerries run twice a day.\n## ⚓ Anchored\n- The harbour freezes in March.\n"
        wb, sa = "novelsmith:worldbuilder", "novelsmith:story-architect"
        proposals, research = self.book / "proposals", self.book / "research"
        proposals.mkdir(exist_ok=True)
        research.mkdir()
        (proposals / "world").symlink_to(Path("../bible/world"))
        layouts = {
            # a file link whose target runs through the link that leaves the book
            "book/proposals/h.md": (proposals / "h.md", "../bible/world/shared/harbour.md"),
            # a link to a folder inside the linked series bible
            "book/proposals/towns/harbour.md": (proposals / "towns", "../bible/world/shared/towns"),
            # a target that runs through another in-book link first
            "book/research/h.md": (research / "h.md", "../proposals/world/shared/harbour.md"),
            # an absolute link between book folders, which starts outside the book at /
            "book/proposals/abs/shared/harbour.md": (proposals / "abs", self.book / "bible/world"),
        }
        for spelled, (link, to) in layouts.items():
            link.symlink_to(Path(to))
            with self.subTest(spelled=spelled):
                decision, why = self.hook("Write", spelled, agent=sa, reason=True, content=edit)
                self.assertEqual(decision, "deny")
                self.assertIn("book/bible/world/shared/", why)
                self.assertIsNone(self.hook("Write", spelled, agent=wb, content=edit))

    def test_a_link_that_climbs_out_of_the_linked_folder_cannot_tell(self):
        self._shared_bible()
        (self.project / "notes.md").write_text("x\n", encoding="utf-8")
        (self.book / "proposals").mkdir(exist_ok=True)
        (self.book / "proposals/up.md").symlink_to(Path("../bible/world/shared/../notes.md"))
        for agent in ("novelsmith:story-architect", "general-purpose"):
            with self.subTest(agent=agent):
                decision, why = self.hook("Write", "book/proposals/up.md", agent=agent, reason=True, content="y")
                self.assertEqual(decision, "deny")
                self.assertIn("cannot tell which book file it is", why)
                self.assertIn("climbs back out of the folder the link book/bible/world/shared leads to", why)
        self.assertEqual(self.hook("Write", "book/proposals/up.md", content="y"), "ask")

    def test_scenes_kept_outside_the_book_is_known_by_any_link(self):
        import shutil
        waiver = dict(old_string="  waivers: {}", new_string='  waivers: {subplot: "x"}')
        series = self.project / "series-outline"
        shutil.move(str(self.book / "outline"), str(series))
        (self.book / "outline").symlink_to(series)
        (self.book / "proposals").mkdir(exist_ok=True)
        (self.book / "proposals/s.yaml").symlink_to(series / "scenes.yaml")
        self.assertEqual(self.hook("Edit", "book/proposals/s.yaml", agent="novelsmith:story-architect", **waiver),
                         "deny")
        self.assertEqual(self.hook("Edit", "book/proposals/s.yaml", **waiver), "ask")

    def test_scenes_and_premise_without_file_identities(self):
        from unittest import mock
        g = guard_module()
        real_stat = os.stat

        def no_identity(p, *a, **k):
            r = real_stat(p, *a, **k)
            return os.stat_result((r.st_mode, 0, 0, r.st_nlink, r.st_uid, r.st_gid, r.st_size, r.st_atime,
                                   r.st_mtime, r.st_ctime))

        outline = self.book / "outline"
        (outline / "scenes.yaml").rename(outline / "scenes-v3.yaml")
        (outline / "scenes.yaml").symlink_to("scenes-v3.yaml")
        with mock.patch.object(g.os, "stat", no_identity):
            self.assertIsNone(g.special((self.book / "bible/style.md").resolve(), self.book))
            self.assertEqual(g.special((outline / "scenes-v3.yaml").resolve(), self.book), g.SCENES)
            self.assertEqual(g.special((self.book / "bible/premise.md").resolve(), self.book), g.PREMISE)

    def test_a_windows_junction_counts_as_a_link(self):
        from unittest import mock
        series = self._shared_bible()
        g = guard_module()
        shared = self.book / "bible/world/shared"
        real_islink, real_readlink = os.path.islink, os.readlink

        def junction(on):  # shared as Windows shows a junction: islink False, isjunction as given, \\?\ target
            return (mock.patch.object(g.os.path, "islink", lambda p: False if Path(p) == shared else real_islink(p)),
                    mock.patch.object(g.os.path, "isjunction", lambda p: on and Path(p) == shared, create=True),
                    mock.patch.object(g.os, "readlink", lambda p: ("\\\\?\\" if Path(p) == shared else "")
                                      + real_readlink(p)))

        parts = ("bible", "world", "shared", "harbour.md")
        self.assertEqual(g.target("book/" + "/".join(parts), self.project, self.book)[0],
                         (series / "harbour.md").resolve())  # the system follows it out of the book
        a, b, c = junction(True)
        with a, b, c:
            self.assertEqual(g.leaving_link(parts, self.book), "bible/world/shared/harbour.md")
        # a link the walk cannot follow, though the system does: cannot tell, and says so
        a, b, c = junction(False)
        with a, b, c:
            rel = g.leaving_link(parts, self.book)
        self.assertIsInstance(rel, g.CannotTell)
        self.assertIn("a link the canon guard cannot follow", rel.why)
        # a junction's target as os.readlink gives it on Windows
        for given, meant in (("\\\\?\\C:\\series", "C:\\series"), ("\\\\?\\UNC\\nas\\series", "\\\\nas\\series"),
                             ("../series", "../series")):
            with mock.patch.object(g.os, "readlink", lambda p, given=given: given):
                self.assertEqual(g.link_target("x"), meant)

    def test_a_hard_link_to_scenes_or_premise_keeps_its_protection(self):
        waiver = dict(old_string="  waivers: {}", new_string='  waivers: {subplot: "x"}')
        genre = dict(old_string="- Base genre: mystery", new_string="- Base genre: literary")
        proposals = self.book / "proposals"
        proposals.mkdir(exist_ok=True)
        os.link(self.book / "outline/scenes.yaml", proposals / "s.yaml")
        os.link(self.book / "bible/premise.md", proposals / "p.md")
        sa = "novelsmith:story-architect"
        self.assertEqual(self.hook("Edit", "book/proposals/s.yaml", agent=sa, **waiver), "deny")
        self.assertEqual(self.hook("Edit", "book/proposals/s.yaml", **waiver), "ask")
        self.assertEqual(self.hook("Edit", "book/proposals/p.md", agent=sa, **genre), "deny")
        self.assertEqual(self.hook("Edit", "book/proposals/p.md", **genre), "ask")

    def test_the_fallback_check_knows_linked_files(self):
        series = self._shared_bible()
        g = guard_module()
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.project)
        try:
            for raw, expected in ((str(series / "harbour.md"), True), ("book/bible/world/shared/harbour.md", True),
                                  ("src/app.py", False)):
                payload = {"cwd": str(self.project), "tool_name": "Write", "tool_input": {"file_path": raw}}
                with self.subTest(raw=raw):
                    self.assertIs(g.writes_book(payload), expected)
            self._folders(self.book / "research")
            payload = {"cwd": str(self.project), "tool_name": "Write", "tool_input": {"file_path": "src/app.py"}}
            self.assertIs(g.writes_book(payload), True)  # cannot tell counts as the book
        finally:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)

    def test_dangling_and_looping_links_are_passed_over(self):
        missing = self.project / "series-bible"
        (self.book / "bible/world").mkdir(parents=True, exist_ok=True)
        (self.book / "bible/world/shared").symlink_to(missing)
        (self.book / "a").symlink_to(self.book / "b")
        (self.book / "b").symlink_to(self.book / "a")
        guard = guard_module()
        self.assertEqual(guard.through_link((missing / "harbour.md",), self.book), ("bible/world/shared/harbour.md",))
        self.assertEqual(guard.through_link((self.project / "src/app.py",), self.book), ())
        self.assertIsNone(self.hook("Write", "src/app.py", agent="general-purpose", content="x"))

    def test_a_link_inside_a_linked_folder_is_still_the_book(self):
        series = self._shared_bible()
        store = self.project / "character-store"
        store.mkdir()
        (store / "aino.md").write_text("# Aino\n## ⚓ Anchored\n- Aino never drinks.\n", encoding="utf-8")
        (series / "people").symlink_to(store)
        self.assertEqual(guard_module().through_link((store / "aino.md",), self.book),
                         ("bible/world/shared/people/aino.md",))
        self.assertEqual(self.hook("Write", str(store / "aino.md"), agent="general-purpose", raw=True,
                                   content="# Aino\n- Aino drinks.\n"), "deny")
        self.assertEqual(self.hook("Write", str(store / "aino.md"), raw=True, content="# Aino\n- Aino drinks.\n"),
                         "ask")

    def test_a_link_back_to_the_book_or_its_folder_ends(self):
        (self.book / "again").symlink_to(self.book)
        (self.book / "up").symlink_to(self.project)
        self.assertEqual(guard_module().through_link((self.project / "src/app.py",), self.book), ("up/src/app.py",))
        self.assertEqual(guard_module().through_link((Path("/nowhere/else.md"),), self.book), ())

    def test_the_symlink_walk_is_skipped_outside_a_book_project(self):
        series = self._shared_bible()
        self._folders(self.book / "research")  # in a book project the walk would answer "cannot tell"
        (self.book / "outline/scenes.yaml").unlink()
        self.assertIsNone(self.hook("Write", str(series / "harbour.md"), agent="general-purpose", raw=True,
                                    content="x"))
        self.assertIsNone(self.hook("Write", "src/app.py", agent="general-purpose", content="x"))
        self.assertIsNone(self.hook("Write", "src/app.py", content="x"))


class HookCommand(unittest.TestCase):
    """Run the exact command string from hooks/hooks.json through sh."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        fixture.build(self.project)
        hook = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["hooks"][0]
        self.command = hook["command"]
        self.payload = json.dumps({
            "hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": "Write",
            "agent_id": "a1", "agent_type": "novelsmith:worldbuilder",
            "tool_input": {"file_path": str(self.project / "book/outline/acts.md"), "content": "x"},
        })

    def tearDown(self):
        self.tmp.cleanup()

    def sh(self, **env):
        base = {"PATH": os.environ["PATH"], "CLAUDE_PROJECT_DIR": str(self.project), **env}
        return subprocess.run(["/bin/sh", "-c", self.command], input=self.payload, capture_output=True,
                              text=True, env=base)

    def test_matcher_covers_every_guarded_tool(self):
        matcher = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["matcher"]
        self.assertEqual(matcher, ".*")  # every tool: an unknown one is denied to subagents, not missed

    def test_deadline_leaves_room_before_the_hook_timeout(self):
        hook = json.loads(HOOKS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["hooks"][0]
        # two interpreter starts and the decision must fit after the child's deadline
        self.assertLess(guard_module().DEADLINE + 2, hook["timeout"])

    def test_denies_when_installed(self):
        p = self.sh(CLAUDE_PLUGIN_ROOT=str(ROOT))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_silent_when_script_missing(self):
        p = self.sh(CLAUDE_PLUGIN_ROOT=str(self.project / "nowhere"))
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))

    def test_silent_when_root_unset(self):
        p = self.sh()
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_silent_without_python(self):
        empty = self.project / "empty-bin"
        empty.mkdir()
        p = self.sh(CLAUDE_PLUGIN_ROOT=str(ROOT), PATH=str(empty))
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
