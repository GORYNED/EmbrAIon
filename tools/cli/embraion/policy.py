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
}


def read_project_overlay(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    manifest = root / ".embraion" / "project.yaml"
    if not manifest.is_file():
        raise RuntimeError(f"Missing {manifest}; run 'embraion init' first.")
    return read_yaml(manifest) or {}


def effective_policy(project: Path | None = None) -> dict[str, Any]:
    data = read_project_overlay(project)

    sources = DEFAULT_POLICY["sources"] | (data.get("sources") or {})
    default_profiles = DEFAULT_POLICY["validation"]["profiles"]
    validation = data.get("validation") or {}
    profiles = default_profiles | (validation.get("profiles") or {})

    return {
        "sources": sources,
        "validation": {"profiles": profiles},
        "review": DEFAULT_POLICY["review"] | (data.get("review") or {}),
        "privacy": DEFAULT_POLICY["privacy"] | (data.get("privacy") or {}),
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
