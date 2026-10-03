"""Explicit Claude scoped profiles and deliberately narrow native hook evidence."""

from __future__ import annotations

import hashlib
import json
import errno
import os
import re
import stat
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
EVIDENCE_LOCK = "claude-native-evidence.lock"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_HOOK_EVENTS = frozenset({"PostToolUse", "SubagentStop"})
_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
_MAX_EVIDENCE_BYTES = 1_000_000
_EVIDENCE_SOURCE = "unverified-command-input"
_EVIDENCE_FIELDS = frozenset({"schema-version", "timestamp-utc", "source", "event", "session-id",
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


def _append_evidence(root: Path, row: bytes) -> str | None:
    """Atomically reserve the journal cap for this observer without waiting."""
    from .project import _projection_target

    state_root(root)
    try:
        path = _projection_target(root, ".embraion/state/" + EVIDENCE_PATH)
        lock = _projection_target(root, ".embraion/state/" + EVIDENCE_LOCK)
    except RuntimeError:
        return "evidence-path-symlink"
    if len(row) > _MAX_EVIDENCE_BYTES:
        return "evidence-limit"
    binary = getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT | binary | nofollow, 0o600)
    except OSError:
        return "evidence-write-failed"
    try:
        if not _prepare_lock_file(lock_fd, lock, windows=os.name == "nt"):
            os.close(lock_fd)
            return "evidence-lock-changed"
    except OSError:
        os.close(lock_fd)
        return "evidence-write-failed"
    try:
        _lock_fd(lock_fd)
    except OSError as error:
        os.close(lock_fd)
        return ("evidence-busy" if error.errno in {errno.EACCES, errno.EAGAIN, errno.EBUSY, errno.EDEADLK}
                else "evidence-write-failed")
    reason: str | None = None
    try:
        if not _opened_regular_matches(lock_fd, lock):
            return "evidence-lock-changed"
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | binary | nofollow
        with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
            if not _opened_regular_matches(stream.fileno(), path):
                reason = "evidence-journal-changed"
            elif os.fstat(stream.fileno()).st_size + len(row) > _MAX_EVIDENCE_BYTES:
                reason = "evidence-limit"
            else:
                stream.write(row)
                stream.flush()
    except OSError:
        reason = "evidence-write-failed"
    finally:
        try:
            _unlock_fd(lock_fd)
        except OSError:
            reason = "evidence-lock-release-failed"
        finally:
            os.close(lock_fd)
    return reason


def _opened_regular_matches(fd: int, path: Path) -> bool:
    """Check the opened inode before writing, including when O_NOFOLLOW is absent."""
    try:
        entry = path.lstat()
        return stat.S_ISREG(entry.st_mode) and os.path.samestat(os.fstat(fd), entry)
    except OSError:
        return False


def _prepare_lock_file(fd: int, path: Path, *, windows: bool) -> bool:
    """Validate the opened file before Windows writes its one-byte lock region."""
    if not _opened_regular_matches(fd, path):
        return False
    if windows and os.fstat(fd).st_size == 0:
        os.write(fd, b"\0")
    return True


def _lock_fd(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_fd(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


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
    record = {"schema-version": 1, "timestamp-utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
              "source": _EVIDENCE_SOURCE,
              "event": payload["hook_event_name"], "session-id": session_id,
              "agent-id": agent_id, "agent-type": agent_type,
              "definition-digest": digests.pop(),
              "expected-effort": expected_effort, "observed-effort": observed_effort,
              "effort-status": effort_status}
    row = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    reason = _append_evidence(root, row)
    if reason is not None:
        return {"status": "unverified", "reason": reason}
    return {"status": "recorded", "event": record["event"],
            "agent-type": agent_type, "reported-effort": "match" if effort_status == "matched" else effort_status,
            "evidence-origin": _EVIDENCE_SOURCE,
            "model-status": "unverified"}


def observer_status(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    installation, assignments = _installation(root)
    result: dict[str, Any] = {"installation": installation,
                              "assignment-count": len(assignments),
                              "execution": "unverified", "callbacks": "none",
                              "effort": "unverified",
                              "reported-effort": "unverified",
                              "evidence-origin": _EVIDENCE_SOURCE,
                              "model": "unverified",
                              "limitations": [
                                  "Classic Claude hook payloads do not expose the resolved model.",
                                  "This observer does not enforce parent or unscoped agents.",
                                  "A recorded callback does not prove agent execution, completion, or applied effort.",
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
                item["source"] != _EVIDENCE_SOURCE or \
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
        result["callbacks"] = "recorded"
        statuses.append(item["effort-status"])
    if "mismatch" in statuses:
        result["reported-effort"] = "mismatch"
    elif "matched" in statuses:
        result["reported-effort"] = "match"
    return result
