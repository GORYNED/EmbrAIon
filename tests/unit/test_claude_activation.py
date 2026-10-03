from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from embraion.common import read_json, write_yaml
from embraion.project import _projection_state_path, init_project, install, projection_is_verified, projection_plan


class ClaudeActivationTests(unittest.TestCase):
    def test_skill_install_owns_activation_and_preserves_user_instructions(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="ClaudeActivation")
            instructions = project / "CLAUDE.md"
            instructions.write_text("@AGENTS.md\nCustom project instruction.\n")
            spec = project / ".claude/skills/speckit-plan/SKILL.md"
            spec.parent.mkdir(parents=True)
            spec.write_text("User-managed Spec Kit\n")
            install("claude-code", project, components=["skills"])
            rule = project / ".claude/rules/embraion.md"
            self.assertTrue(rule.is_file())
            self.assertFalse(rule.read_text().startswith("---"))
            self.assertIn(".claude/skills/orchestration/SKILL.md", rule.read_text())
            state = read_json(_projection_state_path(project, "claude-code"))
            self.assertIn(".claude/rules/embraion.md", state["files"])
            self.assertEqual("@AGENTS.md\nCustom project instruction.\n", instructions.read_text())
            self.assertEqual("User-managed Spec Kit\n", spec.read_text())
            self.assertTrue(projection_is_verified(projection_plan("claude-code", project, components=["skills"])))
            rule.write_text(rule.read_text() + "User edit\n")
            self.assertFalse(projection_is_verified(projection_plan("claude-code", project, components=["skills"])))
            with self.assertRaises(RuntimeError):
                install("claude-code", project, components=["skills"])

    def test_agents_only_install_does_not_claim_skill_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="ClaudeAgents")
            install("claude-code", project, components=["agents"])
            self.assertFalse((project / ".claude/rules/embraion.md").exists())

    def test_native_names_use_valid_bounded_ids_instead_of_display_titles(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="ClaudeNames")
            identity = "project-" + "long-" * 14 + "worker"
            write_yaml(project / ".embraion/agents.yaml", {"agents": [
                {"id": "video-cv", "title": "Video/CV", "extends": "worker",
                 "purpose": "Work on video.", "access": "workspace-write",
                 "responsibilities": ["Implement video behavior."]},
                {"id": identity, "extends": "reviewer", "purpose": "Review project work.",
                 "access": "read-only", "responsibilities": ["Review bounded work."]},
            ]})
            install("claude-code", project, components=["agents"])
            for path in (project / ".claude/agents").glob("*.md"):
                import yaml
                name = yaml.safe_load(path.read_text().split("---", 2)[1])["name"]
                self.assertRegex(name, r"^[a-zA-Z0-9_-]{1,64}$")
            self.assertIn('name: "video-cv"', (project / ".claude/agents/video-cv.md").read_text())
            self.assertIn("# Video/CV", (project / ".claude/agents/video-cv.md").read_text())


if __name__ == "__main__":
    unittest.main()
