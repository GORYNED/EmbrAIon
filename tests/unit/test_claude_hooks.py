from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.claude_hooks import COMMAND, HOOKS, hook_project, install_observer_hooks, observer_hooks_status
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

    def test_exact_hook_does_not_hide_malformed_or_conflicting_siblings(self):
        for event, expected in HOOKS.items():
            altered = json.loads(json.dumps(expected))
            altered["hooks"][0]["timeout"] = 60
            for sibling in ({"hooks": "bad"}, {"hooks": ["bad"]}, altered):
                for entries in ([expected, sibling], [sibling, expected]):
                    for dry_run in (True, False):
                        with self.subTest(event=event, entries=entries, dry_run=dry_run):
                            write_json(self.path, {"hooks": {event: entries}})
                            original = self.path.read_bytes()
                            with self.assertRaises(RuntimeError):
                                install_observer_hooks(self.project, dry_run=dry_run)
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

    def test_same_version_artifact_identity_and_runtime_origin_are_required(self):
        import os
        from embraion import __version__
        from embraion.common import framework_root, read_yaml

        manifest = self.project / ".embraion/project.yaml"
        data = read_yaml(manifest)
        artifact = {"schema": 1, "source": "github-release", "release": "v" + __version__,
                    "asset": "embraion-" + __version__ + "-py3-none-any.whl", "digest": "sha256:" + "a" * 64}
        data["framework"]["artifact"] = artifact
        write_yaml(manifest, data)
        payload = {"cwd": str(self.project)}
        # A standalone same-version distribution is not a digest-bound runtime.
        with self.assertRaisesRegex(RuntimeError, "artifact"):
            hook_project(payload)
        runtime = self.project / "runtime-fixture"
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.touch()
        active_framework = framework_root()
        marker = {"version": __version__, "framework-root": str(active_framework),
                  "artifact": {"repository": "GORYNED/EmbrAIon", "version": __version__, **artifact}}
        write_json(runtime / ".embraion-runtime.json", marker)
        with patch("sys.prefix", str(runtime)):
            self.assertEqual(self.project.resolve(), hook_project(payload))
            data["framework"]["artifact"]["digest"] = "sha256:" + "b" * 64
            write_yaml(manifest, data)
            with self.assertRaisesRegex(RuntimeError, "artifact"):
                hook_project(payload)
            data["framework"]["artifact"] = "malformed"
            write_yaml(manifest, data)
            with self.assertRaises(RuntimeError):
                hook_project(payload)
            data["framework"]["artifact"] = {**artifact, "digest": "sha256:" + "a" * 64}
            write_yaml(manifest, data)
            marker["framework-root"] = str(self.project)
            write_json(runtime / ".embraion-runtime.json", marker)
            with self.assertRaisesRegex(RuntimeError, "artifact"):
                hook_project(payload)


if __name__ == "__main__":
    unittest.main()
