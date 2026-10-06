from __future__ import annotations

import io
import os
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from embraion.cli import main
from embraion.common import framework_root, read_yaml, write_yaml
from embraion.policy import effective_policy, merge_mode, read_policy_config
from embraion.project import (
    CLAUDE_CORE_RULES, COPILOT_CORE_RULES, core_rules_text, init_project, install, projection_is_verified,
    projection_plan,
)


class MergePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="MergePolicy")
        self.policy = self.project / ".embraion/policy.yaml"

    def set_mode(self, value: object) -> None:
        data = read_yaml(self.policy)
        data["merge"] = {"mode": value}
        write_yaml(self.policy, data)

    def test_default_is_human_only_and_both_modes_validate(self) -> None:
        self.assertNotIn("merge", read_yaml(self.policy))
        self.assertEqual("human-only", merge_mode(self.project))
        self.assertEqual({"mode": "human-only"}, effective_policy(self.project)["merge"])
        for mode in ("human-only", "owner-permission"):
            with self.subTest(mode=mode):
                self.set_mode(mode)
                self.assertEqual(mode, read_policy_config(self.project)["merge"]["mode"])
                self.assertEqual(mode, merge_mode(self.project))
                self.assertEqual(mode, effective_policy(self.project)["merge"]["mode"])

    def test_unknown_or_malformed_merge_policy_fails_closed(self) -> None:
        for value in ("auto", "", None, ["human-only"]):
            with self.subTest(value=value):
                self.set_mode(value)
                with self.assertRaisesRegex(RuntimeError, "merge"):
                    read_policy_config(self.project)
                with self.assertRaisesRegex(RuntimeError, "merge"):
                    merge_mode(self.project)
                with self.assertRaisesRegex(RuntimeError, "merge"):
                    install("claude-code", self.project, components=["skills"])
        data = read_yaml(self.policy)
        data["merge"] = {"mode": "human-only", "auto-merge": True}
        write_yaml(self.policy, data)
        with self.assertRaisesRegex(RuntimeError, "merge"):
            merge_mode(self.project)

    def test_rules_state_the_mode_once_after_the_merge_rule(self) -> None:
        root = framework_root()
        self.assertNotIn("merge mode: `", core_rules_text(root))
        text = core_rules_text(root, "owner-permission")
        line = "This project's merge mode: `owner-permission` (`merge.mode` in `.embraion/policy.yaml`)."
        self.assertEqual(1, text.count(line))
        self.assertLess(text.index("\n## Human Merge\n"), text.index(line))
        self.assertLess(text.index(line), text.index("\n## Authorization\n"))
        self.assertIn("`human-only`", text)
        self.assertIn("never enables auto-merge", text)

    def test_every_host_projects_the_selected_mode_and_reports_drift(self) -> None:
        self.set_mode("owner-permission")
        expected = core_rules_text(framework_root(), "owner-permission")
        install("claude-code", self.project, components=["skills"])
        install("copilot", self.project, components=["skills"])
        install("codex", self.project, components=["config"])
        self.assertEqual(expected, (self.project / CLAUDE_CORE_RULES).read_text(encoding="utf-8"))
        self.assertTrue((self.project / COPILOT_CORE_RULES).read_text(encoding="utf-8").endswith(expected))
        config = tomllib.loads((self.project / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertIn(expected.strip(), config["developer_instructions"])
        self.set_mode("human-only")
        for host, component in (("claude-code", "skills"), ("copilot", "skills"), ("codex", "config")):
            with self.subTest(host=host):
                plan = projection_plan(host, self.project, components=[component])
                self.assertFalse(projection_is_verified(plan))

    def test_policy_show_prints_the_mode(self) -> None:
        self.set_mode("owner-permission")
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            self.assertEqual(0, main(["policy", "show"]))
        self.assertIn("Merge mode: owner-permission", output.getvalue())


if __name__ == "__main__":
    unittest.main()
