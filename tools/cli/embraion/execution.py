"""Provider-neutral, fail-closed bounded execution orchestration."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .common import project_root
from .failures import may_fallback, normalize_failure
from .health import evaluate_health
from .policy import _validated_config_mapping, read_deployments_config
from .pricing import _validate, calculate_cost


class ExecutionAdapter(Protocol):
    def preflight(self, request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any]) -> None: ...
    def execute(self, request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any],
                credential: str | None) -> dict[str, Any]: ...


class CredentialResolver(Protocol):
    def resolve(self, reference: str, deployment: str, adapter: str) -> str: ...


class EnvironmentResolver:
    def resolve(self, reference: str, deployment: str, adapter: str) -> str:
        if not reference.startswith("env:"):
            raise RuntimeError("Unsupported credential reference.")
        value = os.environ.get(reference[4:])
        if not value:
            raise RuntimeError("Configured credential is unavailable.")
        return value


def read_execution_config(project: Path | None = None) -> dict[str, Any]:
    path = project_root(project) / ".embraion" / "execution.yaml"
    if not path.is_file():
        return {"schemaVersion": 1, "bindings": {}}
    return _validated_config_mapping(path, schema_name="execution-config.schema.json", label=".embraion/execution.yaml")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _eligible(request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any]) -> bool:
    capabilities = deployment.get("capabilities") or {}
    return bool(
        deployment.get("enabled", True)
        and deployment["host"] == request["host"]
        and all(capabilities.get(key) for key in ("data-classes", "access-modes", "roles", "task-classes"))
        and request["dataClass"] in capabilities["data-classes"]
        and request["access"] in capabilities["access-modes"]
        and request["role"] in capabilities["roles"]
        and request["routeClass"] in capabilities["task-classes"]
        and set(request["sourceIds"]).issubset(binding["sourceIds"])
        and request["trustLevel"] in binding["trustLevels"]
        and (request["access"] != "workspace-write" or bool(request["ownedPaths"]))
    )


def execute(
    request: dict[str, Any], *, project: Path | None = None,
    adapters: dict[str, ExecutionAdapter] | None = None,
    resolver: CredentialResolver | None = None,
    evidence_sink: Callable[[dict[str, Any]], None] | None = None,
    health_observations: dict[str, list[dict[str, Any]]] | None = None,
    health_policy: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Execute only predeclared candidates under the immutable original request ceilings.

    The result and sink intentionally omit prompt/context bytes and credential values.
    """
    _validate(request, "execution-request.schema.json")
    identities = [item["deployment"] for item in request["candidates"]]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Execution candidate repeats a deployment.")
    root = project_root(project)
    registry = read_deployments_config(root)["deployments"]
    bindings = read_execution_config(root)["bindings"]
    adapter_map = adapters or {}
    credential_resolver = resolver or EnvironmentResolver()
    attempts: list[dict[str, Any]] = []
    seen: set[str] = set()
    status = "failed"
    for candidate in request["candidates"][: request["maxAttempts"]]:
        identifier = candidate["deployment"]
        if identifier in seen:
            raise RuntimeError("Execution candidate repeats a deployment.")
        seen.add(identifier)
        deployment = registry.get(identifier)
        binding = bindings.get(identifier)
        if deployment is None:
            raise RuntimeError("Execution candidate is not a declared deployment.")
        if binding is None:
            # Unbound native/host candidates require an explicit host handoff.
            status = "handoff-required"
            break
        if not _eligible(request, deployment, binding):
            raise RuntimeError("Execution candidate violates original role/data/source/trust/access ceilings.")
        effort = candidate.get("effort")
        if effort and effort not in (deployment.get("efforts") or []):
            raise RuntimeError("Execution candidate requests an unsupported effort.")
        if set((candidate.get("options") or {}).keys()) - set(binding.get("optionAllowlist") or []):
            raise RuntimeError("Execution candidate contains an unapproved option.")
        if request["timeoutSeconds"] > binding.get("maxTimeoutSeconds", 3600):
            raise RuntimeError("Execution timeout exceeds the project binding limit.")
        if health_observations is not None:
            health = evaluate_health(health_observations.get(identifier, []), **(health_policy or {}))
            if health["state"] == "unavailable":
                continue
        adapter = adapter_map.get(binding["adapter"])
        if adapter is None:
            status = "handoff-required"
            break
        model = deployment["model"]
        started = _now()
        raw: dict[str, Any]
        try:
            attempt_request = {**request, "selected": {"deployment": identifier, "effort": effort,
                                                        "options": candidate.get("options") or {}}}
            adapter.preflight(attempt_request, deployment, binding)
            credential = credential_resolver.resolve(binding["credentialRef"], identifier, binding["adapter"]) if binding.get("credentialRef") else None
            raw = adapter.execute(attempt_request, deployment, binding, credential)
        except Exception:
            raw = {"status": "failed", "failure": "unknown", "terminationConfirmed": False,
                   "mutationConfirmed": False, "observedModel": None, "usage": None}
        failure = normalize_failure(raw.get("failure"), http_status=raw.get("httpStatus")) if raw.get("failure") is not None or raw.get("httpStatus") is not None else None
        attempt_status = raw.get("status")
        if attempt_status not in {"completed", "failed", "cancelled"}:
            attempt_status, failure = "failed", "unknown"
        if attempt_status != "completed" and failure is None:
            failure = "unknown"
        observed = raw.get("observedModel")
        if attempt_status == "completed" and (not isinstance(observed, str) or not observed):
            attempt_status, failure = "failed", "unknown"
        raw_usage = raw.get("usage")
        usage = ({key: value for key, value in raw_usage.items()
                  if key in {"inputTokens", "cachedInputTokens", "outputTokens", "reasoningTokens"}
                  and type(value) is int and value >= 0}
                 if isinstance(raw_usage, dict) else None)
        cost = calculate_cost(identifier, usage, project=root, billing=(deployment.get("billing") or {}).get("mode", "api"),
                              provider_exact=raw.get("providerExactCost"), adapter_cost=raw.get("adapterCost"),
                              usage_semantics=raw.get("usageSemantics"), reported_currency=raw.get("reportedCurrency"))
        attempt = {
            "deployment": identifier, "requestedModel": model, "observedModel": observed if isinstance(observed, str) else None,
            "startedUtc": started, "finishedUtc": _now(), "status": attempt_status,
            "failure": failure, "usage": usage, "cost": cost,
            "terminationConfirmed": raw.get("terminationConfirmed") is True,
            "mutationConfirmed": raw.get("mutationConfirmed") is True,
            "fallbackFrom": attempts[-1]["deployment"] if attempts else None,
        }
        # Validate before sending to the durable sink. No raw adapter output is persisted.
        _validate({"schemaVersion": 1, "runId": request["runId"], "workItemId": request["workItemId"],
                   "status": "completed" if attempt_status == "completed" else "failed", "attempts": [attempt]},
                  "execution-result.schema.json")
        attempts.append(attempt)
        if evidence_sink:
            evidence_sink(attempt)
        if attempt_status == "completed":
            status = "completed"
            break
        if attempt_status == "cancelled" or failure == "cancelled":
            status = "cancelled"
            break
        if not may_fallback(failure, termination_confirmed=attempt["terminationConfirmed"],
                            mutation_confirmed=attempt["mutationConfirmed"]):
            status = "failed"
            break
    result = {"schemaVersion": 1, "runId": request["runId"], "workItemId": request["workItemId"],
              "status": status, "attempts": attempts}
    _validate(result, "execution-result.schema.json")
    return result
