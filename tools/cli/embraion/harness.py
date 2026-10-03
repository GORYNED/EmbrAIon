"""Read-only inspection of installed host projection surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import framework_root, project_root, read_yaml
from .project import load_agents


_AGENT_SUFFIX = {
    "codex": ".toml",
    "copilot": ".agent.md",
    "claude-code": ".md",
}
_ACTIVATION = {
    "codex": ".codex/config.toml",
    "claude-code": ".claude/rules/embraion.md",
}


def audit_harness(
    host: str = "all",
    project: Path | None = None,
) -> dict[str, Any]:
    """Report installation evidence; live host loading and execution are out of scope."""
    root = project_root(project)
    data = read_yaml(framework_root() / "adapters" / "harness-capabilities.yaml") or {}
    hosts = data.get("hosts") or {}

    selected = sorted(hosts) if host == "all" else [host]
    rows: list[dict[str, Any]] = []
    agent_config = ".embraion/agents.yaml"
    project_config_present = (root / agent_config).is_file()
    agents = load_agents(framework_root(), root if project_config_present else None)

    for current in selected:
        if current not in hosts:
            raise RuntimeError(f"Unknown host for harness audit: {current}")

        config = hosts[current]
        agent_relative = str(config["agents"])
        skill_relative = str(config["skills"])
        agent_path = root / agent_relative
        skill_path = root / skill_relative
        suffix = _AGENT_SUFFIX[current]
        expected_agents = [
            f"{agent_relative}/{agent['id']}{suffix}"
            for agent in agents
            if agent["id"] != "lead"
        ]
        # The orchestration entry point is the minimum shared skill needed to
        # recognize an EmbrAIon projection. Unrelated skills cannot satisfy it.
        expected_skills = [f"{skill_relative}/orchestration/SKILL.md"]
        missing_agents = [path for path in expected_agents if not (root / path).is_file()]
        missing_skills = [path for path in expected_skills if not (root / path).is_file()]
        activation_path = _ACTIVATION.get(current)
        missing_activation = (
            [activation_path]
            if activation_path and not (root / activation_path).is_file()
            else []
        )
        missing = ([] if project_config_present else [agent_config]) + missing_agents + missing_skills + missing_activation

        hooks = config.get("hooks") or {}
        hook_location = hooks.get("location")
        hook_present = (root / str(hook_location)).exists() if hook_location else False
        enforcement_path = root / ".github" / "workflows" / "embraion-enforcement.yml"

        rows.append(
            {
                "host": current,
                "stage": "installation",
                "ready-scope": "projected-file-presence",
                "agents": {
                    "path": agent_relative,
                    "present": agent_path.is_dir() and not missing_agents,
                    "expected": expected_agents,
                    "missing": missing_agents,
                },
                "skills": {
                    "path": skill_relative,
                    "present": skill_path.is_dir() and not missing_skills,
                    "expected": expected_skills,
                    "missing": missing_skills,
                },
                "activation": {
                    "path": activation_path,
                    "present": not missing_activation if activation_path else None,
                    "missing": missing_activation,
                },
                "hooks": {
                    "mode": hooks.get("mode", "unknown"),
                    "location": hook_location,
                    "projected": bool(hooks.get("projected", False)),
                    "present": hook_present,
                },
                "enforcement": {
                    "github-actions": {
                        "path": ".github/workflows/embraion-enforcement.yml",
                        "present": enforcement_path.is_file(),
                        "explicit-opt-in": True,
                    },
                    "native-hooks-projected": False,
                },
                "missing": missing,
                "content-verified": False,
                "instructions-loaded": "unverified",
                "runtime-settings": "unverified",
                "execution": "unverified",
                "ready": not missing,
            }
        )

    return {
        "schema-version": 1,
        "project": str(root),
        "hosts": rows,
    }
