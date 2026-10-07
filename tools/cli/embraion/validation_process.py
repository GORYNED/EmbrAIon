"""Ending a validation command's process tree and confirming that it is gone."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

GRACE_SECONDS = 2.0
VERIFY_SECONDS = 5.0
POLL_SECONDS = 0.05

class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


class _WindowsProcesses:
    """Native process observations, loaded only on the Windows termination path."""

    def __init__(self) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._snapshot = kernel.CreateToolhelp32Snapshot
        self._snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self._snapshot.restype = wintypes.HANDLE
        self._first = kernel.Process32FirstW
        self._first.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        self._first.restype = wintypes.BOOL
        self._next = kernel.Process32NextW
        self._next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        self._next.restype = wintypes.BOOL
        self._open = kernel.OpenProcess
        self._open.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._open.restype = wintypes.HANDLE
        self._times = kernel.GetProcessTimes
        self._times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self._times.restype = wintypes.BOOL
        self._wait = kernel.WaitForSingleObject
        self._wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._wait.restype = wintypes.DWORD
        self._close = kernel.CloseHandle
        self._close.argtypes = [wintypes.HANDLE]
        self._close.restype = wintypes.BOOL

    def snapshot(self) -> dict[int, int]:
        handle = self._snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            if not self._first(handle, ctypes.byref(entry)):
                raise ctypes.WinError(ctypes.get_last_error())
            result = {}
            while True:
                result[entry.th32ProcessID] = entry.th32ParentProcessID
                if not self._next(handle, ctypes.byref(entry)):
                    error = ctypes.get_last_error()
                    if error != 18:  # ERROR_NO_MORE_FILES
                        raise ctypes.WinError(error)
                    return result
        finally:
            self._close(handle)

    def open(self, pid: int) -> int:
        # OpenProcess handles are noninheritable when bInheritHandle is false.
        handle = self._open(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def created(self, handle: int) -> int:
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not self._times(handle, ctypes.byref(created), ctypes.byref(exited),
                           ctypes.byref(kernel), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (created.dwHighDateTime << 32) | created.dwLowDateTime

    def alive(self, handle: int) -> bool:
        result = self._wait(handle, 0)
        if result == 0x102:  # WAIT_TIMEOUT
            return True
        if result == 0:  # WAIT_OBJECT_0
            return False
        raise ctypes.WinError(ctypes.get_last_error())

    def close(self, handle: int) -> None:
        self._close(handle)


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
    deadline = time.monotonic() + VERIFY_SECONDS
    root_already_exited = process.poll() is not None
    handles: list[int] = []
    api = None
    captured = False
    try:
        try:
            api = _WindowsProcesses()
            captured = _capture_windows_descendants(process, api, handles)
        except (OSError, AttributeError):
            captured = False

        try:
            result = subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(deadline - time.monotonic(), 0.001),
                check=False,
            )
            # With a failed tree kill, a captured descendant could have spawned
            # another child after the snapshot. Only an already-ended root with
            # no observed descendants is proven gone without a successful kill.
            attempted = result.returncode == 0 or (root_already_exited and not handles)
        except (OSError, subprocess.SubprocessError):
            attempted = False

        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                if process.poll() is None:
                    return False
        try:
            process.wait(timeout=max(deadline - time.monotonic(), 0))
        except (OSError, subprocess.TimeoutExpired):
            return False
        if not captured or not attempted or api is None:
            return False
        while True:
            try:
                if not any(api.alive(handle) for handle in handles):
                    return True
            except OSError:
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(POLL_SECONDS, max(deadline - time.monotonic(), 0)))
    finally:
        if api is not None:
            for handle in handles:
                api.close(handle)


def _capture_windows_descendants(process: subprocess.Popen, api: _WindowsProcesses,
                                 handles: list[int]) -> bool:
    """Pin observed descendants; reject unknown or stale parent process identities."""
    # Popen retains the original process object, even after the root exits.
    # Its creation time anchors parent edges without reopening a reused PID.
    root_handle = process._handle
    root_created = api.created(root_handle)
    table = api.snapshot()
    if not table:
        return False

    children: dict[int, list[int]] = {}
    for pid, parent in table.items():
        children.setdefault(parent, []).append(pid)
    pending = [(process.pid, root_created)]
    seen = {process.pid}
    while pending:
        parent, parent_created = pending.pop()
        for pid in children.get(parent, []):
            if pid in seen:
                continue
            seen.add(pid)
            try:
                handle = api.open(pid)
            except OSError:
                # Even a process that just exited could have surviving children.
                # Without its identity we cannot prove their parent edge.
                return False
            try:
                created = api.created(handle)
                if created < parent_created:
                    continue  # Parent PID was reused after this process started.
                handles.append(handle)
                handle = None
                pending.append((pid, created))
            finally:
                if handle is not None:
                    api.close(handle)
    return True
