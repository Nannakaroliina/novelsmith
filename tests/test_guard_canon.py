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

    def hook(self, tool, rel, agent=None, **tool_input):
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.project), "tool_name": tool,
                   "tool_input": {"file_path": str(self.project / rel), **tool_input}}
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
        payload_rel = "book/bible/world/x.md"
        self.assertEqual(self.hook("Write", payload_rel, agent="novelsmith:character-designer", content="x"), "deny")

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
