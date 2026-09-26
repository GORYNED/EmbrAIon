"""Optional, single-call LiteLLM transport through a short-lived loopback child."""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..common import project_root
from .provider_pricing import OFFICIAL_HOSTS


_BODY_LIMIT = 1_048_576
_OUTPUT_LIMIT = 32_768
_LITELLM_VERSION = "1.77.7"
_EVIDENCE_LIMIT = 65_536


def _valid_input(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 1:
        return False
    message = value[0]
    if not isinstance(message, dict) or set(message) != {"role", "content"} or message["role"] != "user":
        return False
    content = message["content"]
    return (isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict)
            and set(content[0]) == {"type", "text"} and content[0]["type"] == "input_text"
            and isinstance(content[0]["text"], str) and bool(content[0]["text"].strip())
            and len(content[0]["text"].encode("utf-8")) <= _BODY_LIMIT)


def _valid_envelope(value: list[dict[str, Any]], request: dict[str, Any],
                    deployment_id: str, deployment: dict[str, Any], binding: dict[str, Any]) -> bool:
    try:
        envelope = json.loads(value[0]["content"][0]["text"])
    except (ValueError, TypeError):
        return False
    if not isinstance(envelope, dict) or envelope.get("schemaVersion") != 1 or envelope.get("boundary") != binding.get("contextBoundary"):
        return False
    item = envelope.get("workItem")
    if not isinstance(item, dict) or any(item.get(key) != expected for key, expected in {
        "workItemId": request["workItemId"], "deploymentId": deployment_id,
        "model": deployment["model"], "role": request["role"],
        "sourceIds": request["sourceIds"], "access": request["access"],
        "dataClass": (binding.get("dataClassAliases") or {}).get(request["dataClass"], request["dataClass"]),
    }.items()):
        return False
    context = envelope.get("context")
    if not isinstance(context, list) or len(context) > 128:
        return False
    for entry in context:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("content"), str):
            return False
        path = entry["path"].replace("\\", "/")
        if (not path or path.startswith("/") or ":" in path or any(part in {"", ".."} for part in path.split("/"))):
            return False
    return True


def _read_port(stream: Any, output: queue.Queue[str]) -> None:
    output.put(stream.readline())


def _clean_child_environment(credential: str | None, selector: str, token: str, lifetime: int,
                             provenance_key: str) -> dict[str, str]:
    permitted = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "SSL_CERT_FILE",
                 "REQUESTS_CA_BUNDLE", "PYTHONIOENCODING", "LANG", "LC_ALL"}
    env = {key: value for key, value in os.environ.items() if key.upper() in permitted}
    env.update({"EMBRAION_SESSION_TOKEN": token, "EMBRAION_UPSTREAM_MODEL": selector,
                "EMBRAION_LIFETIME_SECONDS": str(lifetime), "EMBRAION_PROVENANCE_KEY": provenance_key})
    if credential is not None:
        env["EMBRAION_PROVIDER_KEY"] = credential
    return env


