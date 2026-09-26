from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import redact_value

from .common import (
    framework_root,
    project_root,
    read_json,
    read_yaml,
    run,
    state_root,
    write_json,
)
from .policy import read_deployments_config, read_routing_config


def _append_event(project: Path, event: dict[str, Any]) -> None:
    path = state_root(project) / "telemetry.jsonl"
    event = {
        "schema-version": 1,
        "timestamp-utc": datetime.now(timezone.utc).isoformat(),
        **event,
    }
    event = redact_value(event)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def _known_route_classes() -> set[str]:
    data = read_yaml(framework_root() / "core" / "routing" / "complexity.yaml") or {}
    return {str(value) for value in (data.get("classes") or {}).keys()}


def _known_data_classes() -> set[str]:
    data = read_yaml(framework_root() / "core" / "routing" / "privacy.yaml") or {}
    return {str(value) for value in (data.get("data-classes") or {}).keys()}


def _routing_override(
    project: Path,
    host: str,
    route_class: str,
    role: str | None,
) -> dict[str, Any]:
    routing = read_routing_config(project)
    overrides = routing.get("overrides") or {}
    host_overrides = overrides.get(host) or {}
    if not isinstance(host_overrides, dict):
        raise RuntimeError(f"Routing overrides for host '{host}' must be a mapping.")

    routes = host_overrides.get("routes") or {}
    roles = host_overrides.get("roles") or {}
    route_override = routes.get(route_class) or {}
    role_override = (roles.get(role) or {}) if role else {}
    if not isinstance(route_override, dict) or not isinstance(role_override, dict):
        raise RuntimeError("Routing route/role overrides must be mappings.")

    merged = {**route_override, **role_override}
    if "deployment" in role_override:
        merged.pop("model", None)
        if "fallbacks" not in role_override:
            merged.pop("fallbacks", None)
    elif "model" in role_override:
        merged.pop("deployment", None)
        if "fallbacks" not in role_override:
            merged.pop("fallbacks", None)
    return merged


