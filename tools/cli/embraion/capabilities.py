"""Read-only external capability inventory and bounded diagnostic evidence.

Declarations do not prove that an AI host loaded or executed a capability.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator


_CONFIG = Path(".embraion/external-capabilities.yaml")
_SCHEMA = Path("schemas/external-capabilities.schema.json")
_REMOVED_BUNDLE = "Built-in Unity bundle has been removed; remove its legacy inventory entry before projection or update."
_STAGES = ("declared", "installed-config", "host-discovered", "instructions-read", "tools-ready", "executed")
_OBSERVED_STAGES = frozenset(_STAGES[1:])
_MAX_FILE_BYTES = 65536
_MAX_OBSERVATION_BYTES = 65536
_MAX_AGE = timedelta(hours=24)
_FUTURE_SKEW = timedelta(minutes=5)


def _safe_file(root: Path, relative: Path) -> Path:
    """Reject symbolic links throughout a framework or project owned path."""
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RuntimeError("Capability path escapes its owner.")
    root = root.resolve()
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError("Capability path contains a symbolic link.")
    if not current.resolve().is_relative_to(root):
        raise RuntimeError("Capability path escapes its owner.")
    return current


def _read_yaml(root: Path, relative: Path) -> Any:
    path = _safe_file(root, relative)
    if not path.is_file():
        raise RuntimeError(f"Missing capability file: {relative.as_posix()}")
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise RuntimeError("Capability file exceeds the size limit.")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (UnicodeError, yaml.YAMLError) as error:
        raise RuntimeError("Invalid capability YAML.") from error


def _source_valid(source: str) -> bool:
    if source.startswith("host:"):
        value = source[5:]
        return bool(value) and len(value) <= 80 and all(
            part and part.isascii() and part.replace("-", "").isalnum()
            for part in value.split("/")
        )
    try:
        parsed = urlsplit(source)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if any(not label or not label[0].isalnum() or not label[-1].isalnum() or
           not all(char.isascii() and (char.isalnum() or char == "-") for char in label)
           for label in parsed.hostname.split(".")):
        return False
    if parsed.query or parsed.fragment or port or not parsed.path.startswith("/"):
        return False
    # Repository identifiers only: no encoded credentials, control characters,
    # ambiguous traversal, or arbitrary URL parameters in published metadata.
    parts = parsed.path.strip("/").split("/")
    return len(parts) >= 2 and all(
        part and part not in {".", ".."} and
        all(char.isascii() and (char.isalnum() or char in "-_.") for char in part)
        for part in parts
    )


def read_external_capabilities(framework_root: Path, project: Path) -> dict[str, Any]:
    """Validate the optional project inventory. An absent file is empty."""
    framework_root, project = Path(framework_root).resolve(), Path(project).resolve()
    path = _safe_file(project, _CONFIG)
    if not path.exists():
        return {"schema-version": 1, "capabilities": []}
    inventory = _read_yaml(project, _CONFIG)
    schema_path = _safe_file(framework_root, _SCHEMA)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(inventory))
    if errors:
        # jsonschema messages can echo user supplied credential values.
        locations = sorted({".".join(map(str, error.absolute_path)) or "<root>" for error in errors})
        raise RuntimeError("Invalid external capability inventory at: " + ", ".join(locations))
    seen: set[str] = set()
    for entry in inventory["capabilities"]:
        if entry["id"] in seen:
            raise RuntimeError("Duplicate external capability ID.")
        seen.add(entry["id"])
        if not set(entry.get("host-requirements", {})) <= set(entry["hosts"]):
            raise RuntimeError("Capability requirements name an undeclared host.")
        if entry["kind"] == "host-managed" and not _source_valid(entry["source"]):
            raise RuntimeError("Invalid host-managed capability source.")
    return inventory


def _framework_version(framework_root: Path) -> str:
    manifest = _read_yaml(framework_root, Path("framework.yaml"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("version"), str):
        raise RuntimeError("Invalid framework version.")
    return manifest["version"]


def projected_skills(framework_root: Path, project: Path, host: str) -> dict[str, Path]:
    """Reject a removed legacy bundle before projecting a selected host."""
    inventory = read_external_capabilities(framework_root, project)
    if any(item["kind"] == "managed-bundle" and host in item["hosts"] for item in inventory["capabilities"]):
        raise RuntimeError(_REMOVED_BUNDLE)
    return {}


def observation_scope(framework_root: Path, project: Path, host: str) -> str:
    """Stable inventory identity for a single resolved project, version, and host."""
    inventory = read_external_capabilities(framework_root, project)
    payload = json.dumps({"project": str(Path(project).resolve()), "framework-version": _framework_version(Path(framework_root)),
                          "host": host, "inventory": inventory}, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _accepted_observation(observation: Any, scope: str, host: str, now: datetime, inventory: dict[str, Any]) -> tuple[dict[str, set[str]], str]:
    if observation is None:
        return {}, "none"
    try:
        if len(json.dumps(observation)) > _MAX_OBSERVATION_BYTES or not isinstance(observation, dict):
            return {}, "invalid"
        if set(observation) != {"schema-version", "scope", "host", "observed-at", "capabilities"}:
            return {}, "invalid"
        if observation["schema-version"] != 1 or observation["scope"] != scope or observation["host"] != host:
            return {}, "identity-mismatch"
        timestamp = datetime.fromisoformat(observation["observed-at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or now - timestamp > _MAX_AGE or timestamp - now > _FUTURE_SKEW:
            return {}, "stale"
        records = observation["capabilities"]
        if not isinstance(records, list) or len(records) > 64:
            return {}, "invalid"
        declared = {entry["id"]: entry for entry in inventory["capabilities"]}
        accepted: dict[str, set[str]] = {}
        for record in records:
            if not isinstance(record, dict) or set(record) != {"id", "source", "version-or-digest", "stages"}:
                return {}, "invalid"
            identity = declared.get(record["id"])
            if identity is None or record["id"] in accepted or record["source"] != identity["source"] or record["version-or-digest"] != identity.get("version", identity.get("digest")):
                return {}, "identity-mismatch"
            stages = record["stages"]
            if not isinstance(stages, list) or len(stages) != len(set(stages)) or not set(stages) <= _OBSERVED_STAGES:
                return {}, "invalid"
            accepted[record["id"]] = set(stages)
        return accepted, "accepted-self-report"
    except (TypeError, ValueError, KeyError, OverflowError):
        return {}, "invalid"


def diagnose_external_capabilities(framework_root: Path, project: Path, host: str, *,
                                   observation: Mapping[str, Any] | None = None,
                                   environ: Mapping[str, str] | None = None,
                                   now: datetime | None = None) -> dict[str, Any]:
    """Inspect local metadata and label supplied host claims as self-reported."""
    if host not in {"codex", "claude-code", "copilot", "portable"}:
        raise RuntimeError("Unsupported capability host.")
    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("Diagnostic time must have a timezone.")
    at = at.astimezone(timezone.utc)
    inventory = read_external_capabilities(framework_root, project)
    scope = observation_scope(framework_root, project, host)
    claims, observation_status = _accepted_observation(observation, scope, host, at, inventory)
    environment = os.environ if environ is None else environ
    rows = []
    for entry in inventory["capabilities"]:
        if host not in entry["hosts"]:
            continue
        removed = entry["kind"] == "managed-bundle"
        required_env = [{"name": name, "present": bool(environment.get(name))} for name in entry["env-vars"]]
        stages: dict[str, dict[str, Any]] = {}
        stages["declared"] = {"status": "verified", "provenance": _CONFIG.as_posix(), "observed-at": at.isoformat()}
        for stage in _STAGES[1:]:
            if not removed and stage in claims.get(entry["id"], set()):
                stages[stage] = {"status": "self-reported", "provenance": "supplied observation", "observed-at": observation["observed-at"]}
            else:
                stages[stage] = {"status": "unverified", "provenance": None, "observed-at": None}
        rows.append({"id": entry["id"], "kind": entry["kind"], "source": entry["source"],
                     "version-or-digest": entry.get("version", entry.get("digest")),
                     "license": entry["license"], "access": entry["access"], "data-class": entry["data-class"],
                     "host-requirements": entry.get("host-requirements", {}).get(host, []),
                     "required-env": required_env, "stages": stages, "ready": False,
                     "issue": _REMOVED_BUNDLE if removed else ("required environment missing" if any(not row["present"] for row in required_env) else None)})
    return {"schema-version": 1, "host": host, "scope": scope, "diagnosed-at": at.isoformat(),
            "observation-status": observation_status, "capabilities": rows}
