"""Local, reference-only task checkpoints and read-only freshness checks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .common import framework_root, project_root, read_json, write_json
from .evidence import review_snapshot

ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")
PHASES = {"planning", "implementing", "validating", "reviewing", "blocked", "complete"}
MAX_METADATA_BYTES = 1024 * 1024


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise RuntimeError(f"Invalid {label}; use 1-80 letters, digits, '_' or '-'.")
    return value


def _safe_file(root: Path, relative: str, *, state: bool = False) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or "\x00" in relative or re.match(r"^[A-Za-z]:", relative)):
        raise RuntimeError("Invalid project-relative path.")
    rel = Path(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise RuntimeError("Path must stay inside the project.")
    if not state and (rel.parts[0] == ".git" or rel.parts[:2] == (".embraion", "state")):
        raise RuntimeError("Task artifacts must be project files outside local runtime state.")
    path = root / rel
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise RuntimeError("Symlinked checkpoint anchor is not allowed.")
    if not path.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Path escapes the project.")
    return path


def _hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    parts = path.parts
    if ".embraion" in parts:
        tail = parts[parts.index(".embraion") + 1:]
        if (tail and (tail[0] == "state" or tail == ("project.yaml",)
                      or tail == ("knowledge.yaml",)
                      or tail == ("knowledge-maintenance.yaml",))):
            try:
                with path.open("rb") as stream:
                    content = stream.read(MAX_METADATA_BYTES + 1)
            except OSError:
                raise RuntimeError("Invalid local metadata.") from None
            if len(content) > MAX_METADATA_BYTES:
                raise RuntimeError("Invalid local metadata.")
            return "sha256:" + hashlib.sha256(content).hexdigest()
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_metadata_object(path: Path, label: str) -> dict[str, Any]:
    """Read bounded local metadata without echoing its contents on failure."""
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_METADATA_BYTES + 1)
        if len(payload) > MAX_METADATA_BYTES:
            raise ValueError("oversized")
        value = json.loads(payload)
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError(f"Invalid {label}.") from None
    if not isinstance(value, dict):
        raise RuntimeError(f"Invalid {label}.")
    return value


def _read_yaml_object(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_METADATA_BYTES + 1)
        if len(payload) > MAX_METADATA_BYTES:
            raise ValueError("oversized")
        value = yaml.safe_load(payload) or {}
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        raise RuntimeError(f"Invalid {label}.") from None
    if not isinstance(value, dict):
        raise RuntimeError(f"Invalid {label}.")
    return value


def _checkpoint_path(root: Path, checkpoint_id: str) -> Path:
    _id(checkpoint_id, "checkpoint ID")
    return _safe_file(root, f".embraion/state/checkpoints/{checkpoint_id}.json", state=True)


def _anchors(root: Path, *, context_id: str | None, run_id: str | None,
             acceptance_path: str | None, remaining_path: str | None) -> dict[str, str]:
    paths = [".embraion/project.yaml", ".embraion/knowledge.yaml"]
    knowledge_file = _safe_file(root, ".embraion/knowledge.yaml")
    if not knowledge_file.is_file():
        raise RuntimeError("Missing project knowledge configuration.")
    knowledge = _read_yaml_object(knowledge_file, "project knowledge configuration")
    entries = [value for key, value in knowledge.items() if key != "slots"]
    slots = knowledge.get("slots") or {}
    if not isinstance(slots, dict):
        raise RuntimeError("Invalid project contract slots.")
    entries.extend(value for value in slots.values() if value is not None)
    for entry in entries:
        relative = entry if isinstance(entry, str) else entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(relative, str):
            raise RuntimeError("Invalid project knowledge path.")
        paths.append(relative)
    if acceptance_path:
        paths.append(acceptance_path)
    if remaining_path:
        paths.append(remaining_path)
    if context_id:
        paths.append(f".embraion/state/context/{_id(context_id, 'context ID')}.json")
    if run_id:
        run_path = f".embraion/state/runs/{_id(run_id, 'run ID')}.json"
        paths.append(run_path)
        run_file = _safe_file(root, run_path, state=True)
        if not run_file.is_file():
            raise RuntimeError("Missing run evidence.")
        run = _read_metadata_object(run_file, "run evidence")
        if run.get("run-id") != run_id:
            raise RuntimeError("Run evidence ID mismatch.")
        validation = run.get("validation") or []
        if not isinstance(validation, list):
            raise RuntimeError("Invalid run evidence.")
        for item in validation:
            if not isinstance(item, dict) or not isinstance(item.get("evidence-id"), str):
                raise RuntimeError("Invalid run evidence.")
            evidence_id = _id(item["evidence-id"], "validation evidence ID")
            evidence_path = f".embraion/state/validation/{evidence_id}.json"
            evidence = _safe_file(root, evidence_path, state=True)
            if not evidence.is_file() or _read_metadata_object(evidence, "validation evidence").get("evidence-id") != evidence_id:
                raise RuntimeError("Validation evidence ID mismatch or missing.")
            paths.append(evidence_path)
    if context_id:
        context_file = _safe_file(root, f".embraion/state/context/{context_id}.json", state=True)
        if not context_file.is_file():
            raise RuntimeError("Missing context evidence.")
        context = _read_metadata_object(context_file, "context evidence")
        if context.get("context-id") != context_id:
            raise RuntimeError("Context evidence ID mismatch.")
        selected = context.get("selected") or []
        if not isinstance(selected, list):
            raise RuntimeError("Invalid context evidence.")
        for item in selected:
            if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                    or not isinstance(item.get("sha256"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
                raise RuntimeError("Invalid context evidence.")
            _safe_file(root, item["path"])
            if _hash(root / item["path"]) != "sha256:" + item["sha256"]:
                raise RuntimeError("Selected context knowledge is stale.")
            paths.append(item["path"])
    result: dict[str, str] = {}
    for relative in paths:
        path = _safe_file(root, relative, state=relative.startswith(".embraion/state/"))
        digest = _hash(path)
        if digest is None:
            raise RuntimeError(f"Missing checkpoint anchor: {relative}")
        result[relative] = digest
    return result


def create_checkpoint(
    checkpoint_id: str, *, task_id: str, phase: str,
    decision_id: str | None = None, next_action_id: str | None = None,
    acceptance_path: str | None = None, remaining_path: str | None = None,
    context_id: str | None = None, run_id: str | None = None,
    project: Path | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    _id(checkpoint_id, "checkpoint ID")
    _id(task_id, "task ID")
    for label, value in (("decision ID", decision_id), ("next action ID", next_action_id)):
        if value is not None:
            _id(value, label)
    if phase not in PHASES:
        raise RuntimeError("Invalid checkpoint phase.")
    destination = _checkpoint_path(root, checkpoint_id)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("Checkpoint ID already exists; create a new checkpoint ID.")
    anchors = _anchors(root, context_id=context_id, run_id=run_id,
                       acceptance_path=acceptance_path, remaining_path=remaining_path)
    # The entire Git-visible tree is an anchor, including untracked files.
    snapshot = review_snapshot(root)
    manifest = _read_yaml_object(_safe_file(root, ".embraion/project.yaml"), "project configuration")
    framework = manifest.get("framework") or {}
    if not isinstance(framework, dict):
        raise RuntimeError("Invalid project configuration.")
    record = {
        "schema-version": 1, "checkpoint-id": checkpoint_id, "task-id": task_id,
        "phase": phase, "decision-id": decision_id, "next-action-id": next_action_id,
        "acceptance-path": acceptance_path, "remaining-path": remaining_path,
        "context-id": context_id, "run-id": run_id,
        "framework-pin": framework.get("version"),
        "git-snapshot": snapshot, "anchors": anchors,
        "created-utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(destination, record)
    return record


def resume_checkpoint(checkpoint_id: str, *, project: Path | None = None) -> dict[str, Any]:
    """Inspect checkpoint freshness; never write state or confer approval."""
    root = project_root(project)
    path = _checkpoint_path(root, checkpoint_id)
    if not path.is_file():
        return {"checkpoint-id": checkpoint_id, "status": "missing", "reasons": ["checkpoint-missing"]}
    record = _read_metadata_object(path, "checkpoint record")
    schema = read_json(framework_root() / "schemas/checkpoint.schema.json")
    if (record.get("checkpoint-id") != checkpoint_id
            or not Draft202012Validator(schema).is_valid(record)):
        raise RuntimeError("Invalid checkpoint record.")
    required = {".embraion/project.yaml", ".embraion/knowledge.yaml"}
    for field, prefix in (("acceptance-path", ""), ("remaining-path", ""),
                          ("context-id", ".embraion/state/context/"),
                          ("run-id", ".embraion/state/runs/")):
        value = record.get(field)
        if value:
            required.add(f"{prefix}{value}.json" if prefix else value)
    if not required.issubset(record["anchors"]):
        raise RuntimeError("Invalid checkpoint record.")
    reasons: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    for relative, expected in record["anchors"].items():
        path = _safe_file(root, relative, state=relative.startswith(".embraion/state/"))
        actual = _hash(path)
        if actual is None:
            missing.append(relative)
        elif actual != expected:
            changed.append(relative)
    if missing:
        reasons.append("anchor-missing")
    if changed:
        reasons.append("anchor-changed")
    snapshot = review_snapshot(root)
    if snapshot is None or record.get("git-snapshot") is None:
        reasons.append("git-snapshot-unavailable")
    elif snapshot != record["git-snapshot"]:
        reasons.append("git-snapshot-changed")
    if record.get("run-id"):
        run_path = f".embraion/state/runs/{_id(record['run-id'], 'run ID')}.json"
        if run_path not in missing and run_path not in changed:
            run = _read_metadata_object(_safe_file(root, run_path, state=True), "run evidence")
            if run.get("run-id") != record["run-id"]:
                reasons.append("run-id-mismatch")
            if run.get("review") == "passed" and run.get("review-snapshot") != snapshot:
                reasons.append("run-review-snapshot-stale")
    # Even if the run file was rewritten, its claimed review cannot survive a
    # changed Git snapshot. Return evidence references, never an approval flag.
    return {
        "checkpoint-id": checkpoint_id, "task-id": record.get("task-id"),
        "phase": record.get("phase"), "decision-id": record.get("decision-id"),
        "next-action-id": record.get("next-action-id"),
        "acceptance-path": record.get("acceptance-path"),
        "remaining-path": record.get("remaining-path"),
        "context-id": record.get("context-id"), "run-id": record.get("run-id"),
        "status": "missing" if missing else ("stale" if reasons else "valid"),
        "reasons": reasons, "missing-anchors": missing, "changed-anchors": changed,
        "evidence-paths": sorted(record["anchors"]),
    }
