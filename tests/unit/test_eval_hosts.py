from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.adapters.eval_hosts import invoke_host, preflight_host
from embraion.skill_evals import _events, _invoke_codex


class EventUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "events.jsonl"

    def observe(self, *events: dict) -> dict:
        self.path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        return _events(self.path, [])

    def test_two_complete_turns_have_complete_usage(self) -> None:
        result = self.observe(
            {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 5}},
            {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 11}},
        )
        self.assertTrue(result["usage-complete"])
        self.assertEqual({"input_tokens": 10, "output_tokens": 16}, result["tokens"])

    def test_one_incomplete_turn_does_not_hide_partial_usage(self) -> None:
        result = self.observe(
            {"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 5}},
            {"type": "turn.completed", "usage": {"input_tokens": 7}},
        )
        self.assertFalse(result["usage-complete"])
        self.assertEqual({"input_tokens": 10, "output_tokens": 5}, result["tokens"])

    def test_malformed_usage_and_no_completion_are_unverified(self) -> None:
        result = self.observe({"type": "turn.completed", "usage": {"input_tokens": True, "output_tokens": -1}})
        self.assertFalse(result["usage-complete"])
        self.assertEqual({}, result["tokens"])
        self.assertFalse(self.observe({"type": "turn.started"})["usage-complete"])


class NativeRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        (self.project / ".codex/agents").mkdir(parents=True)
        (self.project / ".codex/config.toml").write_text('developer_instructions="lead instructions"\n', encoding="utf-8")
        (self.project / ".codex/agents/reviewer.toml").write_text(
            'name="reviewer"\nsandbox_mode="read-only"\ndeveloper_instructions="reviewer instructions"\n',
            encoding="utf-8",
        )
        (self.project / ".codex/agents/worker.toml").write_text(
            'name="worker"\nsandbox_mode="workspace-write"\ndeveloper_instructions="worker instructions"\n',
            encoding="utf-8",
        )

    def invoke(self, **kwargs):
        with patch("embraion.experiment_evals._scratch_root", return_value=self.root):
            return invoke_host("codex", "unused", self.project, "prompt", "gpt-6-sol", "medium", 1, [], self.root, **kwargs)

    def test_lead_and_reviewer_translate_read_only(self) -> None:
        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex", side_effect=lambda *args, **kwargs: {"status": "completed"}
        ) as native:
            lead = self.invoke(role="lead", access="read-only")
            self.assertEqual("lead instructions", native.call_args.kwargs["developer_instructions"])
            self.assertEqual("read-only", native.call_args.kwargs["sandbox"])
            reviewer = self.invoke(role="reviewer", access="read-only")
            self.assertEqual("reviewer instructions", native.call_args.kwargs["developer_instructions"])
            self.assertEqual("read-only", native.call_args.kwargs["sandbox"])
        self.assertEqual("lead-profile-explicit-argument", lead["role-evidence"])
        self.assertEqual("reviewer-profile-explicit-argument", reviewer["role-evidence"])
        self.assertEqual("read-only", reviewer["access-evidence"])

    def test_read_only_role_cannot_widen_and_unknown_role_rejects(self) -> None:
        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex"
        ) as native:
            self.assertEqual("native-config-unverified", self.invoke(role="reviewer", access="workspace-write")["status"])
            with self.assertRaisesRegex(ValueError, "role"):
                self.invoke(role="unknown")
            native.assert_not_called()

    def test_all_non_lead_profiles_translate_with_worker_narrowing(self) -> None:
        roles = {"worker": "workspace-write", "reviewer": "read-only", "architect": "read-only",
                 "analyst": "read-only", "validator": "workspace-write", "researcher": "read-only",
                 "steward": "workspace-write"}
        for role, ceiling in roles.items():
            (self.project / f".codex/agents/{role}.toml").write_text(
                f'name="{role}"\nsandbox_mode="{ceiling}"\ndeveloper_instructions="{role} instructions"\n',
                encoding="utf-8",
            )
        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex", side_effect=lambda *args, **kwargs: {"status": "completed"}
        ) as native:
            for role, ceiling in roles.items():
                result = self.invoke(role=role, access="read-only")
                self.assertEqual(f"{role}-profile-explicit-argument", result["role-evidence"])
                self.assertEqual("read-only", native.call_args.kwargs["sandbox"])
                self.assertEqual(f"{role} instructions", native.call_args.kwargs["developer_instructions"])

    def test_model_bearing_profile_rejects(self) -> None:
        profile = self.project / ".codex/agents/worker.toml"
        profile.write_text(profile.read_text(encoding="utf-8") + 'model="other"\n', encoding="utf-8")
        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex"
        ) as native:
            self.assertEqual("native-config-unverified", self.invoke()["status"])
            native.assert_not_called()

    def test_read_only_role_rejects_writable_profile(self) -> None:
        profile = self.project / ".codex/agents/reviewer.toml"
        profile.write_text(profile.read_text(encoding="utf-8").replace("read-only", "workspace-write"), encoding="utf-8")
        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex"
        ) as native:
            self.assertEqual("native-config-unverified", self.invoke(role="reviewer", access="read-only")["status"])
            native.assert_not_called()

    def test_observer_sees_raw_then_temporary_data_is_removed(self) -> None:
        seen = []

        def native(*args, **kwargs):
            raw = args[-1]
            (raw / "events.jsonl").write_text("private canary", encoding="utf-8")
            seen.append(raw)
            return {"status": "completed"}

        def observer(raw, result):
            self.assertEqual(seen[-1], raw)
            self.assertEqual("private canary", (raw / "events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("completed", result["status"])
            return {"status": "pass", "observer-id": "canary"}

        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex", side_effect=native
        ):
            result = self.invoke(observer=observer)
        self.assertEqual({"status": "pass", "observer-id": "canary"}, result["observer"])
        self.assertFalse(seen[0].exists())
        self.assertNotIn("private canary", str(result))

    def test_observer_error_is_typed_inconclusive(self) -> None:
        def observer(raw, result):
            raise RuntimeError("private canary")

        with patch("embraion.adapters.eval_hosts._windows_sandbox", return_value="unelevated"), patch(
            "embraion.adapters.eval_hosts._invoke_codex", return_value={"status": "completed"}
        ):
            result = self.invoke(observer=observer)
        self.assertEqual({"status": "inconclusive", "reason": "observer-unavailable"}, result["observer"])
        self.assertNotIn("private canary", str(result))

    def test_invoker_validates_and_emits_explicit_sandbox(self) -> None:
        with self.assertRaisesRegex(ValueError, "sandbox"):
            _invoke_codex("unused", self.project, "prompt", None, None, 1, [], self.root, sandbox="danger-full-access")
        with patch("embraion.skill_evals.subprocess.Popen") as process:
            process.return_value.poll.return_value = 0
            process.return_value.returncode = 0
            _invoke_codex("unused", self.project, "prompt", None, None, 1, [], self.root, sandbox="read-only")
        argv = process.call_args.args[0]
        self.assertEqual("read-only", argv[argv.index("--sandbox") + 1])

    def test_read_only_preflight_uses_reviewer_and_actual_nonce_answer(self) -> None:
        home = self.root / "eval-home"
        home.mkdir()
        (home / "config.toml").write_text("# private profile\n", encoding="utf-8")
        (home / "embraion-eval-profile.json").write_text(
            json.dumps({"schema-version": 1, "purpose": "embraion-native-eval"}), encoding="utf-8")
        workspace = self.root / "preflight-project"
        observed = []

        def invoke(host, binary, project, prompt, model, effort, timeout, skills, scratch, **kwargs):
            self.assertEqual(("reviewer", "read-only"), (kwargs["role"], kwargs["access"]))
            self.assertEqual("gpt-6-sol", model)
            self.assertTrue((project / ".codex/agents/reviewer.toml").is_file())
            self.assertFalse((project / ".codex/agents/worker.toml").exists())
            self.assertNotIn("write its exact contents", prompt)
            nonce = (project / "marker.txt").read_text(encoding="utf-8")
            with tempfile.TemporaryDirectory(dir=self.root) as raw:
                directory = Path(raw)
                (directory / "last-message.txt").write_text(nonce if len(observed) == 0 else "wrong", encoding="utf-8")
                summary = kwargs["observer"](directory, {"status": "completed"})
            observed.append(nonce)
            return {"status": "completed", "observer": summary}

        with patch.dict(os.environ, {"CODEX_HOME": str(home)}), patch(
            "embraion.adapters.eval_hosts.invoke_host", side_effect=invoke
        ):
            first = preflight_host("codex", "unused", self.project, "gpt-6-sol", "medium", 1,
                                   workspace=workspace, role="reviewer", access="read-only")
            self.assertEqual("pass", first["status"])
            self.assertEqual("fixture-read", first["kind"])
            self.assertTrue(first["read-verified"])
            self.assertFalse((workspace / "result.txt").exists())
            # A fresh workspace is required for each probe.
            workspace = self.root / "second-project"
            second = preflight_host("codex", "unused", self.project, "gpt-6-sol", "medium", 1,
                                    workspace=workspace, role="reviewer", access="read-only")
        self.assertEqual("inconclusive", second["status"])
        self.assertNotIn(observed[0], str(first))
        self.assertNotIn(observed[1], str(second))

    def test_lead_preflight_copies_lead_config_without_worker_profile(self) -> None:
        home = self.root / "eval-home"
        home.mkdir()
        (home / "config.toml").write_text("# private profile\n", encoding="utf-8")
        (home / "embraion-eval-profile.json").write_text(
            json.dumps({"schema-version": 1, "purpose": "embraion-native-eval"}), encoding="utf-8")

        def invoke(host, binary, project, prompt, model, effort, timeout, skills, scratch, **kwargs):
            self.assertEqual(("lead", "read-only"), (kwargs["role"], kwargs["access"]))
            self.assertIn("lead instructions", (project / ".codex/config.toml").read_text(encoding="utf-8"))
            self.assertFalse((project / ".codex/agents/worker.toml").exists())
            with tempfile.TemporaryDirectory(dir=self.root) as raw:
                directory = Path(raw)
                (directory / "last-message.txt").write_text(
                    (project / "marker.txt").read_text(encoding="utf-8"), encoding="utf-8")
                summary = kwargs["observer"](directory, {"status": "completed"})
            return {"status": "completed", "observer": summary}

        with patch.dict(os.environ, {"CODEX_HOME": str(home)}), patch(
            "embraion.adapters.eval_hosts.invoke_host", side_effect=invoke
        ):
            result = preflight_host("codex", "unused", self.project, "gpt-6-sol", "medium", 1,
                                    workspace=self.root / "lead-project", role="lead", access="read-only")
        self.assertEqual("pass", result["status"])


if __name__ == "__main__":
    unittest.main()
