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
from .policy import read_project_overlay


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
    try:
        overlay = read_project_overlay(project)
    except RuntimeError:
        return {}

    routing = overlay.get("routing") or {}
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

    return {**route_override, **role_override}


def route(
    host: str,
    route_class: str,
    data_class: str,
    *,
    role: str | None = None,
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

    result = {
        "host": host,
        "route": route_class,
        "role": role,
        "resolution": "project-override" if override else "host-default",
        "model": override.get("model"),
        "effort": override.get("effort"),
        "options": options,
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
            "model": result["model"],
            "effort": result["effort"],
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
        "model": selected["model"],
        "effort": selected.get("effort"),
        "options": selected.get("options") or {},
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
            "model": selected["model"],
            "effort": selected.get("effort"),
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
