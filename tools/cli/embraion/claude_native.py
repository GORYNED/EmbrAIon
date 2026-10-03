"""Explicit Claude scoped profiles and deliberately narrow native hook evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yaml import YAMLError

from .common import framework_root, project_root, read_json, state_root
from .delegation import prepare_native_assignment
from .policy import _validated_config_mapping
from .runtime import _resolve_route

METADATA_PATH = ".claude/embraion-native.json"
EVIDENCE_PATH = "claude-native-evidence.jsonl"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_HOOK_EVENTS = frozenset({"PostToolUse", "SubagentStop"})
_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
_MAX_EVIDENCE_BYTES = 1_000_000
_EVIDENCE_FIELDS = frozenset({"schema-version", "timestamp-utc", "event", "session-id",
                              "agent-id", "agent-type", "definition-digest",
                              "expected-effort", "observed-effort", "effort-status"})


def _effort_status(expected: str | None, observed: str | None) -> str:
    if expected is None or observed is None:
        return "unverified"
    return "matched" if expected == observed else "mismatch"


def _utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?\+00:00", value):
        return False
    try:
        return datetime.fromisoformat(value).utcoffset().total_seconds() == 0
    except ValueError:
        return False


def read_config(project: Path | None = None) -> dict[str, Any] | None:
    """Read an optional, explicit assignment list; a present invalid file fails."""
    root = project_root(project)
    from .project import _projection_target

    path = _projection_target(root, ".embraion/claude-native.yaml")
    if not path.exists():
        return None
    if not path.is_file():
        raise RuntimeError("Invalid .embraion/claude-native.yaml: expected a regular file.")
    try:
        return _validated_config_mapping(path, schema_name="claude-native.schema.json",
                                         label=".embraion/claude-native.yaml")
    except (OSError, ValueError, RuntimeError, YAMLError):
        raise RuntimeError("Invalid or unreadable .embraion/claude-native.yaml.") from None


def configured_assignments(project: Path | None = None) -> list[dict[str, Any]]:
    root = project_root(project)
    config = read_config(root)
    if config is None:
        return []
    from .project import load_agents

    available = {agent["id"]: agent for agent in load_agents(framework_root(), root) if agent["id"] != "lead"}
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for assignment in config["assignments"]:
        role = assignment["role"]
        route_class = assignment["route-class"]
        data_class = assignment["data-class"]
        access = assignment["access"]
        key = (role, route_class, data_class, access)
        if key in seen:
            raise RuntimeError("Duplicate Claude native assignment tuple.")
        seen.add(key)
        native_agent = config["bindings"].get(role)
        if native_agent not in available:
            raise RuntimeError(f"Claude native role '{role}' lacks a valid explicit specialist binding.")
        if access == "write" and available[native_agent].get("access") != "workspace-write":
            raise RuntimeError("Claude native write assignment requires a writable specialist binding.")
        selected = _resolve_route("claude-code", route_class, data_class, role=role,
                                  access=access, project=root)
        if selected["resolution"] == "host-default":
            raise RuntimeError("Claude native assignment requires explicit project routing settings.")
        plan = prepare_native_assignment(selected, "claude-agent", role=role,
                                         native_agent=native_agent, project=root, access=access)
        if plan["status"] != "handoff-required" or "scoped-definition" not in plan or plan["limitations"]:
            raise RuntimeError("Claude native assignment has no usable scoped definition.")
        if plan["arguments"].get("subagent_type") != plan["scoped-definition"]["name"]:
            raise RuntimeError("Claude native plan and scoped definition disagree.")
        records.append({**assignment, "native-agent": native_agent, "plan": plan})
    return records


def definition_digest(definition: dict[str, Any]) -> str:
    encoded = json.dumps(definition, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def definition_markdown(definition: dict[str, Any]) -> str:
    """One canonical LF rendering shared by projection and tamper checks."""
    lines = ["---", f'name: {json.dumps(definition["name"], ensure_ascii=False)}',
             f'description: {json.dumps(definition["description"], ensure_ascii=False)}',
             "tools:"]
    lines.extend(f"  - {json.dumps(tool, ensure_ascii=False)}" for tool in definition["tools"])
    for field in ("model", "effort"):
        if field in definition:
            lines.append(f'{field}: {json.dumps(definition[field], ensure_ascii=False)}')
    lines.extend(["---", "", definition["prompt"].rstrip("\n"), ""])
    return "\n".join(lines)


def projection_metadata(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for record in assignments:
        definition = record["plan"]["scoped-definition"]
        entries.append({
            **{key: record[key] for key in ("role", "route-class", "data-class", "access", "native-agent")},
            "name": definition["name"],
            **{key: definition[key] for key in ("model", "effort") if key in definition},
            "tools": list(definition["tools"]),
            "definition-digest": definition_digest(definition),
        })
    return {"schema-version": 1, "assignments": entries}


def _installation(project: Path) -> tuple[str, list[dict[str, Any]]]:
    """Require fresh config, exact metadata and exact generated agent bytes."""
    assignments = configured_assignments(project)
    if not assignments:
        return "missing", []
    from .project import _projection_target

    try:
        metadata_path = _projection_target(project, METADATA_PATH)
        if not metadata_path.is_file():
            return "missing", assignments
        if metadata_path.stat().st_size > 100_000 or read_json(metadata_path) != projection_metadata(assignments):
            return "stale", assignments
        for record in assignments:
            definition = record["plan"]["scoped-definition"]
            path = _projection_target(project, f'.claude/agents/{definition["name"]}.md')
            if not path.is_file() or path.read_bytes() != definition_markdown(definition).encode("utf-8"):
                return "stale", assignments
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError):
        return "stale", assignments
    return "verified", assignments


def observe(payload: Any, project: Path | None = None) -> dict[str, Any]:
    """Record only bounded native identity and effort metadata from a hook."""
    root = project_root(project)
    if not isinstance(payload, dict) or payload.get("hook_event_name") not in _HOOK_EVENTS:
        return {"status": "ignored", "reason": "unsupported-event"}
    agent_id, agent_type = payload.get("agent_id"), payload.get("agent_type")
    session_id = payload.get("session_id")
    if not all(isinstance(value, str) and _SAFE_ID.fullmatch(value)
               for value in (agent_id, agent_type, session_id)):
        return {"status": "ignored", "reason": "missing-or-invalid-native-identity"}
    installation, assignments = _installation(root)
    if installation != "verified":
        return {"status": "unverified", "reason": f"projection-{installation}"}
    matching = [record for record in assignments
                if record["plan"]["scoped-definition"]["name"] == agent_type]
    if not matching:
        return {"status": "ignored", "reason": "unrelated-agent"}
    digests = {definition_digest(record["plan"]["scoped-definition"]) for record in matching}
    if len(digests) != 1:
        return {"status": "unverified", "reason": "ambiguous-definition"}
    expected = {record["plan"]["scoped-definition"].get("effort") for record in matching}
    if len(expected) != 1:
        return {"status": "unverified", "reason": "ambiguous-effort"}
    expected_effort = expected.pop()
    effort = payload.get("effort")
    observed_effort = effort.get("level") if isinstance(effort, dict) else None
    if not isinstance(observed_effort, str) or observed_effort not in _EFFORTS:
        observed_effort = None
    effort_status = _effort_status(expected_effort, observed_effort)
    record = {"schema-version": 1, "timestamp-utc": datetime.now(timezone.utc).isoformat(),
              "event": payload["hook_event_name"], "session-id": session_id,
              "agent-id": agent_id, "agent-type": agent_type,
              "definition-digest": digests.pop(),
              "expected-effort": expected_effort, "observed-effort": observed_effort,
              "effort-status": effort_status}
    from .project import _projection_target

    state_root(root)
    try:
        path = _projection_target(root, ".embraion/state/" + EVIDENCE_PATH)
    except RuntimeError:
        return {"status": "unverified", "reason": "evidence-path-symlink"}
    if path.exists() and path.stat().st_size > _MAX_EVIDENCE_BYTES:
        return {"status": "unverified", "reason": "evidence-limit"}
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        return {"status": "unverified", "reason": "evidence-write-failed"}
    return {"status": "observed", "event": record["event"],
            "agent-type": agent_type, "effort-status": effort_status,
            "model-status": "unverified"}


def observer_status(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    installation, assignments = _installation(root)
    result: dict[str, Any] = {"installation": installation,
                              "assignment-count": len(assignments),
                              "execution": "unverified", "effort": "unverified",
                              "model": "unverified",
                              "limitations": [
                                  "Classic Claude hook payloads do not expose the resolved model.",
                                  "This observer does not enforce parent or unscoped agents.",
                              ]}
    from .claude_hooks import observer_hooks_status
    result["hooks"] = observer_hooks_status(root)
    if installation != "verified":
        return result
    from .project import _projection_target

    try:
        path = _projection_target(root, ".embraion/state/" + EVIDENCE_PATH)
    except RuntimeError:
        return result
    if not path.is_file() or path.stat().st_size > _MAX_EVIDENCE_BYTES:
        return result
    definitions = {record["plan"]["scoped-definition"]["name"]:
                   record["plan"]["scoped-definition"] for record in assignments}
    statuses: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return result
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or set(item) != _EVIDENCE_FIELDS or \
                type(item["schema-version"]) is not int or item["schema-version"] != 1 or \
                not _utc_timestamp(item["timestamp-utc"]):
            continue
        if any(not isinstance(item[key], str) or not _SAFE_ID.fullmatch(item[key])
               for key in ("session-id", "agent-id", "agent-type")):
            continue
        definition = definitions.get(item["agent-type"])
        if definition is None or item["definition-digest"] != definition_digest(definition) or \
                not isinstance(item["event"], str) or item["event"] not in _HOOK_EVENTS or \
                item["expected-effort"] != definition.get("effort"):
            continue
        observed = item["observed-effort"]
        if observed is not None and (not isinstance(observed, str) or observed not in _EFFORTS):
            continue
        if item["effort-status"] != _effort_status(definition.get("effort"), observed):
            continue
        result["execution"] = "observed"
        statuses.append(item["effort-status"])
    if "mismatch" in statuses:
        result["effort"] = "mismatch"
    elif "matched" in statuses:
        result["effort"] = "observed-match"
    return result
