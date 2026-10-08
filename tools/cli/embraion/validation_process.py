"""Contain validation commands in a Windows job or a POSIX process group."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

GRACE_SECONDS = 2.0
VERIFY_SECONDS = 5.0
POLL_SECONDS = 0.05


class ContainmentUnavailable(RuntimeError):
    """The target command was not released into a proven process container."""

    def __init__(self, message: str, *, termination_confirmed: bool = True) -> None:
        super().__init__(message)
        self.termination_confirmed = termination_confirmed


class _JobBasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                ("maximum", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]


class _JobIoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("read_operations", "write_operations", "other_operations", "read_bytes",
                 "write_bytes", "other_bytes")]


class _JobExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", _JobBasicLimits), ("io", _JobIoCounters),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


class _JobAccounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
                ("user_time", "kernel_time", "period_user_time", "period_kernel_time")] + [
                    (name, wintypes.DWORD) for name in
                    ("page_faults", "total", "active", "terminated")]


class _WindowsJob:
    """Kill-on-close containment assigned before the bootstrap releases its child."""

    def __init__(self) -> None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close = kernel.CloseHandle
        self._close.argtypes = [wintypes.HANDLE]
        self._close.restype = wintypes.BOOL
        create = kernel.CreateJobObjectW
        create.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        create.restype = wintypes.HANDLE
        self.handle = create(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            configure = kernel.SetInformationJobObject
            configure.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            configure.restype = wintypes.BOOL
            limits = _JobExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not configure(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise
        self._assign = kernel.AssignProcessToJobObject
        self._assign.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._assign.restype = wintypes.BOOL
        self._query = kernel.QueryInformationJobObject
        self._query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                wintypes.DWORD, ctypes.c_void_p]
        self._query.restype = wintypes.BOOL
        self._terminate = kernel.TerminateJobObject
        self._terminate.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._terminate.restype = wintypes.BOOL

    def assign(self, process: subprocess.Popen) -> None:
        if not self._assign(self.handle, process._handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def active(self) -> int:
        accounting = _JobAccounting()
        if not self._query(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return accounting.active

    def terminate(self) -> None:
        if not self._terminate(self.handle, 137):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self._close(handle):
                raise ctypes.WinError(ctypes.get_last_error())


_BOOTSTRAP = (
    "import subprocess,sys\n"
    "if sys.stdin.buffer.read(1)!=b'1': sys.exit(125)\n"
    "mode=sys.argv[1]\n"
    "target=sys.argv[2] if mode=='shell' else sys.argv[2:]\n"
    "child=subprocess.Popen(target,shell=(mode=='shell'),stdin=subprocess.DEVNULL)\n"
    "sys.exit(child.wait())\n"
)


def spawn_contained(command: str | list[str], cwd: Path, environment: dict[str, str],
                    stdout: object, stderr: object) -> subprocess.Popen:
    """Start the target only after containment is established."""
    if os.name != "nt":
        try:
            return subprocess.Popen(command, cwd=str(cwd), env=environment, shell=isinstance(command, str),
                                    stdout=stdout, stderr=stderr, start_new_session=True)
        except OSError as error:
            raise ContainmentUnavailable("process group could not be created") from error
    try:
        job = _WindowsJob()
    except OSError as error:
        raise ContainmentUnavailable("Windows Job Object could not be created") from error
    process = None
    try:
        target = (["shell", command] if isinstance(command, str) else ["argv", *command])
        process = subprocess.Popen([sys.executable, "-I", "-S", "-c", _BOOTSTRAP, *target],
                                   cwd=str(cwd), env=environment, stdin=subprocess.PIPE,
                                   stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        job.assign(process)
        process._embraion_job = job
        process.stdin.write(b"1")
        process.stdin.close()
        return process
    except (OSError, subprocess.SubprocessError) as error:
        confirmed = True
        if process is not None:
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()  # EOF keeps the target behind its launch gate.
                except OSError:
                    confirmed = False
            if getattr(process, "_embraion_job", None) is job:
                confirmed = _terminate_windows_job(process) and confirmed
            else:
                try:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=VERIFY_SECONDS)
                except (OSError, subprocess.SubprocessError):
                    confirmed = False
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        confirmed = False
        try:
            job.close()
        except OSError:
            confirmed = False
        raise ContainmentUnavailable("Windows process containment could not be established",
                                     termination_confirmed=confirmed) from error


def containment_has_live_members(process: subprocess.Popen) -> bool:
    job = getattr(process, "_embraion_job", None)
    if job is not None:
        return job.active() != 0
    return group_has_live_members(process.pid)


def containment_quiescent(process: subprocess.Popen, timeout: float = 0.25) -> bool:
    """Allow job members or same-group children a brief bounded exit window."""
    deadline = time.monotonic() + timeout
    while True:
        if not containment_has_live_members(process):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(POLL_SECONDS, max(deadline - time.monotonic(), 0)))


def close_containment(process: subprocess.Popen) -> None:
    job = getattr(process, "_embraion_job", None)
    if job is not None:
        job.close()

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
    """End the Windows job or POSIX group; confirm that container is gone."""
    if os.name == "nt":
        if getattr(process, "_embraion_job", None) is not None:
            return _terminate_windows_job(process)
        return _terminate_windows(process)
    return _terminate_posix(process)


def _terminate_windows_job(process: subprocess.Popen) -> bool:
    job = process._embraion_job
    deadline = time.monotonic() + VERIFY_SECONDS
    try:
        if job.active():
            job.terminate()
        process.wait(timeout=max(deadline - time.monotonic(), 0))
        while job.active():
            if time.monotonic() >= deadline:
                return False
            time.sleep(POLL_SECONDS)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


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
    try:
        process.wait(timeout=VERIFY_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return False
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
