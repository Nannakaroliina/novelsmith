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

    def hook(self, tool, rel, agent=None, raw=False, cwd=None, tool_input_override=None, **tool_input):
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
        return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]

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
        self.assertIsNone(self.hook("Write", "book/bible/characters/new2.md", agent="novelsmith:character-designer",
                                    content="# New\n## ⚓ Anchored\n<!-- author decisions go here -->\n"))

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

    def test_subagent_mcp_calls_naming_book_files_denied(self):
        for inp in ({"path": str(self.book / "bible/premise.md"), "content": "x"},
                    {"path": "book/outline/scenes.yaml", "content": "x"},
                    {"edits": [{"file": "file://" + str(self.book / "outline/acts.md")}]},
                    {"source": "/tmp/x", "destination": "BOOK/bible/style.md"}):
            with self.subTest(inp=inp):
                self.assertEqual(self.mcp(inp), "deny")
                self.assertEqual(self.mcp(inp, agent="novelsmith:outliner"), "deny")
        self.assertIsNone(self.mcp({"path": "src/notes.md", "content": "the book's bible is mentioned here"}))
        self.assertIsNone(self.mcp({"path": str(self.book / "bible/premise.md")}, agent=None))

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

    def test_watchdog_counts_a_slow_check_as_unchecked(self):
        import time
        g = guard_module()
        g.DEADLINE = 0.2
        g.main = lambda payload: time.sleep(5)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            g.run({})
        self.assertLess(time.monotonic() - start, 2)

    # --- Round 4 RES-2: growth is measured before an edit is applied --------------
    def test_replace_all_growth_past_the_cap_denied(self):
        (self.book / "outline/chapters.md").write_text("a\n" * 1000, encoding="utf-8")
        self.assertEqual(self.hook("Edit", "book/outline/chapters.md", agent="novelsmith:outliner",
                                   old_string="a", new_string="b" * 2000, replace_all=True), "deny")
        self.assertEqual(self.hook("Edit", "book/outline/chapters.md",
                                   old_string="a", new_string="b" * 2000, replace_all=True), "ask")


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
        self.assertEqual(set(matcher.split("|")), set(guard_module().WRITE_TOOLS) | {"Bash", "mcp__.*"})

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
