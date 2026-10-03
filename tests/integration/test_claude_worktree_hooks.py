from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.claude_native import observer_status
from embraion.common import read_yaml, write_yaml
from embraion.environment import child_environment
from embraion.project import init_project, install


class ClaudeWorktreeHookTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.main = Path(temporary.name).resolve() / "project"
        self.main.mkdir()
        init_project(self.main, name="HookWorktree")
        write_yaml(self.main / ".embraion/routing.yaml", {
            "overrides": {"claude-code": {"routes": {
                "complex": {"model": "claude-opus-5-5", "effort": "high"}}}}})
        write_yaml(self.main / ".embraion/claude-native.yaml", {
            "bindings": {"reviewer": "reviewer"}, "assignments": [
                {"role": "reviewer", "route-class": "complex", "data-class": "PRIVATE", "access": "review"}],
            "read-policy": {"project-only": True, "deny-protected": True}})
        install("claude-code", self.main, components=["scoped-agents"])
        from embraion.claude_hooks import install_observer_hooks

        install_observer_hooks(self.main)
        metadata = json.loads((self.main / ".claude/embraion-native.json").read_text())
        self.agent = metadata["assignments"][0]["name"]
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "Hook fixture")
        self.worktree = self.main / ".claude/worktrees/review"
        self.git("worktree", "add", "--detach", str(self.worktree), "HEAD")
        # The hash-named definition stays identical; the working-tree policy
        # differs, so a main-checkout fallback would incorrectly allow reads.
        policy_path = self.worktree / ".embraion/policy.yaml"
        policy = read_yaml(policy_path)
        policy["sources"]["protected"] = ["secret/**"]
        write_yaml(policy_path, policy)
        (self.worktree / "secret").mkdir()
        (self.worktree / "secret/key.txt").write_text("never-echo-this", encoding="utf-8")
        (self.worktree / "docs").mkdir(exist_ok=True)
        (self.worktree / "docs/safe.txt").write_text("safe", encoding="utf-8")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.main), *args], check=True,
                       capture_output=True, text=True, env=child_environment())

    def payload(self, event: str, *, cwd: object | None = None, tool="Read",
                inputs: dict | None = None) -> dict:
        return {"hook_event_name": event, "cwd": str(self.worktree) if cwd is None else cwd,
                "agent_id": "agent-1", "agent_type": self.agent, "session_id": "session-1",
                "tool_name": tool, "tool_input": inputs or {"file_path": "docs/safe.txt"},
                "effort": {"level": "high"}, "tool_response": "never-echo-this"}

    def hook(self, command: str, payload: dict) -> str:
        environment = child_environment()
        environment["EMBRAION_DISABLE_VERSION_RESOLUTION"] = "1"
        result = subprocess.run([sys.executable, "-m", "embraion.cli", "claude-native", command],
                                cwd=self.main, env=environment, input=json.dumps(payload),
                                text=True, capture_output=True, check=True)
        self.assertNotIn("never-echo-this", result.stdout + result.stderr)
        self.assertEqual("", result.stderr)
        return result.stdout

    def test_process_in_main_records_only_in_event_worktree(self) -> None:
        for event in ("PostToolUse", "SubagentStop"):
            self.assertEqual("", self.hook("observe", self.payload(event)))
        self.assertFalse((self.main / ".embraion/state/claude-native-evidence.jsonl").exists())
        path = self.worktree / ".embraion/state/claude-native-evidence.jsonl"
        rows = [json.loads(row) for row in path.read_text().splitlines()]
        self.assertEqual(["PostToolUse", "SubagentStop"], [row["event"] for row in rows])
        self.assertEqual("recorded", observer_status(self.worktree)["callbacks"])
        self.assertEqual("none", observer_status(self.main)["callbacks"])
        self.assertEqual("unverified", observer_status(self.worktree)["effort"])
        self.assertNotIn("cwd", rows[0])
        self.assertNotIn("tool_response", rows[0])

    def test_guard_uses_worktree_policy_and_relative_and_absolute_paths(self) -> None:
        for path in ("secret/key.txt", str(self.worktree / "secret/key.txt")):
            result = json.loads(self.hook("guard", self.payload("PreToolUse", inputs={"file_path": path})))
            self.assertEqual("deny", result["hookSpecificOutput"]["permissionDecision"])
        for path in ("docs/safe.txt", str(self.worktree / "docs/safe.txt")):
            self.assertEqual("", self.hook("guard", self.payload("PreToolUse", inputs={"file_path": path})))
        self.assertEqual("", self.hook("guard", self.payload("PreToolUse", cwd=str(self.worktree / "docs"))))
        denied = json.loads(self.hook("guard", self.payload("PreToolUse", tool="Agent", inputs={
            "subagent_type": self.agent, "model": "sonnet"})))
        self.assertEqual("deny", denied["hookSpecificOutput"]["permissionDecision"])

    def test_invalid_context_never_falls_back_to_main(self) -> None:
        invalid = ("relative", "", "bad\x00path", 123, [], str(self.main / "missing"),
                   str(self.worktree / "docs/safe.txt"), str(self.main.parent))
        for cwd in invalid:
            with self.subTest(cwd=cwd):
                denied = json.loads(self.hook("guard", self.payload("PreToolUse", cwd=cwd)))
                self.assertEqual("deny", denied["hookSpecificOutput"]["permissionDecision"])
                self.assertEqual("", self.hook("observe", self.payload("SubagentStop", cwd=cwd)))
        self.assertFalse((self.main / ".embraion/state/claude-native-evidence.jsonl").exists())
        self.assertFalse((self.worktree / ".embraion/state/claude-native-evidence.jsonl").exists())

    def test_different_worktree_pin_and_malformed_manifest_fail_closed(self) -> None:
        manifest = self.worktree / ".embraion/project.yaml"
        original = manifest.read_text()
        data = read_yaml(manifest)
        data["framework"]["version"] = "0.1.0"
        write_yaml(manifest, data)
        for text in (manifest.read_text(), "framework: [never-echo-this", "- never-echo-this"):
            manifest.write_text(text, encoding="utf-8")
            denied = json.loads(self.hook("guard", self.payload("PreToolUse")))
            self.assertEqual("deny", denied["hookSpecificOutput"]["permissionDecision"])
            self.assertEqual("", self.hook("observe", self.payload("SubagentStop")))
        manifest.write_text(original, encoding="utf-8")

    def test_explicit_project_cannot_redirect_event_and_null_cwd_is_invalid(self) -> None:
        from embraion.claude_guard import guard
        from embraion.claude_native import observe

        for payload in (self.payload("PreToolUse"), dict(self.payload("PreToolUse"), cwd=None)):
            self.assertEqual("deny", guard(payload, self.main)["hookSpecificOutput"]["permissionDecision"])
        payload = self.payload("SubagentStop")
        self.assertEqual("invalid-hook-project", observe(payload, self.main)["reason"])
        payload["cwd"] = None
        self.assertEqual("invalid-hook-project", observe(payload)["reason"])

    def test_legacy_payload_without_cwd_keeps_process_context(self) -> None:
        payload = self.payload("SubagentStop")
        del payload["cwd"]
        self.assertEqual("", self.hook("observe", payload))
        self.assertEqual("recorded", observer_status(self.main)["callbacks"])
        self.assertFalse((self.worktree / ".embraion/state/claude-native-evidence.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
