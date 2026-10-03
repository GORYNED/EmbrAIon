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
    prepared: list[tuple[str, list[int], list[str]]] = []
    for pattern in patterns:
        canonical = pattern.replace("\\", "/")
        if len(canonical) > 4096:
            raise RuntimeError("Policy path pattern exceeds the supported length.")
        segments = canonical.split("/")
        optional = [index for index, segment in enumerate(segments[:-1]) if segment == "**"]
        if len(optional) > 8:
            raise RuntimeError("Policy path pattern has too many recursive segments.")
        prepared.append((canonical, optional, segments))

    for canonical, optional, segments in prepared:
        # Preserve every match the original fnmatchcase semantics allowed,
        # including '*' crossing a slash.
        if fnmatchcase(normalized, canonical):
            return True
        # Whole-segment '**/' also matches zero directory levels. At most eight
        # such segments produce 255 additional bounded variants.
        for mask in range(1, 1 << len(optional)):
            omitted = {optional[bit] for bit in range(len(optional)) if mask & (1 << bit)}
            variant = "/".join(segment for index, segment in enumerate(segments)
                               if index not in omitted)
            if fnmatchcase(normalized, variant):
                return True
    return False


def classify_path(path: str, project: Path | None = None) -> list[str]:
    policy = effective_policy(project)
    return [
        category
        for category, patterns in policy["sources"].items()
        if path_matches(path, list(patterns or []))
    ]
