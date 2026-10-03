from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.claude_hooks import COMMAND, HOOKS, install_observer_hooks, observer_hooks_status
from embraion.claude_native import observer_status
from embraion.cli import main
from embraion.common import write_json, write_yaml
from embraion.project import init_project, install


class ClaudeHookInstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="HookInstallation")
        write_yaml(self.project / ".embraion/routing.yaml", {
            "overrides": {"claude-code": {"routes": {
                "complex": {"model": "claude-opus-5-5", "effort": "high"}}}}})
        write_yaml(self.project / ".embraion/claude-native.yaml", {
            "bindings": {"reviewer": "reviewer"}, "assignments": [
                {"role": "reviewer", "route-class": "complex", "data-class": "PRIVATE", "access": "review"}]})
        install("claude-code", self.project, components=["scoped-agents"])
        self.path = self.project / ".claude/settings.json"

    def test_merge_preserves_other_settings_and_is_idempotent(self):
        original = {"permissions": {"deny": ["Read(.env)"]},
                    "hooks": {"PostToolUse": [{"matcher": "Edit", "hooks": [
                        {"type": "command", "command": "project-validator"}]}]},
                    "env": {"PROJECT_SETTING": "preserve"}}
        write_json(self.path, original)
        report = install_observer_hooks(self.project, dry_run=True)
        self.assertEqual(3, len(report["added"]))
        self.assertEqual(original, json.loads(self.path.read_text()))
        install_observer_hooks(self.project)
        installed = json.loads(self.path.read_text())
        self.assertEqual("Agent|Task|Read|Grep|Glob", installed["hooks"]["PreToolUse"][-1]["matcher"])
        self.assertEqual(original["permissions"], installed["permissions"])
        self.assertEqual(original["env"], installed["env"])
        self.assertEqual(original["hooks"]["PostToolUse"][0], installed["hooks"]["PostToolUse"][0])
        first = self.path.read_bytes()
        self.assertEqual([], install_observer_hooks(self.project)["added"])
        self.assertEqual(first, self.path.read_bytes())
        self.assertTrue(observer_hooks_status(self.project)["installed"])
        status = observer_status(self.project)
        self.assertTrue(status["hooks"]["installed"])
        self.assertEqual("unverified", status["execution"])
        self.assertEqual("unverified", status["hooks"]["instructions-loaded"])

    def test_stale_projection_or_conflicting_hook_cannot_change_settings(self):
        write_json(self.path, {"hooks": {"PostToolUse": [{"hooks": [
            {"type": "command", "command": COMMAND, "timeout": 60}]}]}})
        original = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "differs"):
            install_observer_hooks(self.project)
        self.assertEqual(original, self.path.read_bytes())
        (self.project / ".claude/embraion-native.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "scoped-agents"):
            install_observer_hooks(self.project)
        self.assertEqual(original, self.path.read_bytes())

    def test_malformed_existing_hook_structure_is_preserved(self):
        for settings in ({"hooks": []}, {"hooks": {"SubagentStop": "bad"}},
                         {"hooks": {"PostToolUse": [{"hooks": "bad"}]}}):
            with self.subTest(settings=settings):
                write_json(self.path, settings)
                original = self.path.read_bytes()
                with self.assertRaises(RuntimeError):
                    install_observer_hooks(self.project)
                self.assertEqual(original, self.path.read_bytes())

    def test_hook_cli_never_echoes_private_payload_on_bad_json(self):
        import io
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
             patch("sys.stdin", io.StringIO('{"private": "do-not-echo"')), \
             patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            self.assertEqual(0, main(["claude-native", "observe"]))
        self.assertEqual("", stdout.getvalue() + stderr.getvalue())
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
             patch("sys.stdin", io.StringIO('{"private": "do-not-echo"')), \
             patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            self.assertEqual(0, main(["claude-native", "guard"]))
        self.assertNotIn("do-not-echo", stdout.getvalue() + stderr.getvalue())
        self.assertEqual("deny", json.loads(stdout.getvalue())["hookSpecificOutput"]["permissionDecision"])


if __name__ == "__main__":
    unittest.main()
