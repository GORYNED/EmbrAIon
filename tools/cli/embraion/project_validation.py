from __future__ import annotations

import hashlib
import math
import locale
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
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
from .validation_process import (
    GRACE_SECONDS, VERIFY_SECONDS, ContainmentUnavailable, close_containment,
    containment_quiescent, spawn_contained, terminate_tree,
)
from .validation_output import CapturedOutput, capture_stream, render_output


MAX_CAPTURE_CHARS = 8000
MAX_CLEAN_TREE_PATHS = 20
MIN_OUTPUT_LIMIT_BYTES = 1024
MAX_FINGERPRINT_BYTES = 64 * 1024 * 1024
RUN_ID_ENVIRONMENT = "EMBRAION_RUN_ID"
TERMINATION_GRACE_SECONDS = GRACE_SECONDS
_GIT_LOCATION_VARIABLES = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX",
})


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
    for name in _GIT_LOCATION_VARIABLES:
        environment.pop(name, None)
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
        suffix = f": {detail[0]}" if detail else ""
        raise _TreeUnavailable(
            "the project is not inside a Git work tree, or Git refused to read it" + suffix
            if arguments[:1] == ("rev-parse",)
            else "git status failed" + suffix
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
    lock = _git_output(root, "rev-parse", "--path-format=absolute", "--git-path", "index.lock")
    lock_path = lock.decode("utf-8", errors="replace").strip()
    if not lock_path:
        raise _TreeUnavailable("the worktree index lock state could not be read")
    if Path(lock_path).exists():
        raise _TreeUnavailable("the worktree index is locked")
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
    baseline_head: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Compare the tree after the run with the baseline; return the record block and a failure."""
    if baseline is None:
        reason = baseline_reason or "the working tree could not be read"
        return {"status": "blocked", "reason": reason}, f"clean-tree guard is blocked: {reason}"
    try:
        after = _tree_snapshot(root)
        after_head = _git_output(root, "rev-parse", "--verify", "HEAD").decode("ascii", "replace").strip()
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
    head_changed = baseline_head != after_head
    if head_changed:
        block["status"] = "failed"
        block["head-changed"] = True
    if not changed:
        if head_changed:
            return block, "clean-tree guard failed: HEAD changed during validation"
        return block, None
    named = ", ".join(changed[:MAX_CLEAN_TREE_PATHS])
    more = len(changed) - MAX_CLEAN_TREE_PATHS
    return block, (
        f"clean-tree guard failed: {len(changed)} path(s) changed during validation: {named}"
        + (f" (and {more} more)" if more > 0 else "")
        + ("; HEAD changed" if head_changed else "")
    )


def _spawn_contained(command: str | list[str], cwd: Path, environment: dict[str, str], stdout: Any, stderr: Any) -> subprocess.Popen:
    """Start only after the process container is established."""
    return spawn_contained(command, cwd, environment, stdout, stderr)


def _wait_for(process: subprocess.Popen, timeout: float | None) -> int:
    return process.wait(timeout=timeout)


def _terminate_tree(process: subprocess.Popen) -> bool:
    """End the command's whole process tree; return whether its end is confirmed."""
    return terminate_tree(process)


def _run_contained(
    command: str | list[str],
    cwd: Path,
    environment: dict[str, str],
    timeout: float | None,
    output_limit: int | None = None,
    capture_bytes: int | None = None,
) -> tuple[int | None, CapturedOutput, CapturedOutput, str | None, str | None, dict[str, Any]]:
    """Run one command; return its exit code (``None`` after a timeout) and its output.

    Termination is recorded after a timeout or a root exit with surviving descendants.
    The final item identifies a containment or supervisor failure separately.

    Without an ``output_limit`` the output is kept whole; with one, only a head and a
    tail of at most that many bytes per stream are read into memory.
    """
    # Drain both pipes while the command runs, so a child cannot block on a full
    # pipe. EOF also proves no escaped descendant retains an output handle.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        lifecycle: dict[str, Any] = {
            "process-id": None, "target-process-id": None,
            "containment-kind": "windows-job" if os.name == "nt" else "posix-process-group",
            "containment-established": False, "root-exit-confirmed": False,
            "process-tree-termination-confirmed": False, "streams-drained": False,
            "recovery-attempted": False, "descendant-processes-detected": None,
            "timed-out": False, "safe-to-continue": False,
        }
        try:
            process = _spawn_contained(command, cwd, environment, subprocess.PIPE, subprocess.PIPE)
        except ContainmentUnavailable as error:
            termination = None if error.termination_confirmed else "unconfirmed"
            lifecycle["process-tree-termination-confirmed"] = error.termination_confirmed
            return None, CapturedOutput(), CapturedOutput(), termination, "containment-unavailable", lifecycle
        lifecycle["process-id"] = process.pid
        lifecycle["target-process-id"] = process.pid if os.name != "nt" and isinstance(command, list) else None
        lifecycle["containment-established"] = True
        stream_errors: list[OSError] = []
        totals = [0, 0]
        newlines = [0, 0]
        last_bytes = [b"", b""]

        def drain(source: Any, destination: Any, index: int) -> None:
            try:
                while chunk := source.read(1 << 16):
                    totals[index] += len(chunk)
                    newlines[index] += chunk.count(b"\n")
                    last_bytes[index] = chunk[-1:]
                    remaining = None if capture_bytes is None else max(capture_bytes - destination.tell(), 0)
                    if remaining is None or remaining:
                        destination.write(chunk if remaining is None else chunk[:remaining])
            except (OSError, ValueError) as error:
                stream_errors.append(error)

        sources = (process.stdout, process.stderr)
        streams = [threading.Thread(target=drain, args=(source, destination, index), daemon=True)
                   for index, (source, destination) in enumerate(zip(sources, (stdout, stderr)))]
        try:
            for stream in streams:
                stream.start()
        except RuntimeError:
            lifecycle["recovery-attempted"] = True
            try:
                _terminate_tree(process)
            finally:
                close_containment(process)
            return None, CapturedOutput(), CapturedOutput(), "unconfirmed", "containment-unavailable", lifecycle
        termination: str | None = None
        failure_kind: str | None = None
        try:
            try:
                returncode: int | None = _wait_for(process, timeout)
                lifecycle["root-exit-confirmed"] = True
                try:
                    descendants = not containment_quiescent(process)
                    lifecycle["descendant-processes-detected"] = descendants
                except (OSError, RuntimeError):
                    descendants = True
                    failure_kind = "containment-unavailable"
                if descendants:
                    lifecycle["recovery-attempted"] = True
                    failure_kind = failure_kind or "descendant-process"
                    try:
                        termination = "confirmed" if _terminate_tree(process) else "unconfirmed"
                    except Exception:
                        termination = "unconfirmed"
                else:
                    lifecycle["process-tree-termination-confirmed"] = True
            except subprocess.TimeoutExpired:
                lifecycle["timed-out"] = True
                lifecycle["recovery-attempted"] = True
                try:
                    termination = "confirmed" if _terminate_tree(process) else "unconfirmed"
                except Exception:
                    termination = "unconfirmed"
                returncode = None
            except (OSError, subprocess.SubprocessError):
                failure_kind = "supervisor-failure"
                lifecycle["recovery-attempted"] = True
                try:
                    termination = "confirmed" if _terminate_tree(process) else "unconfirmed"
                except Exception:
                    termination = "unconfirmed"
                returncode = None
            except BaseException:
                _terminate_tree(process)
                raise
        finally:
            try:
                close_containment(process)
            except OSError:
                termination = "unconfirmed"
                failure_kind = "containment-unavailable"
        if termination is not None:
            lifecycle["root-exit-confirmed"] = process.poll() is not None
            lifecycle["process-tree-termination-confirmed"] = termination == "confirmed"
        for stream in streams:
            stream.join(timeout=VERIFY_SECONDS)
        for source, stream in zip(sources, streams):
            if not stream.is_alive():
                try:
                    source.close()
                except OSError as error:
                    stream_errors.append(error)
        if stream_errors or any(stream.is_alive() for stream in streams):
            termination = "unconfirmed"
            failure_kind = "stream-drain-failure"
            lifecycle["streams-drained"] = False
            lifecycle["safe-to-continue"] = False
            return returncode, CapturedOutput(), CapturedOutput(), termination, failure_kind, lifecycle
        lifecycle["streams-drained"] = True
        lifecycle["safe-to-continue"] = (
            lifecycle["containment-established"] and lifecycle["root-exit-confirmed"]
            and lifecycle["process-tree-termination-confirmed"] and lifecycle["streams-drained"]
        )
        # Text-mode subprocess output used the locale encoding; keep that decoding.
        encoding = locale.getpreferredencoding(False)
        if capture_bytes is None:
            captured = [capture_stream(handle, output_limit, encoding) for handle in (stdout, stderr)]
        else:
            captured = []
            for index, handle in enumerate((stdout, stderr)):
                handle.seek(0)
                retained = handle.read()
                kept_lines = retained.count(b"\n") + bool(retained and not retained.endswith(b"\n"))
                total_lines = newlines[index] + bool(totals[index] and last_bytes[index] != b"\n")
                captured.append(CapturedOutput(
                    head=retained.decode("utf-8", "replace"), total_bytes=totals[index],
                    total_lines=total_lines, omitted_bytes=totals[index] - len(retained),
                    omitted_lines=max(total_lines - kept_lines, 0),
                ))
    return returncode, captured[0], captured[1], termination, failure_kind, lifecycle


