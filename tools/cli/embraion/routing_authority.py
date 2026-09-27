"""Audit manually maintained consumer files for duplicate concrete routing facts."""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Iterable

from .common import project_root, read_yaml
from .policy import read_deployments_config, read_routing_config
from .project import HOST_COMPONENTS, projection_plan


_STRUCTURED_FACT = re.compile(
    r"(?im)(?:^|[,{\s])['\"]?(?:provider|model|deployment|effort|fallbacks?|"
    r"capabilities|billing|sku|selector|credentialRef|expectedProvider|"
    r"expectedResponseModels?|taskClassAliases)['\"]?\s*[:=]\s*\S+"
)
_TEXT_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ps1", ".psm1", ".py", ".sh"}
_SKIP_DIRECTORIES = {".git", ".embraion", "__pycache__", "Library", "node_modules", ".venv", "venv", "bin", "obj"}


def _manual_files(root: Path) -> Iterable[Path]:
    for directory, child_directories, filenames in os.walk(root):
        child_directories[:] = sorted(name for name in child_directories
                                      if name not in _SKIP_DIRECTORIES)
        for name in sorted(filenames):
            yield Path(directory) / name


def _concrete_markers(project: Path) -> set[str]:
    deployments = read_deployments_config(project)
    routing = read_routing_config(project)
    markers = set(deployments["deployments"])
    markers.update(str(item["model"]) for item in deployments["deployments"].values())
    markers.update(str(item["billing"]["plan"]) for item in deployments["deployments"].values()
                   if (item.get("billing") or {}).get("plan"))
    markers.update((routing.get("candidate-groups") or {}).keys())
    for name in ("execution.yaml", "pricing.yaml"):
        path = project / ".embraion" / name
        if not path.is_file():
            continue
        data = read_yaml(path) or {}
        if name == "execution.yaml":
            for binding in (data.get("bindings") or {}).values():
                for key in ("selector", "credentialRef", "expectedProvider",
                            "expectedResponseModelPattern"):
                    if binding.get(key):
                        markers.add(str(binding[key]))
                markers.update(str(value) for value in binding.get("expectedResponseModels") or [])
        else:
            for source in (data.get("sources") or {}).values():
                for sku_id, sku in (source.get("skus") or {}).items():
                    markers.add(str(sku_id))
                    if sku.get("sku"):
                        markers.add(str(sku["sku"]))
    return {value for value in markers if len(value) >= 5}


def audit_routing_authority(project: Path | None = None, *,
                            paths: Iterable[Path] | None = None) -> list[dict[str, str]]:
    """Report duplicates; generated projections are exempt only when verified."""
    root = project_root(project)
    markers = _concrete_markers(root)
    verified: set[str] = set()
    for host in HOST_COMPONENTS:
        try:
            plan = projection_plan(host, root)
        except (RuntimeError, OSError):
            continue
        verified.update(plan.get("unchanged") or [])
    files = paths if paths is not None else _manual_files(root)
    findings: list[dict[str, str]] = []
    for path in files:
        path = Path(path)
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative.startswith((".embraion/", ".git/")) or relative in verified:
            continue
        if any(part in _SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        contents = path.read_text(encoding="utf-8", errors="ignore")
        for number, line in enumerate(contents.splitlines(), 1):
            duplicate = next((value for value in sorted(markers, key=len, reverse=True)
                              if value in line), None)
            if duplicate or _STRUCTURED_FACT.search(line):
                findings.append({"path": relative, "line": str(number),
                                 "reason": "duplicate concrete routing fact"})
    return findings
