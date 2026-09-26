from __future__ import annotations

import os
import shlex
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


def _normalize_validation_profile(
    name: str,
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "commands": [str(command) for command in value],
            "parameters": {},
        }
    if not isinstance(value, dict):
        raise RuntimeError(
            f"Invalid validation profile '{name}': expected a command list or mapping."
        )
    return {
        "commands": [str(command) for command in (value.get("commands") or [])],
        "parameters": {
            str(parameter): dict(definition or {})
            for parameter, definition in (value.get("parameters") or {}).items()
        },
    }


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


def _quote_validation_argument(value: str) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([value])
    return shlex.quote(value)


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
    environment = os.environ.copy()

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
        began = time.monotonic()
        try:
            result = subprocess.run(
                prepared_command,
                cwd=str(root),
                env=command_environment,
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
                "command": prepared_command,
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
                "command": prepared_command,
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
            "parameters": resolved_parameters,
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
