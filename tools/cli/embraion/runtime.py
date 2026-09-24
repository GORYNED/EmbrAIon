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


def _catalog(root: Path, host: str) -> tuple[dict[str, Any], dict[str, Any]]:
    base = root / "adapters" / host
    return read_yaml(base / "models.yaml") or {}, read_yaml(base / "routes.yaml") or {}


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


def route(
    host: str,
    route_class: str,
    data_class: str,
    *,
    project: Path | None = None,
) -> dict[str, Any]:
    root = framework_root()
    models, routes = _catalog(root, host)

    mapping = routes.get("routes", {}).get(route_class)
    if not mapping:
        raise RuntimeError(f"No route '{route_class}' for {host}")

    model_id = mapping.get("model")
    catalog = {
        str(item.get("id")): item
        for group in ("models", "options")
        for item in models.get(group, []) or []
        if item.get("id")
    }

    model = catalog.get(model_id)
    if not model:
        raise RuntimeError(f"Route selects unknown model: {model_id}")

    allowed = model.get("data")

    if data_class == "CONFIDENTIAL":
        if not allowed or data_class not in allowed:
            raise RuntimeError(
                f"{host}/{model_id} is not explicitly eligible for CONFIDENTIAL data"
            )
    elif allowed and data_class not in allowed:
        raise RuntimeError(f"{host}/{model_id} is not eligible for {data_class}")

    result = {
        "host": host,
        "route": route_class,
        "model": model_id,
        "effort": mapping.get("effort"),
        "data": data_class,
    }

    _append_event(
        project_root(project),
        {
            "event": "route-selected",
            "host": host,
            "route": route_class,
            "model": model_id,
            "effort": mapping.get("effort"),
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

    selected = route(host, route_class, data_class)
    dispatch_id = uuid.uuid4().hex

    record = {
        "schema-version": 1,
        "dispatch-id": dispatch_id,
        "task": task,
        "role": role,
        "host": host,
        "route": route_class,
        "model": selected["model"],
        "effort": selected.get("effort"),
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
