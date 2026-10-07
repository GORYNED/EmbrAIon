from __future__ import annotations

import hashlib
import locale
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
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
from .security import redact_text, redact_value
from .validation_output import CapturedOutput, capture_stream, render_output


MAX_CAPTURE_CHARS = 8000
MAX_CLEAN_TREE_PATHS = 20
MIN_OUTPUT_LIMIT_BYTES = 1024
MAX_FINGERPRINT_BYTES = 64 * 1024 * 1024
RUN_ID_ENVIRONMENT = "EMBRAION_RUN_ID"
TERMINATION_GRACE_SECONDS = 2.0


_PLATFORMS = ("linux", "macos", "windows")


def _command_entry(name: str, index: int, item: Any) -> tuple[str, dict[str, Any]]:
    """Return a command string and its run semantics.

    A plain string keeps the previous behavior: required, with no prerequisites.
    """
    if not isinstance(item, dict):
        return str(item), {"required": True, "requires": {}}
    location = f"Invalid validation profile '{name}': command {index}"
    unknown = sorted(set(item) - {"command", "required", "requires"})
    if unknown or not isinstance(item.get("command"), str) or not item["command"]:
        raise RuntimeError(
            f"{location} must be a string or a mapping with a 'command' and optional "
            "'required' and 'requires'."
        )
    required = item.get("required", True)
    if not isinstance(required, bool):
        raise RuntimeError(f"{location} has a non-boolean 'required'.")
    declared = item.get("requires") or {}
    if not isinstance(declared, dict) or set(declared) - {"executables", "env", "platforms"}:
        raise RuntimeError(
            f"{location} has invalid 'requires'; allowed keys are executables, env, platforms."
        )
    requires: dict[str, list[str]] = {}
    for key in ("executables", "env", "platforms"):
        values = declared.get(key)
        if values is None:
            continue
        if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
            raise RuntimeError(f"{location} requires.{key} must be a list of non-empty strings.")
        if key == "platforms" and (not values or set(values) - set(_PLATFORMS)):
            raise RuntimeError(
                f"{location} requires.platforms must be a non-empty list of: "
                + ", ".join(_PLATFORMS) + "."
            )
        requires[key] = list(values)
    return item["command"], {"required": required, "requires": requires}


