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
            routing = read_yaml(project / ".embraion/routing.yaml")
            knowledge = read_yaml(project / ".embraion/knowledge.yaml")
            project_policy = read_yaml(project / ".embraion/policy.yaml")
            validation = read_yaml(project / ".embraion/validation.yaml")
            agents = read_yaml(project / ".embraion/agents.yaml")
            project_manifest = read_yaml(project / ".embraion/project.yaml")
            self.assertEqual({"overrides": {}}, routing)
            self.assertEqual({}, knowledge)
            self.assertEqual(
                {"fast": [], "affected": [], "full": []},
                validation["profiles"],
            )
            self.assertEqual({"agents": []}, agents)
            self.assertEqual("PRIVATE", project_policy["privacy"]["default-class"])
            self.assertTrue(project_policy["review"]["substantial-required"])
            self.assertEqual([], project_policy["sources"]["protected"])
            for key in (
                "routing",
                "knowledge",
                "sources",
                "review",
                "privacy",
                "validation",
                "agents",
            ):
                self.assertNotIn(key, project_manifest)
            self.assertEqual("PRIVATE", policy["privacy"]["default-class"])
            self.assertTrue(policy["review"]["substantial-required"])
            self.assertEqual([], policy["sources"]["protected"])
            local_ignore = (project / ".embraion/.gitignore").read_text(
                encoding="utf-8"
            )
            self.assertIn("state/", local_ignore)
            self.assertIn("cache/", local_ignore)

    def test_init_preserves_existing_local_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            local_ignore = project / ".embraion/.gitignore"
            local_ignore.parent.mkdir(parents=True)
            local_ignore.write_text("custom-local-rule/\n", encoding="utf-8")

            init_project(project, name="Consumer")
            self.assertEqual(
                "custom-local-rule/\n",
                local_ignore.read_text(encoding="utf-8"),
            )

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

    def test_selective_projection_preserves_existing_host_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")

            existing = project / ".codex/config.toml"
            existing.parent.mkdir(parents=True)
            existing.write_text("[project]\ncustom = true\n", encoding="utf-8")

            plan = projection_plan(
                "codex",
                project,
                components=["skills"],
            )
            self.assertEqual(["skills"], plan["components"])
            self.assertEqual([], plan["conflict"])

            installed = install(
                "codex",
                project,
                components=["skills"],
            )
            self.assertEqual(["skills"], installed["components"])
            self.assertEqual(
                "[project]\ncustom = true\n",
                existing.read_text(encoding="utf-8"),
            )
            self.assertFalse((project / ".codex/agents/reviewer.toml").exists())
            self.assertTrue((project / ".agents/skills/review/SKILL.md").is_file())

            full = projection_plan("codex", project)
            self.assertIn(".codex/config.toml", full["conflict"])
            self.assertIn(
                ".agents/skills/review/SKILL.md",
                full["unchanged"],
            )

    def test_selective_projection_does_not_orphan_unselected_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            selective = projection_plan(
                "codex",
                project,
                components=["skills"],
            )
            self.assertEqual([], selective["obsolete-owned"])
            self.assertEqual([], selective["obsolete-modified"])

            install("codex", project, components=["skills"])
            state = read_json(
                project / ".embraion/state/projections/codex.json"
            )
            self.assertIn(".codex/config.toml", state["files"])
            self.assertIn(".codex/agents/reviewer.toml", state["files"])
            self.assertEqual(
                ["agents", "config", "skills"],
                state["managed-components"],
            )

    def test_selective_install_infers_legacy_managed_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)

            state_path = project / ".embraion/state/projections/codex.json"
            state = read_json(state_path)
            state.pop("managed-components", None)
            write_json(state_path, state)

            install("codex", project, components=["skills"])
            upgraded = read_json(state_path)
            self.assertEqual(
                ["agents", "config", "skills"],
                upgraded["managed-components"],
            )

    def test_invalid_projection_component_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            with self.assertRaises(RuntimeError):
                projection_plan(
                    "copilot",
                    project,
                    components=["config"],
                )

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

    def test_structured_knowledge_uses_dedicated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            knowledge_dir = project / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "architecture.md").write_text(
                "architecture",
                encoding="utf-8",
            )

            knowledge_path = manifest.with_name("knowledge.yaml")
            data = read_yaml(knowledge_path)
            data["architecture"] = {
                "path": "knowledge/architecture.md",
                "data-class": "PRIVATE",
                "trust": "project",
                "roles": ["architect"],
                "triggers": ["architecture"],
            }
            write_yaml(knowledge_path, data)

            self.assertNotIn("knowledge", read_yaml(manifest))
            self.assertEqual(
                "knowledge/architecture.md",
                read_yaml(knowledge_path)["architecture"]["path"],
            )


if __name__ == "__main__":
    unittest.main()
