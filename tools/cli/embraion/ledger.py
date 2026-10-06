"""Bounded local JSONL ledger of validated execution attempts and derived health.

Records hold only the redacted attempt object that execution already validates:
never prompt or context bytes, worker output, or credential values.
"""

from __future__ import annotations

import errno
import json
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import state_root
from .health import evaluate_health
from .security import redact_value


LEDGER_NAME = "execution-attempts.jsonl"
ROTATED_NAME = "execution-attempts.1.jsonl"
LOCK_NAME = "execution-attempts.lock"
MAX_LEDGER_BYTES = 1_048_576
MAX_RECORD_BYTES = 16_384
_LOCK_WAIT_SECONDS = 5.0


def _paths(root: Path, *, create: bool) -> tuple[Path, Path, Path]:
    from .project import _projection_target

    if create:
        state_root(root)
    return tuple(_projection_target(root, ".embraion/state/" + name)  # type: ignore[return-value]
                 for name in (LEDGER_NAME, ROTATED_NAME, LOCK_NAME))


def _regular_matches(fd: int, path: Path) -> bool:
    try:
        entry = path.lstat()
        return stat.S_ISREG(entry.st_mode) and os.path.samestat(os.fstat(fd), entry)
    except OSError:
        return False


def _lock(fd: int) -> None:
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    while True:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EBUSY, errno.EDEADLK} or time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def _unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def append_attempt(root: Path, attempt: dict[str, Any], *, run_id: str, work_item_id: str) -> None:
    """Append one record under an exclusive lock, rotating once at the size bound.

    A truncated final line from an interrupted writer is closed with a newline first,
    so it stays one unreadable line instead of corrupting the new record.
    """
    record = redact_value({"schemaVersion": 1, "recordedUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                           "runId": run_id, "workItemId": work_item_id, "attempt": attempt})
    row = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(row) > MAX_RECORD_BYTES:
        raise OSError("Execution attempt record exceeds its bound.")
    ledger, rotated, lock = _paths(root, create=True)
    binary, nofollow = getattr(os, "O_BINARY", 0), getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT | binary | nofollow, 0o600)
    try:
        if not _regular_matches(lock_fd, lock):
            raise OSError("Execution ledger lock changed.")
        if os.name == "nt" and os.fstat(lock_fd).st_size == 0:
            os.write(lock_fd, b"\0")
        _lock(lock_fd)
        try:
            if ledger.exists() and not ledger.is_symlink() and ledger.stat().st_size + len(row) > MAX_LEDGER_BYTES:
                os.replace(ledger, rotated)
            fd = os.open(ledger, os.O_RDWR | os.O_APPEND | os.O_CREAT | binary | nofollow, 0o600)
            with os.fdopen(fd, "r+b") as stream:
                if not _regular_matches(stream.fileno(), ledger):
                    raise OSError("Execution ledger changed.")
                size = os.fstat(stream.fileno()).st_size
                prefix = b""
                if size:
                    stream.seek(size - 1)
                    if stream.read(1) != b"\n":
                        prefix = b"\n"
                stream.write(prefix + row)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            _unlock(lock_fd)
    finally:
        os.close(lock_fd)


def read_records(root: Path) -> dict[str, Any]:
    """Read the rotated and current ledgers; unreadable lines are counted, never trusted."""
    records: list[dict[str, Any]] = []
    corrupt = 0
    try:
        ledger, rotated, _ = _paths(root, create=False)
    except RuntimeError:
        return {"records": [], "corruptLines": 0, "unavailable": True}
    for path in (rotated, ledger):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            data = path.read_bytes()[: MAX_LEDGER_BYTES + MAX_RECORD_BYTES]
        except OSError:
            corrupt += 1
            continue
        for line in data.split(b"\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                attempt = record["attempt"]
                if (record.get("schemaVersion") != 1 or not isinstance(attempt.get("deployment"), str)
                        or attempt.get("status") not in {"completed", "failed", "cancelled"}):
                    raise ValueError("record")
                datetime.fromisoformat(str(attempt["finishedUtc"]).replace("Z", "+00:00"))
            except (ValueError, TypeError, KeyError, AttributeError):
                corrupt += 1
                continue
            records.append(record)
    return {"records": records, "corruptLines": corrupt, "unavailable": False}


def _observations(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    observations: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        attempt = record["attempt"]
        observations.setdefault(attempt["deployment"], []).append(
            {"at": attempt["finishedUtc"], "status": attempt["status"], "failure": attempt.get("failure")})
    return observations


def health_observations(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Map deployments to the observation shape that `evaluate_health` consumes."""
    return _observations(read_records(root)["records"])


def health_report(root: Path, *, at: datetime | None = None, policy: dict[str, int] | None = None) -> dict[str, Any]:
    loaded = read_records(root)
    observations = _observations(loaded["records"])
    deployments = []
    for identifier in sorted(observations):
        items = observations[identifier]
        health = evaluate_health(items, at=at, **(policy or {}))
        deployments.append({"deployment": identifier, **health, "attempts": len(items),
                            "lastStatus": max(items, key=lambda item: item["at"])["status"]})
    return {"schemaVersion": 1, "ledger": ".embraion/state/" + LEDGER_NAME,
            "records": len(loaded["records"]), "corruptLines": loaded["corruptLines"],
            "deployments": deployments}
