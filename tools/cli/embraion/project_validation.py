from __future__ import annotations

import locale
import os
import re
import shlex
import signal
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root, state_root, write_json
from .evidence import attach_validation_evidence, read_run
from .environment import child_environment
from .policy import read_validation_config
from .runtime import _append_event
from .security import redact_child_output, redact_text, redact_value


MAX_CAPTURE_CHARS = 8000
RUN_ID_ENVIRONMENT = "EMBRAION_RUN_ID"
TERMINATION_GRACE_SECONDS = 2.0


def _normalize_validation_profile(
    name: str,
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "commands": [str(command) for command in value],
            "parameters": {},
            "timeouts": [None] * len(value),
        }
    if not isinstance(value, dict):
        raise RuntimeError(
            f"Invalid validation profile '{name}': expected a command list or mapping."
        )
    commands = [str(command) for command in (value.get("commands") or [])]
    return {
        "commands": commands,
        "parameters": {
            str(parameter): dict(definition or {})
            for parameter, definition in (value.get("parameters") or {}).items()
        },
        "timeouts": _configured_timeouts(name, value.get("timeout-seconds"), len(commands)),
    }


def _configured_timeouts(name: str, value: Any, count: int) -> list[float | None]:
    """Return one configured timeout per command; ``None`` keeps the command unbounded."""
    if value is None:
        return [None] * count
    values = value if isinstance(value, list) else [value] * count
    if len(values) != count:
        raise RuntimeError(
            f"Invalid validation profile '{name}': timeout-seconds lists {len(values)} "
            f"value(s) for {count} command(s)."
        )
    timeouts: list[float | None] = []
    for item in values:
        if item is not None and (isinstance(item, bool) or not isinstance(item, (int, float)) or item <= 0):
            raise RuntimeError(
                f"Invalid validation profile '{name}': timeout-seconds must be positive numbers."
            )
        timeouts.append(None if item is None else float(item))
    return timeouts


def validation_profile_specs(
    project: Path | None = None,
) -> dict[str, dict[str, Any]]:
    root = project_root(project)
    config = read_validation_config(root)
    profiles = config.get("profiles") or {}
    return {
        str(name): _normalize_validation_profile(str(name), value)
        for name, value in profiles.items()
    }


def validation_profiles(project: Path | None = None) -> dict[str, list[str]]:
    return {
        name: list(spec["commands"])
        for name, spec in validation_profile_specs(project).items()
    }


_WINDOWS_SHELL_UNSAFE = re.compile(r'[\r\n&|<>^()%!"]')


def _quote_validation_argument(value: str) -> str:
    if os.name == "nt":
        if _WINDOWS_SHELL_UNSAFE.search(value):
            raise RuntimeError(
                "Validation argument value contains characters that are unsafe "
                "for cmd.exe shell execution on Windows. Use an environment "
                "parameter or a safer value."
            )
        return subprocess.list2cmdline([value])
    return shlex.quote(value)


def _redact_validation_parameter_values(
    text: str,
    resolved: dict[str, str],
) -> str:
    redacted = text
    for value in sorted(
        {item for item in resolved.values() if item},
        key=len,
        reverse=True,
    ):
        redacted = redacted.replace(
            value,
            "<REDACTED:validation-parameter>",
        )
    return redacted


def _resolve_validation_parameters(
    profile: str,
    spec: dict[str, Any],
    supplied: dict[str, str] | None,
) -> tuple[dict[str, str], list[tuple[str, dict[str, Any]]]]:
    supplied_values = dict(supplied or {})
    definitions = spec.get("parameters") or {}
    unknown = sorted(set(supplied_values) - set(definitions))
    if unknown:
        raise RuntimeError(
            f"Unknown validation parameter(s) for profile '{profile}': "
            + ", ".join(unknown)
        )

    resolved: dict[str, str] = {}
    command_count = len(spec.get("commands") or [])
    normalized_definitions: list[tuple[str, dict[str, Any]]] = []

    for name, raw_definition in definitions.items():
        definition = dict(raw_definition or {})
        targets = definition.get("commands")
        if targets:
            invalid_targets = [
                int(index)
                for index in targets
                if int(index) < 1 or int(index) > command_count
            ]
            if invalid_targets:
                raise RuntimeError(
                    f"Validation parameter '{name}' for profile '{profile}' "
                    f"targets command(s) outside 1..{command_count}: "
                    + ", ".join(str(index) for index in invalid_targets)
                )

        value = supplied_values.get(name)
        if value is None and "default" in definition:
            value = str(definition["default"])
        if value is None:
            if bool(definition.get("required")):
                raise RuntimeError(
                    f"Missing required validation parameter '{name}' "
                    f"for profile '{profile}'."
                )
            continue

        resolved[name] = str(value)
        normalized_definitions.append((name, definition))

    return resolved, normalized_definitions