def _normalize_validation_profile(
    name: str,
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, list):
        parsed = [_command_entry(name, index, item) for index, item in enumerate(value, start=1)]
        return {
            "commands": [command for command, _ in parsed],
            "entries": [entry for _, entry in parsed],
            "parameters": {},
            "timeouts": [None] * len(value),
            "clean-tree": False,
            "output-limit": None,
        }
    if not isinstance(value, dict):
        raise RuntimeError(
            f"Invalid validation profile '{name}': expected a command list or mapping."
        )
    parsed = [
        _command_entry(name, index, item)
        for index, item in enumerate(value.get("commands") or [], start=1)
    ]
    commands = [command for command, _ in parsed]
    clean_tree = value.get("clean-tree", False)
    if not isinstance(clean_tree, bool):
        raise RuntimeError(f"Invalid validation profile '{name}': clean-tree must be true or false.")
    output_limit = value.get("output-limit-bytes")
    if output_limit is not None and (
        isinstance(output_limit, bool) or not isinstance(output_limit, int) or output_limit < MIN_OUTPUT_LIMIT_BYTES
    ):
        raise RuntimeError(
            f"Invalid validation profile '{name}': output-limit-bytes must be an integer "
            f"of at least {MIN_OUTPUT_LIMIT_BYTES}."
        )
    return {
        "commands": commands,
        "entries": [entry for _, entry in parsed],
        "clean-tree": clean_tree,
        "output-limit": output_limit,
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


def _current_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _find_executable(name: str, root: Path, environment: dict[str, str]) -> bool:
    search = next((value for key, value in environment.items() if key.upper() == "PATH"), None)
    if "/" in name or "\\" in name:
        # A path-like name is relative to the project root, where the command runs.
        candidate = Path(name)
        candidate = candidate if candidate.is_absolute() else root / candidate
        return shutil.which(str(candidate), path=search) is not None
    return shutil.which(name, path=search) is not None


def _blocked_reason(
    requires: dict[str, list[str]],
    root: Path,
    environment: dict[str, str],
) -> str | None:
    """Return why a command cannot run in this environment, or ``None`` when it can."""
    reasons: list[str] = []
    platforms = requires.get("platforms")
    if platforms and _current_platform() not in platforms:
        reasons.append(
            f"platform '{_current_platform()}' is not one of: " + ", ".join(platforms)
        )
    for name in requires.get("executables") or []:
        if not _find_executable(name, root, environment):
            reasons.append(f"executable '{name}' was not found on PATH")
    for name in requires.get("env") or []:
        if not environment.get(name):
            reasons.append(f"environment variable '{name}' is not set")
    return "; ".join(reasons) if reasons else None


def _git_output(root: Path, *arguments: str) -> bytes:
    environment = child_environment()
    # A read-only status must not take the index lock or rewrite the index.
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=str(root),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as error:
        raise _TreeUnavailable("the git executable was not found") from error
    except subprocess.TimeoutExpired as error:
        raise _TreeUnavailable("git status did not finish within 120 seconds") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise _TreeUnavailable(
            "the project is not inside a Git work tree"
            if arguments[:1] == ("rev-parse",)
            else "git status failed" + (f": {detail[0]}" if detail else "")
        )
    return completed.stdout


class _TreeUnavailable(Exception):
    """The clean-tree guard cannot observe the working tree."""


def _path_fingerprint(path: Path) -> str:
    """Return a stable content fingerprint so a re-edit of a dirty file is still seen."""
    try:
        if path.is_symlink():
            return "link:" + os.readlink(path)
        if path.is_dir():
            return "dir"
        size = path.stat().st_size
        if size > MAX_FINGERPRINT_BYTES:
            return f"size:{size}"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except OSError:
        return "absent"


def _tree_snapshot(root: Path) -> dict[str, str]:
    """Map every path that Git reports as changed or untracked to its status and content."""
    top = Path(
        _git_output(root, "rev-parse", "--show-toplevel").decode("utf-8", errors="replace").strip()
    )
    try:
        # Validation writes its own evidence here, so that state is not a tree change.
        ignored = state_root(root).resolve().relative_to(top.resolve()).as_posix() + "/"
    except ValueError:
        ignored = None
    output = _git_output(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    tokens = output.decode("utf-8", errors="replace").split("\0")
    snapshot: dict[str, str] = {}
    position = 0
    while position < len(tokens):
        token = tokens[position]
        position += 1
        if len(token) < 4:
            continue
        code, relative = token[:2], token[3:]
        origin = ""
        if "R" in code or "C" in code:
            origin = tokens[position] if position < len(tokens) else ""
            position += 1
        if ignored and (relative + "/").startswith(ignored):
            continue
        snapshot[relative] = f"{code}|{origin}|{_path_fingerprint(top / relative)}"
    return snapshot


def _evaluate_clean_tree(
    root: Path,
    baseline: dict[str, str] | None,
    baseline_reason: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Compare the tree after the run with the baseline; return the record block and a failure."""
    if baseline is None:
        reason = baseline_reason or "the working tree could not be read"
        return {"status": "blocked", "reason": reason}, f"clean-tree guard is blocked: {reason}"
    try:
        after = _tree_snapshot(root)
    except _TreeUnavailable as error:
        reason = f"the working tree could not be read after the run: {error}"
        return {"status": "blocked", "reason": reason}, f"clean-tree guard is blocked: {reason}"
    changed = sorted(
        path for path in set(baseline) | set(after) if baseline.get(path) != after.get(path)
    )
    block: dict[str, Any] = {
        "status": "failed" if changed else "passed",
        "baseline-dirty": bool(baseline),
        "changed-count": len(changed),
        "changed-paths": changed[:MAX_CLEAN_TREE_PATHS],
    }
    if not changed:
        return block, None
    named = ", ".join(changed[:MAX_CLEAN_TREE_PATHS])
    more = len(changed) - MAX_CLEAN_TREE_PATHS
    return block, (
        f"clean-tree guard failed: {len(changed)} path(s) changed during validation: {named}"
        + (f" (and {more} more)" if more > 0 else "")
    )


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
    output_limit: int | None = None,
) -> tuple[int | None, CapturedOutput, CapturedOutput]:
    """Run one command; return its exit code (``None`` after a timeout) and its output.

    Without an ``output_limit`` the output is kept whole; with one, only a head and a
    tail of at most that many bytes per stream are read into memory.
    """
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
        captured = [capture_stream(handle, output_limit, encoding) for handle in (stdout, stderr)]
    return returncode, captured[0], captured[1]


def _log_path(project: Path, evidence_id: str, index: int) -> Path:
    return state_root(project) / "validation" / evidence_id / f"command-{index}.log"


def _write_command_log(path: Path, command: str, stdout: str, stderr: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"$ {redact_text(command)}\n--- stdout ---\n{stdout}"
    if stdout and not stdout.endswith("\n"):
        text += "\n"
    text += f"--- stderr ---\n{stderr}"
    path.write_text(text, encoding="utf-8")


def _write_blocked_log(path: Path, command: str, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"$ {redact_text(command)}\n--- blocked ---\nNot run: {reason}\n",
        encoding="utf-8",
    )


def _captured_tail(value: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(value) <= limit:
        return value
    return "...<truncated>\n" + value[-limit:]


def _output_details(
    stdout: str,
    stderr: str,
    raw_stdout: CapturedOutput,
    raw_stderr: CapturedOutput,
) -> dict[str, Any]:
    """Describe output that did not fit; empty when nothing was cut, so records stay as before."""
    details: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    for name, text, raw in (("stdout", stdout, raw_stdout), ("stderr", stderr, raw_stderr)):
        record_truncated = len(text) > MAX_CAPTURE_CHARS
        if not record_truncated and not raw.truncated:
            continue
        details[f"{name}-head"] = text[:MAX_CAPTURE_CHARS]
        summary[name] = {
            "bytes": raw.total_bytes,
            "lines": raw.total_lines,
            "log-truncated": raw.truncated,
        }
    if summary:
        details["output"] = summary
    return details


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
    entries = list(spec["entries"])
    clean_tree = bool(spec.get("clean-tree"))
    extended = clean_tree or any(not entry["required"] or entry["requires"] for entry in entries)
    resolved_parameters, parameter_definitions = _resolve_validation_parameters(
        profile,
        spec,
        parameters,
    )
    evidence_id = f"{profile}-{uuid.uuid4().hex[:12]}"
    started = datetime.now(timezone.utc).isoformat()
    command_results: list[dict[str, Any]] = []
    failure_reasons: list[str] = []
    warnings = 0
    baseline: dict[str, str] | None = None
    baseline_reason: str | None = None
    if clean_tree and commands:
        try:
            baseline = _tree_snapshot(root)
        except _TreeUnavailable as error:
            baseline_reason = str(error)

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
        entry = entries[index - 1]
        blocked_reason = _blocked_reason(entry["requires"], root, command_environment)
        log_path = _log_path(root, evidence_id, index)
        if blocked_reason is not None:
            _write_blocked_log(log_path, command, blocked_reason)
            row = {
                "index": index,
                "command": command,
                "status": "blocked",
                "exit-code": None,
                "duration-ms": 0,
                "timeout-seconds": command_timeout,
                "log-path": log_path.relative_to(root).as_posix(),
                "stdout": "",
                "stderr": "",
                "reason": blocked_reason,
            }
        else:
            began = time.monotonic()
            exit_code, raw_stdout, raw_stderr = _run_contained(
                prepared_command,
                root,
                command_environment,
                command_timeout,
                spec.get("output-limit"),
            )
            duration_ms = int((time.monotonic() - began) * 1000)

            def scrub(text: str) -> str:
                return _redact_validation_parameter_values(redact_text(text), resolved_parameters)

            stdout = render_output(raw_stdout, scrub)
            stderr = render_output(raw_stderr, scrub)
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
            row.update(_output_details(stdout, stderr, raw_stdout, raw_stderr))
        if not entry["required"]:
            row["required"] = False
        command_results.append(row)
        if row["status"] != "passed":
            if entry["required"]:
                if row["status"] == "blocked":
                    failure_reasons.append(f"command {index} is blocked: {row['reason']}")
                if fail_fast:
                    break
            else:
                warnings += 1

    clean_tree_block: dict[str, Any] | None = None
    if clean_tree and commands:
        clean_tree_block, clean_tree_failure = _evaluate_clean_tree(root, baseline, baseline_reason)
        if clean_tree_failure:
            failure_reasons.append(clean_tree_failure)

    if not commands:
        status = "skipped"
    elif len(command_results) == len(commands) and all(
        item["status"] == "passed" or item.get("required") is False
        for item in command_results
    ) and not failure_reasons:
        status = "passed"
    else:
        status = "failed"

    completed = datetime.now(timezone.utc).isoformat()
    extra: dict[str, Any] = {}
    if extended:
        extra["warnings"] = warnings
    if spec.get("output-limit"):
        extra["output-limit-bytes"] = spec["output-limit"]
    if clean_tree_block is not None:
        extra["clean-tree"] = clean_tree_block
    if failure_reasons:
        extra["failure-reasons"] = failure_reasons
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
            **extra,
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
