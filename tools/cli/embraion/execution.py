"""Provider-neutral, fail-closed bounded execution orchestration."""

from __future__ import annotations

import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .common import project_root
from .failures import may_fallback, normalize_failure, UnsupportedExecutionSettings
from .health import evaluate_health
from .policy import _validated_config_mapping, read_deployments_config
from .pricing import _validate, calculate_cost


class ExecutionAdapter(Protocol):
    def preflight(self, request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any]) -> None: ...
    def execute(self, request: dict[str, Any], deployment: dict[str, Any], binding: dict[str, Any],
                credential: str | None) -> dict[str, Any]: ...


class ExecutionEvidenceWarning(UserWarning):
    """A validated attempt could not be persisted; the result itself remains valid."""


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
    bound_class = (binding.get("dataClassAliases") or {}).get(request["dataClass"], request["dataClass"])
    route_class = request["routeClass"]
    project_task_class = request.get("taskClass")
    task_class = (binding.get("taskClassAliases") or {}).get(
        project_task_class or route_class, project_task_class or route_class
    )
    permitted_classes = binding.get("taskClasses")
    return bool(
        deployment.get("enabled", True)
        and deployment["host"] == request["host"]
        and all(capabilities.get(key) for key in ("data-classes", "access-modes", "roles"))
        and bool(capabilities.get("task-classes"))
        and bound_class in capabilities["data-classes"]
        and request["access"] in capabilities["access-modes"]
        and request["role"] in capabilities["roles"]
        and (permitted_classes is None or route_class in permitted_classes or task_class in permitted_classes)
        and (route_class in capabilities["task-classes"] or
             (route_class != "critical" and task_class in capabilities["task-classes"]))
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
    persist_attempts: bool = False,
) -> dict[str, Any]:
    """Execute only predeclared candidates under the immutable original request ceilings.

    The result and sink intentionally omit prompt/context bytes and credential values.
    With `persist_attempts`, each validated attempt is appended to the local attempt
    ledger, and ledger health is used when neither the caller nor the request
    supplies observations.
    """
    _validate(request, "execution-request.schema.json")
    if request["routeClass"] == "critical" and not (request.get("justification") or "").strip():
        raise RuntimeError("Critical task routing requires justification.")
    if request["routeClass"] == "critical":
        from .ceilings import enforce_critical_justification
        enforce_critical_justification(request.get("justification"), project)
    identities = [item["deployment"] for item in request["candidates"]]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Execution candidate repeats a deployment.")
    root = project_root(project)
    if request.get("taskClass"):
        from .runtime import resolve_task_route
        resolved = resolve_task_route(
            request["taskClass"], data_class=request["dataClass"], role=request["role"],
            access=request["access"], escalation=request.get("escalation"),
            justification=request.get("justification"), shape=request.get("shape"), project=root,
            _emit_event=False,
        )
        expected_route = resolved["selected"]["route"]
        if request["routeClass"] != expected_route:
            raise RuntimeError("Execution route class does not match the effective task route.")
        allowed = ([resolved["selected"]] if request.get("escalation") else resolved["candidates"])
        allowed_ids = [item["deployment"] for item in allowed]
        actual_ids = [item["deployment"] for item in request["candidates"]]
        if any(item not in allowed_ids for item in actual_ids) or actual_ids != [item for item in allowed_ids if item in actual_ids]:
            raise RuntimeError("Execution candidates do not follow the project effective route.")
    elif request.get("escalation"):
        raise RuntimeError("Execution escalation requires a project task class.")
    registry = read_deployments_config(root)["deployments"]
    bindings = read_execution_config(root)["bindings"]
    if request["routeClass"] == "critical":
        from .runtime import _append_event
        # Retain the reason even for direct stdin requests. This records an
        # execution request, not a selected/started/successful adapter attempt.
        # The common event writer redacts credentials before persistence.
        _append_event(root, {
            "event": "critical-execution-requested",
            "run-id": request["runId"], "work-item-id": request["workItemId"],
            "task-id": request["taskId"], "host": request["host"],
            "role": request["role"], "route": request["routeClass"],
            "data-class": request["dataClass"], "justification": request["justification"],
        })
    adapter_map = adapters or {}
    credential_resolver = resolver or EnvironmentResolver()
    attempts: list[dict[str, Any]] = []
    seen: set[str] = set()
    status = "failed"
    output_text: str | None = None
    handoff: dict[str, str] | None = None
    observations = health_observations if health_observations is not None else request.get("healthObservations")
    if observations is None and persist_attempts:
        from .ledger import health_observations as ledger_observations
        observations = ledger_observations(root)
    policy = health_policy if health_policy is not None else request.get("healthPolicy")
    states = ({identifier: evaluate_health(observations.get(identifier, []), **(policy or {}))["state"]
               for identifier in identities} if observations is not None else {})
    candidates = list(request["candidates"])
    if not request.get("taskClass") and not request.get("preserveCandidateOrder", False):
        candidates.sort(key=lambda item: 1 if states.get(item["deployment"]) == "degraded" else
                        2 if states.get(item["deployment"]) == "unavailable" else 0)
    for candidate in candidates:
        if len(attempts) >= request["maxAttempts"]:
            break
        identifier = candidate["deployment"]
        if identifier in seen:
            raise RuntimeError("Execution candidate repeats a deployment.")
        seen.add(identifier)
        deployment = registry.get(identifier)
        binding = bindings.get(identifier)
        if deployment is None:
            raise RuntimeError("Execution candidate is not a declared deployment.")
        if deployment["host"] != request["host"]:
            from .runtime import _deployment_registry, _resolve_deployment
            _resolve_deployment(identifier, registry=_deployment_registry(root),
                                host=deployment["host"], route_class=request["routeClass"],
                                task_class=request.get("taskClass"), data_class=request["dataClass"],
                                role=request["role"], access=request["access"],
                                effort=candidate.get("effort"), options=candidate.get("options"))
            if binding is not None and not _eligible({**request, "host": deployment["host"]}, deployment, binding):
                raise RuntimeError("Cross-host candidate violates original request ceilings.")
            status = "handoff-required"
            handoff = {"deployment": identifier, "host": deployment["host"], "reason": "host-boundary"}
            break
        if binding is None:
            # Unbound native/host candidates require an explicit host handoff.
            status = "handoff-required"
            handoff = {"deployment": identifier, "host": deployment["host"], "reason": "unbound-adapter"}
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
        if states.get(identifier) == "unavailable":
            continue
        adapter = adapter_map.get(binding["adapter"])
        if adapter is None:
            status = "handoff-required"
            break
        model = deployment["model"]
        started = _now()
        raw: dict[str, Any]
        preflight_finished = False
        try:
            attempt_request = {**request, "selected": {"deployment": identifier, "effort": effort,
                                                        "options": candidate.get("options") or {}},
                               "_adapterCandidateDeployments": [
                                   item for item in identities
                                   if registry.get(item, {}).get("host") == request["host"]
                                   and bindings.get(item, {}).get("adapter") == binding["adapter"]
                               ]}
            adapter.preflight(attempt_request, deployment, binding)
            preflight_finished = True
            test_host = (binding["adapter"] == "litellm-loopback" and os.environ.get("EMBRAION_TEST_MODE") == "1"
                         and bool(os.environ.get("EMBRAION_LITELLM_TEST_SERVER_SCRIPT")))
            credential = (credential_resolver.resolve(binding["credentialRef"], identifier, binding["adapter"])
                          if binding.get("credentialRef") and not test_host else None)
            raw = adapter.execute(attempt_request, deployment, binding, credential)
        except UnsupportedExecutionSettings:
            raw = ({"status": "failed", "failure": "unknown",
                    "terminationConfirmed": False, "mutationConfirmed": False} if preflight_finished else
                   {"status": "failed", "failure": "unsupported-capability",
                    "diagnostic": UnsupportedExecutionSettings.diagnostic,
                    "terminationConfirmed": True, "mutationConfirmed": True})
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
        if attempt_status == "completed" and raw.get("observedProvider") is not None and binding.get("expectedProvider") is not None and raw["observedProvider"] != binding["expectedProvider"]:
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
            "fallbackReason": attempts[-1]["failure"] if attempts else None,
            "correlationId": raw.get("correlationId") if isinstance(raw.get("correlationId"), str) else None,
            "callId": raw.get("callId") if isinstance(raw.get("callId"), str) else None,
            "requestedProvider": binding.get("expectedProvider"),
            "observedProvider": raw.get("observedProvider") if isinstance(raw.get("observedProvider"), str) else None,
            "usageState": "upstream-unavailable" if usage is None else ("complete" if "inputTokens" in usage and "outputTokens" in usage else "partial"),
            "validationState": "pending" if attempt_status == "completed" else "rejected",
        }
        if raw.get("diagnostic") == UnsupportedExecutionSettings.diagnostic:
            attempt["diagnostic"] = UnsupportedExecutionSettings.diagnostic
        # Validate before sending to the durable sink. No raw adapter output is persisted.
        _validate({"schemaVersion": 1, "runId": request["runId"], "workItemId": request["workItemId"],
                   "status": "completed" if attempt_status == "completed" else "failed", "attempts": [attempt]},
                  "execution-result.schema.json")
        attempts.append(attempt)
        if evidence_sink:
            evidence_sink(attempt)
        if persist_attempts:
            from .ledger import append_attempt
            try:
                append_attempt(root, attempt, run_id=request["runId"], work_item_id=request["workItemId"])
            except (OSError, RuntimeError):
                warnings.warn("Execution attempt evidence could not be persisted to the local ledger.",
                              ExecutionEvidenceWarning, stacklevel=2)
        if attempt_status == "completed":
            status = "completed"
            output_text = raw.get("outputText") if isinstance(raw.get("outputText"), str) else None
            break
        if attempt_status == "cancelled" or failure == "cancelled":
            status = "cancelled"
            break
        if not may_fallback(failure, termination_confirmed=attempt["terminationConfirmed"],
                            mutation_confirmed=attempt["mutationConfirmed"]):
            status = "failed"
            break
    result = {"schemaVersion": 1, "runId": request["runId"], "workItemId": request["workItemId"],
              "status": status, "attempts": attempts, "outputText": output_text}
    if handoff is not None:
        result["handoff"] = handoff
    _validate(result, "execution-result.schema.json")
    return result


