from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .common import framework_root, project_root, read_json, read_yaml


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
    "enforcement": {
        "enabled": False,
        "validation-profile": "affected",
        "require-review": False,
    },
    "routing": {"overrides": {}},
}


def normalize_project_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _validated_config_mapping(
    path: Path,
    *,
    schema_name: str,
    label: str,
) -> dict[str, Any]:
    data = read_yaml(path)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid {label}: expected a mapping.")

    schema = read_json(framework_root() / "schemas" / schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(data),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        formatted: list[str] = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            formatted.append(f"{location}: {error.message}")
        raise RuntimeError(f"Invalid {label}: " + "; ".join(formatted))

    return data


def read_project_overlay(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    manifest = root / ".embraion" / "project.yaml"
    if not manifest.is_file():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")
    return _validated_config_mapping(
        manifest,
        schema_name="project.schema.json",
        label=".embraion/project.yaml",
    )


def read_routing_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "routing.yaml"
    if not path.is_file():
        return {"overrides": {}}
    return _validated_config_mapping(
        path,
        schema_name="routing.schema.json",
        label=".embraion/routing.yaml",
    )


def read_deployments_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "deployments.yaml"
    if not path.is_file():
        return {"providers": {}, "deployments": {}}
    return _validated_config_mapping(
        path,
        schema_name="deployments.schema.json",
        label=".embraion/deployments.yaml",
    )


def read_knowledge_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "knowledge.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="knowledge.schema.json",
        label=".embraion/knowledge.yaml",
    )


def read_validation_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "validation.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="validation.schema.json",
        label=".embraion/validation.yaml",
    )


def read_agents_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "agents.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="agents.schema.json",
        label=".embraion/agents.yaml",
    )


def read_policy_config(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    path = root / ".embraion" / "policy.yaml"
    if not path.is_file():
        raise RuntimeError(f"Missing {path}; run 'embraion init' first.")
    return _validated_config_mapping(
        path,
        schema_name="policy.schema.json",
        label=".embraion/policy.yaml",
    )


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
        "enforcement": (
            DEFAULT_POLICY["enforcement"]
            | (project_policy.get("enforcement") or {})
        ),
        "routing": DEFAULT_POLICY["routing"] | routing,
    }


def path_matches(path: str, patterns: list[str]) -> bool:
    normalized = normalize_project_path(path)
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
