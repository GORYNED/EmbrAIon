"""Check that project routing configuration stays within declared policy ceilings.

Ceilings are a project declaration in `.embraion/policy.yaml`. Deployments,
execution bindings, and task classes may narrow them, never widen them. An
unlisted capability dimension on a ceilinged deployment counts as unrestricted
and therefore as a widening.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .common import project_root
from .policy import read_deployments_config, read_policy_config, read_routing_config


_CAPABILITY_DIMENSIONS = ("data-classes", "access-modes", "roles")


def read_ceilings(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    if not (root / ".embraion" / "policy.yaml").is_file():
        return {}
    return read_policy_config(root).get("ceilings") or {}


def _finding(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _task_class_deployments(
    profile: dict[str, Any],
    groups: dict[str, Any],
) -> Iterable[str]:
    candidates = list(profile.get("candidates") or [])
    candidates += list((profile.get("escalations") or {}).values())
    for candidate in candidates:
        if candidate.get("deployment"):
            yield candidate["deployment"]
        group = groups.get(candidate.get("group") or "")
        for item in (group or {}).get("deployments") or []:
            yield item["deployment"]


def check_policy_ceilings(project: Path | None = None) -> list[dict[str, str]]:
    """Return every place where routing configuration exceeds a declared ceiling."""
    root = project_root(project)
    ceilings = read_ceilings(root)
    if not ceilings:
        return []

    from .execution import read_execution_config

    policy = read_policy_config(root)
    default_data_class = (policy.get("privacy") or {}).get("default-class", "PRIVATE")
    deployments = read_deployments_config(root).get("deployments") or {}
    routing = read_routing_config(root)
    task_classes = routing.get("task-classes") or {}
    groups = routing.get("candidate-groups") or {}
    bindings = read_execution_config(root).get("bindings") or {}
    findings: list[dict[str, str]] = []

    enabled = {
        name: definition
        for name, definition in deployments.items()
        if (definition or {}).get("enabled", True) is True
    }

    def within(ceiling: dict[str, Any], dimension: str, values: Iterable[str]) -> bool:
        return dimension not in ceiling or set(values) <= set(ceiling[dimension])

    def check_task_class(ceiling: dict[str, Any], name: str, location: str, provider: str) -> None:
        profile = task_classes.get(name)
        if profile is None:
            # Route-class or alias names cannot be traced to a role and data class.
            if "data-classes" in ceiling or "roles" in ceiling:
                findings.append(_finding(
                    "ceiling-unbounded", location,
                    f"'{name}' is not a routing task class, so the {provider} role and data-class "
                    "ceilings cannot be checked; list routing task classes.",
                ))
            return
        data_class = profile.get("data-class") or default_data_class
        if not within(ceiling, "data-classes", [data_class]):
            findings.append(_finding(
                "ceiling-data-class", location,
                f"Task class '{name}' uses data class {data_class}, above the {provider} ceiling.",
            ))
        if "roles" in ceiling and profile.get("role") not in ceiling["roles"]:
            findings.append(_finding(
                "ceiling-role", location,
                f"Task class '{name}' uses role '{profile.get('role')}', outside the {provider} ceiling.",
            ))

    provider_ceilings = ceilings.get("providers") or {}
    for name, definition in sorted(enabled.items()):
        provider = definition.get("provider")
        ceiling = provider_ceilings.get(provider or "")
        if provider is None and provider_ceilings:
            findings.append(_finding(
                "ceiling-provider-missing", f"deployments.{name}",
                "Enabled deployment declares no provider, so provider ceilings cannot apply.",
            ))
        if ceiling is None:
            continue
        location = f"deployments.{name}"
        capabilities = definition.get("capabilities") or {}
        for dimension in _CAPABILITY_DIMENSIONS:
            if dimension not in ceiling:
                continue
            values = capabilities.get(dimension)
            if not values:
                findings.append(_finding(
                    "ceiling-unbounded", f"{location}.capabilities.{dimension}",
                    f"Deployment does not restrict {dimension}; the {provider} ceiling allows only "
                    f"{', '.join(ceiling[dimension])}.",
                ))
            elif not within(ceiling, dimension, values):
                extra = sorted(set(values) - set(ceiling[dimension]))
                findings.append(_finding(
                    "ceiling-exceeded", f"{location}.capabilities.{dimension}",
                    f"Deployment allows {', '.join(extra)}, above the {provider} ceiling.",
                ))

        binding = bindings.get(name)
        billing = (definition.get("billing") or {}).get("mode")
        if binding is None:
            if billing and billing in (ceiling.get("binding-required-billing-modes") or []):
                findings.append(_finding(
                    "ceiling-binding-missing", location,
                    f"{provider} deployments billed as '{billing}' require an execution binding.",
                ))
        else:
            binding_location = f"execution.bindings.{name}"
            if not within(ceiling, "sources", binding.get("sourceIds") or []):
                extra = sorted(set(binding.get("sourceIds") or []) - set(ceiling["sources"]))
                findings.append(_finding(
                    "ceiling-source", f"{binding_location}.sourceIds",
                    f"Binding may receive {', '.join(extra)}, outside the {provider} source ceiling.",
                ))
            if "data-classes" in ceiling or "roles" in ceiling:
                permitted = binding.get("taskClasses")
                if not permitted:
                    findings.append(_finding(
                        "ceiling-unbounded", f"{binding_location}.taskClasses",
                        "Binding does not restrict task classes under a provider ceiling.",
                    ))
                for task_class in permitted or []:
                    check_task_class(ceiling, task_class, f"{binding_location}.taskClasses", provider)

    # Routing references can only select deployments, so a ceilinged
    # deployment must not be named by a task class above that ceiling.
    for task_class, profile in sorted(task_classes.items()):
        for deployment in sorted(set(_task_class_deployments(profile, groups))):
            definition = enabled.get(deployment) or {}
            ceiling = provider_ceilings.get(definition.get("provider") or "")
            if ceiling is not None:
                check_task_class(ceiling, task_class, f"routing.task-classes.{task_class}",
                                 str(definition.get("provider")))
    def selected(selection: dict[str, Any]) -> Iterable[tuple[str, str, dict[str, Any]]]:
        for item in [selection, *(selection.get("fallbacks") or [])]:
            definition = enabled.get(item.get("deployment") or "") or {}
            ceiling = provider_ceilings.get(definition.get("provider") or "")
            if ceiling is not None:
                yield item["deployment"], str(definition.get("provider")), ceiling

    def check_role(ceiling: dict[str, Any], role: str, deployment: str, provider: str, location: str) -> None:
        if "roles" in ceiling and role not in ceiling["roles"]:
            findings.append(_finding(
                "ceiling-role", location,
                f"Role '{role}' selects '{deployment}', outside the {provider} ceiling.",
            ))

    # Host overrides select deployments for every request that matches their key,
    # so each key is checked against the ceiling dimensions it cannot narrow.
    for host, overrides in sorted((routing.get("overrides") or {}).items()):
        base = f"routing.overrides.{host}"
        for route, selection in sorted((overrides.get("routes") or {}).items()):
            for deployment, provider, ceiling in selected(selection):
                bounded = [dimension for dimension in ("roles", "data-classes") if dimension in ceiling]
                if bounded:
                    findings.append(_finding(
                        "ceiling-unbounded", f"{base}.routes.{route}",
                        f"Route class '{route}' selects '{deployment}' for every role and data class, "
                        f"but the {provider} ceiling limits {' and '.join(bounded)}; "
                        "use a role, route-role, or task-class override.",
                    ))
        for role, selection in sorted((overrides.get("roles") or {}).items()):
            for deployment, provider, ceiling in selected(selection):
                check_role(ceiling, role, deployment, provider, f"{base}.roles.{role}")
        for route, roles in sorted((overrides.get("route-roles") or {}).items()):
            for role, selection in sorted((roles or {}).items()):
                for deployment, provider, ceiling in selected(selection):
                    check_role(ceiling, role, deployment, provider, f"{base}.route-roles.{route}.{role}")
        for task_class, selection in sorted((overrides.get("task-classes") or {}).items()):
            for _deployment, provider, ceiling in selected(selection):
                check_task_class(ceiling, task_class, f"{base}.task-classes.{task_class}", provider)

    for data_class, rule in sorted((ceilings.get("data-classes") or {}).items()):
        allowed = set(rule.get("providers") or [])
        for name, definition in sorted(enabled.items()):
            values = (definition.get("capabilities") or {}).get("data-classes")
            if (not values or data_class in values) and definition.get("provider") not in allowed:
                findings.append(_finding(
                    "ceiling-data-class-provider", f"deployments.{name}",
                    f"{data_class} is limited to providers {', '.join(sorted(allowed))}; "
                    f"deployment provider is '{definition.get('provider') or 'unspecified'}'"
                    + ("" if values else " and its data classes are unrestricted") + ".",
                ))

    for source, rule in sorted((ceilings.get("sources") or {}).items()):
        allowed = set(rule.get("providers") or [])
        for name, binding in sorted(bindings.items()):
            if source not in (binding.get("sourceIds") or []):
                continue
            provider = (deployments.get(name) or {}).get("provider")
            if provider not in allowed:
                findings.append(_finding(
                    "ceiling-source-provider", f"execution.bindings.{name}.sourceIds",
                    f"Source '{source}' is limited to providers {', '.join(sorted(allowed))}; "
                    f"binding provider is '{provider or 'unspecified'}'.",
                ))

    for task_class, expected in sorted((ceilings.get("task-classes") or {}).items()):
        profile = task_classes.get(task_class)
        location = f"routing.task-classes.{task_class}"
        if profile is None:
            findings.append(_finding("ceiling-task-class", location, "Pinned task class is missing."))
            continue
        actual = {
            "route-class": profile.get("route-class"),
            "role": profile.get("role"),
            "data-class": profile.get("data-class") or default_data_class,
        }
        for key, value in expected.items():
            if actual[key] != value:
                findings.append(_finding(
                    "ceiling-task-class", f"{location}.{key}",
                    f"Expected {key} '{value}', found '{actual[key]}'.",
                ))
    return findings


def critical_justifications(project: Path | None = None) -> list[str] | None:
    critical = read_ceilings(project).get("critical") or {}
    values = critical.get("justifications")
    return list(values) if values else None


def enforce_critical_justification(justification: str | None, project: Path | None = None) -> None:
    """Require a closed reason when the project declares one: `<reason>` or `<reason>: details`."""
    allowed = critical_justifications(project)
    if allowed is None:
        return
    reason = (justification or "").split(":", 1)[0].strip()
    if reason not in allowed:
        raise RuntimeError(
            "Critical task routing requires one of the project's justifications: "
            + ", ".join(allowed) + " (optionally followed by ': details')."
        )
