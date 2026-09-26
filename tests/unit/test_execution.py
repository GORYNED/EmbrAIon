from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from embraion.execution import execute
from embraion.pricing import refresh_pricing
from embraion.adapters.provider_pricing import fetch_and_parse


def request() -> dict:
    return {
        "schemaVersion": 1, "runId": "run-1", "workItemId": "work-1", "taskId": "task-1",
        "role": "analysis", "routeClass": "ordinary", "host": "test-host", "dataClass": "PRIVATE",
        "sourceIds": ["source-a"], "trustLevel": "project", "access": "read-only",
        "ownedPaths": [], "contextRef": "context-1", "timeoutSeconds": 30, "maxAttempts": 2,
        "candidates": [{"deployment": "first"}, {"deployment": "second"}],
        "payload": {"prompt": "secret context bytes never reach evidence"},
    }


class FakeAdapter:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def preflight(self, request: dict, deployment: dict, binding: dict) -> None:
        self.calls.append("preflight:" + deployment["model"])

    def execute(self, request: dict, deployment: dict, binding: dict, credential: str | None) -> dict:
        self.calls.append("execute:" + deployment["model"])
        return self.responses.pop(0)


class ExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        folder = self.project / ".embraion"
        folder.mkdir()
        definitions = {name: {"host": "test-host", "model": name, "enabled": True,
                              "billing": {"mode": "subscription"},
                              "capabilities": {"data-classes": ["PRIVATE"], "access-modes": ["read-only"],
                                               "roles": ["analysis"], "task-classes": ["ordinary"]}}
                       for name in ("first", "second")}
        (folder / "deployments.yaml").write_text(yaml.safe_dump({"providers": {}, "deployments": definitions}), encoding="utf-8")
        bindings = {name: {"adapter": "fake", "selector": name, "sourceIds": ["source-a"],
                           "trustLevels": ["project"]} for name in definitions}
        (folder / "execution.yaml").write_text(yaml.safe_dump({"schemaVersion": 1, "bindings": bindings}), encoding="utf-8")

    def test_safe_operational_failure_falls_back_once(self) -> None:
        adapter = FakeAdapter([
            {"status": "failed", "failure": "rate-limited", "terminationConfirmed": True,
             "mutationConfirmed": True, "observedModel": None, "usage": None},
            {"status": "completed", "failure": None, "terminationConfirmed": True,
             "mutationConfirmed": True, "observedModel": "second", "usage": None},
        ])
        evidence: list[dict] = []
        result = execute(request(), project=self.project, adapters={"fake": adapter}, evidence_sink=evidence.append)
        self.assertEqual("completed", result["status"])
        self.assertEqual(2, len(result["attempts"]))
        self.assertEqual("first", result["attempts"][1]["fallbackFrom"])
        self.assertNotIn("secret context bytes", str(evidence))

    def test_unknown_or_uncertain_failure_is_terminal(self) -> None:
        for failure, termination in (("unknown", True), ("rate-limited", False)):
            adapter = FakeAdapter([{"status": "failed", "failure": failure,
                                    "terminationConfirmed": termination, "mutationConfirmed": True}])
            result = execute(request(), project=self.project, adapters={"fake": adapter})
            self.assertEqual("failed", result["status"])
            self.assertEqual(1, len(result["attempts"]))

    def test_pricing_cannot_widen_eligibility(self) -> None:
        pricing = {"schemaVersion": 1, "sources": {"official": {
            "url": "https://developers.openai.com/api/docs/pricing", "adapter": "openai",
            "currency": "USD", "freshnessDays": 30,
            "skus": {"first": {"sku": "first-sku", "patterns": {
                "input": r"first input=(?P<rate>[0-9.]+)"}}}}}}
        (self.project / ".embraion" / "pricing.yaml").write_text(yaml.safe_dump(pricing), encoding="utf-8")
        for rate in ("1", "2"):
            refresh_pricing(self.project, fetcher=lambda source_id, source: fetch_and_parse(
                source_id, source, f"first input={rate}".encode("utf-8")))
            candidate = request()
            candidate["sourceIds"] = ["source-b"]
            adapter = FakeAdapter([])
            with self.assertRaises(RuntimeError):
                execute(candidate, project=self.project, adapters={"fake": adapter})
            self.assertEqual([], adapter.calls)

    def test_unsupported_option_cannot_expand_transport_behavior(self) -> None:
        candidate = request()
        candidate["candidates"][0]["options"] = {"externalUrl": "https://example.test/"}
        adapter = FakeAdapter([])
        with self.assertRaises(RuntimeError):
            execute(candidate, project=self.project, adapters={"fake": adapter})
        self.assertEqual([], adapter.calls)

    def test_binding_task_class_cannot_override_deployment_capability(self) -> None:
        folder = self.project / ".embraion"
        config = yaml.safe_load((folder / "execution.yaml").read_text(encoding="utf-8"))
        config["bindings"]["first"]["taskClasses"] = ["review"]
        (folder / "execution.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        candidate = request()
        candidate["routeClass"] = "review"
        candidate["candidates"] = [{"deployment": "first"}]
        candidate["maxAttempts"] = 1
        adapter = FakeAdapter([])
        with self.assertRaisesRegex(RuntimeError, "ceiling"):
            execute(candidate, project=self.project, adapters={"fake": adapter})
        self.assertEqual([], adapter.calls)
        config["bindings"]["first"]["taskClassAliases"] = {"review": "ordinary"}
        (folder / "execution.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        allowed = FakeAdapter([{"status": "completed", "observedModel": "first",
                                "terminationConfirmed": True, "mutationConfirmed": True}])
        result = execute(candidate, project=self.project, adapters={"fake": allowed})
        self.assertEqual("completed", result["status"])

    def test_degraded_health_moves_behind_healthy_without_changing_override(self) -> None:
        now = datetime.now(timezone.utc)
        degraded = [{"at": (now - timedelta(minutes=minute)).isoformat(),
                     "status": "failed", "failure": "timeout"} for minute in (2, 1)]
        observations = {"first": degraded, "second": []}
        completed = {"status": "completed", "observedModel": "second",
                     "terminationConfirmed": True, "mutationConfirmed": True}
        adapter = FakeAdapter([completed])
        result = execute(request(), project=self.project, adapters={"fake": adapter},
                         health_observations=observations)
        self.assertEqual("second", result["attempts"][0]["deployment"])
        self.assertEqual(["preflight:second", "execute:second"], adapter.calls)
        override = request()
        override["preserveCandidateOrder"] = True
        adapter = FakeAdapter([{**completed, "observedModel": "first"}])
        result = execute(override, project=self.project, adapters={"fake": adapter},
                         health_observations=observations)
        self.assertEqual("first", result["attempts"][0]["deployment"])

    def test_unavailable_candidate_does_not_consume_attempt_budget(self) -> None:
        now = datetime.now(timezone.utc)
        failures = [{"at": (now - timedelta(minutes=minute)).isoformat(),
                     "status": "failed", "failure": "timeout"} for minute in (3, 2, 1)]
        candidate = request()
        candidate["maxAttempts"] = 1
        adapter = FakeAdapter([{"status": "completed", "observedModel": "second",
                                "terminationConfirmed": True, "mutationConfirmed": True}])
        result = execute(candidate, project=self.project, adapters={"fake": adapter},
                         health_observations={"first": failures, "second": []})
        self.assertEqual("second", result["attempts"][0]["deployment"])
        self.assertEqual(1, len(result["attempts"]))

    def test_duplicate_fallback_is_rejected(self) -> None:
        candidate = request()
        candidate["candidates"][1]["deployment"] = "first"
        adapter = FakeAdapter([{"status": "failed", "failure": "rate-limited",
                                "terminationConfirmed": True, "mutationConfirmed": True}])
        with self.assertRaises(RuntimeError):
            execute(candidate, project=self.project, adapters={"fake": adapter})

    def test_unbound_native_candidate_requires_handoff(self) -> None:
        candidate = request()
        candidate["candidates"] = [{"deployment": "first"}]
        candidate["maxAttempts"] = 1
        (self.project / ".embraion" / "execution.yaml").unlink()
        result = execute(candidate, project=self.project)
        self.assertEqual("handoff-required", result["status"])


if __name__ == "__main__":
    unittest.main()