def _token_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _normalize_usage(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    input_details = value.get("input_tokens_details") or {}
    output_details = value.get("output_tokens_details") or {}
    if not isinstance(input_details, dict) or not isinstance(output_details, dict):
        return None
    fields = {"inputTokens": _token_count(value.get("input_tokens")),
              "outputTokens": _token_count(value.get("output_tokens")),
              "cachedInputTokens": _token_count(input_details.get("cached_tokens")),
              "reasoningTokens": _token_count(output_details.get("reasoning_tokens"))}
    return {key: item for key, item in fields.items() if item is not None}


def _model_matches(binding: dict[str, Any], observed: str) -> bool:
    expected = binding.get("expectedResponseModels", [])
    if observed in expected:
        return True
    pattern = binding.get("expectedResponseModelPattern")
    if not pattern:
        return False
    # regex is an existing bounded-parser dependency. Never use re for project patterns.
    import regex
    try:
        return regex.fullmatch(pattern, observed, timeout=0.1) is not None
    except (TimeoutError, regex.error):
        return False


def _verified_usage_semantics(binding: dict[str, Any], observed_version: object,
                              project: Path) -> dict[str, str] | None:
    """Use only a reviewed, current fixture for this exact transport build and selector.

    Invalid or absent evidence affects cost only; it must not block a completed AI call.
    """
    reference = binding.get("usageSemanticsEvidence")
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        return None
    relative, digest = reference["path"], reference["sha256"]
    if (not isinstance(relative, str) or
            not re.fullmatch(r"\.embraion/usage-evidence/[a-z0-9][a-z0-9._-]*\.json", relative) or
            not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest) or
            observed_version != _LITELLM_VERSION):
        return None
    try:
        root = project.resolve(strict=True)
        if any(path.is_symlink() for path in (root / ".embraion", root / ".embraion/usage-evidence", root / relative)):
            return None
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file() or target.stat().st_size > _EVIDENCE_LIMIT:
            return None
        content = target.read_bytes()
        if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), digest):
            return None
        evidence = json.loads(content)
        if not isinstance(evidence, dict) or set(evidence) != {
            "schemaVersion", "transport", "adapterVersion", "provider", "selector",
            "sourceUrl", "verifiedUtc", "validThroughUtc", "usageSemantics", "sampleUsage",
        }:
            return None
        if (evidence["schemaVersion"] != 1 or evidence["transport"] != "litellm-responses" or
                evidence["adapterVersion"] != _LITELLM_VERSION or
                evidence["provider"] != binding.get("expectedProvider") or
                evidence["selector"] != binding.get("selector")):
            return None
        source = urlsplit(evidence["sourceUrl"])
        if (source.scheme != "https" or source.hostname not in OFFICIAL_HOSTS.get(evidence["provider"], set())
                or source.port not in (None, 443) or source.username or source.password or source.fragment):
            return None
        verified = datetime.fromisoformat(evidence["verifiedUtc"].replace("Z", "+00:00"))
        valid_through = datetime.fromisoformat(evidence["validThroughUtc"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if verified.tzinfo is None or valid_through.tzinfo is None or not verified <= now <= valid_through:
            return None
        semantics = evidence["usageSemantics"]
        if (not isinstance(semantics, dict) or set(semantics) != {"input", "output"} or
                any(value not in {"inclusive", "disjoint"} for value in semantics.values())):
            return None
        sample = evidence["sampleUsage"]
        if (not isinstance(sample, dict) or _normalize_usage(sample) is None or
                "inputTokens" not in _normalize_usage(sample) or "outputTokens" not in _normalize_usage(sample)):
            return None
        return semantics
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


class LiteLLMLoopbackAdapter:
    """Launch one scoped child, send one approved request, then reap it."""

    def __init__(self, project: Path | None = None) -> None:
        self.project = project_root(project)

    def preflight(self, request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any]) -> None:
        selector = binding["selector"]
        provider = binding.get("expectedProvider")
        if not isinstance(selector, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}/[^\s]{1,128}", selector):
            raise RuntimeError("LiteLLM selector must name one explicit upstream provider/model.")
        if provider != selector.split("/", 1)[0]:
            raise RuntimeError("LiteLLM provider binding is inconsistent.")
        if not binding.get("expectedResponseModels") and not binding.get("expectedResponseModelPattern"):
            raise RuntimeError("LiteLLM observed model evidence is not configured.")
        if not isinstance(binding.get("contextBoundary"), str) or not binding["contextBoundary"]:
            raise RuntimeError("LiteLLM requires an approved context boundary binding.")
        pattern = binding.get("expectedResponseModelPattern")
        if pattern and (len(pattern) > 512 or not pattern.startswith("^") or not pattern.endswith("$")):
            raise RuntimeError("LiteLLM model evidence pattern must be bounded and anchored.")
        if request["access"] != "read-only":
            raise RuntimeError("LiteLLM adapter accepts read-only work only.")
        payload = request.get("payload")
        candidates = {item["deployment"] for item in request["candidates"]}
        if (not isinstance(payload, dict) or set(payload) - {"inputsByDeployment", "maxOutputTokens"}
                or not isinstance(payload.get("inputsByDeployment"), dict)
                or set(payload["inputsByDeployment"]) != candidates):
            raise RuntimeError("LiteLLM requires one bounded input for every candidate.")
        if any(not _valid_input(value) for value in payload["inputsByDeployment"].values()):
            raise RuntimeError("LiteLLM input envelope is invalid.")
        if not _valid_envelope(payload["inputsByDeployment"][request["selected"]["deployment"]],
                               request, request["selected"]["deployment"], deployment, binding):
            raise RuntimeError("LiteLLM context provenance does not match the selected work item.")
        maximum = payload.get("maxOutputTokens", 4096)
        if type(maximum) is not int or not 1 <= maximum <= _OUTPUT_LIMIT:
            raise RuntimeError("LiteLLM output token bound is invalid.")
        if not binding.get("credentialRef") and os.environ.get("EMBRAION_TEST_MODE") != "1":
            raise RuntimeError("LiteLLM requires an opaque credential binding.")

    def execute(self, request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any],
                credential: str | None) -> dict[str, Any]:
        selected = request["selected"]["deployment"]
        test_mode = os.environ.get("EMBRAION_TEST_MODE") == "1"
        fixture = os.environ.get("EMBRAION_LITELLM_TEST_SERVER_SCRIPT") if test_mode else None
        if not fixture and not credential:
            return {"status": "failed", "failure": "authentication", "terminationConfirmed": True,
                    "mutationConfirmed": True}
        input_value = request["payload"]["inputsByDeployment"][selected]
        if credential and credential in json.dumps(input_value, ensure_ascii=False):
            return {"status": "failed", "failure": "policy-denied", "terminationConfirmed": True,
                    "mutationConfirmed": True}
        bearer = secrets.token_urlsafe(32)
        correlation = secrets.token_hex(16)
        nonce = secrets.token_hex(16)
        provenance_key = secrets.token_hex(32)
        lifetime = min(request["timeoutSeconds"] + 5, 3605)
        script = Path(fixture).resolve() if fixture else Path(__file__).with_name("litellm_host.py")
        if fixture and (not script.is_file() or not test_mode):
            raise RuntimeError("LiteLLM test host is unavailable.")
        environment = _clean_child_environment(None if fixture else credential, binding["selector"], bearer, lifetime,
                                               provenance_key)
        context_text = input_value[0]["content"][0]["text"]
        signed = ("EmbrAIonContext/v1\n" + correlation + "\n" + request["workItemId"] + "\n" +
                  binding["selector"] + "\n" + nonce + "\n" + context_text).encode("utf-8")
        mac = hmac.new(bytes.fromhex(provenance_key), signed, hashlib.sha256).hexdigest()
        body = json.dumps({"correlationId": correlation, "workItemId": request["workItemId"],
                           "input": input_value, "maxOutputTokens": request["payload"].get("maxOutputTokens", 4096),
                           "timeoutSeconds": request["timeoutSeconds"], "nonce": nonce,
                           "provenanceMac": mac}, separators=(",", ":")).encode("utf-8")
        if len(body) > _BODY_LIMIT:
            raise RuntimeError("LiteLLM request exceeds the body limit.")
        process: subprocess.Popen[bytes] | None = None
        completed = False
        try:
            process = subprocess.Popen([sys.executable, "-u", str(script)], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment)
            ports: queue.Queue[str] = queue.Queue(maxsize=1)
            threading.Thread(target=_read_port, args=(process.stdout, ports), daemon=True).start()
            try:
                port_text = ports.get(timeout=min(10, request["timeoutSeconds"]))
                port = int(port_text.strip())
                if not 1 <= port <= 65535 or process.poll() is not None:
                    raise ValueError("child port")
            except (queue.Empty, ValueError) as error:
                raise RuntimeError("LiteLLM loopback child did not become ready.") from error
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            message = urllib.request.Request(f"http://127.0.0.1:{port}/v1/responses", data=body,
                                             headers={"Authorization": "Bearer " + bearer,
                                                      "Content-Type": "application/json"}, method="POST")
            try:
                response = opener.open(message, timeout=request["timeoutSeconds"] + 2)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                if response.headers.get("Content-Length") and int(response.headers["Content-Length"]) > _BODY_LIMIT:
                    raise RuntimeError("LiteLLM response exceeds the body limit.")
                data = response.read(_BODY_LIMIT + 1)
                if len(data) > _BODY_LIMIT:
                    raise RuntimeError("LiteLLM response exceeds the body limit.")
                raw = json.loads(data)
            process.wait(timeout=3)
            completed = process.returncode == 0
            if not completed or not isinstance(raw, dict):
                raise RuntimeError("LiteLLM child completion is unverified.")
            if raw.get("status") != "completed":
                return {"status": "failed", "failure": raw.get("failure", "unknown"),
                        "httpStatus": response.status, "correlationId": correlation,
                        "terminationConfirmed": True, "mutationConfirmed": True}
            observed = raw.get("observedModel")
            provider = raw.get("observedProvider")
            call_id = raw.get("callId")
            if (raw.get("correlationId") != correlation or not isinstance(observed, str)
                    or not _model_matches(binding, observed) or provider != binding["expectedProvider"]):
                return {"status": "failed", "failure": "unknown", "correlationId": correlation,
                    "terminationConfirmed": True, "mutationConfirmed": False}
            if not isinstance(call_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", call_id):
                return {"status": "failed", "failure": "unknown", "correlationId": correlation,
                        "terminationConfirmed": True, "mutationConfirmed": False}
            output = raw.get("outputText")
            if not isinstance(output, str) or not output.strip():
                return {"status": "failed", "failure": "unknown", "correlationId": correlation,
                        "terminationConfirmed": True, "mutationConfirmed": False}
            cost = raw.get("adapterCost")
            return {"status": "completed", "observedModel": observed, "observedProvider": provider,
                    "correlationId": correlation, "callId": call_id,
                    "usage": _normalize_usage(raw.get("usage")),
                    "usageSemantics": _verified_usage_semantics(binding, raw.get("adapterVersion"), self.project),
                    "adapterCost": str(cost) if cost is not None else None, "reportedCurrency": "USD" if cost is not None else None,
                    "outputText": output, "terminationConfirmed": True, "mutationConfirmed": True}
        except (OSError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError):
            return {"status": "failed", "failure": "transport", "correlationId": correlation,
                    "terminationConfirmed": completed, "mutationConfirmed": False}
        finally:
            if process is not None:
                if process.stdin:
                    process.stdin.close()
                if process.poll() is None:
                    process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                if process.stdout:
                    process.stdout.close()
