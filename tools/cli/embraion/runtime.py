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
    task_class: str | None = None,
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
    route_role = ((host_overrides.get("route-roles") or {}).get(route_class) or {}).get(role) if role else None
    task_override = (host_overrides.get("task-classes") or {}).get(task_class) if task_class else None
    for specific in (route_role, task_override):
        if specific is None:
            continue
        if not isinstance(specific, dict):
            raise RuntimeError("Routing specific override must be a mapping.")
        if "deployment" in specific or "model" in specific:
            merged.pop("deployment", None)
            merged.pop("model", None)
            if "fallbacks" not in specific:
                merged.pop("fallbacks", None)
        merged.update(specific)
    return merged


def _routing_layers(project: Path, host: str, route_class: str,
                    role: str | None, task_class: str | None) -> list[str]:
    host_config = (read_routing_config(project).get("overrides") or {}).get(host) or {}
    layers: list[str] = []
    if route_class in (host_config.get("routes") or {}):
        layers.append("route")
    if role and role in (host_config.get("roles") or {}):
        layers.append("role")
    if role and role in ((host_config.get("route-roles") or {}).get(route_class) or {}):
        layers.append("route-role")
    if task_class and task_class in (host_config.get("task-classes") or {}):
        layers.append("task-class")
    return layers or ["host-default"]


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
    task_class: str | None,
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
    allowed_task = route_class in task_classes or (
        route_class != "critical" and task_class in task_classes
    )
    if task_classes and not allowed_task:
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
        "host": host,
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
    task_class: str | None,
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
                task_class=task_class,
                data_class=data_class,
                role=role,
                access=access,
                effort=value.get("effort"),
                options=value.get("options") or {},
            )
        )
    return resolved


def _record_route_selection(project: Path, selected: dict[str, Any], *,
                            data_class: str, role: str | None,
                            justification: str | None = None) -> None:
    event = {
        "event": "route-selected",
        "host": selected["host"],
        "route": selected["route"],
        "role": role,
        "resolution": selected["resolution"],
        "deployment": selected.get("deployment"),
        "provider": selected.get("provider"),
        "model": selected.get("model"),
        "effort": selected.get("effort"),
        "fallback-count": len(selected.get("fallbacks") or []),
        "data-class": data_class,
    }
    if selected["route"] == "critical":
        event["justification"] = justification
    _append_event(project, event)


def _resolve_route(
    host: str,
    route_class: str,
    data_class: str,
    *,
    role: str | None = None,
    access: str | None = None,
    project: Path | None = None,
    task_class: str | None = None,
) -> dict[str, Any]:
    if route_class not in _known_route_classes():
        raise RuntimeError(f"Unknown route class: {route_class}")
    if data_class not in _known_data_classes():
        raise RuntimeError(f"Unknown data class: {data_class}")

    project_path = project_root(project)
    override = _routing_override(project_path, host, route_class, role, task_class)
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
            task_class=task_class,
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
        task_class=task_class,
        data_class=data_class,
        role=role,
        access=access,
    )
    result = {
        "host": host,
        "route": route_class,
        "task-class": task_class,
        "role": role,
        "resolution": resolution,
        "provenance": _routing_layers(project_path, host, route_class, role, task_class),
        "deployment": str(deployment_id) if deployment_id else None,
        "provider": provider,
        "model": model,
        "effort": effort,
        "options": resolved_options,
        "fallbacks": fallbacks,
        "billing": billing,
        "data": data_class,
    }
    return result


def route(
    host: str,
    route_class: str,
    data_class: str,
    *,
    role: str | None = None,
    access: str | None = None,
    project: Path | None = None,
    task_class: str | None = None,
    justification: str | None = None,
) -> dict[str, Any]:
    """Resolve an explicitly selected host route and enforce critical justification."""
    if route_class == "critical" and not (justification or "").strip():
        raise RuntimeError("Critical task routing requires justification.")
    selected = _resolve_route(host, route_class, data_class, role=role, access=access,
                              project=project, task_class=task_class)
    if route_class == "critical":
        selected["justification"] = justification
    _record_route_selection(project_root(project), selected, data_class=data_class,
                            role=role, justification=justification)
    return selected


_DATA_RANK = {"PUBLIC": 0, "PRIVATE": 1, "CONFIDENTIAL": 2}
_COMPLEX_REVIEW_SEMANTICS = frozenset({"concurrency", "lifecycle", "compatibility", "architecture"})


def classify_review_assignment(*, delta_semantics: list[str] | tuple[str, ...] = (),
                               difficult: bool = False,
                               previous_route: str | None = None) -> str:
    """Classify the current bounded review; prior complexity is evidence only."""
    if previous_route is not None and previous_route not in _known_route_classes():
        raise RuntimeError(f"Unknown previous route class: {previous_route}")
    if any(not isinstance(value, str) or not value for value in delta_semantics):
        raise RuntimeError("Review delta semantics must be non-empty strings.")
    return ("complex" if difficult or _COMPLEX_REVIEW_SEMANTICS.intersection(delta_semantics)
            else "substantial")


