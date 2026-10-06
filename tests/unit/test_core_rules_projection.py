from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from embraion.common import framework_root, read_json
from embraion.project import (
    CLAUDE_CORE_RULES, COPILOT_CORE_RULES, _projection_state_path, core_rules_text, init_project, install,
    projection_is_verified, projection_plan,
)


class CoreRulesProjectionTests(unittest.TestCase):
    def test_rules_document_contains_every_rule_in_readme_order_with_local_links(self) -> None:
        text = core_rules_text(framework_root())
        rules = framework_root() / "core" / "rules"
        titles = [(rules / name).read_text(encoding="utf-8").splitlines()[0][2:]
                  for name in ("minimum-change.md", "evidence.md", "spec-kit.md")]
        positions = [text.index("\n## " + title + "\n") for title in titles]
        self.assertEqual(sorted(positions), positions)
        self.assertNotIn(".md)", text)
        self.assertIn("](#authorization)", text)
        self.assertIn("persisted-data compatibility", text)
        self.assertIn("deferred tasks", text)

    def test_each_host_loads_the_rules_at_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="CoreRules")
            expected = core_rules_text(framework_root())
            install("claude-code", project, components=["skills"])
            self.assertEqual(expected, (project / CLAUDE_CORE_RULES).read_text(encoding="utf-8"))
            install("copilot", project, components=["skills"])
            copilot = (project / COPILOT_CORE_RULES).read_text(encoding="utf-8")
            self.assertTrue(copilot.startswith('---\napplyTo: "**"\n---\n\n'))
            self.assertTrue(copilot.endswith(expected))
            install("codex", project, components=["config"])
            config = tomllib.loads((project / ".codex/config.toml").read_text(encoding="utf-8"))
            self.assertIn(expected.strip(), config["developer_instructions"])
            for host, path in (("claude-code", CLAUDE_CORE_RULES), ("copilot", COPILOT_CORE_RULES)):
                with self.subTest(host=host):
                    self.assertIn(path, read_json(_projection_state_path(project, host))["files"])
                    self.assertTrue(projection_is_verified(projection_plan(host, project, components=["skills"])))
            (project / COPILOT_CORE_RULES).write_text("edited\n", encoding="utf-8")
            self.assertFalse(projection_is_verified(projection_plan("copilot", project, components=["skills"])))

    def test_agents_only_install_does_not_write_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="CoreRulesAgents")
            install("claude-code", project, components=["agents"])
            install("copilot", project, components=["agents"])
            self.assertFalse((project / CLAUDE_CORE_RULES).exists())
            self.assertFalse((project / COPILOT_CORE_RULES).exists())


if __name__ == "__main__":
    unittest.main()
