"""Optional project source registry and its machine-local availability map.

`.embraion/sources.yaml` is committed and says, per stable source ID, its role, write policy,
documentation, and an optional raised data class. `.embraion/state/sources-local.yaml` is ignored
local state that maps a source ID to an absolute path on this machine. Paths from the local file
are never printed; reports name the ID and `available`, `missing`, or `unset` only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .common import atomic_write_bytes, framework_root, read_json, read_yaml
from .policy import DATA_CLASS_ORDER

SOURCES_CONFIG = Path(".embraion") / "sources.yaml"
LOCAL_SOURCES = Path(".embraion") / "state" / "sources-local.yaml"
WRITABLE = "workspace-write"


def _location(error: Any) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def _load_mapping(path: Path, label: str) -> Any:
    if path.is_symlink():
        raise RuntimeError(f"Invalid {label}: must not be a symbolic link.")
    try:
        return read_yaml(path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise RuntimeError(f"Invalid {label}: not readable YAML ({type(error).__name__}).") from error


def _policy_privacy(root: Path) -> tuple[dict[str, str] | None, str]:
    """Return the declared per-source classes (or None) and the default class."""
    if not (root / ".embraion" / "policy.yaml").is_file():
        return None, "PRIVATE"
    from .policy import read_policy_config
    privacy = read_policy_config(root).get("privacy") or {}
    declared = privacy.get("sources")
    return (dict(declared) if declared is not None else None), str(privacy.get("default-class", "PRIVATE"))


def registry_errors(root: Path) -> list[str]:
    """Return every problem of `.embraion/sources.yaml`, or an empty list when it is absent or valid."""
    path = root / SOURCES_CONFIG
    if not path.exists() and not path.is_symlink():
        return []
    try:
        data = _load_mapping(path, str(SOURCES_CONFIG))
    except RuntimeError as error:
        return [str(error)]
    if not isinstance(data, dict):
        return [f"Invalid {SOURCES_CONFIG}: expected a mapping."]
    schema = read_json(framework_root() / "schemas" / "sources.schema.json")
    schema_errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda item: list(item.absolute_path))
    if schema_errors:
        return [f"Invalid {SOURCES_CONFIG}: {_location(error)}: {error.message}" for error in schema_errors]

    errors: list[str] = []
    try:
        declared, default_class = _policy_privacy(root)
    except RuntimeError as error:
        return [str(error)]
    seen: set[str] = set()
    project = root.resolve()
    for index, entry in enumerate(data["sources"]):
        source_id = entry["id"]
        where = f"{SOURCES_CONFIG}: sources[{index}] '{source_id}'"
        if source_id in seen:
            errors.append(f"{where}: duplicate id.")
        seen.add(source_id)
        if declared is not None and source_id not in declared:
            errors.append(f"{where}: id is not declared in privacy.sources of .embraion/policy.yaml.")
        raised = entry.get("data-class")
        if raised is not None:
            base = declared.get(source_id, default_class) if declared is not None else default_class
            if DATA_CLASS_ORDER[raised] < DATA_CLASS_ORDER[base]:
                errors.append(f"{where}: data-class {raised} is below the declared class {base}; it may only raise it.")
        doc = entry.get("doc")
        if doc is not None:
            errors.extend(f"{where}: {message}" for message in _doc_errors(project, doc))
    return errors


def _doc_errors(project: Path, doc: str) -> list[str]:
    if doc.startswith(("/", "\\")) or "\\" in doc or "\x00" in doc or (len(doc) > 1 and doc[1] == ":"):
        return ["doc must be a repository-relative path."]
    if any(part in ("", ".", "..") for part in doc.split("/")):
        return ["doc must not contain empty, '.', or '..' segments."]
    target = project / doc
    try:
        target.resolve().relative_to(project)
    except ValueError:
        return ["doc leaves the project."]
    if not target.is_file():
        return [f"doc does not exist: {doc}"]
    return []


def load_registry(root: Path) -> list[dict[str, Any]] | None:
    """Return the validated registry entries, None when the file is absent; raise on any problem."""
    if not (root / SOURCES_CONFIG).exists() and not (root / SOURCES_CONFIG).is_symlink():
        return None
    errors = registry_errors(root)
    if errors:
        raise RuntimeError("; ".join(errors))
    return [dict(entry) for entry in read_yaml(root / SOURCES_CONFIG)["sources"]]


def _require_registry(root: Path) -> list[dict[str, Any]]:
    registry = load_registry(root)
    if registry is None:
        raise RuntimeError(f"Missing {SOURCES_CONFIG}; declare the project sources first.")
    return registry


def effective_data_classes(root: Path, declared: dict[str, str]) -> dict[str, str]:
    """Apply registry `data-class` values, which only raise, on top of the declared source classes."""
    registry = load_registry(root)
    if registry is None:
        return declared
    result = dict(declared)
    for entry in registry:
        raised = entry.get("data-class")
        current = result.get(entry["id"])
        if raised is not None and current is not None and DATA_CLASS_ORDER[raised] > DATA_CLASS_ORDER[current]:
            result[entry["id"]] = raised
    return result


def check_source_writes(access: str, source_ids: list[str], root: Path) -> None:
    """Fail closed when a write request names a source that is not writable.

    Only a project that declares `.embraion/sources.yaml` is affected. A `workspace-write` request
    may name only registry sources whose write policy is `workspace-write`.
    """
    if access != WRITABLE:
        return
    registry = load_registry(root)
    if registry is None:
        return
    policies = {entry["id"]: entry["write"] for entry in registry}
    refused = sorted(source for source in set(source_ids) if policies.get(source, "unregistered") != WRITABLE)
    if refused:
        raise RuntimeError(
            "Workspace-write execution names sources that are not writable: "
            + ", ".join(f"{source} ({policies.get(source, 'unregistered')})" for source in refused) + "."
        )


def read_local_paths(root: Path) -> dict[str, str]:
    """Return the machine-local source paths; raise on a malformed file. Absent means empty."""
    path = root / LOCAL_SOURCES
    if not path.exists() and not path.is_symlink():
        return {}
    data = _load_mapping(path, str(LOCAL_SOURCES))
    if data is None:
        return {}
    if not isinstance(data, dict) or not all(
            isinstance(key, str) and key and isinstance(value, str) and value for key, value in data.items()):
        raise RuntimeError(f"Invalid {LOCAL_SOURCES}: expected a mapping of source ID to absolute path.")
    if any(not Path(value).is_absolute() for value in data.values()):
        raise RuntimeError(f"Invalid {LOCAL_SOURCES}: every path must be absolute.")
    return dict(data)


def list_sources(root: Path) -> list[dict[str, Any]]:
    return _require_registry(root)


def source_status(root: Path) -> list[dict[str, Any]]:
    """Per source: id, role, write, and `available`, `missing`, or `unset`. Never includes a path."""
    registry = _require_registry(root)
    local = read_local_paths(root)
    rows = []
    for entry in registry:
        raw = local.get(entry["id"])
        availability = "unset" if raw is None else ("available" if Path(raw).exists() else "missing")
        rows.append({"id": entry["id"], "role": entry["role"], "write": entry["write"],
                     "availability": availability})
    return rows


def set_local_path(root: Path, source_id: str, raw_path: str) -> str:
    """Record the local path of a declared source. Returns the source ID."""
    registry = _require_registry(root)
    if source_id not in {entry["id"] for entry in registry}:
        raise RuntimeError(f"Unknown source id '{source_id}'; declare it in {SOURCES_CONFIG} first.")
    resolved = Path(raw_path).expanduser().resolve()
    if not resolved.exists():
        raise RuntimeError(f"The path for source '{source_id}' does not exist.")
    local = read_local_paths(root)
    local[source_id] = str(resolved)
    target = root / LOCAL_SOURCES
    if target.parent.is_symlink():
        raise RuntimeError(f"Invalid {LOCAL_SOURCES}: the state folder must not be a symbolic link.")
    atomic_write_bytes(target, yaml.safe_dump(local, sort_keys=True, allow_unicode=True).encode("utf-8"), mode=0o600)
    return source_id


def local_path_values(root: Path) -> dict[str, str]:
    """Machine-local paths for the security scan; a missing or unusable file yields nothing."""
    try:
        return read_local_paths(root)
    except RuntimeError:
        return {}


__all__ = [
    "LOCAL_SOURCES", "SOURCES_CONFIG", "check_source_writes", "effective_data_classes", "list_sources",
    "load_registry", "local_path_values", "read_local_paths", "registry_errors",
    "set_local_path", "source_status",
]