def resolve_task_route(
    task_class: str,
    *,
    data_class: str | None = None,
    role: str | None = None,
    access: str | None = None,
    escalation: str | None = None,
    justification: str | None = None,
    project: Path | None = None,
    shape: str | None = None,
    _emit_event: bool = True,
) -> dict[str, Any]:
    """Resolve a project task class without making availability a quality decision."""
    root = project_root(project)
    config = read_routing_config(root)
    profile = (config.get("task-classes") or {}).get(task_class)
    if profile is None:
        raise RuntimeError(f"Unknown project task class: {task_class}")
    route_class = profile["route-class"]
    minimum_data = profile.get("data-class", "PRIVATE")
    selected_data = data_class or minimum_data
    if selected_data not in _DATA_RANK or _DATA_RANK[selected_data] < _DATA_RANK[minimum_data]:
        raise RuntimeError("Task data class cannot be below the project minimum.")
    selected_role = role or profile.get("role")
    registry = _deployment_registry(root)
    groups = config.get("candidate-groups") or {}

    def resolve_candidate(spec: dict[str, Any], *, source: str) -> list[dict[str, Any]]:
        host = spec["host"]
        candidate_route = spec.get("route-class", route_class)
        selected_escalation = source == f"escalation:{escalation}"
        optional_escalation = source.startswith("escalation:") and not selected_escalation
        candidate_data = minimum_data if optional_escalation else selected_data
        candidate_access = None if optional_escalation else access
        if "deployment" not in spec and ("effort" in spec or "options" in spec):
            raise RuntimeError("Candidate effort/options require an explicit deployment.")
        if "group" in spec:
            group_id = spec["group"]
            if group_id not in groups:
                raise RuntimeError(f"Unknown routing candidate group: {group_id}")
            group = groups[group_id]
            choices = list(group["deployments"])
            for preferred in (group.get("preferred") or {}).values():
                if preferred not in [item["deployment"] for item in choices]:
                    raise RuntimeError(f"Candidate group '{group_id}' has an unknown preferred deployment.")
            preferred_id = (group.get("preferred") or {}).get(shape) if shape else None
            if preferred_id:
                choices.sort(key=lambda item: 0 if item["deployment"] == preferred_id else 1)
            return [
                {
                    **_resolve_deployment(item["deployment"], registry=registry, host=host,
                                          route_class=candidate_route, task_class=task_class,
                                          data_class=candidate_data, role=selected_role, access=candidate_access,
                                          effort=item.get("effort"), options=item.get("options")),
                    "source": f"{source}:group:{group_id}", "route": candidate_route,
                    "resolution": "project-deployment",
                }
                for item in choices
            ]
        if "deployment" in spec:
            resolved = _resolve_deployment(
                spec["deployment"], registry=registry, host=host,
                route_class=candidate_route, task_class=task_class,
                data_class=candidate_data, role=selected_role, access=candidate_access,
                effort=spec.get("effort"), options=spec.get("options"),
            )
            return [{**resolved, "source": source, "route": candidate_route,
                     "resolution": "project-deployment"}]
        selected = _resolve_route(host, candidate_route, candidate_data, role=selected_role,
                                  access=candidate_access, project=root, task_class=task_class)
        primary = {key: selected.get(key) for key in ("deployment", "provider", "model", "effort", "options", "billing")}
        results = [{**primary, "host": host, "route": candidate_route,
                    "resolution": selected["resolution"],
                    "provenance": selected["provenance"],
                    "source": f"{source}:host-route"}]
        results.extend({**fallback, "route": candidate_route,
                        "resolution": "project-deployment",
                        "source": f"{source}:host-fallback"}
                       for fallback in selected["fallbacks"])
        return results

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, spec in enumerate(profile["candidates"]):
        for candidate in resolve_candidate(spec, source=f"candidate:{index}"):
            identity = candidate.get("deployment") or f"host-default:{candidate['host']}"
            if identity in seen:
                raise RuntimeError(f"Duplicate effective route candidate: {identity}")
            seen.add(identity)
            candidate["requires-handoff"] = bool(candidates and candidate["host"] != candidates[-1]["host"])
            candidate["requires-fresh-privacy-access"] = candidate["requires-handoff"]
            candidates.append(candidate)
    if not candidates:
        raise RuntimeError("Task route requires at least one candidate.")

    escalations: dict[str, dict[str, Any]] = {}
    for kind, spec in (profile.get("escalations") or {}).items():
        if kind == "critical" and spec.get("route-class") != "critical":
            raise RuntimeError("Critical escalation requires an explicit critical route class.")
        resolved = resolve_candidate(spec, source=f"escalation:{kind}")
        if len(resolved) != 1:
            raise RuntimeError("Escalation must resolve to one candidate.")
        escalations[kind] = resolved[0]
        escalations[kind]["requires-handoff"] = resolved[0]["host"] != candidates[0]["host"]
        escalations[kind]["requires-fresh-privacy-access"] = escalations[kind]["requires-handoff"]
    if escalation is not None and escalation not in escalations:
        raise RuntimeError(f"No declared {escalation} escalation for task class '{task_class}'.")
    if escalation is not None and not (justification or "").strip():
        raise RuntimeError("Explicit escalation requires justification.")
    selected = escalations[escalation] if escalation else candidates[0]
    if selected["route"] == "critical" and not (justification or "").strip():
        raise RuntimeError("Critical task routing requires justification.")
    if selected["route"] == "critical":
        selected["justification"] = justification
    if _emit_event:
        _record_route_selection(root, {**selected,
                                       "fallbacks": candidates[1:] if escalation is None else []},
                                data_class=selected_data, role=selected_role,
                                justification=justification)
    return {
        "task-class": task_class,
        "route": route_class,
        "role": selected_role,
        "data": selected_data,
        "candidates": candidates,
        "selected": selected,
        "fallbacks": candidates[1:] if escalation is None else [],
        "escalations": escalations,
        "selection-reason": escalation or "initial",
        "shape": shape,
        "group-preferences": {name: group.get("preferred") or {} for name, group in groups.items()},
        "justification": justification if escalation or selected["route"] == "critical" else None,
    }


