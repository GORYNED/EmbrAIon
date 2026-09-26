"""One-shot LiteLLM adapter contracts without provider credentials or network calls."""

from __future__ import annotations

import json
import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from embraion.adapters.litellm_execution import LiteLLMLoopbackAdapter
from embraion.execution import execute
from embraion.adapters.provider_pricing import fetch_and_parse
from embraion.pricing import refresh_pricing


_FIXTURE = r'''
import hashlib, hmac, json, os, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        context = body["input"][0]["content"][0]["text"]
        signed = ("EmbrAIonContext/v1\n" + body["correlationId"] + "\n" + body["workItemId"] + "\n" +
                  os.environ["EMBRAION_UPSTREAM_MODEL"] + "\n" + body["nonce"] + "\n" + context).encode()
        expected = hmac.new(bytes.fromhex(os.environ["EMBRAION_PROVENANCE_KEY"]), signed, hashlib.sha256).hexdigest()
        assert hmac.compare_digest(expected, body["provenanceMac"])
        assert self.headers["Authorization"] == "Bearer " + os.environ["EMBRAION_SESSION_TOKEN"]
        assert "SENTINEL_OTHER_PROVIDER_KEY" not in os.environ
        value = {"status": "completed", "correlationId": body["correlationId"], "callId": "call-1",
                 "adapterVersion": "1.77.7",
                 "observedProvider": "openai", "observedModel": os.environ.get("FIXTURE_MODEL", "gpt-6-luna-2026-09-01"),
                 "outputText": "worker answer", "usage": {"input_tokens": 100, "output_tokens": 20,
                     "input_tokens_details": {"cached_tokens": 10}}, "adapterCost": None}
        encoded = json.dumps(value).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(encoded))); self.end_headers()
        self.wfile.write(encoded)
server = HTTPServer(("127.0.0.1", 0), Handler)
print(server.server_port, flush=True)
server.handle_request()
server.server_close()
'''


class LiteLLMExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        self.fixture = Path(directory.name) / "host.py"
        self.fixture.write_text(_FIXTURE, encoding="utf-8")
        self.environment = patch.dict(os.environ, {"EMBRAION_TEST_MODE": "1",
                                                 "EMBRAION_LITELLM_TEST_SERVER_SCRIPT": str(self.fixture),
                                                 "SENTINEL_OTHER_PROVIDER_KEY": "withheld"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.adapter = LiteLLMLoopbackAdapter()
        self.deployment = {"model": "gpt-6-luna"}
        self.binding = {"selector": "openai/gpt-6-luna", "expectedProvider": "openai",
                        "contextBoundary": "ContextBuilder/v1",
                        "expectedResponseModelPattern": r"^gpt-6-luna-[0-9]{4}-[0-9]{2}-[0-9]{2}$"}
        envelope = {"schemaVersion": 1, "boundary": "ContextBuilder/v1",
                    "workItem": {"workItemId": "work-1", "deploymentId": "first", "model": "gpt-6-luna",
                                 "role": "worker", "sourceIds": ["source-a"], "access": "read-only", "dataClass": "PRIVATE"},
                    "task": {"responsibility": "test"}, "context": []}
        self.request = {"workItemId": "work-1", "role": "worker", "sourceIds": ["source-a"],
                        "access": "read-only", "dataClass": "PRIVATE", "timeoutSeconds": 5,
                        "candidates": [{"deployment": "first"}], "selected": {"deployment": "first"},
                        "payload": {"inputsByDeployment": {"first": [{"role": "user", "content": [
                            {"type": "input_text", "text": json.dumps(envelope)}]}]}}}

    def test_one_shot_child_scopes_credentials_and_returns_evidence(self) -> None:
        self.adapter.preflight(self.request, self.deployment, self.binding)
        raw = self.adapter.execute(self.request, self.deployment, self.binding, None)
        self.assertEqual("completed", raw["status"])
        self.assertEqual("worker answer", raw["outputText"])
        self.assertEqual("call-1", raw["callId"])
        self.assertEqual({"inputTokens": 100, "outputTokens": 20, "cachedInputTokens": 10}, raw["usage"])
        self.assertIsNone(raw["usageSemantics"])

    def _write_usage_evidence(self, **overrides: object) -> None:
        folder = self.project / ".embraion" / "usage-evidence"
        folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        evidence = {"schemaVersion": 1, "transport": "litellm-responses", "adapterVersion": "1.77.7",
                    "provider": "openai", "selector": "openai/gpt-6-luna",
                    "sourceUrl": "https://developers.openai.com/api/docs/pricing",
                    "verifiedUtc": (now - timedelta(days=1)).isoformat(),
                    "validThroughUtc": (now + timedelta(days=30)).isoformat(),
                    "usageSemantics": {"input": "inclusive", "output": "inclusive"},
                    "sampleUsage": {"input_tokens": 100, "output_tokens": 20,
                                    "input_tokens_details": {"cached_tokens": 10}}}
        evidence.update(overrides)
        path = folder / "openai-luna.json"
        content = json.dumps(evidence, sort_keys=True).encode("utf-8")
        path.write_bytes(content)
        self.binding["usageSemanticsEvidence"] = {"path": ".embraion/usage-evidence/openai-luna.json",
                                                  "sha256": hashlib.sha256(content).hexdigest()}
        self.adapter = LiteLLMLoopbackAdapter(project=self.project)

    def test_reviewed_version_tied_usage_fixture_enables_only_its_semantics(self) -> None:
        self._write_usage_evidence()
        raw = self.adapter.execute(self.request, self.deployment, self.binding, None)
        self.assertEqual("completed", raw["status"])
        self.assertEqual({"input": "inclusive", "output": "inclusive"}, raw["usageSemantics"])

    def test_expired_or_mismatched_usage_evidence_remains_unknown(self) -> None:
        self._write_usage_evidence(validThroughUtc="2020-01-01T00:00:00Z")
        self.assertIsNone(self.adapter.execute(self.request, self.deployment, self.binding, None)["usageSemantics"])
        self._write_usage_evidence(adapterVersion="1.77.6")
        self.assertIsNone(self.adapter.execute(self.request, self.deployment, self.binding, None)["usageSemantics"])
        self._write_usage_evidence(provider="anthropic")
        self.assertIsNone(self.adapter.execute(self.request, self.deployment, self.binding, None)["usageSemantics"])
        self._write_usage_evidence(sourceUrl="https://example.test/usage")
        self.assertIsNone(self.adapter.execute(self.request, self.deployment, self.binding, None)["usageSemantics"])

    def test_usage_evidence_path_escape_and_digest_mismatch_remain_unknown(self) -> None:
        self._write_usage_evidence()
        self.binding["usageSemanticsEvidence"]["path"] = "../outside.json"
        self.assertIsNone(self.adapter.execute(self.request, self.deployment, self.binding, None)["usageSemantics"])
        self._write_usage_evidence()
        self.binding["usageSemanticsEvidence"]["sha256"] = "0" * 64
        self.assertIsNone(self.adapter.execute(self.request, self.deployment, self.binding, None)["usageSemantics"])

    def test_model_mismatch_fails_closed(self) -> None:
        self.binding["expectedResponseModels"] = ["different-model"]
        self.binding.pop("expectedResponseModelPattern")
        self.adapter.preflight(self.request, self.deployment, self.binding)
        raw = self.adapter.execute(self.request, self.deployment, self.binding, None)
        self.assertEqual("failed", raw["status"])
        self.assertFalse(raw["mutationConfirmed"])

    def test_unapproved_envelope_fails_before_process_start(self) -> None:
        self.request["payload"]["inputsByDeployment"]["first"][0]["content"][0]["text"] = "unreviewed text"
        with self.assertRaisesRegex(RuntimeError, "context provenance"):
            self.adapter.preflight(self.request, self.deployment, self.binding)

    def test_test_host_runs_through_generic_execution_without_real_credential(self) -> None:
        folder = self.project / ".embraion"
        folder.mkdir()
        definitions = {"first": {"host": "test-host", "model": "gpt-6-luna", "enabled": True,
                                 "capabilities": {"data-classes": ["PRIVATE"], "access-modes": ["read-only"],
                                                  "roles": ["worker"], "task-classes": ["ordinary"]}}}
        (folder / "deployments.yaml").write_text(yaml.safe_dump({"providers": {}, "deployments": definitions}), encoding="utf-8")
        binding = {**self.binding, "adapter": "litellm-loopback", "credentialRef": "env:UNSET_PROVIDER_TEST_KEY",
                   "sourceIds": ["source-a"], "trustLevels": ["verified"]}
        (folder / "execution.yaml").write_text(yaml.safe_dump({"schemaVersion": 1, "bindings": {"first": binding}}), encoding="utf-8")
        request = {**self.request, "schemaVersion": 1, "runId": "run-1", "taskId": "task-1",
                   "routeClass": "ordinary", "host": "test-host", "trustLevel": "verified",
                   "ownedPaths": [], "contextRef": "context-1", "maxAttempts": 1}
        request.pop("selected")
        evidence = []
        result = execute(request, project=self.project, adapters={"litellm-loopback": self.adapter},
                         evidence_sink=evidence.append)
        self.assertEqual("completed", result["status"])
        self.assertEqual("worker answer", result["outputText"])
        self.assertEqual("call-1", result["attempts"][0]["callId"])
        self.assertEqual("pending", result["attempts"][0]["validationState"])
        self.assertNotIn("worker answer", str(evidence))

    def test_absent_overlap_evidence_keeps_snapshot_cost_unknown(self) -> None:
        folder = self.project / ".embraion"
        folder.mkdir()
        pricing = {"schemaVersion": 1, "sources": {"openai": {
            "url": "https://developers.openai.com/api/docs/pricing", "adapter": "openai",
            "currency": "USD", "freshnessDays": 30,
            "skus": {"first": {"sku": "gpt-6-luna", "patterns": {
                "input": r"input=(?P<rate>[0-9.]+)",
                "cachedInput": r"cached=(?P<rate>[0-9.]+)",
                "output": r"output=(?P<rate>[0-9.]+)"}}}}}}
        (folder / "pricing.yaml").write_text(yaml.safe_dump(pricing), encoding="utf-8")
        refresh_pricing(self.project, fetcher=lambda source_id, source: fetch_and_parse(
            source_id, source, b"input=1; cached=0.5; output=2"))
        from embraion.pricing import calculate_cost
        raw = self.adapter.execute(self.request, self.deployment, self.binding, None)
        cost = calculate_cost("first", raw["usage"], project=self.project,
                              usage_semantics=raw["usageSemantics"])
        self.assertEqual("unknown-provider", cost["state"])


if __name__ == "__main__":
    unittest.main()
