from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from embraion.common import read_json, read_yaml, write_yaml
from embraion.project import generate_host, init_project, install, projection_is_verified, projection_plan


class ClaudeScopedProjectionTests(unittest.TestCase):
    def _project(self, root: Path, *, model: str = "claude-fable-5-1") -> Path:
        project = root / "project"
        init_project(project)
        write_yaml(project / ".embraion/claude-native.yaml", {
            "bindings": {"worker": "worker"},
            "assignments": [{
                "role": "worker",
                "route-class": "complex",
                "data-class": "PRIVATE",
                "access": "write",
            }],
        })
        self._set_model(project, model)
        return project

    def _set_model(self, project: Path, model: str) -> None:
        routing = read_yaml(project / ".embraion/routing.yaml")
        routing["overrides"] = {
            "claude-code": {"routes": {"complex": {"model": model, "effort": "high"}}}
        }
        write_yaml(project / ".embraion/routing.yaml", routing)

    def _metadata(self, project: Path) -> dict:
        return read_json(project / ".claude/embraion-native.json")

    def test_combined_components_generate_base_and_scoped_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project, components=["agents", "skills", "scoped-agents"])
            self.assertTrue((project / ".claude/agents/worker.md").is_file())
            self.assertTrue((project / ".claude/skills/orchestration/SKILL.md").is_file())
            name = self._metadata(project)["assignments"][0]["name"]
            self.assertTrue((project / ".claude/agents" / f"{name}.md").is_file())

    def test_scoped_projection_is_explicit_and_keeps_core_roles_model_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project)
            self.assertFalse((project / ".claude/embraion-native.json").exists())

            plan = install("claude-code", project, components=["scoped-agents"])
            self.assertEqual(["scoped-agents"], plan["components"])
            metadata = self._metadata(project)
            self.assertEqual(1, metadata["schema-version"])
            self.assertEqual(1, len(metadata["assignments"]))
            assignment = metadata["assignments"][0]
            self.assertEqual("worker", assignment["role"])
            self.assertEqual("worker", assignment["native-agent"])
            self.assertEqual("claude-fable-5-1", assignment["model"])
            self.assertEqual("high", assignment["effort"])
            self.assertNotIn("prompt", assignment)
            name = assignment["name"]
            scoped = project / ".claude/agents" / f"{name}.md"
            self.assertTrue(scoped.is_file())
            self.assertIn("claude-fable-5-1", scoped.read_text(encoding="utf-8"))
            self.assertNotIn("claude-fable-5-1", (project / ".claude/agents/worker.md").read_text(encoding="utf-8"))
            self.assertTrue((project / ".claude/agents/reviewer.md").is_file())

            install("claude-code", project, prune=True)
            self.assertTrue(scoped.is_file())

            unchanged = projection_plan("claude-code", project, components=["scoped-agents"])
            self.assertEqual([], unchanged["create"] + unchanged["update"] + unchanged["conflict"])
            self.assertIn(f".claude/agents/{name}.md", unchanged["unchanged"])

    def test_scoped_component_requires_configured_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            with self.assertRaisesRegex(RuntimeError, "scoped assignments"):
                install("claude-code", project, components=["scoped-agents"])
            self.assertFalse((project / ".claude/embraion-native.json").exists())

    def test_changed_model_rotates_definition_and_prunes_only_owned_scoped_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project)
            install("claude-code", project, components=["scoped-agents"])
            old_name = self._metadata(project)["assignments"][0]["name"]
            old_path = project / ".claude/agents" / f"{old_name}.md"
            self._set_model(project, "claude-sonnet-4-6")

            preview = projection_plan("claude-code", project, components=["scoped-agents"])
            self.assertIn(f".claude/agents/{old_name}.md", preview["obsolete-owned"])
            install("claude-code", project, components=["scoped-agents"], prune=True)
            self.assertFalse(old_path.exists())
            self.assertTrue((project / ".claude/agents/reviewer.md").is_file())
            new_name = self._metadata(project)["assignments"][0]["name"]
            self.assertNotEqual(old_name, new_name)
            self.assertTrue((project / ".claude/agents" / f"{new_name}.md").is_file())

    def test_scoped_prune_preserves_project_agent_with_similar_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            config_path = project / ".embraion/agents.yaml"
            config = read_yaml(config_path)
            config["agents"] = [{
                "id": "embraion-helper",
                "purpose": "Assist this project.",
                "access": "workspace-write",
                "responsibilities": ["Assist this project."],
            }]
            write_yaml(config_path, config)

            install("claude-code", project)
            base = project / ".claude/agents/embraion-helper.md"
            original = base.read_bytes()
            plan = install("claude-code", project, components=["scoped-agents"], prune=True)

            self.assertEqual(original, base.read_bytes())
            self.assertNotIn(".claude/agents/embraion-helper.md", plan["obsolete-owned"])
            self.assertNotIn(".claude/agents/embraion-helper.md", plan["obsolete-modified"])
            name = self._metadata(project)["assignments"][0]["name"]
            self.assertTrue(name.startswith("embraion--"))
            self.assertTrue((project / ".claude/agents" / f"{name}.md").is_file())

    def test_long_project_agent_name_stays_within_native_name_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            specialist = "a" * 40 + "-worker"
            config_path = project / ".embraion/agents.yaml"
            config = read_yaml(config_path)
            config["agents"] = [{
                "id": specialist,
                "purpose": "Assist this project.",
                "access": "workspace-write",
                "responsibilities": ["Assist this project."],
            }]
            write_yaml(config_path, config)
            native_path = project / ".embraion/claude-native.yaml"
            native = read_yaml(native_path)
            native["bindings"]["worker"] = specialist
            write_yaml(native_path, native)

            install("claude-code", project, components=["scoped-agents"])
            name = self._metadata(project)["assignments"][0]["name"]
            self.assertTrue(name.startswith("embraion--"))
            self.assertLessEqual(len(name), 64)

    def test_user_modified_obsolete_scoped_file_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project, components=["scoped-agents"])
            name = self._metadata(project)["assignments"][0]["name"]
            old_path = project / ".claude/agents" / f"{name}.md"
            old_path.write_text(old_path.read_text(encoding="utf-8") + "\nuser edit\n", encoding="utf-8")
            self._set_model(project, "claude-sonnet-4-6")

            plan = install("claude-code", project, components=["scoped-agents"], prune=True)
            self.assertIn(f".claude/agents/{name}.md", plan["obsolete-modified"])
            self.assertIn("user edit", old_path.read_text(encoding="utf-8"))

    def test_user_modified_active_scoped_file_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project, components=["scoped-agents"])
            name = self._metadata(project)["assignments"][0]["name"]
            target = project / ".claude/agents" / f"{name}.md"
            target.write_text("user edit\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Projection conflicts"):
                install("claude-code", project, components=["scoped-agents"])
            self.assertEqual("user edit\n", target.read_text(encoding="utf-8"))

    def test_existing_unowned_scoped_name_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            generated = Path(temporary) / "generated"
            generate_host(
                Path(__file__).resolve().parents[2],
                "claude-code",
                generated,
                ["scoped-agents"],
                project=project,
            )
            name = read_json(generated / ".claude/embraion-native.json")["assignments"][0]["name"]
            target = project / ".claude/agents" / f"{name}.md"
            target.parent.mkdir(parents=True)
            target.write_text("user owned\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Projection conflicts"):
                install("claude-code", project, components=["scoped-agents"])
            self.assertEqual("user owned\n", target.read_text(encoding="utf-8"))

    def test_review_scoped_definition_has_no_write_or_bash_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            write_yaml(project / ".embraion/claude-native.yaml", {
                "bindings": {"reviewer": "reviewer"},
                "assignments": [{
                    "role": "reviewer",
                    "route-class": "complex",
                    "data-class": "PRIVATE",
                    "access": "review",
                }],
            })
            install("claude-code", project, components=["scoped-agents"])
            assignment = self._metadata(project)["assignments"][0]
            self.assertEqual({"Read", "Grep", "Glob"}, set(assignment["tools"]))
            content = (project / ".claude/agents" / f"{assignment['name']}.md").read_text(encoding="utf-8")
            self.assertNotIn('"Bash"', content)
            self.assertNotIn('"Write"', content)

    def test_stale_reserved_profiles_are_obsolete_drift_without_a_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project, components=["agents", "skills", "scoped-agents"])
            old_name = self._metadata(project)["assignments"][0]["name"]
            self._set_model(project, "claude-sonnet-4-6")
            install("claude-code", project, components=["scoped-agents"])
            new_name = self._metadata(project)["assignments"][0]["name"]
            stray = project / ".claude/agents/embraion--stray-0123456789ab.md"
            stray.write_text("stale\n", encoding="utf-8")
            # A clean clone or CI checkout has no local ownership ledger.
            shutil.rmtree(project / ".embraion/state")

            plan = projection_plan("claude-code", project, components=["scoped-agents"])
            self.assertEqual(
                sorted([f".claude/agents/{old_name}.md", ".claude/agents/embraion--stray-0123456789ab.md"]),
                plan["obsolete-modified"],
            )
            self.assertIn(f".claude/agents/{new_name}.md", plan["unchanged"])
            self.assertFalse(projection_is_verified(plan))

            # Without ownership evidence the files are reported, never pruned.
            install("claude-code", project, components=["scoped-agents"], prune=True)
            self.assertTrue(stray.is_file())
            self.assertTrue((project / ".claude/agents" / f"{old_name}.md").is_file())

            # Unselected components and unreserved names stay user-owned.
            agents = projection_plan("claude-code", project, components=["agents"])
            self.assertEqual([], agents["obsolete-owned"] + agents["obsolete-modified"])

            stray.unlink()
            (project / ".claude/agents" / f"{old_name}.md").unlink()
            (project / ".claude/agents/embraion-helper.md").write_text("user owned\n", encoding="utf-8")
            self.assertTrue(projection_is_verified(
                projection_plan("claude-code", project, components=["scoped-agents"])
            ))

    def test_ledgered_stale_reserved_profile_is_reported_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            install("claude-code", project, components=["scoped-agents"])
            old_name = self._metadata(project)["assignments"][0]["name"]
            self._set_model(project, "claude-sonnet-4-6")
            plan = projection_plan("claude-code", project, components=["scoped-agents"])
            self.assertEqual([f".claude/agents/{old_name}.md"], plan["obsolete-owned"])
            self.assertEqual([], plan["obsolete-modified"])


if __name__ == "__main__":
    unittest.main()
