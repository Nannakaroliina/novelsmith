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


class GuardCanon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        self.book = fixture.build(self.project)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, tool, rel, agent=None, raw=False, cwd=None, **tool_input):
        target = {} if rel is None else {"file_path": rel if raw else str(self.project / rel)}
        payload = {"hook_event_name": "PreToolUse", "cwd": str(cwd or self.project), "tool_name": tool,
                   "tool_input": {**target, **tool_input}}
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

    def test_outside_book_is_ignored(self):
        self.assertIsNone(self.hook("Write", "src/app.py", agent="novelsmith:outliner", content="x"))

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

    def test_inexact_old_string_elsewhere_allowed(self):
        self.assertIsNone(self.hook("Edit", "book/outline/chapters.md", agent="novelsmith:outliner",
                                    old_string="nothing", new_string="x"))

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
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("guard", SCRIPT)
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        self.assertEqual(set(guard.AGENT_SCOPES), {p.stem for p in (ROOT / "agents").glob("*.md")})

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

    def test_shell_of_main_session_and_other_agents_untouched(self):
        self.assertIsNone(self.bash("ls book", agent=None))
        self.assertIsNone(self.bash("ls book", agent="general-purpose"))

    def test_bad_input_fails_open(self):
        p = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, "")


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
