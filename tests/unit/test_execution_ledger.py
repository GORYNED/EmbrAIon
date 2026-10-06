"""Persisted attempt ledger: bounded append, recovery, rotation, and health feedback."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from embraion import ledger
from embraion.execution import ExecutionEvidenceWarning, execute


def _attempt(deployment: str, status: str = "completed", failure: str | None = None,
             minutes_ago: int = 1) -> dict:
    at = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    return {"deployment": deployment, "requestedModel": deployment, "observedModel": None,
            "startedUtc": at, "finishedUtc": at, "status": status, "failure": failure, "usage": None,
            "cost": None, "terminationConfirmed": True, "mutationConfirmed": True,
            "fallbackFrom": None, "fallbackReason": None}


class FakeAdapter:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def preflight(self, request: dict, deployment: dict, binding: dict) -> None:
        return None

    def execute(self, request: dict, deployment: dict, binding: dict, credential: str | None) -> dict:
        self.calls.append(deployment["model"])
        return self.responses.pop(0)


def _request() -> dict:
    return {"schemaVersion": 1, "runId": "run-1", "workItemId": "work-1", "taskId": "task-1",
            "role": "analysis", "routeClass": "ordinary", "host": "test-host", "dataClass": "PRIVATE",
            "sourceIds": ["source-a"], "trustLevel": "project", "access": "read-only",
            "ownedPaths": [], "contextRef": "context-1", "timeoutSeconds": 30, "maxAttempts": 2,
            "candidates": [{"deployment": "first"}, {"deployment": "second"}],
            "payload": {"prompt": "private context bytes stay out of the ledger"}}


_COMPLETED = {"status": "completed", "failure": None, "terminationConfirmed": True,
              "mutationConfirmed": True, "observedModel": "observed", "usage": None,
              "outputText": "worker output stays out of the ledger"}


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        folder = self.project / ".embraion"
        folder.mkdir()
        definitions = {name: {"host": "test-host", "model": name, "enabled": True,
                              "billing": {"mode": "subscription"},
                              "capabilities": {"data-classes": ["PRIVATE"], "access-modes": ["read-only"],
                                               "roles": ["analysis"], "task-classes": ["ordinary"]}}
                       for name in ("first", "second")}
        (folder / "deployments.yaml").write_text(yaml.safe_dump({"providers": {}, "deployments": definitions}),
                                                 encoding="utf-8")
        bindings = {name: {"adapter": "fake", "selector": name, "sourceIds": ["source-a"],
                           "trustLevels": ["project"]} for name in definitions}
        (folder / "execution.yaml").write_text(yaml.safe_dump({"schemaVersion": 1, "bindings": bindings}),
                                               encoding="utf-8")
        self.path = folder / "state" / ledger.LEDGER_NAME

    def append(self, attempt: dict) -> None:
        ledger.append_attempt(self.project, attempt, run_id="run-1", work_item_id="work-1")

    def test_append_read_and_observation_shape(self) -> None:
        self.assertEqual({}, ledger.health_observations(self.project))
        self.assertFalse((self.project / ".embraion" / "state").exists())
        self.append(_attempt("first"))
        self.append(_attempt("first", "failed", "rate-limited"))
        observations = ledger.health_observations(self.project)
        self.assertEqual(["completed", "failed"], [item["status"] for item in observations["first"]])
        self.assertEqual({"at", "status", "failure"}, set(observations["first"][1]))

    def test_truncated_last_line_and_garbage_are_recovered(self) -> None:
        self.append(_attempt("first"))
        with self.path.open("ab") as stream:
            stream.write(b'{"schemaVersion": 1, "attempt": {"deploy')
        self.append(_attempt("second"))
        with self.path.open("ab") as stream:
            stream.write(b"not json\n[]\n" + json.dumps({"schemaVersion": 1, "attempt": {"deployment": "x"}}).encode() + b"\n")
        loaded = ledger.read_records(self.project)
        self.assertEqual(["first", "second"], [item["attempt"]["deployment"] for item in loaded["records"]])
        self.assertEqual(4, loaded["corruptLines"])
        report = ledger.health_report(self.project)
        self.assertEqual(4, report["corruptLines"])
        self.assertEqual(["first", "second"], [item["deployment"] for item in report["deployments"]])

    def test_rotation_bounds_size_and_keeps_previous_generation(self) -> None:
        with patch.object(ledger, "MAX_LEDGER_BYTES", 1200):
            for index in range(8):
                self.append(_attempt("first", minutes_ago=index))
            self.assertLessEqual(self.path.stat().st_size, 1200)
            rotated = self.path.with_name(ledger.ROTATED_NAME)
            self.assertTrue(rotated.is_file())
            self.assertLessEqual(rotated.stat().st_size, 1200)
            records = ledger.read_records(self.project)["records"]
        self.assertGreater(len(records), 1)
        self.assertLess(len(records), 8)

    @unittest.skipIf(os.name == "nt", "symbolic links need extra privileges on Windows")
    def test_symlinked_ledger_is_refused(self) -> None:
        (self.project / ".embraion" / "state").mkdir()
        outside = self.project / "outside.jsonl"
        outside.write_text("", encoding="utf-8")
        self.path.symlink_to(outside)
        with self.assertRaises((OSError, RuntimeError)):
            self.append(_attempt("first"))
        self.assertEqual("", outside.read_text(encoding="utf-8"))
        self.assertEqual([], ledger.read_records(self.project)["records"])

    def test_execute_persists_redacted_attempts_only_when_enabled(self) -> None:
        execute(_request(), project=self.project, adapters={"fake": FakeAdapter([dict(_COMPLETED)])})
        self.assertFalse(self.path.exists())
        result = execute(_request(), project=self.project, adapters={"fake": FakeAdapter([dict(_COMPLETED)])},
                         persist_attempts=True)
        self.assertEqual("completed", result["status"])
        content = self.path.read_text(encoding="utf-8")
        record = json.loads(content)
        self.assertEqual(result["attempts"][0], record["attempt"])
        self.assertEqual(("run-1", "work-1"), (record["runId"], record["workItemId"]))
        self.assertNotIn("private context bytes", content)
        self.assertNotIn("worker output", content)

    def test_ledger_health_orders_candidates_unless_request_supplies_observations(self) -> None:
        for _ in range(3):
            self.append(_attempt("first", "failed", "rate-limited"))
        adapter = FakeAdapter([dict(_COMPLETED)])
        execute(_request(), project=self.project, adapters={"fake": adapter}, persist_attempts=True)
        self.assertEqual(["second"], adapter.calls)
        adapter = FakeAdapter([dict(_COMPLETED)])
        execute({**_request(), "healthObservations": {}}, project=self.project, adapters={"fake": adapter},
                persist_attempts=True)
        self.assertEqual(["first"], adapter.calls)

    def test_ledger_write_failure_warns_and_keeps_result(self) -> None:
        with patch("embraion.ledger.append_attempt", side_effect=OSError("disk")):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = execute(_request(), project=self.project,
                                 adapters={"fake": FakeAdapter([dict(_COMPLETED)])}, persist_attempts=True)
        self.assertEqual("completed", result["status"])
        self.assertTrue(any(issubclass(item.category, ExecutionEvidenceWarning) for item in caught))


if __name__ == "__main__":
    unittest.main()
