from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .common import project_root, read_yaml


DEFAULT_POLICY: dict[str, Any] = {
    "sources": {
        "canonical": [],
        "protected": [],
        "generated": [],
        "external": [],
    },
    "validation": {
        "profiles": {
            "fast": [],
            "affected": [],
            "full": [],
        }
    },
    "review": {"substantial-required": True},
    "privacy": {"default-class": "PRIVATE"},
    "routing": {"overrides": {}},
}


def read_project_overlay(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    manifest = root / ".embraion" / "project.yaml"
    if not manifest.is_file():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")
    return read_yaml(manifest) or {}


def read_routing_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "routing.yaml"
    if not path.is_file():
        return {"overrides": {}}

    data = read_yaml(path) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid routing configuration: {path}")
    return data


def read_knowledge_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "knowledge.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")

    data = read_yaml(path) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid project knowledge configuration: {path}")
    return data


def read_validation_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "validation.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")

    data = read_yaml(path) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid project validation configuration: {path}")
    return data


def read_agents_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "agents.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")

    data = read_yaml(path) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid project agents configuration: {path}")
    return data


def read_policy_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "policy.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")

    data = read_yaml(path) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid project policy configuration: {path}")
    return data


def effective_policy(project: Path | None = None) -> dict[str, Any]:
    read_project_overlay(project)
    project_policy = read_policy_config(project)
    routing = read_routing_config(project)
    validation = read_validation_config(project)

    sources = DEFAULT_POLICY["sources"] | (project_policy.get("sources") or {})
    default_profiles = DEFAULT_POLICY["validation"]["profiles"]
    profiles = default_profiles | (validation.get("profiles") or {})

    return {
        "sources": sources,
        "validation": {"profiles": profiles},
        "review": DEFAULT_POLICY["review"] | (project_policy.get("review") or {}),
        "privacy": DEFAULT_POLICY["privacy"] | (project_policy.get("privacy") or {}),
        "routing": DEFAULT_POLICY["routing"] | routing,
    }


def path_matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return any(
        fnmatchcase(normalized, pattern.replace("\\", "/"))
        for pattern in patterns
    )


def classify_path(path: str, project: Path | None = None) -> list[str]:
    policy = effective_policy(project)
    return [
        category
        for category, patterns in policy["sources"].items()
        if path_matches(path, list(patterns or []))
    ]
