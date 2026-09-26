"""One-request, loopback-only LiteLLM child. No project policy is loaded here."""

from __future__ import annotations

import json
import hashlib
import hmac
import importlib.metadata
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import TCPServer


_LIMIT = 1_048_576


def _provider_failure(error: Exception) -> str:
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "http_status", None)
    mapped = {400: "invalid-request", 401: "authentication", 403: "authorization",
              408: "timeout", 413: "context-limit", 429: "rate-limited",
              500: "provider-error", 502: "provider-unavailable", 503: "provider-unavailable",
              504: "timeout"}
    if type(status) is int and status in mapped:
        return mapped[status]
    name = type(error).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "ratelimit" in name:
        return "rate-limited"
    return "provider-error"


def _response_payload(response: object) -> dict:
    value = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    if not isinstance(value, dict):
        raise ValueError("provider response")
    if not value.get("output_text"):
        parts = []
        for item in value.get("output", []):
            if isinstance(item, dict) and item.get("type") == "message":
                for content in item.get("content", []):
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        parts.append(content["text"])
        value["output_text"] = "".join(parts)
    return value


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass

    def do_POST(self) -> None:
        if self.path != "/v1/responses" or self.headers.get("Authorization") != "Bearer " + os.environ["EMBRAION_SESSION_TOKEN"]:
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= _LIMIT:
                raise ValueError("request size")
            data = json.loads(self.rfile.read(size))
            if (not isinstance(data, dict) or set(data) != {"correlationId", "workItemId", "input", "maxOutputTokens", "timeoutSeconds", "nonce", "provenanceMac"}
                    or not isinstance(data["correlationId"], str)
                    or not isinstance(data["workItemId"], str)):
                raise ValueError("request shape")
            input_value = data["input"]
            if (not isinstance(input_value, list) or len(input_value) != 1 or
                    not isinstance(input_value[0], dict) or set(input_value[0]) != {"role", "content"} or
                    input_value[0]["role"] != "user" or not isinstance(input_value[0]["content"], list) or
                    len(input_value[0]["content"]) != 1 or not isinstance(input_value[0]["content"][0], dict) or
                    set(input_value[0]["content"][0]) != {"type", "text"} or
                    input_value[0]["content"][0]["type"] != "input_text" or
                    not isinstance(input_value[0]["content"][0]["text"], str)):
                raise ValueError("context envelope")
            nonce = data["nonce"]
            if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
                raise ValueError("provenance nonce")
            context_text = input_value[0]["content"][0]["text"]
            message = ("EmbrAIonContext/v1\n" + data["correlationId"] + "\n" + data["workItemId"] +
                       "\n" + os.environ["EMBRAION_UPSTREAM_MODEL"] + "\n" + nonce + "\n" + context_text).encode("utf-8")
            expected = hmac.new(bytes.fromhex(os.environ["EMBRAION_PROVENANCE_KEY"]), message, hashlib.sha256).hexdigest()
            if not isinstance(data["provenanceMac"], str) or not hmac.compare_digest(expected, data["provenanceMac"]):
                raise ValueError("context provenance")
            if importlib.metadata.version("litellm") != "1.77.7":
                raise RuntimeError("unsupported LiteLLM version")
            import litellm  # Optional dependency, loaded only by the selected child.

            litellm.num_retries = 0
            response = litellm.responses(
                model=os.environ["EMBRAION_UPSTREAM_MODEL"], input=input_value,
                metadata={"correlationId": data["correlationId"], "workItemId": data["workItemId"]},
                stream=False, timeout=data["timeoutSeconds"], max_output_tokens=data["maxOutputTokens"],
                max_retries=0, api_key=os.environ["EMBRAION_PROVIDER_KEY"],
            )
            payload = _response_payload(response)
            hidden = getattr(response, "_hidden_params", {}) or {}
            attempted = os.environ["EMBRAION_UPSTREAM_MODEL"].split("/", 1)[0]
            reported = hidden.get("custom_llm_provider")
            if not isinstance(reported, str) or reported != attempted:
                raise ValueError("provider identity")
            result = {"status": "completed", "correlationId": data["correlationId"],
                      "adapterVersion": "1.77.7",
                      "callId": hidden.get("litellm_call_id") or hidden.get("response_cost_id"),
                      "observedProvider": reported, "observedModel": payload.get("model"),
                      "outputText": payload.get("output_text"), "usage": payload.get("usage"),
                      "adapterCost": hidden.get("response_cost")}
            code = 200
        except ValueError:
            result = {"status": "failed", "failure": "invalid-request"}
            code = 400
        except Exception as error:
            result = {"status": "failed", "failure": _provider_failure(error)}
            code = 502
        encoded = json.dumps(result, separators=(",", ":"), default=str).encode("utf-8")
        if len(encoded) > _LIMIT:
            encoded = b'{"status":"failed","failure":"unknown"}'
            code = 502
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class _LoopbackServer(HTTPServer):
    def server_bind(self) -> None:
        # HTTPServer's reverse-DNS lookup is unnecessary for a fixed loopback host
        # and can delay readiness on isolated CI and offline machines.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def _exit_on_parent_eof() -> None:
    sys.stdin.buffer.read()
    os._exit(0)


def _exit_at_deadline(seconds: int) -> None:
    time.sleep(seconds)
    os._exit(0)


def main() -> None:
    lifetime = int(os.environ["EMBRAION_LIFETIME_SECONDS"])
    if not 1 <= lifetime <= 3605:
        raise RuntimeError("invalid lifetime")
    server = _LoopbackServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=_exit_on_parent_eof, daemon=True).start()
    threading.Thread(target=_exit_at_deadline, args=(lifetime,), daemon=True).start()
    print(server.server_port, flush=True)
    server.handle_request()
    server.server_close()


if __name__ == "__main__":
    main()
