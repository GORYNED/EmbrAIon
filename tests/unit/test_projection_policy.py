from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from embraion.common import read_json, read_yaml, write_json, write_yaml
from embraion.policy import effective_policy
from embraion.project import init_project, install, projection_plan


class ProjectionPolicyTests(unittest.TestCase):
    def test_init_creates_project_policy_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            policy = effective_policy(project)
            self.assertEqual("PRIVATE", policy["privacy"]["default-class"])
            self.assertTrue(policy["review"]["substantial-required"])
            self.assertEqual([], policy["sources"]["protected"])

    def test_host_projection_includes_project_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)
            install("copilot", project)
            install("claude-code", project)

            self.assertTrue((project / ".agents/skills/review/SKILL.md").is_file())
            self.assertTrue((project / ".github/skills/review/SKILL.md").is_file())
            self.assertTrue((project / ".claude/skills/review/SKILL.md").is_file())

    def test_projection_lifecycle_detects_local_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            clean = projection_plan("codex", project)
            self.assertEqual([], clean["conflict"])
            self.assertGreater(len(clean["unchanged"]), 0)

            reviewer = project / ".codex/agents/reviewer.toml"
            reviewer.write_text(
                reviewer.read_text(encoding="utf-8") + "\n# local change\n",
                encoding="utf-8",
            )

            dirty = projection_plan("codex", project)
            self.assertIn(".codex/agents/reviewer.toml", dirty["conflict"])
            with self.assertRaises(RuntimeError):
                install("codex", project)

            install("codex", project, force=True)
            restored = projection_plan("codex", project)
            self.assertEqual([], restored["conflict"])

    def test_obsolete_projection_ownership_survives_until_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            relative = ".codex/agents/obsolete.toml"
            stale = project / relative
            original = "generated obsolete projection\n"
            stale.write_text(original, encoding="utf-8")

            state_path = project / ".embraion/state/projections/codex.json"
            state = read_json(state_path)
            state["files"][relative] = hashlib.sha256(stale.read_bytes()).hexdigest()
            write_json(state_path, state)

            before = projection_plan("codex", project)
            self.assertIn(relative, before["obsolete-owned"])

            install("codex", project)
            retained = projection_plan("codex", project)
            self.assertIn(relative, retained["obsolete-owned"])

            stale.write_text(original + "# local change\n", encoding="utf-8")
            modified = projection_plan("codex", project)
            self.assertIn(relative, modified["obsolete-modified"])

            install("codex", project, prune=True)
            self.assertTrue(stale.is_file())
            still_modified = projection_plan("codex", project)
            self.assertIn(relative, still_modified["obsolete-modified"])

            stale.write_text(original, encoding="utf-8")
            install("codex", project, prune=True)
            self.assertFalse(stale.exists())

    def test_structured_knowledge_remains_backward_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            knowledge = project / "knowledge"
            knowledge.mkdir()
            (knowledge / "architecture.md").write_text("architecture", encoding="utf-8")

            data = read_yaml(manifest)
            data["knowledge"] = {
                "architecture": {
                    "path": "knowledge/architecture.md",
                    "data-class": "PRIVATE",
                    "trust": "project",
                    "roles": ["architect"],
                    "triggers": ["architecture"],
                }
            }
            write_yaml(manifest, data)
            self.assertEqual(
                "knowledge/architecture.md",
                read_yaml(manifest)["knowledge"]["architecture"]["path"],
            )


if __name__ == "__main__":
    unittest.main()
