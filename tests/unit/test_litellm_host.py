"""Exercise the real one-request host with an in-memory LiteLLM response stub."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import patch

from embraion.adapters import litellm_host


class _Response:
    def __init__(self, reported_provider: str | None):
        self._hidden_params = {"litellm_call_id": "call-1", "custom_llm_provider": reported_provider}

    def model_dump(self):
        return {"model": "gpt-6-luna-2026-09-01", "output_text": "bounded answer",
                "usage": {"input_tokens": 7, "output_tokens": 3}}


class LiteLLMHostTests(unittest.TestCase):
    def _call(self, reported_provider: str | None):
        captured = []
        stub = types.ModuleType("litellm")
        stub.num_retries = 7

        def respond(**kwargs):
            captured.append(kwargs)
            return _Response(reported_provider)

        stub.responses = respond
        token = "test-session-token"
        key = "aa" * 32
        selector = "openai/gpt-6-luna"
        context = "reviewed fixture envelope"
        correlation = "test-correlation"
        work_item = "test-work"
        nonce = "ab" * 16
        signed = ("EmbrAIonContext/v1\n" + correlation + "\n" + work_item + "\n" +
                  selector + "\n" + nonce + "\n" + context).encode()
        mac = hmac.new(bytes.fromhex(key), signed, hashlib.sha256).hexdigest()
        body = json.dumps({"correlationId": correlation, "workItemId": work_item,
                           "input": [{"role": "user", "content": [{"type": "input_text", "text": context}]}],
                           "maxOutputTokens": 64, "timeoutSeconds": 5, "nonce": nonce,
                           "provenanceMac": mac}).encode()
        environment = {"EMBRAION_SESSION_TOKEN": token, "EMBRAION_PROVENANCE_KEY": key,
                       "EMBRAION_UPSTREAM_MODEL": selector, "EMBRAION_PROVIDER_KEY": "scoped-key"}
        with (patch.dict(os.environ, environment), patch.dict(sys.modules, {"litellm": stub}),
              patch.object(litellm_host.importlib.metadata, "version", return_value="1.77.7")):
            server = HTTPServer(("127.0.0.1", 0), litellm_host._Handler)
            thread = threading.Thread(target=server.handle_request, daemon=True)
            thread.start()
            request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/responses", body,
                                             {"Authorization": "Bearer " + token,
                                              "Content-Type": "application/json"})
            try:
                response = urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.status
                payload = json.loads(response.read())
            thread.join(timeout=5)
            server.server_close()
            self.assertFalse(thread.is_alive())
        return status, payload, captured, stub

    def test_one_provider_call_disables_retry_and_reports_observed_identity(self):
        status, payload, calls, stub = self._call("openai")
        self.assertEqual(200, status)
        self.assertEqual(1, len(calls))
        self.assertEqual("openai/gpt-6-luna", calls[0]["model"])
        self.assertEqual("scoped-key", calls[0]["api_key"])
        self.assertEqual(0, calls[0]["max_retries"])
        self.assertEqual(0, stub.num_retries)
        self.assertEqual("openai", payload["observedProvider"])
        self.assertEqual("call-1", payload["callId"])

    def test_requested_provider_is_not_substituted_for_missing_observation(self):
        status, payload, calls, _ = self._call(None)
        self.assertEqual(400, status)
        self.assertEqual(1, len(calls))
        self.assertEqual("invalid-request", payload["failure"])


if __name__ == "__main__":
    unittest.main()
