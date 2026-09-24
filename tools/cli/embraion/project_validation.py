from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root, state_root, write_json
from .evidence import attach_validation_evidence, read_run
from .policy import read_validation_config
from .runtime import _append_event
from .security import redact_child_output, redact_value


MAX_CAPTURE_CHARS = 8000


def validation_profiles(project: Path | None = None) -> dict[str, list[str]]:
    root = project_root(project)
    config = read_validation_config(root)
    profiles = config.get("profiles") or {}
    return {
        str(name): [str(command) for command in (commands or [])]
        for name, commands in profiles.items()
    }


def _captured_tail(value: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(value) <= limit:
        return value
    return "...<truncated>\n" + value[-limit:]


def _validation_path(project: Path, evidence_id: str) -> Path:
    return state_root(project) / "validation" / f"{evidence_id}.json"


def read_validation_evidence(
    evidence_id: str,
    project: Path | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    path = _validation_path(root, evidence_id)
    if not path.is_file():
        raise RuntimeError(f"Unknown validation evidence: {evidence_id}")
    from .common import read_json

    return read_json(path)


def run_validation_profile(
    profile: str,
    *,
    project: Path | None = None,
    run_id: str | None = None,
    fail_fast: bool = False,
    timeout: float | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    profiles = validation_profiles(root)

    if profile not in profiles:
        available = ", ".join(sorted(profiles)) or "none"
        raise RuntimeError(
            f"Unknown validation profile '{profile}'. Available profiles: {available}."
        )

    if timeout is not None and timeout <= 0:
        raise RuntimeError("Validation timeout must be greater than zero.")

    if run_id:
        run_record = read_run(run_id, root)
        if run_record.get("state") != "active":
            raise RuntimeError(
                f"Validation evidence can only attach to an active run: {run_id}"
            )

    commands = profiles[profile]
    evidence_id = f"{profile}-{uuid.uuid4().hex[:12]}"
    started = datetime.now(timezone.utc).isoformat()
    command_results: list[dict[str, Any]] = []

    for index, command in enumerate(commands, start=1):
        began = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=str(root),
                env=os.environ.copy(),
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            duration_ms = int((time.monotonic() - began) * 1000)
            output = redact_child_output(result.stdout, result.stderr)
            status = "passed" if result.returncode == 0 else "failed"
            row = {
                "index": index,
                "command": command,
                "status": status,
                "exit-code": result.returncode,
                "duration-ms": duration_ms,
                "stdout": _captured_tail(output["stdout"]),
                "stderr": _captured_tail(output["stderr"]),
            }
        except subprocess.TimeoutExpired as error:
            duration_ms = int((time.monotonic() - began) * 1000)
            stdout = error.stdout
            stderr = error.stderr
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            output = redact_child_output(stdout, stderr)
            row = {
                "index": index,
                "command": command,
                "status": "timed-out",
                "exit-code": None,
                "duration-ms": duration_ms,
                "stdout": _captured_tail(output["stdout"]),
                "stderr": _captured_tail(output["stderr"]),
            }

        command_results.append(row)
        if fail_fast and row["status"] != "passed":
            break

    if not commands:
        status = "skipped"
    elif all(item["status"] == "passed" for item in command_results) and (
        len(command_results) == len(commands)
    ):
        status = "passed"
    else:
        status = "failed"

    completed = datetime.now(timezone.utc).isoformat()
    record = redact_value(
        {
            "schema-version": 1,
            "evidence-id": evidence_id,
            "evidence-path": (
                f".embraion/state/validation/{evidence_id}.json"
            ),
            "profile": profile,
            "status": status,
            "command-count": len(commands),
            "executed-command-count": len(command_results),
            "fail-fast": fail_fast,
            "timeout-seconds": timeout,
            "run-id": run_id,
            "commands": command_results,
            "started-utc": started,
            "completed-utc": completed,
        }
    )
    write_json(_validation_path(root, evidence_id), record)

    _append_event(
        root,
        {
            "event": "validation-profile-completed",
            "evidence-id": evidence_id,
            "profile": profile,
            "status": status,
            "command-count": len(commands),
            "executed-command-count": len(command_results),
            "run-id": run_id,
        },
    )

    if run_id:
        attach_validation_evidence(
            run_id,
            profile=profile,
            status=status,
            evidence_id=evidence_id,
            project=root,
        )

    return record
