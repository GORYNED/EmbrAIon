"""Adapter scope and native handoff contracts with generic project definitions."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from embraion.adapters.litellm_execution import LiteLLMLoopbackAdapter
from embraion.execution import execute


class MixedExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        (self.project / ".embraion").mkdir()
        self.definitions = {name: {
            "host": "api-host" if name != "native" else "native-host", "model": name,
            "capabilities": {"data-classes": ["PRIVATE"], "access-modes": ["read-only"],
                             "roles": ["worker"], "task-classes": ["ordinary"]},
        } for name in ("first", "second", "native", "unused")}
        self.bindings = {name: {
            "adapter": "litellm-loopback", "selector": "example/" + name,
            "expectedProvider": "example", "expectedResponseModels": [name],
            "contextBoundary": "Context/v1", "credentialRef": "env:EXAMPLE_KEY",
            "sourceIds": ["project-source"], "trustLevels": ["verified"],
        } for name in ("first", "second", "unused")}
        self.request = {
            "schemaVersion": 1, "runId": "run", "workItemId": "work", "taskId": "task",
            "role": "worker", "routeClass": "ordinary", "host": "api-host", "dataClass": "PRIVATE",
            "sourceIds": ["project-source"], "trustLevel": "verified", "access": "read-only",
            "ownedPaths": [], "contextRef": "context", "timeoutSeconds": 5, "maxAttempts": 3,
            "preserveCandidateOrder": True,
            "candidates": [{"deployment": "first"}, {"deployment": "second"}],
            "payload": {"inputsByDeployment": {name: self.input(name) for name in ("first", "second")}},
        }
        self.adapter = LiteLLMLoopbackAdapter(project=self.project)
        self.preflight = Mock(wraps=self.adapter.preflight)
        self.adapter.preflight = self.preflight
        self.transport = Mock(return_value=self.completed("first"))
        self.adapter.execute = self.transport
        self.resolver = Mock()
        self.resolver.resolve.return_value = "test-only"
        self.write_config()

    def input(self, name: str) -> list[dict]:
        envelope = {"schemaVersion": 1, "boundary": "Context/v1", "context": [],
                    "workItem": {"workItemId": "work", "deploymentId": name, "model": name,
                                 "role": "worker", "sourceIds": ["project-source"],
                                 "access": "read-only", "dataClass": "PRIVATE"}}
        return [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(envelope)}]}]

    @staticmethod
    def completed(name: str) -> dict:
        return {"status": "completed", "observedModel": name, "observedProvider": "example",
                "terminationConfirmed": True, "mutationConfirmed": True}

    @staticmethod
    def failed() -> dict:
        return {"status": "failed", "failure": "rate-limited",
                "terminationConfirmed": True, "mutationConfirmed": True}

    def write_config(self) -> None:
        folder = self.project / ".embraion"
        (folder / "deployments.yaml").write_text(yaml.safe_dump({
            "providers": {}, "deployments": self.definitions}), encoding="utf-8")
        (folder / "execution.yaml").write_text(yaml.safe_dump({
            "schemaVersion": 1, "bindings": self.bindings}), encoding="utf-8")

    def run_request(self) -> dict:
        return execute(self.request, project=self.project,
                       adapters={"litellm-loopback": self.adapter}, resolver=self.resolver)

    def mixed_route(self) -> None:
        self.request["candidates"] = [{"deployment": "first"}, {"deployment": "native"}]
        self.request["payload"]["inputsByDeployment"].pop("second", None)

    def assert_rejected_before_transport(self) -> None:
        result = self.run_request()
        self.assertEqual("failed", result["status"])
        self.assertEqual(1, len(result["attempts"]))
        self.assertEqual("unknown", result["attempts"][0]["failure"])
        self.transport.assert_not_called()
        self.resolver.resolve.assert_not_called()

    def test_external_only_complete_inputs_pass(self) -> None:
        self.assertEqual("completed", self.run_request()["status"])
        self.assertEqual(["first", "second"], self.preflight.call_args.args[0]["_adapterCandidateDeployments"])

    def test_mixed_route_needs_no_native_input(self) -> None:
        self.mixed_route()
        self.assertEqual("completed", self.run_request()["status"])
        self.assertEqual(["first"], self.preflight.call_args.args[0]["_adapterCandidateDeployments"])

    def test_safe_failure_hands_off_without_native_adapter_calls(self) -> None:
        for bound in (False, True):
            with self.subTest(bound=bound):
                self.mixed_route()
                if bound:
                    self.bindings["native"] = {**self.bindings["first"], "selector": "example/native"}
                self.write_config()
                self.transport.return_value = self.failed()
                self.preflight.reset_mock()
                self.transport.reset_mock()
                self.resolver.reset_mock()
                result = self.run_request()
                self.assertEqual("handoff-required", result["status"])
                self.assertEqual({"deployment": "native", "host": "native-host", "reason": "host-boundary"},
                                 result["handoff"])
                self.assertEqual(["first"], [item["deployment"] for item in result["attempts"]])
                self.preflight.assert_called_once()
                self.transport.assert_called_once()
                self.resolver.resolve.assert_called_once_with("env:EXAMPLE_KEY", "first", "litellm-loopback")

    def test_native_first_and_same_host_unbound_never_invoke_adapter(self) -> None:
        for host in ("native-host", "api-host"):
            with self.subTest(host=host):
                self.definitions["native"]["host"] = host
                self.write_config()
                self.request["candidates"] = [{"deployment": "native"}]
                self.request.pop("payload", None)
                self.assertEqual("handoff-required", self.run_request()["status"])
                self.preflight.assert_not_called()
                self.transport.assert_not_called()
                self.resolver.resolve.assert_not_called()

    def test_missing_selected_and_fallback_inputs_fail_closed(self) -> None:
        original = copy.deepcopy(self.request)
        for name in ("first", "second"):
            with self.subTest(missing=name):
                self.request = copy.deepcopy(original)
                self.request["payload"]["inputsByDeployment"].pop(name)
                self.assert_rejected_before_transport()

    def test_unknown_and_declared_non_candidate_input_fail_closed(self) -> None:
        for name in ("unknown", "unused"):
            with self.subTest(extra=name):
                self.request["payload"]["inputsByDeployment"][name] = self.input(name)
                self.assert_rejected_before_transport()
                self.request["payload"]["inputsByDeployment"].pop(name)

    def test_required_input_scope_ignores_attempt_budget_and_health(self) -> None:
        from datetime import datetime, timezone
        self.request["payload"]["inputsByDeployment"].pop("second")
        self.request["maxAttempts"] = 1
        self.assert_rejected_before_transport()
        self.request["healthObservations"] = {"second": [
            {"at": datetime.now(timezone.utc).isoformat(), "status": "failed", "failure": "timeout"}
            for _ in range(3)]}
        self.assert_rejected_before_transport()

    def test_invalid_internal_adapter_scope_fails_closed(self) -> None:
        request = {**self.request, "selected": {"deployment": "first"}}
        for scope in (None, [], ["unknown"], ["second"], ["first", "first"], [1]):
            with self.subTest(scope=scope):
                request["_adapterCandidateDeployments"] = scope
                with self.assertRaisesRegex(RuntimeError, "Core-derived adapter candidate scope"):
                    LiteLLMLoopbackAdapter().preflight(request, self.definitions["first"], self.bindings["first"])

    def test_invalid_bounded_fallback_input_fails_before_first_call(self) -> None:
        self.request["payload"]["inputsByDeployment"]["second"] = []
        self.assert_rejected_before_transport()

    def test_selected_provenance_and_fallback_provenance_fail_closed(self) -> None:
        original = copy.deepcopy(self.request)
        for name in ("first", "second"):
            with self.subTest(invalid=name):
                self.request = copy.deepcopy(original)
                self.request["payload"]["inputsByDeployment"][name] = self.input("unused")
                self.transport.reset_mock()
                self.resolver.reset_mock()
                self.transport.return_value = self.failed()
                result = self.run_request()
                self.assertEqual("failed", result["status"])
                self.assertEqual(0 if name == "first" else 1, self.transport.call_count)
                self.assertEqual(0 if name == "first" else 1, self.resolver.resolve.call_count)
                self.assertEqual("unknown", result["attempts"][-1]["failure"])

    def test_external_fallback_still_executes_in_order(self) -> None:
        self.transport.side_effect = [self.failed(), self.completed("second")]
        result = self.run_request()
        self.assertEqual("completed", result["status"])
        self.assertEqual(["first", "second"], [item["deployment"] for item in result["attempts"]])
        self.assertEqual("first", result["attempts"][1]["fallbackFrom"])

    def test_cross_host_capability_ceilings_are_rechecked_bound_and_unbound(self) -> None:
        self.mixed_route()
        self.transport.return_value = self.failed()
        original = copy.deepcopy(self.definitions["native"])
        for bound in (False, True):
            if bound:
                self.bindings["native"] = copy.deepcopy(self.bindings["first"])
            for capability in ("data-classes", "access-modes", "roles", "task-classes"):
                with self.subTest(bound=bound, capability=capability):
                    self.definitions["native"] = copy.deepcopy(original)
                    self.definitions["native"]["capabilities"][capability] = ["disallowed"]
                    self.write_config()
                    with self.assertRaises(RuntimeError):
                        self.run_request()

    def test_cross_host_binding_source_and_trust_ceilings_are_rechecked(self) -> None:
        self.mixed_route()
        self.transport.return_value = self.failed()
        for ceiling in ("sourceIds", "trustLevels"):
            with self.subTest(ceiling=ceiling):
                self.bindings["native"] = copy.deepcopy(self.bindings["first"])
                self.bindings["native"][ceiling] = ["disallowed"]
                self.write_config()
                with self.assertRaisesRegex(RuntimeError, "original request ceilings"):
                    self.run_request()

    def test_optional_native_input_remains_compatible(self) -> None:
        self.mixed_route()
        self.request["payload"]["inputsByDeployment"]["native"] = self.input("native")
        self.assertEqual("completed", self.run_request()["status"])

    def test_different_adapter_candidate_needs_no_litellm_input(self) -> None:
        self.bindings["second"]["adapter"] = "other-adapter"
        self.write_config()
        self.request["payload"]["inputsByDeployment"].pop("second")
        self.assertEqual("completed", self.run_request()["status"])

    def test_consumer_cannot_supply_internal_adapter_scope(self) -> None:
        self.request["_adapterCandidateDeployments"] = ["first"]
        with self.assertRaises(RuntimeError):
            self.run_request()
        self.preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