def _deployment_registry(project: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = read_deployments_config(project)
    providers = dict(config.get("providers") or {})
    deployments = dict(config.get("deployments") or {})
    for deployment_id, raw in deployments.items():
        definition = dict(raw or {})
        provider = definition.get("provider")
        if provider and provider not in providers:
            raise RuntimeError(
                f"Deployment '{deployment_id}' references unknown provider '{provider}'."
            )
        efforts = [str(value) for value in (definition.get("efforts") or [])]
        default_effort = definition.get("default-effort")
        if default_effort and efforts and str(default_effort) not in efforts:
            raise RuntimeError(
                f"Deployment '{deployment_id}' default effort '{default_effort}' "
                "is not listed in its supported efforts."
            )
    return providers, deployments


def list_deployments(project: Path | None = None) -> dict[str, Any]:
    project_path = project_root(project)
    providers, deployments = _deployment_registry(project_path)
    return {
        "providers": providers,
        "deployments": deployments,
        "provider-count": len(providers),
        "deployment-count": len(deployments),
    }


def get_deployment(deployment_id: str, project: Path | None = None) -> dict[str, Any]:
    project_path = project_root(project)
    providers, deployments = _deployment_registry(project_path)
    if deployment_id not in deployments:
        raise RuntimeError(f"Unknown project deployment: {deployment_id}")
    definition = dict(deployments[deployment_id])
    provider_id = definition.get("provider")
    return {
        "id": deployment_id,
        **definition,
        "provider-definition": providers.get(str(provider_id)) if provider_id else None,
    }


def _normalized_access_mode(access: str | None) -> str | None:
    if access is None:
        return None
    if access == "write":
        return "workspace-write"
    if access in {"inspect", "plan", "review", "external-read"}:
        return "read-only"
    return access


def _resolve_deployment(
    deployment_id: str,
    *,
    registry: tuple[dict[str, Any], dict[str, Any]],
    host: str,
    route_class: str,
    data_class: str,
    role: str | None,
    access: str | None,
    effort: str | None,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    providers, deployments = registry
    if deployment_id not in deployments:
        raise RuntimeError(f"Unknown project deployment: {deployment_id}")
    definition = dict(deployments[deployment_id])
    if definition.get("enabled", True) is not True:
        raise RuntimeError(f"Project deployment '{deployment_id}' is disabled.")
    deployment_host = str(definition["host"])
    if deployment_host != host:
        raise RuntimeError(
            f"Project deployment '{deployment_id}' belongs to host "
            f"'{deployment_host}', not '{host}'."
        )
    provider = definition.get("provider")
    if provider and provider not in providers:
        raise RuntimeError(
            f"Deployment '{deployment_id}' references unknown provider '{provider}'."
        )
    selected_effort = effort or definition.get("default-effort")
    supported_efforts = {str(value) for value in (definition.get("efforts") or [])}
    if selected_effort and supported_efforts and str(selected_effort) not in supported_efforts:
        raise RuntimeError(
            f"Project deployment '{deployment_id}' does not support effort "
            f"'{selected_effort}'."
        )
    capabilities = dict(definition.get("capabilities") or {})
    data_classes = {str(value) for value in (capabilities.get("data-classes") or [])}
    if data_classes and data_class not in data_classes:
        raise RuntimeError(
            f"Project deployment '{deployment_id}' does not allow data class '{data_class}'."
        )
    task_classes = {str(value) for value in (capabilities.get("task-classes") or [])}
    if task_classes and route_class not in task_classes:
        raise RuntimeError(
            f"Project deployment '{deployment_id}' does not allow route class '{route_class}'."
        )
    allowed_roles = {str(value) for value in (capabilities.get("roles") or [])}
    if role and allowed_roles and role not in allowed_roles:
        raise RuntimeError(
            f"Project deployment '{deployment_id}' does not allow role '{role}'."
        )
    access_mode = _normalized_access_mode(access)
    access_modes = {str(value) for value in (capabilities.get("access-modes") or [])}
    if access_mode and access_modes and access_mode not in access_modes:
        raise RuntimeError(
            f"Project deployment '{deployment_id}' does not allow access mode '{access_mode}'."
        )
    resolved_options = dict(definition.get("options") or {})
    resolved_options.update(options or {})
    return {
        "deployment": deployment_id,
        "provider": provider,
        "model": definition["model"],
        "effort": selected_effort,
        "options": resolved_options,
        "billing": definition.get("billing"),
    }


def _resolve_fallbacks(
    values: list[dict[str, Any]],
    *,
    primary_deployment: str | None,
    registry: tuple[dict[str, Any], dict[str, Any]],
    host: str,
    route_class: str,
    data_class: str,
    role: str | None,
    access: str | None,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        deployment_id = str(value["deployment"])
        if deployment_id == primary_deployment:
            raise RuntimeError(
                f"Project deployment '{deployment_id}' cannot fall back to itself."
            )
        if deployment_id in seen:
            raise RuntimeError(f"Duplicate fallback deployment: {deployment_id}")
        seen.add(deployment_id)
        resolved.append(
            _resolve_deployment(
                deployment_id,
                registry=registry,
                host=host,
                route_class=route_class,
                data_class=data_class,
                role=role,
                access=access,
                effort=value.get("effort"),
                options=value.get("options") or {},
            )
        )
    return resolved


def route(
    host: str,
    route_class: str,
    data_class: str,
    *,
    role: str | None = None,
    access: str | None = None,
    project: Path | None = None,
) -> dict[str, Any]:
    if route_class not in _known_route_classes():
        raise RuntimeError(f"Unknown route class: {route_class}")
    if data_class not in _known_data_classes():
        raise RuntimeError(f"Unknown data class: {data_class}")

    project_path = project_root(project)
    override = _routing_override(project_path, host, route_class, role)
    options = override.get("options") or {}
    if not isinstance(options, dict):
        raise RuntimeError("Routing override options must be a mapping.")

    registry = _deployment_registry(project_path)
    deployment_id = override.get("deployment")
    if deployment_id:
        primary = _resolve_deployment(
            str(deployment_id),
            registry=registry,
            host=host,
            route_class=route_class,
            data_class=data_class,
            role=role,
            access=access,
            effort=override.get("effort"),
            options=options,
        )
        resolution = "project-deployment"
        model = primary["model"]
        effort = primary["effort"]
        resolved_options = primary["options"]
        provider = primary["provider"]
        billing = primary["billing"]
    else:
        resolution = "project-override" if override else "host-default"
        model = override.get("model")
        effort = override.get("effort")
        resolved_options = options
        provider = None
        billing = None

    fallbacks = _resolve_fallbacks(
        list(override.get("fallbacks") or []),
        primary_deployment=str(deployment_id) if deployment_id else None,
        registry=registry,
        host=host,
        route_class=route_class,
        data_class=data_class,
        role=role,
        access=access,
    )
    result = {
        "host": host,
        "route": route_class,
        "role": role,
        "resolution": resolution,
        "deployment": str(deployment_id) if deployment_id else None,
        "provider": provider,
        "model": model,
        "effort": effort,
        "options": resolved_options,
        "fallbacks": fallbacks,
        "billing": billing,
        "data": data_class,
    }
    _append_event(
        project_path,
        {
            "event": "route-selected",
            "host": host,
            "route": route_class,
            "role": role,
            "resolution": result["resolution"],
            "deployment": result["deployment"],
            "provider": result["provider"],
            "model": result["model"],
            "effort": result["effort"],
            "fallback-count": len(fallbacks),
            "data-class": data_class,
        },
    )
    return result


def _current_branch(project: Path) -> str | None:
    try:
        result = run(
            ["git", "-C", str(project), "rev-parse", "--abbrev-ref", "HEAD"]
        )
        return result.stdout.strip()
    except Exception:
        return None


def create_dispatch(
    task: str,
    role: str,
    host: str,
    route_class: str,
    data_class: str,
    access: str,
    owned_paths: list[str],
) -> dict[str, Any]:
    project = project_root()

    if access == "write":
        if not owned_paths:
            raise RuntimeError("Writable dispatch requires at least one owned path.")

        branch = _current_branch(project)
        if branch in {"main", "master"}:
            raise RuntimeError(
                "Writable dispatch is not allowed from the stable main/master branch."
            )

    selected = route(
        host,
        route_class,
        data_class,
        role=role,
        access=access,
        project=project,
    )
    dispatch_id = uuid.uuid4().hex

    record = {
        "schema-version": 1,
        "dispatch-id": dispatch_id,
        "task": task,
        "role": role,
        "host": host,
        "route": route_class,
        "resolution": selected["resolution"],
        "deployment": selected.get("deployment"),
        "provider": selected.get("provider"),
        "model": selected["model"],
        "effort": selected.get("effort"),
        "options": selected.get("options") or {},
        "fallbacks": selected.get("fallbacks") or [],
        "data-class": data_class,
        "access": access,
        "owned-paths": owned_paths,
        "state": "planned",
        "created-utc": datetime.now(timezone.utc).isoformat(),
    }

    record = redact_value(record)
    destination = state_root(project) / "dispatch" / f"{dispatch_id}.json"
    write_json(destination, record)

    _append_event(
        project,
        {
            "event": "dispatch-planned",
            "dispatch-id": dispatch_id,
            "role": role,
            "host": host,
            "resolution": selected["resolution"],
            "deployment": selected.get("deployment"),
            "provider": selected.get("provider"),
            "model": selected["model"],
            "effort": selected.get("effort"),
            "fallback-count": len(selected.get("fallbacks") or []),
            "data-class": data_class,
            "access": access,
            "owned-path-count": len(owned_paths),
        },
    )

    return record


def start_session(
    session_id: str,
    task: str,
    role: str = "lead",
    host: str = "codex",
    model: str | None = None,
    effort: str | None = None,
    access: str = "plan",
) -> dict[str, Any]:
    project = project_root()

    record = {
        "schema-version": 1,
        "session-id": session_id,
        "task": {"id": task},
        "agent": {"role": role},
        "execution": {
            "host": host,
            "model": model,
            "effort": effort,
            "access": access,
        },
        "workspace": {"root": "."},
        "state": "active",
        "validation": "not-planned",
        "review": "not-required",
        "updated-utc": datetime.now(timezone.utc).isoformat(),
    }

    record = redact_value(record)
    write_json(state_root(project) / "session.json", record)
    _append_event(
        project,
        {
            "event": "session-started",
            "session-id": session_id,
            "role": role,
            "host": host,
            "model": model,
            "effort": effort,
            "access": access,
        },
    )
    return record


def read_session() -> dict[str, Any]:
    path = state_root(project_root()) / "session.json"
    if not path.exists():
        raise RuntimeError("No active EmbrAIon session state.")
    return read_json(path)


def update_session(
    state: str | None = None,
    validation: str | None = None,
    review: str | None = None,
) -> dict[str, Any]:
    project = project_root()
    path = state_root(project) / "session.json"

    if not path.exists():
        raise RuntimeError("No session state; start one first.")

    record = read_json(path)

    if state:
        record["state"] = state
    if validation:
        record["validation"] = validation
    if review:
        record["review"] = review

    record["updated-utc"] = datetime.now(timezone.utc).isoformat()
    write_json(path, record)

    _append_event(
        project,
        {
            "event": "session-updated",
            "session-id": record.get("session-id"),
            "state": record.get("state"),
            "validation": record.get("validation"),
            "review": record.get("review"),
        },
    )

    return record
