from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import framework_root, project_root, read_yaml


def audit_harness(
    host: str = "all",
    project: Path | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    data = read_yaml(framework_root() / "adapters" / "harness-capabilities.yaml") or {}
    hosts = data.get("hosts") or {}

    selected = sorted(hosts) if host == "all" else [host]
    rows: list[dict[str, Any]] = []

    for current in selected:
        if current not in hosts:
            raise RuntimeError(f"Unknown host for harness audit: {current}")

        config = hosts[current]
        agent_path = root / str(config["agents"])
        skill_path = root / str(config["skills"])
        hooks = config.get("hooks") or {}
        hook_location = hooks.get("location")
        hook_present = (
            (root / str(hook_location)).exists()
            if hook_location
            else False
        )
        skills_present = skill_path.is_dir() and any(skill_path.glob("*/SKILL.md"))

        rows.append(
            {
                "host": current,
                "agents": {
                    "path": str(config["agents"]),
                    "present": agent_path.is_dir(),
                },
                "skills": {
                    "path": str(config["skills"]),
                    "present": skills_present,
                },
                "hooks": {
                    "mode": hooks.get("mode", "unknown"),
                    "location": hook_location,
                    "projected": bool(hooks.get("projected", False)),
                    "present": hook_present,
                },
                "ready": agent_path.is_dir() and skills_present,
            }
        )

    return {
        "schema-version": 1,
        "project": str(root),
        "hosts": rows,
    }
