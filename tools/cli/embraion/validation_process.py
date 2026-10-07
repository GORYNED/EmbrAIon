"""Ending a validation command's process tree and confirming that it is gone."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

GRACE_SECONDS = 2.0
VERIFY_SECONDS = 5.0
POLL_SECONDS = 0.05
_QUERY_TIMEOUT_SECONDS = 30


def terminate_tree(process: subprocess.Popen) -> bool:
    """End the command and its descendants; return whether the tree is confirmed gone."""
    if os.name == "nt":
        return _terminate_windows(process)
    return _terminate_posix(process)


def _terminate_posix(process: subprocess.Popen) -> bool:
    group = process.pid
    try:
        os.killpg(group, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    # Descendants that ignore SIGTERM or outlive the leader are killed as well.
    _kill_group(group)
    process.wait()
    return _wait_until_group_gone(group)


def _kill_group(group: int) -> None:
    try:
        os.killpg(group, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def group_has_live_members(group: int) -> bool:
    """Tell whether any process of the group still runs; a zombie no longer does."""
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return not _only_zombies(group)


def _only_zombies(group: int) -> bool:
    """Linux only: members that exist but are zombies. Elsewhere a member counts as live."""
    proc = Path("/proc")
    if not proc.is_dir():
        return False
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue  # the process ended while it was listed
        if fields[2] == str(group) and fields[0] != "Z":
            return False
    return True


def _wait_until_group_gone(group: int) -> bool:
    deadline = time.monotonic() + VERIFY_SECONDS
    while True:
        if not group_has_live_members(group):
            return True
        if time.monotonic() >= deadline:
            return False
        _kill_group(group)
        time.sleep(POLL_SECONDS)


def _terminate_windows(process: subprocess.Popen) -> bool:
    descendants = windows_descendants(process.pid)
    subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(process.pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if process.poll() is None:
        process.kill()
    process.wait()
    if descendants is None:
        # The members of the tree could not be listed, so their end cannot be shown.
        return False
    deadline = time.monotonic() + VERIFY_SECONDS
    remaining = [pid for pid in descendants if windows_pid_alive(pid)]
    while remaining and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        remaining = [pid for pid in remaining if windows_pid_alive(pid)]
    return not remaining


def windows_descendants(root: int) -> list[int] | None:
    """List the descendants of a process, or ``None`` when the process table is unreadable."""
    try:
        completed = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "Get-CimInstance Win32_Process | ForEach-Object "
                "{ '{0},{1}' -f $_.ProcessId, $_.ParentProcessId }",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    children: dict[int, list[int]] = {}
    for line in completed.stdout.decode("utf-8", errors="replace").splitlines():
        parts = line.strip().split(",")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    if not children:
        return None
    found: list[int] = []
    pending = [root]
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in found and child != root:
                found.append(child)
                pending.append(child)
    return found


def windows_pid_alive(pid: int) -> bool:
    """Ask ``tasklist`` whether a PID exists; an unanswered question counts as alive."""
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if completed.returncode != 0:
        return True
    return f'"{pid}"' in completed.stdout.decode("utf-8", errors="replace")
