from __future__ import annotations

import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process
from pathlib import Path
from unittest.mock import patch

from embraion.claude_native import (
    _lock_fd,
    _prepare_lock_file,
    _unlock_fd,
    configured_assignments,
    definition_markdown,
    observe,
    observer_status,
    projection_metadata,
    read_config,
)
from embraion.common import write_json, write_yaml
from embraion.project import init_project


def _exit_while_holding_lock(path: str) -> None:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    _lock_fd(fd)
    os._exit(0)


class ClaudeNativeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="ClaudeNativeFixture")

    def configure(self, *, role="worker", native="worker", access="write", effort="high") -> None:
        write_yaml(self.project / ".embraion/claude-native.yaml", {
            "bindings": {role: native},
            "assignments": [{"role": role, "route-class": "complex",
                             "data-class": "PRIVATE", "access": access}],
        })
        write_yaml(self.project / ".embraion/routing.yaml", {"overrides": {"claude-code": {
            "routes": {"complex": {"model": "claude-fable-5-1", "effort": effort}},
        }}})

    def install_fixture(self) -> dict:
        records = configured_assignments(self.project)
        metadata = projection_metadata(records)
        write_json(self.project / ".claude/embraion-native.json", metadata)
        for record in records:
            definition = record["plan"]["scoped-definition"]
            path = self.project / ".claude/agents" / (definition["name"] + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(definition_markdown(definition), encoding="utf-8", newline="\n")
        return metadata["assignments"][0]

    @staticmethod
    def hook(name: str, *, event="PostToolUse", effort="high") -> dict:
        return {"hook_event_name": event, "session_id": "session-1",
                "agent_id": "agent-1", "agent_type": name,
                "effort": {"level": effort}, "tool_input": {"secret": "never-log-this"},
                "tool_result": "never-log-this", "transcript_path": "/private/never-log-this"}

    def test_absent_opt_in_and_exact_configured_tuple(self) -> None:
        self.assertIsNone(read_config(self.project))
        self.assertEqual([], configured_assignments(self.project))
        self.configure()
        records = configured_assignments(self.project)
        self.assertEqual(1, len(records))
        self.assertEqual("worker", records[0]["native-agent"])
        self.assertEqual("handoff-required", records[0]["plan"]["status"])
        definition = records[0]["plan"]["scoped-definition"]
        self.assertEqual("claude-fable-5-1", definition["model"])
        self.assertEqual("high", definition["effort"])
        self.assertEqual(["Read", "Grep", "Glob", "Write", "Edit", "Bash"], definition["tools"])

    def test_bad_config_and_unscoped_route_fail_closed(self) -> None:
        self.configure()
        config_path = self.project / ".embraion/claude-native.yaml"
        write_yaml(config_path, {"bindings": {"worker": "worker"},
                                 "assignments": [{"role": "worker", "route-class": "complex",
                                                  "data-class": "UNKNOWN", "access": "write"}]})
        with self.assertRaises(RuntimeError):
            configured_assignments(self.project)
        self.configure()
        (self.project / ".embraion/routing.yaml").unlink()
        with self.assertRaisesRegex(RuntimeError, "explicit project routing"):
            configured_assignments(self.project)
        self.configure(role="reviewer", native="reviewer", access="write")
        with self.assertRaisesRegex(RuntimeError, "writable specialist"):
            configured_assignments(self.project)

    def test_config_accepts_long_agent_id_and_rejects_symlink_or_bad_read_policy(self) -> None:
        self.configure()
        path = self.project / ".embraion/claude-native.yaml"
        config = read_config(self.project)
        config["bindings"]["worker"] = "project-" + "long-" * 14 + "worker"
        config["read-policy"] = {"project-only": True, "deny-protected": True}
        write_yaml(path, config)
        self.assertTrue(read_config(self.project)["read-policy"]["project-only"])
        config["read-policy"]["unexpected"] = True
        write_yaml(path, config)
        with self.assertRaises(RuntimeError):
            read_config(self.project)
        path.write_text("bindings: [never-log-this\n", encoding="utf-8")
        with self.assertRaises(RuntimeError) as error:
            read_config(self.project)
        self.assertNotIn("never-log-this", str(error.exception))
        path.unlink()
        outside = self.project / "outside.yaml"
        outside.write_text("bindings: {}\nassignments: []\n", encoding="utf-8")
        path.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "nested symlink"):
            read_config(self.project)

    def test_metadata_has_no_prompt_and_installation_detects_tampering(self) -> None:
        self.configure()
        entry = self.install_fixture()
        self.assertNotIn("prompt", json.dumps(entry))
        self.assertEqual("verified", observer_status(self.project)["installation"])
        agent_file = self.project / ".claude/agents" / (entry["name"] + ".md")
        agent_file.write_text(agent_file.read_text() + "tamper", encoding="utf-8")
        self.assertEqual("stale", observer_status(self.project)["installation"])
        self.install_fixture()
        metadata_file = self.project / ".claude/embraion-native.json"
        metadata_file.write_text('{"schema-version": 1, "assignments": []}', encoding="utf-8")
        self.assertEqual("stale", observer_status(self.project)["installation"])

    def test_observer_records_only_exact_agent_and_safe_metadata(self) -> None:
        self.configure()
        entry = self.install_fixture()
        self.assertEqual("ignored", observe(self.hook("unrelated"), self.project)["status"])
        self.assertEqual("ignored", observe(self.hook(entry["name"], event="UserPromptSubmit"), self.project)["status"])
        result = observe(self.hook(entry["name"]), self.project)
        self.assertEqual("observed", result["status"])
        self.assertEqual("matched", result["effort-status"])
        saved = (self.project / ".embraion/state/claude-native-evidence.jsonl").read_text()
        self.assertNotIn("never-log-this", saved)
        self.assertNotIn("tool_input", saved)
        status = observer_status(self.project)
        self.assertEqual("observed", status["execution"])
        self.assertEqual("observed-match", status["effort"])
        self.assertEqual("unverified", status["model"])
        self.assertTrue(any("unscoped" in limitation for limitation in status["limitations"]))

    def test_missing_effort_is_unverified_and_mismatch_is_recorded(self) -> None:
        self.configure()
        entry = self.install_fixture()
        missing = self.hook(entry["name"], event="SubagentStop")
        missing.pop("effort")
        self.assertEqual("unverified", observe(missing, self.project)["effort-status"])
        self.assertEqual("unverified", observer_status(self.project)["effort"])
        self.assertEqual("mismatch", observe(self.hook(entry["name"], effort="low"), self.project)["effort-status"])
        self.assertEqual("mismatch", observer_status(self.project)["effort"])

    def test_changed_route_invalidates_old_metadata_and_evidence(self) -> None:
        self.configure()
        entry = self.install_fixture()
        observe(self.hook(entry["name"]), self.project)
        self.configure(effort="medium")
        self.assertEqual("stale", observer_status(self.project)["installation"])
        self.assertEqual("unverified", observe(self.hook(entry["name"]), self.project)["status"])

    def test_nested_symlink_and_untrusted_effort_do_not_create_claims(self) -> None:
        self.configure()
        entry = self.install_fixture()
        payload = self.hook(entry["name"], effort="never-log-this")
        self.assertEqual("unverified", observe(payload, self.project)["effort-status"])
        evidence = self.project / ".embraion/state/claude-native-evidence.jsonl"
        self.assertNotIn("never-log-this", evidence.read_text())
        evidence.unlink()
        external = self.project / "unrelated.txt"
        external.write_text("preserve", encoding="utf-8")
        evidence.symlink_to(external)
        self.assertEqual("unverified", observe(self.hook(entry["name"]), self.project)["status"])
        self.assertEqual("preserve", external.read_text())
        evidence.unlink()
        agent_file = self.project / ".claude/agents" / (entry["name"] + ".md")
        agent_file.unlink()
        agent_file.symlink_to(external)
        self.assertEqual("stale", observer_status(self.project)["installation"])

    def test_status_rejects_incomplete_or_forged_evidence_rows(self) -> None:
        self.configure()
        entry = self.install_fixture()
        observe(self.hook(entry["name"]), self.project)
        evidence = self.project / ".embraion/state/claude-native-evidence.jsonl"
        genuine = json.loads(evidence.read_text().strip())
        minimal = {key: genuine[key] for key in
                   ("schema-version", "agent-type", "definition-digest", "event", "effort-status")}
        variants = [minimal]
        for field in ("session-id", "agent-id", "timestamp-utc", "observed-effort"):
            forged = dict(genuine)
            forged.pop(field)
            variants.append(forged)
        for field, value in (("session-id", "secret / invalid"),
                             ("agent-id", ""),
                             ("timestamp-utc", "2026-10-03T00:00:00+01:00"),
                             ("event", ["PostToolUse"]),
                             ("expected-effort", "low"),
                             ("observed-effort", "never-log-this"),
                             ("effort-status", "mismatch")):
            forged = dict(genuine)
            forged[field] = value
            variants.append(forged)
        for forged in variants:
            with self.subTest(forged=forged):
                evidence.write_text(json.dumps(forged) + "\n", encoding="utf-8")
                status = observer_status(self.project)
                self.assertEqual("unverified", status["execution"])
                self.assertEqual("unverified", status["effort"])
        evidence.unlink()
        unknown = self.hook(entry["name"], effort="never-log-this")
        self.assertEqual("unverified", observe(unknown, self.project)["effort-status"])
        status = observer_status(self.project)
        self.assertEqual("observed", status["execution"])
        self.assertEqual("unverified", status["effort"])

    def test_journal_exact_cap_and_busy_lock_preserve_existing_rows(self) -> None:
        self.configure()
        entry = self.install_fixture()
        payload = self.hook(entry["name"])
        evidence = self.project / ".embraion/state/claude-native-evidence.jsonl"
        self.assertEqual("observed", observe(payload, self.project)["status"])
        row = evidence.read_bytes()
        evidence.unlink()
        with patch("embraion.claude_native._MAX_EVIDENCE_BYTES", len(row)):
            self.assertEqual("observed", observe(payload, self.project)["status"])
            exact = evidence.read_bytes()
            self.assertEqual(len(row), len(exact))
            self.assertEqual("evidence-limit", observe(payload, self.project)["reason"])
            self.assertEqual(exact, evidence.read_bytes())
            self.assertEqual("observed", observer_status(self.project)["execution"])
        lock = self.project / ".embraion/state/claude-native-evidence.lock"
        self.assertTrue(lock.is_file())
        fd = os.open(lock, os.O_RDWR)
        try:
            _lock_fd(fd)
            self.assertEqual("evidence-busy", observe(payload, self.project)["reason"])
        finally:
            _unlock_fd(fd)
            os.close(fd)
        self.assertEqual(exact, evidence.read_bytes())
        self.assertEqual("observed", observe(payload, self.project)["status"])

    def test_os_releases_lock_after_holder_process_exits(self) -> None:
        self.configure()
        entry = self.install_fixture()
        payload = self.hook(entry["name"])
        self.assertEqual("observed", observe(payload, self.project)["status"])
        lock = self.project / ".embraion/state/claude-native-evidence.lock"
        child = Process(target=_exit_while_holding_lock, args=(str(lock),))
        child.start()
        child.join(timeout=5)
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
        self.assertEqual(0, child.exitcode)
        self.assertTrue(lock.is_file())
        self.assertEqual("observed", observe(payload, self.project)["status"])

    def test_swapped_lock_and_journal_paths_never_write_outside_file(self) -> None:
        self.configure()
        entry = self.install_fixture()
        payload = self.hook(entry["name"])
        state = self.project / ".embraion/state"
        state.mkdir(parents=True, exist_ok=True)
        real_open = os.open
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        for filename, reason, original in (
            ("claude-native-evidence.lock", "evidence-lock-changed", b""),
            ("claude-native-evidence.jsonl", "evidence-journal-changed", b"outside-intact"),
        ):
            with self.subTest(filename=filename):
                target = state / filename
                outside = self.project / (filename + ".outside")
                outside.write_bytes(original)
                swapped = False

                def swap_after_validation(path, flags, *args, **kwargs):
                    nonlocal swapped
                    if Path(path) == target and not swapped:
                        target.symlink_to(outside)
                        flags &= ~nofollow  # Simulate Windows without O_NOFOLLOW.
                        swapped = True
                    return real_open(path, flags, *args, **kwargs)

                with patch("embraion.claude_native.os.open", side_effect=swap_after_validation):
                    result = observe(payload, self.project)
                self.assertTrue(swapped)
                self.assertEqual(reason, result["reason"])
                self.assertEqual(original, outside.read_bytes())
                if filename.endswith(".lock"):
                    fd = real_open(target, os.O_RDWR)
                    try:
                        self.assertFalse(_prepare_lock_file(fd, target, windows=True))
                        self.assertEqual(original, outside.read_bytes())
                    finally:
                        os.close(fd)
                target.unlink()

    def test_concurrent_observers_cannot_cross_journal_cap(self) -> None:
        self.configure()
        entry = self.install_fixture()
        payload = self.hook(entry["name"])
        evidence = self.project / ".embraion/state/claude-native-evidence.jsonl"
        observe(payload, self.project)
        row_size = len(evidence.read_bytes())
        evidence.unlink()
        cap = row_size * 3
        with patch("embraion.claude_native._MAX_EVIDENCE_BYTES", cap):
            with ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(lambda _: observe(payload, self.project), range(24)))
            content = evidence.read_bytes()
            self.assertLessEqual(len(content), cap)
            rows = content.splitlines()
            self.assertEqual(sum(result["status"] == "observed" for result in results), len(rows))
            self.assertTrue(all(json.loads(row)["effort-status"] == "matched" for row in rows))
            self.assertNotIn(b"never-log-this", content)


if __name__ == "__main__":
    unittest.main()