_COMMAND_REQUEST_KEYS = {
    "executable", "argv", "cwd", "env", "timeout_seconds", "output_limit_bytes",
    "stdout_path", "stderr_path",
}


def _command_error(kind: str, reason: str) -> dict[str, Any]:
    return {
        "schema-version": 1, "succeeded": False, "failure-kind": kind, "reason": reason,
        "exit-code": None, "duration-ms": 0, "process-id": None,
        "target-process-id": None, "containment-kind": None,
        "containment-established": False, "root-exit-confirmed": False,
        "process-tree-termination-confirmed": False, "streams-drained": False,
        "recovery-attempted": False, "descendant-processes-detected": None,
        "timed-out": False, "safe-to-continue": False,
        "stdout-bytes": 0, "stderr-bytes": 0,
        "stdout-truncated": False, "stderr-truncated": False,
    }


def _validate_command_request(request: Any) -> tuple[list[str], Path, dict[str, str], float, int, tuple[Path | None, Path | None], list[str]]:
    if not isinstance(request, dict) or set(request) - _COMMAND_REQUEST_KEYS:
        raise ValueError("request must be an object with only documented fields")
    executable = request.get("executable")
    argv = request.get("argv")
    cwd_value = request.get("cwd")
    timeout = request.get("timeout_seconds")
    limit = request.get("output_limit_bytes", 1024 * 1024)
    if not isinstance(executable, str) or not executable or "\x00" in executable:
        raise ValueError("executable must be a nonempty string")
    if not isinstance(argv, list) or any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise ValueError("argv must be an array of strings")
    if not isinstance(cwd_value, str) or not Path(cwd_value).is_absolute():
        raise ValueError("cwd must be an absolute directory path")
    cwd = Path(cwd_value)
    if not cwd.is_dir():
        raise ValueError("cwd must exist as a directory")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400 or not math.isfinite(timeout):
        raise ValueError("timeout_seconds must be greater than zero and at most 86400")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 16 * 1024 * 1024:
        raise ValueError("output_limit_bytes must be between 1 and 16777216")
    delta = request.get("env", {})
    if not isinstance(delta, dict):
        raise ValueError("env must be an object of environment name to string or null")
    environment = child_environment()
    # A child can echo inherited values and argv just as readily as a delta.
    # Include parent values removed by resolver filtering or an env null delta:
    # omitting a value from the child environment is not proof it is absent from output.
    secrets = [value for value in os.environ.values() if value]
    for name, value in delta.items():
        if not isinstance(name, str) or not name or "=" in name or "\x00" in name:
            raise ValueError("env contains an invalid name")
        if value is None:
            environment.pop(name, None)
        elif isinstance(value, str) and "\x00" not in value:
            environment[name] = value
            if value:
                secrets.append(value)
        else:
            raise ValueError("env values must be strings or null")
    paths: list[Path | None] = []
    for key in ("stdout_path", "stderr_path"):
        raw = request.get(key)
        if raw is None:
            paths.append(None)
            continue
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ValueError(f"{key} must be an absolute path")
        path = Path(raw)
        if not path.parent.is_dir() or path.exists() or path.is_symlink():
            raise ValueError(f"{key} parent must exist and target must not exist")
        # A system alias such as macOS /var -> /private/var is acceptable only
        # after resolving its existing parent to a concrete destination.
        canonical_parent = path.parent.resolve(strict=True)
        cursor = canonical_parent
        while True:
            if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
                raise ValueError(f"{key} must not traverse a link")
            if cursor == cursor.parent:
                break
            cursor = cursor.parent
        path = canonical_parent / path.name
        if path.exists() or path.is_symlink():
            raise ValueError(f"{key} target must not exist")
        paths.append(path)
    if paths[0] is not None and paths[1] is not None and os.path.normcase(str(paths[0])) == os.path.normcase(str(paths[1])):
        raise ValueError("stdout_path and stderr_path must differ")
    resolved = executable if Path(executable).is_absolute() else shutil.which(executable, path=environment.get("PATH"))
    if not resolved or not Path(resolved).is_file():
        raise ValueError("executable could not be resolved to a file")
    # abspath fixes relative PATH entries against the supervisor's cwd without
    # requiring reparse-point traversal, which may be denied for valid files.
    resolved = os.path.abspath(resolved)
    if os.name == "nt" and Path(resolved).suffix.lower() in {".bat", ".cmd"}:
        raise ValueError("Windows batch files cannot preserve exact argv without a command shell")
    secrets.extend(value for value in environment.values() if value)
    secrets.extend(value for value in (executable, str(resolved), *argv) if value)
    return [str(resolved), *argv], cwd, environment, float(timeout), limit, (paths[0], paths[1]), secrets