def _prepare_validation_command(
    command: str,
    index: int,
    resolved: dict[str, str],
    definitions: list[tuple[str, dict[str, Any]]],
) -> tuple[str, dict[str, str]]:
    prepared = command
    environment = child_environment()

    for name, definition in definitions:
        targets = definition.get("commands")
        if targets and index not in {int(value) for value in targets}:
            continue

        value = resolved[name]
        argument = definition.get("argument")
        if argument:
            separator = "" if str(argument).endswith("=") else " "
            prepared += (
                f" {argument}{separator}{_quote_validation_argument(value)}"
            )

        environment_name = definition.get("environment")
        if environment_name:
            environment[str(environment_name)] = value

    return prepared, environment


def _spawn_contained(command: str, cwd: Path, environment: dict[str, str], stdout: Any, stderr: Any) -> subprocess.Popen:
    """Start a shell command as the leader of its own process group."""
    options: dict[str, Any] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=environment,
        shell=True,
        stdout=stdout,
        stderr=stderr,
        **options,
    )


def _wait_for(process: subprocess.Popen, timeout: float | None) -> int:
    return process.wait(timeout=timeout)


def _terminate_tree(process: subprocess.Popen) -> None:
    """Terminate the command and every descendant that stayed in its process group."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if process.poll() is None:
            process.kill()
        process.wait()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    # Descendants that ignore SIGTERM or outlive the leader are killed as well.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    process.wait()


def _run_contained(
    command: str,
    cwd: Path,
    environment: dict[str, str],
    timeout: float | None,
) -> tuple[int | None, str, str]:
    """Run one command; return its exit code (``None`` after a timeout) and full output."""
    # Anonymous temporary files keep raw output out of the project state and do
    # not block when a descendant keeps an inherited output handle open.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = _spawn_contained(command, cwd, environment, stdout, stderr)
        try:
            returncode: int | None = _wait_for(process, timeout)
        except subprocess.TimeoutExpired:
            _terminate_tree(process)
            returncode = None
        except BaseException:
            _terminate_tree(process)
            raise
        # Text-mode subprocess output used the locale encoding; keep that decoding.
        encoding = locale.getpreferredencoding(False)
        texts = []
        for handle in (stdout, stderr):
            handle.seek(0)
            texts.append(handle.read().decode(encoding, errors="replace"))
    return returncode, texts[0], texts[1]


def _log_path(project: Path, evidence_id: str, index: int) -> Path:
    return state_root(project) / "validation" / evidence_id / f"command-{index}.log"


def _write_command_log(path: Path, command: str, stdout: str, stderr: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"$ {redact_text(command)}\n--- stdout ---\n{stdout}"
    if stdout and not stdout.endswith("\n"):
        text += "\n"
    text += f"--- stderr ---\n{stderr}"
    path.write_text(text, encoding="utf-8")


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
    parameters: dict[str, str] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = project_root(project)
    specs = validation_profile_specs(root)

    if profile not in specs:
        available = ", ".join(sorted(specs)) or "none"
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

    if plan is not None:
        # A plan restricts the run to its selected commands; see validation_plan.
        from .validation_plan import plan_spec

        specs[profile], parameters = plan_spec(specs, profile, plan, parameters)
    spec = specs[profile]
    commands = list(spec["commands"])
    resolved_parameters, parameter_definitions = _resolve_validation_parameters(
        profile,
        spec,
        parameters,
    )
    evidence_id = f"{profile}-{uuid.uuid4().hex[:12]}"
    started = datetime.now(timezone.utc).isoformat()
    command_results: list[dict[str, Any]] = []

    for index, command in enumerate(commands, start=1):
        prepared_command, command_environment = _prepare_validation_command(
            command,
            index,
            resolved_parameters,
            parameter_definitions,
        )
        # Commands see only this invocation's run; an inherited value is not theirs.
        command_environment.pop(RUN_ID_ENVIRONMENT, None)
        if run_id:
            command_environment[RUN_ID_ENVIRONMENT] = run_id
        command_timeout = timeout if timeout is not None else spec["timeouts"][index - 1]
        began = time.monotonic()
        exit_code, raw_stdout, raw_stderr = _run_contained(
            prepared_command,
            root,
            command_environment,
            command_timeout,
        )
        duration_ms = int((time.monotonic() - began) * 1000)
        output = redact_child_output(raw_stdout, raw_stderr)
        stdout = _redact_validation_parameter_values(output["stdout"], resolved_parameters)
        stderr = _redact_validation_parameter_values(output["stderr"], resolved_parameters)
        log_path = _log_path(root, evidence_id, index)
        _write_command_log(log_path, command, stdout, stderr)
        if exit_code is None:
            status = "timed-out"
        else:
            status = "passed" if exit_code == 0 else "failed"
        row = {
            "index": index,
            "command": command,
            "status": status,
            "exit-code": exit_code,
            "duration-ms": duration_ms,
            "timeout-seconds": command_timeout,
            "log-path": log_path.relative_to(root).as_posix(),
            "stdout": _captured_tail(stdout),
            "stderr": _captured_tail(stderr),
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
    if plan is not None:
        from .validation_plan import write_plan_evidence

        plan_path = write_plan_evidence(root, evidence_id, plan)
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
            "parameters": sorted(resolved_parameters),
            "commands": command_results,
            "started-utc": started,
            "completed-utc": completed,
            **({"plan": plan, "plan-path": plan_path} if plan is not None else {}),
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
