"""Explicit, preserving installation of Claude's scoped guard and metadata-only observer hooks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import atomic_write_bytes, project_root
from .project import _projection_target


COMMAND = "embraion claude-native observe"
GUARD_COMMAND = "embraion claude-native guard"
HOOKS = {
    "PreToolUse": {
        "matcher": "Agent|Task|Read|Grep|Glob",
        "hooks": [{"type": "command", "command": GUARD_COMMAND, "timeout": 10}],
    },
    "PostToolUse": {
        "matcher": "Read|Grep|Glob|Write|Edit|Bash",
        "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}],
    },
    "SubagentStop": {
        "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}],
    },
}


def hook_project(payload: Any, project: Path | None = None) -> Path:
    """Use the event's working tree, never the hook process's launch folder.

    Legacy payloads without cwd retain explicit-project/process-cwd behavior.
    A present but invalid cwd never falls back to another project's policy.
    """
    if not isinstance(payload, dict) or "cwd" not in payload:
        return project_root(project)
    raw = payload["cwd"]
    if not isinstance(raw, str) or not raw or len(raw) > 32768 or "\x00" in raw:
        raise RuntimeError("Invalid Claude hook project context.")
    start = Path(raw)
    if not start.is_absolute() or not start.is_dir():
        raise RuntimeError("Invalid Claude hook project context.")
    root = project_root(start)
    manifest = _projection_target(root, ".embraion/project.yaml")
    if not manifest.is_file() or (project is not None and root != project_root(project)):
        raise RuntimeError("Invalid Claude hook project context.")
    # A launcher can have selected its runtime from the process cwd before it
    # reads stdin. Never apply that runtime to a differently pinned worktree.
    from . import __version__
    from .versioning import _load_cached_runtime, package_version_for_pin, read_project_pin
    from .artifacts import read_project_artifact_lock
    from .common import framework_root
    import sys
    import yaml

    try:
        pin = package_version_for_pin(read_project_pin(manifest))
        lock = read_project_artifact_lock(manifest, required=False)
    except (yaml.YAMLError, AttributeError, TypeError):
        raise RuntimeError("Invalid Claude hook project context.") from None
    if pin != package_version_for_pin(__version__):
        raise RuntimeError("Claude hook runtime does not match the working-tree pin.")
    if lock is not None:
        runtime = _load_cached_runtime(Path(sys.prefix), pin, artifact_lock=lock)
        if runtime is None or runtime.framework_root != framework_root():
            raise RuntimeError("Claude hook runtime does not match the working-tree artifact.")
    return root


def install_observer_hooks(project: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    """Merge only our exact hook entries; never replace other host settings."""
    from .claude_native import observer_status

    root = project_root(project)
    status = observer_status(root)
    if status.get("installation") != "verified":
        raise RuntimeError("Install and verify the configured scoped-agents projection before installing observer hooks.")
    path = _projection_target(root, ".claude/settings.json")
    try:
        settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError) as error:
        raise RuntimeError("Cannot read Claude settings JSON; existing settings were preserved.") from error
    if not isinstance(settings, dict):
        raise RuntimeError("Claude settings must be a JSON object.")
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise RuntimeError("Claude settings hooks must be an object.")
    added: list[str] = []
    for event, expected in HOOKS.items():
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
            raise RuntimeError("Existing Claude hook entries are malformed; settings were preserved.")
        for entry in entries:
            commands = entry.get("hooks", [])
            if not isinstance(commands, list) or any(not isinstance(command, dict) for command in commands):
                raise RuntimeError("Existing Claude hook commands are malformed; settings were preserved.")
            if entry != expected and any(command.get("command") in {COMMAND, GUARD_COMMAND} for command in commands):
                raise RuntimeError("An existing EmbrAIon observer hook differs; review it before installation.")
        if expected in entries:
            continue
        entries.append(expected)
        added.append(event)
    if added and not dry_run:
        atomic_write_bytes(path, (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return {"path": ".claude/settings.json", "added": added, "dry-run": dry_run,
            "instructions-loaded": "unverified", "execution": "unverified"}


def observer_hooks_status(project: Path | None = None) -> dict[str, Any]:
    root = project_root(project)
    try:
        path = _projection_target(root, ".claude/settings.json")
        settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        hooks = settings.get("hooks", {}) if isinstance(settings, dict) else {}
        missing = [event for event, entry in HOOKS.items()
                   if not isinstance(hooks, dict) or entry not in hooks.get(event, [])]
    except (RuntimeError, OSError, ValueError, TypeError):
        return {"installed": False, "configuration": "unverified"}
    return {"installed": not missing, "missing-events": missing,
            "instructions-loaded": "unverified"}