def _scrub_command_output(value: str, secrets: list[str]) -> str:
    for secret in sorted(set(secrets), key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    return redact_text(value)


def _render_command_log(captured: CapturedOutput, secrets: list[str], limit: int) -> tuple[str, bool]:
    if captured.truncated:
        # A byte boundary can bisect a Unicode secret, token, or armored key.
        # No retained prefix is safe to persist without the complete output.
        return f"[... output truncated: {captured.total_bytes} bytes; content omitted ...]", True
    content = _scrub_command_output(captured.head, secrets)
    encoded = content.encode("utf-8")
    redaction_clipped = len(encoded) > limit
    if redaction_clipped:
        content = encoded[:limit].decode("utf-8", "ignore")
    if redaction_clipped:
        content += "\n[... redacted output clipped to byte limit ...]"
    return content, redaction_clipped


def run_validation_command(request: Any) -> dict[str, Any]:
    """Run exactly one argv command; return a bounded, machine-readable lifecycle."""
    try:
        command, cwd, environment, timeout, limit, paths, secrets = _validate_command_request(request)
    except (OSError, ValueError) as error:
        return _command_error("invalid-request", str(error))

    handles = []
    try:
        for path in paths:
            if path is None:
                handles.append(None)
            else:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(path, flags, 0o600)
                try:
                    handles.append(os.fdopen(descriptor, "w", encoding="utf-8", newline=""))
                except OSError:
                    os.close(descriptor)
                    path.unlink(missing_ok=True)
                    raise
    except OSError:
        for handle in handles:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        for path, handle in zip(paths, handles):
            if path is not None and handle is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        return _command_error("log-path-unavailable", "output log could not be created exclusively")

    began = time.monotonic()
    result = _command_error("supervisor-failure", "process supervision failed")
    try:
        exit_code, stdout, stderr, termination, failure_kind, lifecycle = _run_contained(
            command, cwd, environment, timeout, capture_bytes=limit,
        )
        result = _command_error("", "")
        result.update(lifecycle)
        result.update({
            "exit-code": exit_code, "duration-ms": int((time.monotonic() - began) * 1000),
            "stdout-bytes": stdout.total_bytes, "stderr-bytes": stderr.total_bytes,
            "stdout-truncated": stdout.truncated, "stderr-truncated": stderr.truncated,
        })
        rendered = [_render_command_log(item, secrets, limit) for item in (stdout, stderr)]
        result["stdout-truncated"], result["stderr-truncated"] = rendered[0][1], rendered[1][1]
        try:
            for handle, (output, _) in zip(handles, rendered):
                if handle is not None:
                    handle.write(output)
                    handle.flush()
        except OSError:
            failure_kind = "log-write-failure"
        if not result["safe-to-continue"] or termination == "unconfirmed":
            failure_kind = failure_kind or "unconfirmed-termination"
        elif failure_kind is None and exit_code is None:
            failure_kind = "timeout"
        elif failure_kind is None and exit_code != 0:
            failure_kind = "nonzero-exit"
        elif failure_kind is None and (result["stdout-truncated"] or result["stderr-truncated"]):
            failure_kind = "output-truncated"
        result["failure-kind"] = failure_kind
        result["reason"] = failure_kind or ""
        result["succeeded"] = failure_kind is None and exit_code == 0
        if failure_kind == "log-write-failure":
            result["safe-to-continue"] = False
    except Exception:
        # Do not infer that a child stopped when supervision itself failed.
        result = _command_error("supervisor-failure", "process supervision failed")
        result["duration-ms"] = int((time.monotonic() - began) * 1000)
    finally:
        for handle in handles:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    result["succeeded"] = False
                    result["safe-to-continue"] = False
                    result["failure-kind"] = "log-write-failure"
                    result["reason"] = "log-write-failure"
    return result


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
    baseline_head: str | None = None
    if clean_tree and commands:
        try:
            baseline = _tree_snapshot(root)
            baseline_head = _git_output(root, "rev-parse", "--verify", "HEAD").decode("ascii", "replace").strip()
        except _TreeUnavailable as error:
            baseline = None
            baseline_reason = str(error)

    for index, command in enumerate(commands, start=1):
        if clean_tree and baseline is None:
            break  # Unknown tree state cannot authorize even the first command.
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
            exit_code, raw_stdout, raw_stderr, termination, failure_kind, _lifecycle = _run_contained(
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
            if failure_kind in {"containment-unavailable", "stream-drain-failure"}:
                status = "blocked"
            elif failure_kind in {"descendant-process", "supervisor-failure"}:
                status = "failed"
            elif exit_code is None:
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
            if termination is not None:
                row["termination"] = termination
            if failure_kind is not None:
                row["reason"] = {
                    "containment-unavailable": "process containment could not be confirmed",
                    "descendant-process": "root exited while descendants remained alive",
                    "supervisor-failure": "process wait failed",
                    "stream-drain-failure": "redirected output streams did not close",
                }[failure_kind]
        if not entry["required"]:
            row["required"] = False
        command_results.append(row)
        if row.get("termination") == "unconfirmed":
            # Stray processes may still run, so the profile fails and nothing else starts.
            failure_reasons.append(
                f"command {index} ended and its process tree could not be confirmed "
                "terminated; processes may still be running"
            )
            break
        if row.get("reason") in {"process containment could not be confirmed", "process wait failed",
                                 "redirected output streams did not close"}:
            failure_reasons.append(f"command {index} is blocked: {row['reason']}")
            break
        if row.get("reason") == "root exited while descendants remained alive":
            failure_reasons.append(f"command {index} left descendants after its root exited")
            break
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
        clean_tree_block, clean_tree_failure = _evaluate_clean_tree(root, baseline, baseline_reason, baseline_head)
        if clean_tree_failure:
            failure_reasons.append(clean_tree_failure)

    skip_reason: str | None = None
    if not commands:
        status = "skipped"
    elif len(command_results) == len(commands) and all(
        item["status"] == "passed" or item.get("required") is False
        for item in command_results
    ) and not failure_reasons:
        status = "passed"
        if not any(item["status"] == "passed" for item in command_results):
            # Optional commands that were blocked or failed prove nothing: never a pass.
            status = "skipped"
            skip_reason = "every command is optional and none passed"
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
    if skip_reason:
        extra["skip-reason"] = skip_reason
    if plan is not None:
        from .validation_plan import write_plan_evidence

        plan_path = write_plan_evidence(root, evidence_id, plan)
        extra["plan"] = plan
        extra["plan-path"] = plan_path
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
