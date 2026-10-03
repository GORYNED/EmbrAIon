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
        if expected in entries:
            continue
        for entry in entries:
            commands = entry.get("hooks", [])
            if not isinstance(commands, list):
                raise RuntimeError("Existing Claude hook commands are malformed; settings were preserved.")
            if any(isinstance(command, dict) and command.get("command") in {COMMAND, GUARD_COMMAND} for command in commands):
                raise RuntimeError("An existing EmbrAIon observer hook differs; review it before installation.")
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
