from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root, read_json, run, state_root, write_json
from .context import read_context
from .policy import effective_policy, path_matches
from .runtime import _append_event, route
from .security import redact_value


def _git_value(project: Path, *args: str) -> str | None:
    result = run(["git", "-C", str(project), *args], check=False)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _run_path(project: Path, run_id: str) -> Path:
    return state_root(project) / "runs" / f"{run_id}.json"


def start_run(
    run_id: str,
    task: str,
    role: str,
    host: str,
    route_class: str,
    data_class: str,
    access: str,
    owned_paths: list[str],
    *,
    context_id: str | None = None,
    substantial: bool = False,
    project: Path | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    if access == "write" and not owned_paths:
        raise RuntimeError("Writable run requires at least one owned path.")

    branch = _git_value(root, "rev-parse", "--abbrev-ref", "HEAD")
    if access == "write" and branch in {"main", "master"}:
        raise RuntimeError("Writable run is not allowed from stable main/master.")

    if context_id:
        read_context(context_id, root)

    selected = route(
        host,
        route_class,
        data_class,
        role=role,
        project=root,
    )
    now = datetime.now(timezone.utc).isoformat()
    record = redact_value(
        {
            "schema-version": 1,
            "run-id": run_id,
            "task": task,
            "role": role,
            "route": {
                "host": host,
                "class": route_class,
                "resolution": selected["resolution"],
                "model": selected["model"],
                "effort": selected.get("effort"),
                "options": selected.get("options") or {},
                "data-class": data_class,
            },
            "access": access,
            "owned-paths": owned_paths,
            "context-id": context_id,
            "substantial": substantial,
            "workspace": {
                "root": ".",
                "branch": branch,
                "head": _git_value(root, "rev-parse", "HEAD"),
            },
            "changed-paths": [],
            "validation": [],
            "review": "not-required",
            "outcome": None,
            "residual-risks": [],
            "state": "active",
            "started-utc": now,
            "updated-utc": now,
        }
    )
    write_json(_run_path(root, run_id), record)
    _append_event(
        root,
        {
            "event": "run-started",
            "run-id": run_id,
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


def read_run(run_id: str, project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = _run_path(root, run_id)
    if not path.is_file():
        raise RuntimeError(f"Unknown run: {run_id}")
    return read_json(path)


def complete_run(
    run_id: str,
    *,
    changed_paths: list[str],
    validation: list[dict[str, str]],
    review: str,
    outcome: str,
    residual_risks: list[str],
    project: Path | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    record = read_run(run_id, root)
    normalized = [path.replace("\\", "/").lstrip("./") for path in changed_paths]

    if record.get("access") == "write":
        owned = list(record.get("owned-paths") or [])
        outside = [path for path in normalized if not path_matches(path, owned)]
        if outside:
            raise RuntimeError(
                "Changed paths exceed owned scope: " + ", ".join(outside)
            )

    policy = effective_policy(root)
    protected = list(policy["sources"].get("protected") or [])
    protected_changes = [path for path in normalized if path_matches(path, protected)]
    if protected_changes:
        raise RuntimeError(
            "Changed paths intersect protected project sources: "
            + ", ".join(protected_changes)
        )

    if (
        outcome == "completed"
        and record.get("substantial")
        and policy["review"].get("substantial-required", True)
        and review != "passed"
    ):
        raise RuntimeError(
            "Substantial completed runs require a passed independent review."
        )

    record["changed-paths"] = normalized
    record["validation"] = validation
    record["review"] = review
    record["outcome"] = outcome
    record["residual-risks"] = residual_risks
    record["state"] = {
        "completed": "completed",
        "blocked": "blocked",
        "failed": "failed",
        "cancelled": "cancelled",
    }[outcome]
    record["updated-utc"] = datetime.now(timezone.utc).isoformat()
    record = redact_value(record)

    write_json(_run_path(root, run_id), record)
    _append_event(
        root,
        {
            "event": "run-completed",
            "run-id": run_id,
            "state": record["state"],
            "review": review,
            "changed-path-count": len(normalized),
            "validation-count": len(validation),
        },
    )
    return record
