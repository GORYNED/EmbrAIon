from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.claude_guard import _case_insensitive_paths, guard
from embraion.claude_native import configured_assignments, definition_markdown, projection_metadata
from embraion.common import read_yaml, write_json, write_yaml
from embraion.project import init_project


class ClaudeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="Claude Guard")
        write_yaml(self.project / ".embraion/claude-native.yaml", {
            "bindings": {"worker": "worker"},
            "assignments": [{"role": "worker", "route-class": "complex",
                             "data-class": "PRIVATE", "access": "write"}],
            "read-policy": {"project-only": True, "deny-protected": True},
        })
        write_yaml(self.project / ".embraion/routing.yaml", {"overrides": {"claude-code": {
            "routes": {"complex": {"model": "claude-fable-5-1", "effort": "high"}},
        }}})
        policy_path = self.project / ".embraion/policy.yaml"
        policy = read_yaml(policy_path)
        policy["sources"]["protected"] = ["secret/**", "Assets/Project/private/**/*.cs"]
        write_yaml(policy_path, policy)
        self.name = self.install_fixture()
        (self.project / "secret").mkdir()
        (self.project / "secret/key.txt").write_text("never-log-this", encoding="utf-8")
        (self.project / "docs").mkdir()
        (self.project / "docs/safe.txt").write_text("safe", encoding="utf-8")

    def install_fixture(self) -> str:
        records = configured_assignments(self.project)
        metadata = projection_metadata(records)
        write_json(self.project / ".claude/embraion-native.json", metadata)
        for record in records:
            definition = record["plan"]["scoped-definition"]
            path = self.project / ".claude/agents" / (definition["name"] + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(definition_markdown(definition), encoding="utf-8", newline="\n")
        return metadata["assignments"][0]["name"]

    def payload(self, tool: str, inputs: dict, *, agent_type: str | None = None,
                agent_id: str | None = "agent-1") -> dict:
        return {"hook_event_name": "PreToolUse", "tool_name": tool,
                "tool_input": inputs, "agent_type": agent_type or self.name,
                "agent_id": agent_id}

    def assert_denied(self, payload: dict) -> None:
        result = guard(payload, self.project)
        self.assertEqual("PreToolUse", result["hookSpecificOutput"]["hookEventName"])
        self.assertEqual("deny", result["hookSpecificOutput"]["permissionDecision"])
        self.assertNotIn("never-log-this", json.dumps(result))
        self.assertNotIn("secret/key.txt", json.dumps(result))

    def test_read_protected_and_project_boundary(self) -> None:
        self.assert_denied(self.payload("Read", {"file_path": "secret/key.txt"}))
        self.assert_denied(self.payload("Read", {"file_path": "docs/safe.txt",
                                                 "unknown": "never-log-this"}))
        self.assertEqual({}, guard(self.payload("Read", {"file_path": "docs/safe.txt"}), self.project))
        self.assert_denied(self.payload("Read", {"file_path": "/etc/passwd"}))
        with tempfile.TemporaryDirectory() as outside:
            (self.project / "docs/outside").symlink_to(Path(outside), target_is_directory=True)
            self.assert_denied(self.payload("Read", {"file_path": "docs/outside/private.txt"}))
        self.assert_denied(self.payload("Read", {"file_path": "../secret/key.txt"}))

    def test_read_denies_zero_depth_recursive_protected_paths(self) -> None:
        policy_path = self.project / ".embraion/policy.yaml"
        policy = read_yaml(policy_path)
        policy["sources"]["protected"] = [
            "Assets/Project/Vendor/SDK/**/*.cs",
            "Assets/Project/Vendor/Driver/**/*.dll",
            "Assets/StreamingAssets/Profiles/**/*.bin",
        ]
        write_yaml(policy_path, policy)
        for file_path in (
            "Assets/Project/Vendor/SDK/Adapter.cs",
            "Assets/Project/Vendor/SDK/nested/Adapter.cs",
            "Assets/Project/Vendor/Driver/driver.dll",
            "Assets/StreamingAssets/Profiles/device.bin",
        ):
            with self.subTest(file_path=file_path):
                self.assert_denied(self.payload("Read", {"file_path": file_path}))
        self.assertEqual({}, guard(self.payload("Read", {"file_path":
                                                      "Assets/Project/Vendor/SDK/sibling.txt"}),
                                    self.project))
        with patch("embraion.claude_guard._case_insensitive_paths", return_value=True):
            self.assert_denied(self.payload("Read", {"file_path":
                                                    "assets/project/vendor/sdk/ADAPTER.CS"}))

    def test_overcomplex_protected_pattern_denies_scoped_read_and_search(self) -> None:
        policy_path = self.project / ".embraion/policy.yaml"
        policy = read_yaml(policy_path)
        policy["sources"]["protected"] = ["**/" * 9 + "secret.txt"]
        write_yaml(policy_path, policy)
        self.assert_denied(self.payload("Read", {"file_path": "docs/safe.txt"}))
        self.assert_denied(self.payload("Grep", {"pattern": "safe", "path": "docs"}))

    def test_broad_search_denied_but_scoped_config_search_allowed(self) -> None:
        self.assert_denied(self.payload("Grep", {"pattern": "never-log-this"}))
        self.assert_denied(self.payload("Glob", {"pattern": "**/*"}))
        self.assert_denied(self.payload("Grep", {"pattern": "x", "path": "Assets/Project"}))
        self.assert_denied(self.payload("Glob", {"pattern": "secret/**"}))
        self.assertEqual({}, guard(self.payload("Grep", {"pattern": "x", "path": ".embraion"}),
                                    self.project))
        self.assertEqual({}, guard(self.payload("Glob", {"path": ".claude", "pattern": "**/*.md"}),
                                    self.project))
        self.assertEqual({}, guard(self.payload("Glob", {"pattern": ".codex/**/*.toml"}),
                                    self.project))
        with tempfile.TemporaryDirectory() as outside:
            (self.project / "docs/outside").symlink_to(Path(outside), target_is_directory=True)
            self.assert_denied(self.payload("Grep", {"pattern": "x", "path": "docs/outside"}))

    def test_only_exact_scoped_read_identity_is_guarded_and_stale_is_denied(self) -> None:
        root = self.payload("Read", {"file_path": "secret/key.txt"}, agent_type="lead")
        self.assertEqual({}, guard(root, self.project))
        self.assertEqual({}, guard(self.payload("Read", {"file_path": "secret/key.txt"},
                                                 agent_type="general-purpose"), self.project))
        for agent_id in (None, "", "invalid id"):
            with self.subTest(agent_id=agent_id):
                self.assert_denied(self.payload("Read", {"file_path": "secret/key.txt"},
                                                agent_id=agent_id))
        self.assert_denied(self.payload("Read", {"file_path": "docs/safe.txt"},
                                        agent_type="embraion--stale-profile", agent_id=None))
        self.assertEqual({}, guard(self.payload("Read", {"file_path": "secret/key.txt"},
                                                 agent_type="general-purpose", agent_id=None), self.project))
        metadata = self.project / ".claude/embraion-native.json"
        metadata.write_text("{}", encoding="utf-8")
        self.assert_denied(self.payload("Read", {"file_path": "docs/safe.txt"}))

    def test_agent_gate_blocks_base_binding_and_scoped_overrides(self) -> None:
        self.assert_denied(self.payload("Agent", {"subagent_type": "worker", "prompt": "task"},
                                        agent_type="lead"))
        self.assertEqual({}, guard(self.payload("Agent", {"subagent_type": "general-purpose",
                                                      "prompt": "task"}, agent_type="lead"), self.project))
        self.assertEqual({}, guard(self.payload("Agent", {"subagent_type": self.name,
                                                      "prompt": "task"}, agent_type="lead"), self.project))
        for extra in ({"model": "opus"}, {"reasoning_effort": "low"}, {"modelId": "opus"}):
            with self.subTest(extra=extra):
                self.assert_denied(self.payload("Agent", {"subagent_type": self.name,
                                                         "prompt": "task", **extra}, agent_type="lead"))
        metadata = self.project / ".claude/embraion-native.json"
        metadata.write_text("{}", encoding="utf-8")
        self.assert_denied(self.payload("Agent", {"subagent_type": self.name,
                                                 "prompt": "task"}, agent_type="lead"))

    def test_windows_protected_paths_compare_without_case(self) -> None:
        with patch("embraion.claude_guard._case_insensitive_paths", return_value=True):
            self.assert_denied(self.payload("Read", {"file_path": "SECRET/KEY.TXT"}))
            self.assert_denied(self.payload("Grep", {"pattern": "x", "path": "assets/PROJECT"}))
            self.assert_denied(self.payload("Glob", {"pattern": "SeCrEt/**/*"}))
            self.assertEqual({}, guard(self.payload("Glob", {"path": ".CLAUDE",
                                                      "pattern": "**/*.md"}), self.project))

    def test_case_insensitive_project_volume_protects_mixed_case_paths(self) -> None:
        with patch("embraion.claude_guard.os.path.samefile", return_value=True) as samefile:
            self.assertTrue(_case_insensitive_paths(self.project))
            self.assert_denied(self.payload("Read", {"file_path": "SECRET/KEY.TXT"}))
            self.assert_denied(self.payload("Grep", {"pattern": "x", "path": "assets/PROJECT"}))
            if os.name != "nt":
                samefile.assert_any_call(self.project / ".embraion", self.project / ".EMBRAION")

    def test_glob_expansion_syntax_cannot_hide_protected_scope(self) -> None:
        for inputs in (
            {"pattern": "{docs,secret}/**"},
            {"pattern": "{docs,../secret}/**"},
            {"pattern": "@(docs|secret)/**"},
            {"pattern": "docs/(../secret)/**"},
            {"path": "{docs,secret}", "pattern": "**/*"},
        ):
            with self.subTest(inputs=inputs):
                self.assert_denied(self.payload("Glob", inputs))
        self.assertEqual({}, guard(self.payload("Glob", {"pattern": "docs/**/*.txt"}),
                                    self.project))

    def test_glob_bracket_class_cannot_hide_protected_prefix(self) -> None:
        self.assert_denied(self.payload("Glob", {"pattern": "[s]ecret/**"}))
        self.assert_denied(self.payload("Glob", {"pattern": "[sd]ecret/**"}))
        self.assertEqual({}, guard(self.payload("Glob", {"pattern": "docs/[ab]*.txt"}),
                                    self.project))

    def test_scoped_agent_rejects_isolation_and_resume_without_propagation_proof(self) -> None:
        base = {"subagent_type": self.name, "prompt": "task"}
        self.assertEqual({}, guard(self.payload("Agent", base, agent_type="lead"), self.project))
        for override in ({"isolation": "remote"}, {"isolation": "worktree"},
                         {"isolation": None}, {"resume": "old-agent"}, {"resume": None}):
            with self.subTest(override=override):
                self.assert_denied(self.payload("Agent", {**base, **override}, agent_type="lead"))

    def test_legacy_task_launch_uses_the_same_scoped_guard(self) -> None:
        current = {"subagent_type": self.name, "prompt": "task"}
        self.assertEqual({}, guard(self.payload("Task", current, agent_type="lead"), self.project))
        self.assertEqual({}, guard(self.payload("Task", {"subagent_type": "general-purpose",
                                                     "prompt": "task"}, agent_type="lead"), self.project))
        for inputs in (
            {"subagent_type": "worker", "prompt": "task"},
            {"subagent_type": "embraion--stale-profile", "prompt": "task"},
            {**current, "model": "opus"},
            {**current, "isolation": "remote"},
            {**current, "resume": "old-agent"},
        ):
            with self.subTest(inputs=inputs):
                self.assert_denied(self.payload("Task", inputs, agent_type="lead"))
        (self.project / ".claude/embraion-native.json").write_text("{}", encoding="utf-8")
        self.assert_denied(self.payload("Task", current, agent_type="lead"))

    def test_read_guard_is_opt_in_but_agent_binding_gate_remains_active(self) -> None:
        path = self.project / ".embraion/claude-native.yaml"
        config = read_yaml(path)
        config.pop("read-policy")
        write_yaml(path, config)
        self.assertEqual({}, guard(self.payload("Read", {"file_path": "secret/key.txt"}),
                                    self.project))
        self.assert_denied(self.payload("Agent", {"subagent_type": "worker", "prompt": "task"},
                                        agent_type="lead"))

    def test_single_hyphen_project_agent_is_unrelated_unless_explicitly_bound(self) -> None:
        base_name = "embraion-helper"
        self.assertEqual({}, guard(self.payload("Agent", {"subagent_type": base_name,
                                                      "prompt": "task"}, agent_type="lead"), self.project))
        self.assertEqual({}, guard(self.payload("Read", {"file_path": "secret/key.txt"},
                                                 agent_type=base_name, agent_id=None), self.project))

        write_yaml(self.project / ".embraion/agents.yaml", {"agents": [{
            "id": base_name, "extends": "worker", "purpose": "Project specialist.",
            "access": "workspace-write", "responsibilities": ["Implement bounded project work."],
        }]})
        config_path = self.project / ".embraion/claude-native.yaml"
        config = read_yaml(config_path)
        config["bindings"]["worker"] = base_name
        write_yaml(config_path, config)
        self.install_fixture()
        self.assert_denied(self.payload("Agent", {"subagent_type": base_name,
                                                 "prompt": "task"}, agent_type="lead"))
        self.assertEqual({}, guard(self.payload("Read", {"file_path": "secret/key.txt"},
                                                 agent_type=base_name, agent_id=None), self.project))


if __name__ == "__main__":
    unittest.main()
