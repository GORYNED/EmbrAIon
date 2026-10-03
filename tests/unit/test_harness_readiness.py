from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from embraion.common import read_yaml, write_yaml
from embraion.harness import audit_harness
from embraion.project import init_project, install


class HarnessReadinessTests(unittest.TestCase):
    def test_uninitialized_directory_reports_missing_project_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            row = audit_harness("codex", Path(temporary))["hosts"][0]
            self.assertFalse(row["ready"])
            self.assertIn(".embraion/agents.yaml", row["missing"])

    def test_fresh_install_reports_installation_only_for_every_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            for host in ("codex", "copilot", "claude-code"):
                install(host, project)

            report = audit_harness("all", project)
            self.assertEqual({"claude-code", "codex", "copilot"}, {row["host"] for row in report["hosts"]})
            for row in report["hosts"]:
                with self.subTest(host=row["host"]):
                    self.assertTrue(row["ready"])
                    self.assertEqual([], row["missing"])
                    self.assertEqual("installation", row["stage"])
                    self.assertEqual("projected-file-presence", row["ready-scope"])
                    self.assertFalse(row["content-verified"])
                    for field in ("instructions-loaded", "runtime-settings", "execution"):
                        self.assertEqual("unverified", row[field])

    def test_empty_agents_directory_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            install("codex", project)
            agents = project / ".codex/agents"
            for entry in agents.iterdir():
                entry.unlink()

            row = audit_harness("codex", project)["hosts"][0]
            self.assertFalse(row["ready"])
            self.assertFalse(row["agents"]["present"])
            self.assertIn(".codex/agents/worker.toml", row["missing"])

    def test_unrelated_skill_cannot_substitute_for_orchestration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            install("codex", project)
            (project / ".agents/skills/orchestration/SKILL.md").unlink()
            unrelated = project / ".agents/skills/speckit/SKILL.md"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("# Spec Kit\n", encoding="utf-8")

            row = audit_harness("codex", project)["hosts"][0]
            self.assertFalse(row["ready"])
            self.assertFalse(row["skills"]["present"])
            self.assertIn(".agents/skills/orchestration/SKILL.md", row["missing"])

    def test_missing_activation_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for host, activation in (
                ("codex", ".codex/config.toml"),
                ("claude-code", ".claude/rules/embraion.md"),
            ):
                with self.subTest(host=host):
                    project = Path(temporary) / host
                    init_project(project)
                    install(host, project)
                    (project / activation).unlink()
                    row = audit_harness(host, project)["hosts"][0]
                    self.assertFalse(row["ready"])
                    self.assertEqual([activation], row["activation"]["missing"])
                    self.assertIn(activation, row["missing"])

    def test_project_extension_requires_its_native_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project)
            config_path = project / ".embraion/agents.yaml"
            config = read_yaml(config_path)
            config["agents"] = [{
                "id": "release-specialist",
                "purpose": "Prepare releases.",
                "access": "workspace-write",
                "responsibilities": ["Prepare releases."],
            }]
            write_yaml(config_path, config)
            install("copilot", project)
            profile = ".github/agents/release-specialist.agent.md"
            self.assertTrue(audit_harness("copilot", project)["hosts"][0]["ready"])
            (project / profile).unlink()
            row = audit_harness("copilot", project)["hosts"][0]
            self.assertFalse(row["ready"])
            self.assertIn(profile, row["missing"])


if __name__ == "__main__":
    unittest.main()