def validate_task_routes(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    config = read_routing_config(root)
    registry = _deployment_registry(root)[1]
    classes = config.get("task-classes") or {}

    def validate_selection(selection: dict[str, Any], *, location: str,
                           host: str | None = None,
                           route_class: str | None = None,
                           role: str | None = None,
                           task_class: str | None = None) -> None:
        primary = selection.get("deployment")
        seen: set[str] = set()
        referenced: list[tuple[str, dict[str, Any]]] = []
        for item in ([selection] if primary else []) + list(selection.get("fallbacks") or []):
            deployment_id = item["deployment"]
            if deployment_id in seen:
                raise RuntimeError(f"{location}: duplicate deployment '{deployment_id}'.")
            seen.add(deployment_id)
            deployment = registry.get(deployment_id)
            if deployment is None:
                raise RuntimeError(f"{location}: unknown project deployment '{deployment_id}'.")
            if deployment.get("enabled", True) is not True:
                raise RuntimeError(f"{location}: project deployment '{deployment_id}' is disabled.")
            if host is not None and deployment["host"] != host:
                raise RuntimeError(
                    f"{location}: project deployment '{deployment_id}' belongs to host "
                    f"'{deployment['host']}', not '{host}'."
                )
            effort = item.get("effort") or deployment.get("default-effort")
            supported = set(deployment.get("efforts") or [])
            if effort and supported and effort not in supported:
                raise RuntimeError(
                    f"{location}: project deployment '{deployment_id}' does not support "
                    f"effort '{effort}'."
                )
            if not isinstance(item.get("options") or {}, dict):
                raise RuntimeError(f"{location}: options must be a mapping.")
            referenced.append((deployment_id, deployment))

        for deployment_id, deployment in referenced:
            capabilities = deployment.get("capabilities") or {}
            allowed_routes = set(capabilities.get("task-classes") or [])
            if route_class and allowed_routes and not (
                route_class in allowed_routes or
                (route_class != "critical" and task_class in allowed_routes)
            ):
                raise RuntimeError(
                    f"{location}: project deployment '{deployment_id}' does not allow "
                    f"route class '{route_class}'."
                )
            allowed_roles = set(capabilities.get("roles") or [])
            if role and allowed_roles and role not in allowed_roles:
                raise RuntimeError(
                    f"{location}: project deployment '{deployment_id}' does not allow role '{role}'."
                )

    for group_id, group in (config.get("candidate-groups") or {}).items():
        ids = [item["deployment"] for item in group["deployments"]]
        if len(ids) != len(set(ids)) or any(item not in registry for item in ids):
            raise RuntimeError(f"Candidate group '{group_id}' contains duplicate or unknown deployments.")
        if any(value not in ids for value in (group.get("preferred") or {}).values()):
            raise RuntimeError(f"Candidate group '{group_id}' has an unknown preferred deployment.")
        for index, item in enumerate(group["deployments"]):
            validate_selection(item, location=f"candidate-groups.{group_id}.deployments.{index}")
        hosts = {registry[deployment_id]["host"] for deployment_id in ids}
        if len(hosts) != 1:
            raise RuntimeError(f"Candidate group '{group_id}' mixes deployment hosts.")

    checked_overrides: list[str] = []
    known_routes = _known_route_classes()
    for host, overrides in (config.get("overrides") or {}).items():
        for route_class, selection in (overrides.get("routes") or {}).items():
            location = f"overrides.{host}.routes.{route_class}"
            if route_class not in known_routes:
                raise RuntimeError(f"{location}: unknown route class '{route_class}'.")
            validate_selection(selection, location=location, host=host, route_class=route_class)
            checked_overrides.append(location)
        for role, selection in (overrides.get("roles") or {}).items():
            location = f"overrides.{host}.roles.{role}"
            validate_selection(selection, location=location, host=host, role=role)
            checked_overrides.append(location)
        for route_class, roles in (overrides.get("route-roles") or {}).items():
            if route_class not in known_routes:
                raise RuntimeError(
                    f"overrides.{host}.route-roles.{route_class}: unknown route class '{route_class}'."
                )
            for role, selection in roles.items():
                location = f"overrides.{host}.route-roles.{route_class}.{role}"
                validate_selection(selection, location=location, host=host,
                                   route_class=route_class, role=role)
                checked_overrides.append(location)
        for task_class, selection in (overrides.get("task-classes") or {}).items():
            location = f"overrides.{host}.task-classes.{task_class}"
            if task_class not in classes:
                raise RuntimeError(f"{location}: unknown project task class '{task_class}'.")
            profile = classes[task_class]
            validate_selection(selection, location=location, host=host,
                               route_class=profile["route-class"], role=profile.get("role"),
                               task_class=task_class)
            checked_overrides.append(location)

    for task_class, profile in classes.items():
        resolved = resolve_task_route(task_class, project=root, justification="configuration validation",
                                      _emit_event=False)
        if not resolved["candidates"]:
            raise RuntimeError(f"Task class '{task_class}' has no candidates.")
    return {"valid": True, "task-classes": sorted(classes),
            "candidate-groups": sorted(config.get("candidate-groups") or {}),
            "override-selections": sorted(checked_overrides),
            "override-selection-count": len(checked_overrides)}


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
    role: str | None,
    host: str | None,
    route_class: str | None,
    data_class: str | None,
    access: str,
    owned_paths: list[str],
    *,
    native_surface: str | None = None,
    native_agent: str | None = None,
    task_class: str | None = None,
    justification: str | None = None,
    project: Path | None = None,
    verified_native_fields: list[str] | None = None,
) -> dict[str, Any]:
    project = project_root(project)

    if native_agent and not native_surface:
        raise RuntimeError("A native-agent binding requires a native-surface.")

    if _normalized_access_mode(access) == "workspace-write":
        if not owned_paths:
            raise RuntimeError("Writable dispatch requires at least one owned path.")

        branch = _current_branch(project)
        if branch in {"main", "master"}:
            raise RuntimeError(
                "Writable dispatch is not allowed from the stable main/master branch."
            )

    if task_class:
        if host or route_class:
            raise RuntimeError("Dispatch --task-class cannot be combined with --host or --route-class.")
        profile = (read_routing_config(project).get("task-classes") or {}).get(task_class) or {}
        role = role or profile.get("role") or "worker"
        effective = resolve_task_route(task_class, role=role, data_class=data_class,
                                       access=access, project=project,
                                       justification=justification)
        selected = {**effective["selected"], "fallbacks": effective["fallbacks"]}
        data_class = effective["data"]
        host = selected["host"]
        route_class = selected["route"]
    else:
        if not host or not route_class:
            raise RuntimeError("Dispatch requires --host and --route-class, or --task-class.")
        role = role or "worker"
        data_class = data_class or "PRIVATE"
        selected = route(host, route_class, data_class, role=role,
                         access=access, project=project,
                         justification=justification)
    dispatch_id = uuid.uuid4().hex

    record = {
        "schema-version": 1,
        "dispatch-id": dispatch_id,
        "task": task,
        "role": role,
        "host": host,
        "route": route_class,
        "resolution": selected["resolution"],
        "provenance": selected.get("provenance") or [selected.get("source", "project-deployment")],
        "task-class": task_class,
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
    if route_class == "critical":
        record["justification"] = justification

    if native_surface:
        from .delegation import prepare_native_assignment
        record["native-plan"] = prepare_native_assignment(
            selected, native_surface, role=role, native_agent=native_agent,
            project=project, access=access,
            verified_native_fields=verified_native_fields,
        )
        if record["native-plan"]["status"] == "capability-limitation":
            record["state"] = "blocked"
        elif record["native-plan"]["status"] == "handoff-required":
            record["state"] = "handoff-required"

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