_PREFLIGHT_TASK = "Readiness check: confirm the bound context envelope only."


def _check_bound(identifier: str, deployment: dict[str, Any], binding: dict[str, Any],
                 adapter: ExecutionAdapter | None, resolver: CredentialResolver) -> dict[str, Any]:
    """Request-independent checks; never resolve more than credential presence."""
    entry: dict[str, Any] = {"deployment": identifier, "adapter": binding.get("adapter"),
                             "binding": "complete", "credential": "not-configured", "reasons": []}
    if adapter is None:
        entry["binding"] = "adapter-unavailable"
        entry["reasons"].append("The binding adapter is not available in this runtime.")
    else:
        check = getattr(adapter, "check_binding", None)
        if callable(check):
            try:
                check(deployment, binding)
            except Exception as error:  # adapter checks raise static reasons only
                entry["binding"] = "incomplete"
                entry["reasons"].append(str(error) if isinstance(error, RuntimeError) else "Binding check failed.")
    reference = binding.get("credentialRef")
    if reference:
        try:
            resolver.resolve(reference, identifier, str(binding.get("adapter")))
            entry["credential"] = "present"
        except Exception:
            entry["credential"] = "missing"
            entry["reasons"].append(f"Credential reference {reference} does not resolve.")
    return entry


def preflight_execution(request: dict[str, Any] | None = None, *, deployments: list[str] | None = None,
                        project: Path | None = None, adapters: dict[str, ExecutionAdapter] | None = None,
                        resolver: CredentialResolver | None = None, paths: list[str] | None = None,
                        task: str | None = None, commit: str = "HEAD") -> dict[str, Any]:
    """Check adapter-bound candidates without credential output or any provider call."""
    root = project_root(project)
    registry = read_deployments_config(root)["deployments"]
    bindings = read_execution_config(root)["bindings"]
    adapter_map = adapters or {}
    credential_resolver = resolver or EnvironmentResolver()
    from .ledger import health_observations as ledger_observations
    observations = ledger_observations(root)
    entries: list[dict[str, Any]] = []
    handoff: list[dict[str, str]] = []
    reasons: list[str] = []
    if request is None:
        for identifier in deployments or []:
            deployment, binding = registry.get(identifier), bindings.get(identifier)
            if deployment is None or binding is None:
                entries.append({"deployment": identifier, "adapter": None, "ready": False,
                                "binding": "undeclared" if deployment is None else "unbound",
                                "credential": "not-configured", "requestPreflight": "not-run",
                                "reasons": ["Deployment is not declared." if deployment is None
                                            else "Deployment has no execution binding."]})
                continue
            entry = _check_bound(identifier, deployment, binding, adapter_map.get(binding["adapter"]),
                                 credential_resolver)
            entry.update({"requestPreflight": "not-run", "ready": not entry["reasons"]})
            entries.append(entry)
        if not entries:
            reasons.append("No deployment was selected.")
    else:
        _validate(request, "execution-request.schema.json")
        from .envelope import EnvelopeRefused, adapter_bound_candidates, build_payload, with_payload
        identities = [item["deployment"] for item in request["candidates"]]
        bound = adapter_bound_candidates(request, registry, bindings)
        payload_reason: str | None = None
        checked = request
        if request.get("payload") is None or set(request.get("payload") or {}) <= {"maxOutputTokens"}:
            if bound:
                try:
                    checked = with_payload(request, build_payload(
                        request, paths=list(paths or []), task=task or _PREFLIGHT_TASK,
                        project=root, commit=commit))
                except (EnvelopeRefused, RuntimeError) as error:
                    payload_reason = str(error)
                    reasons.append("Context envelope: " + payload_reason)
        for candidate in request["candidates"]:
            identifier = candidate["deployment"]
            deployment, binding = registry.get(identifier), bindings.get(identifier)
            if deployment is None:
                entries.append({"deployment": identifier, "adapter": None, "ready": False, "binding": "undeclared",
                                "credential": "not-configured", "requestPreflight": "not-run",
                                "reasons": ["Deployment is not declared."]})
                continue
            if deployment["host"] != request["host"] or binding is None:
                handoff.append({"deployment": identifier, "host": deployment["host"],
                                "reason": "host-boundary" if deployment["host"] != request["host"] else "unbound-adapter"})
                continue
            adapter = adapter_map.get(binding["adapter"])
            entry = _check_bound(identifier, deployment, binding, adapter, credential_resolver)
            entry["requestPreflight"] = "not-run"
            if not _eligible(request, deployment, binding):
                entry["reasons"].append("Candidate violates the request role/data/source/trust/access ceilings.")
            elif payload_reason is not None and identifier in bound:
                entry["reasons"].append("No valid context envelope could be built.")
            elif adapter is not None:
                attempt_request = {**checked, "selected": {"deployment": identifier, "effort": candidate.get("effort"),
                                                           "options": candidate.get("options") or {}},
                                   "_adapterCandidateDeployments": [
                                       item for item in identities
                                       if registry.get(item, {}).get("host") == request["host"]
                                       and bindings.get(item, {}).get("adapter") == binding["adapter"]]}
                try:
                    adapter.preflight(attempt_request, deployment, binding)
                    entry["requestPreflight"] = "passed"
                except UnsupportedExecutionSettings:
                    entry["requestPreflight"] = "failed"
                    entry["reasons"].append(UnsupportedExecutionSettings.diagnostic)
                except Exception as error:  # adapter preflight raises static reasons only
                    entry["requestPreflight"] = "failed"
                    entry["reasons"].append(str(error) if isinstance(error, RuntimeError) else "Adapter preflight failed.")
            entry["ready"] = not entry["reasons"]
            entries.append(entry)
        if not entries:
            reasons.append("The request has no adapter-bound candidate on its host.")
    for entry in entries:
        entry["health"] = evaluate_health(observations.get(entry["deployment"], []))["state"]
    return {"schemaVersion": 1, "ready": bool(entries) and not reasons and all(item["ready"] for item in entries),
            "deployments": entries, "handoff": handoff, "reasons": reasons}
