"""Optional Claude PreToolUse guard for verified scoped native assignments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .claude_native import _SAFE_ID, _installation, observer_status, read_config
from .policy import effective_policy, path_matches
from .project import _projection_target

_READ_TOOLS = frozenset({"Read", "Grep", "Glob"})
_LAUNCH_TOOLS = frozenset({"Agent", "Task"})
_SCOPED_PREFIX = "embraion--"
_AGENT_INPUTS = frozenset({"subagent_type", "description", "prompt", "run_in_background"})
_TOOL_INPUTS = {
    "Read": frozenset({"file_path", "offset", "limit", "pages"}),
    "Grep": frozenset({"pattern", "path", "glob", "output_mode", "-A", "-B", "-C",
                       "-i", "-n", "type", "head_limit", "offset", "multiline"}),
    "Glob": frozenset({"pattern", "path"}),
}
_GLOB_MARKERS = frozenset("*?[]{}()|")
_UNVERIFIED_EXPANSION = frozenset("{}()|")


def _case_insensitive_paths(root: Path) -> bool:
    if os.name == "nt":
        return True
    try:
        # Configured projects have this directory. On default APFS, a spelling
        # with different case resolves to the same inode; on case-sensitive
        # volumes it does not. This read-only probe follows the actual volume.
        return os.path.samefile(root / ".embraion", root / ".EMBRAION")
    except (OSError, ValueError):
        return False


def _deny(reason: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def _relative_path(root: Path, raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        return None
    path = Path(raw)
    try:
        relative = path.relative_to(root) if path.is_absolute() else path
        target = _projection_target(root, relative.as_posix())
        return target.relative_to(root).as_posix()
    except (OSError, ValueError, RuntimeError):
        return None


def _literal_prefix(pattern: str) -> tuple[str, ...]:
    parts: list[str] = []
    for part in pattern.replace("\\", "/").split("/"):
        if not part or part == ".":
            continue
        if any(marker in part for marker in _GLOB_MARKERS):
            break
        parts.append(part)
    return tuple(parts)


def _overlaps_protected(scope: str, patterns: list[str], root: Path) -> bool:
    scope_parts = tuple(part for part in Path(scope).parts if part != ".")
    insensitive = _case_insensitive_paths(root)
    if insensitive:
        scope_parts = tuple(part.casefold() for part in scope_parts)
    for pattern in patterns:
        protected = _literal_prefix(pattern)
        if insensitive:
            protected = tuple(part.casefold() for part in protected)
        shared = min(len(scope_parts), len(protected))
        if scope_parts[:shared] == protected[:shared]:
            return True
    return False


def _search_scope(tool: str, inputs: dict[str, Any], root: Path) -> str | None:
    raw_path = inputs.get("path", ".")
    if isinstance(raw_path, str) and any(marker in raw_path for marker in _GLOB_MARKERS):
        return None
    scope = _relative_path(root, raw_path)
    if scope is None:
        return None
    if tool == "Grep":
        return scope if isinstance(inputs.get("pattern"), str) and inputs["pattern"] else None
    pattern = inputs.get("pattern")
    if not isinstance(pattern, str) or not pattern or pattern.startswith(("/", "\\")):
        return None
    if any(marker in pattern for marker in _UNVERIFIED_EXPANSION):
        return None
    parts = Path(pattern.replace("\\", "/")).parts
    if ".." in parts or "\x00" in pattern:
        return None
    prefix = _literal_prefix(pattern)
    return _relative_path(root, (Path(scope) / Path(*prefix)).as_posix()) if prefix else scope


def _verified(root: Path) -> bool:
    try:
        return observer_status(root).get("installation") == "verified"
    except (OSError, ValueError, RuntimeError):
        return False


def _protected_patterns(root: Path) -> list[str] | None:
    try:
        patterns = list(effective_policy(root)["sources"].get("protected") or [])
        path_matches("", patterns)  # Validate bounded pattern complexity for every read tool.
        return patterns
    except (OSError, ValueError, RuntimeError):
        return None


def _matches_protected(path: str, patterns: list[str], root: Path) -> bool:
    if _case_insensitive_paths(root):
        return path_matches(path.casefold(), [pattern.casefold() for pattern in patterns])
    return path_matches(path, patterns)


def guard(payload: Any, project: Path | None = None) -> dict[str, Any]:
    """Return a Claude denial only for a configured scoped identity and tool."""
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "PreToolUse":
        return {}
    tool = payload.get("tool_name")
    if tool not in _READ_TOOLS | _LAUNCH_TOOLS:
        return {}
    inputs = payload.get("tool_input")
    agent_type = payload.get("agent_type")
    agent_id = payload.get("agent_id")
    from .claude_hooks import hook_project

    try:
        root = hook_project(payload, project)
    except (OSError, ValueError, RuntimeError):
        return _deny("Scoped hook project context is unavailable or mismatched.")

    try:
        config = read_config(root)
        installation, assignments = _installation(root) if config is not None else ("missing", [])
    except (OSError, ValueError, RuntimeError):
        # A malformed configuration cannot authorize a scoped invocation.
        if tool in _LAUNCH_TOOLS and isinstance(inputs, dict) and str(inputs.get("subagent_type", "")).startswith(_SCOPED_PREFIX):
            return _deny("Scoped agent configuration is unavailable.")
        if tool in _READ_TOOLS and isinstance(agent_type, str) and agent_type.startswith(_SCOPED_PREFIX):
            return _deny("Scoped agent configuration is unavailable.")
        return {}

    scoped_names = {record["plan"]["scoped-definition"]["name"] for record in assignments}
    if tool in _LAUNCH_TOOLS:
        if config is None or not isinstance(inputs, dict):
            return {}
        requested = inputs.get("subagent_type")
        if requested in set(config["bindings"].values()):
            return _deny("Use the freshly resolved scoped agent type for this assignment.")
        if not isinstance(requested, str) or not requested.startswith(_SCOPED_PREFIX):
            return {}
        if requested not in scoped_names or installation != "verified" or not _verified(root):
            return _deny("Scoped agent definition is unavailable or stale.")
        if set(inputs) - _AGENT_INPUTS:
            return _deny("Scoped agent settings must come from its verified definition.")
        return {}

    if not isinstance(agent_type, str):
        return {}
    if agent_type not in scoped_names and not (config is not None and agent_type.startswith(_SCOPED_PREFIX)):
        return {}
    if not isinstance(agent_id, str) or _SAFE_ID.fullmatch(agent_id) is None:
        return _deny("Scoped agent identity is unavailable.")
    if agent_type not in scoped_names:
        return _deny("Scoped agent definition is unavailable or stale.")
    if installation != "verified" or not _verified(root):
        return _deny("Scoped agent definition is unavailable or stale.")
    read_policy = config.get("read-policy") or {}
    if not read_policy.get("project-only") and not read_policy.get("deny-protected"):
        return {}
    if not isinstance(inputs, dict):
        return _deny("Scoped read request has an ambiguous path.")
    if set(inputs) - _TOOL_INPUTS[tool]:
        return _deny("Scoped read request has unsupported input fields.")
    patterns = _protected_patterns(root) if read_policy.get("deny-protected") else []
    if patterns is None:
        return _deny("Protected project policy is unavailable.")
    if tool == "Read":
        relative = _relative_path(root, inputs.get("file_path"))
        if relative is None:
            return _deny("Scoped read must stay within the project boundary.")
        try:
            if _matches_protected(relative, patterns, root):
                return _deny("Scoped read overlaps protected project content.")
        except RuntimeError:
            return _deny("Protected project policy is unavailable.")
        return {}
    scope = _search_scope(tool, inputs, root)
    if scope is None:
        return _deny("Scoped search has an ambiguous project scope.")
    if _overlaps_protected(scope, patterns, root):
        return _deny("Scoped search may include protected project content.")
    return {}
