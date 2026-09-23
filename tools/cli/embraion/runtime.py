from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import (
    framework_root,
    project_root,
    read_json,
    read_yaml,
    state_root,
    write_json,
)


def _catalog(root: Path, host: str) -> tuple[dict[str, Any], dict[str, Any]]:
    base = root / "adapters" / host
    return read_yaml(base / "models.yaml") or {}, read_yaml(base / "routes.yaml") or {}


def route(host: str, route_class: str, data_class: str) -> dict[str, Any]:
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

    return {
        "host": host,
        "route": route_class,
        "model": model_id,
        "effort": mapping.get("effort"),
        "data": data_class,
    }


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

    write_json(state_root(project) / "session.json", record)
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
    path = state_root(project_root()) / "session.json"

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
    return record
