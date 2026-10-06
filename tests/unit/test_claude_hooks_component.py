from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from embraion.claude_hooks import COMMAND, GUARD_COMMAND, HOOKS, install_observer_hooks, managed_hooks
from embraion.cli import main
from embraion.common import read_json, write_json, write_yaml
from embraion.project import (
    CLAUDE_SETTINGS, _projection_state_path, init_project, install, projection_is_verified, projection_plan,
)


class ClaudeHooksComponentTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="HooksComponent")
        write_yaml(self.project / ".embraion/routing.yaml", {
            "overrides": {"claude-code": {"routes": {
                "complex": {"model": "claude-opus-5-5", "effort": "high"}}}}})
        write_yaml(self.project / ".embraion/claude-native.yaml", {
            "bindings": {"reviewer": "reviewer"}, "assignments": [
                {"role": "reviewer", "route-class": "complex", "data-class": "PRIVATE", "access": "review"}]})
        install("claude-code", self.project, components=["scoped-agents"])
        self.path = self.project / CLAUDE_SETTINGS
        self.user = {"permissions": {"deny": ["Read(.env)"]}, "env": {"PROJECT_SETTING": "keep"},
                     "hooks": {"PostToolUse": [{"matcher": "Edit", "hooks": [
                         {"type": "command", "command": "project-validator"}]}],
                               "Stop": [{"hooks": [{"type": "command", "command": "project-stop"}]}]}}

    def plan(self) -> dict:
        return projection_plan("claude-code", self.project, components=["hooks"])

    def ledger(self) -> dict:
        return read_json(_projection_state_path(self.project, "claude-code"))

    def test_default_components_never_include_hooks(self) -> None:
        install("claude-code", self.project)
        self.assertFalse(self.path.exists())
        self.assertNotIn(CLAUDE_SETTINGS, self.ledger()["files"])
        self.assertNotIn("managed-hooks", self.ledger())

    def test_install_merges_preserves_user_content_and_records_managed_entries(self) -> None:
        write_json(self.path, self.user)
        self.assertEqual([CLAUDE_SETTINGS], self.plan()["update"])
        plan = install("claude-code", self.project, components=["hooks"])
        self.assertEqual([CLAUDE_SETTINGS], plan["update"])
        installed = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(self.user["permissions"], installed["permissions"])
        self.assertEqual(self.user["env"], installed["env"])
        self.assertEqual(self.user["hooks"]["Stop"], installed["hooks"]["Stop"])
        self.assertEqual(self.user["hooks"]["PostToolUse"][0], installed["hooks"]["PostToolUse"][0])
        for event, entry in HOOKS.items():
            self.assertEqual(1, installed["hooks"][event].count(entry))
        ledger = self.ledger()
        self.assertEqual(managed_hooks(), ledger["managed-hooks"])
        self.assertIn("hooks", ledger["managed-components"])
        self.assertIn(CLAUDE_SETTINGS, ledger["files"])
        self.assertTrue(projection_is_verified(self.plan()))
        # Reinstalling is byte-stable, and the hooks record survives other components.
        before = self.path.read_bytes()
        install("claude-code", self.project, components=["hooks"])
        install("claude-code", self.project, components=["agents", "skills"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(managed_hooks(), self.ledger()["managed-hooks"])
        self.assertIn(CLAUDE_SETTINGS, self.ledger()["files"])

    def test_creates_missing_settings(self) -> None:
        self.assertEqual([CLAUDE_SETTINGS], self.plan()["create"])
        install("claude-code", self.project, components=["hooks"])
        self.assertEqual({"hooks": managed_hooks()}, json.loads(self.path.read_text(encoding="utf-8")))
        self.assertTrue(projection_is_verified(self.plan()))

    def test_verify_reports_drift_but_not_user_edits(self) -> None:
        write_json(self.path, self.user)
        install("claude-code", self.project, components=["hooks"])
        settings = json.loads(self.path.read_text(encoding="utf-8"))
        settings["env"]["ANOTHER"] = "user"
        settings["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "second"}]})
        write_json(self.path, settings)
        self.assertTrue(projection_is_verified(self.plan()))
        self.assertEqual(0, self.verify_cli())
        # A removed managed entry is drift that installation restores.
        settings["hooks"]["SubagentStop"] = []
        write_json(self.path, settings)
        self.assertEqual([CLAUDE_SETTINGS], self.plan()["update"])
        self.assertEqual(1, self.verify_cli())
        # A changed managed entry is a conflict that installation refuses, even with --force.
        changed = json.loads(json.dumps(HOOKS["SubagentStop"]))
        changed["hooks"][0]["timeout"] = 60
        settings["hooks"]["SubagentStop"] = [changed]
        write_json(self.path, settings)
        self.assertEqual([CLAUDE_SETTINGS], self.plan()["conflict"])
        self.assertEqual(1, self.verify_cli())
        original = self.path.read_bytes()
        for force in (False, True):
            with self.assertRaisesRegex(RuntimeError, "differs"):
                install("claude-code", self.project, components=["hooks"], force=force)
        self.assertEqual(original, self.path.read_bytes())

    def test_malformed_settings_are_conflicts_and_preserved(self) -> None:
        for content in ("{", "[]", '{"hooks": []}', '{"hooks": {"PreToolUse": "bad"}}'):
            with self.subTest(content=content):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(content, encoding="utf-8")
                self.assertEqual([CLAUDE_SETTINGS], self.plan()["conflict"])
                with self.assertRaises(RuntimeError):
                    install("claude-code", self.project, components=["hooks"])
                self.assertEqual(content, self.path.read_text(encoding="utf-8"))

    def test_recorded_obsolete_entry_is_replaced_but_unrecorded_one_conflicts(self) -> None:
        install("claude-code", self.project, components=["hooks"])
        old = {"matcher": "Read", "hooks": [{"type": "command", "command": GUARD_COMMAND, "timeout": 5}]}
        settings = json.loads(self.path.read_text(encoding="utf-8"))
        settings["hooks"]["PreToolUse"] = [old]
        write_json(self.path, settings)
        self.assertEqual([CLAUDE_SETTINGS], self.plan()["conflict"])
        state = _projection_state_path(self.project, "claude-code")
        ledger = read_json(state)
        ledger["managed-hooks"]["PreToolUse"] = [old]
        write_json(state, ledger)
        self.assertEqual([CLAUDE_SETTINGS], self.plan()["update"])
        install("claude-code", self.project, components=["hooks"])
        self.assertEqual([HOOKS["PreToolUse"]], json.loads(self.path.read_text(encoding="utf-8"))["hooks"]["PreToolUse"])
        self.assertEqual(managed_hooks(), self.ledger()["managed-hooks"])

    def test_hooks_require_a_verified_scoped_projection(self) -> None:
        (self.project / ".claude/embraion-native.json").write_text("{}", encoding="utf-8")
        for dry_run in (True, False):
            with self.assertRaisesRegex(RuntimeError, "scoped-agents"):
                install("claude-code", self.project, components=["hooks"], dry_run=dry_run)
        self.assertFalse(self.path.exists())
        install("claude-code", self.project, components=["scoped-agents", "hooks"], force=True)
        self.assertTrue(projection_is_verified(
            projection_plan("claude-code", self.project, components=["scoped-agents", "hooks"])))

    def test_existing_install_command_delegates_to_the_component(self) -> None:
        write_json(self.path, self.user)
        report = install_observer_hooks(self.project)
        self.assertEqual(sorted(HOOKS), sorted(report["added"]))
        self.assertEqual(managed_hooks(), self.ledger()["managed-hooks"])
        self.assertTrue(projection_is_verified(self.plan()))
        self.assertEqual([], install_observer_hooks(self.project)["added"])
        self.assertIn(COMMAND, self.path.read_text(encoding="utf-8"))

    def verify_cli(self) -> int:
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(io.StringIO()):
            return main(["projection", "verify", "--host", "claude-code", "--destination", str(self.project),
                         "--component", "hooks"])


if __name__ == "__main__":
    unittest.main()
