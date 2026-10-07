"""Run every EmbrAIon check a project configures, as one command for CI."""

from __future__ import annotations

import argparse
import io
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from .common import project_root
from .policy import read_policy_config


def planned_checks(
    project: Path | None = None,
    *,
    base_ref: str | None = None,
    fail_on: str | None = None,
    all_files: bool | None = None,
) -> list[dict[str, Any]]:
    """Return the checks the project configuration selects, in run order.

    Explicit options override the policy `check` section, which overrides the defaults.
    """
    root = project_root(project)
    policy = read_policy_config(root) if (root / ".embraion" / "policy.yaml").is_file() else {}
    projection = policy.get("projection") or {}
    options = policy.get("check") or {}
    fail_on = fail_on or options.get("fail-on", "high")
    all_files = options.get("all-files", False) if all_files is None else all_files
    checks: list[dict[str, Any]] = [
        {"id": "validate", "argv": ["validate", "--strict"]},
        {"id": "routes", "argv": ["route", "--validate"]},
        {"id": "routing-authority", "argv": ["route", "--audit-authority"]},
    ]
    for host in ("codex", "copilot", "claude-code"):
        components = list((projection.get(host) or {}).get("components") or [])
        if not components:
            continue
        argv = ["projection", "verify", "--host", host, "--json"]
        for component in components:
            argv += ["--component", component]
        if host == "codex" and "config" in components:
            argv += ["--config-mode", (projection.get(host) or {}).get("config-mode", "replace")]
        checks.append({"id": f"projection-{host}", "argv": argv})
    claude = list((projection.get("claude-code") or {}).get("components") or [])
    required = [name for name, component in (("installed", "scoped-agents"), ("hooks", "hooks"))
                if component in claude]
    if required:
        checks.append({"id": "claude-native", "argv": ["claude-native", "status", "--require", ",".join(required)]})
    if (root / ".embraion" / "organization.yaml").is_file():
        argv = ["organization", "check", "--require-config", "--path", ".", "--json"]
        modes = options.get("organization")
        if modes is None:
            # Without a declaration the mode follows the base ref, as before.
            checks.append({"id": "organization", "argv": argv + (["--base-ref", base_ref] if base_ref else [])})
        else:
            if "full" in modes:
                checks.append({"id": "organization-full", "argv": argv})
            if "compare" in modes:
                if base_ref:
                    checks.append({"id": "organization-compare", "argv": argv + ["--base-ref", base_ref]})
                else:
                    checks.append({"id": "organization-compare", "argv": None, "not-run": "needs --base-ref"})
    if (root / ".embraion" / "decisions.yaml").is_file():
        if base_ref:
            checks.append({"id": "decisions", "argv": ["decisions", "check", "--require-config", "--path", ".",
                                                       "--base-ref", base_ref, "--json"]})
        else:
            checks.append({"id": "decisions", "argv": None, "not-run": "needs --base-ref"})
    argv = ["security", "scan", "--path", ".", "--fail-on", fail_on]
    if all_files:
        argv.append("--all-files")
    checks.append({"id": "security", "argv": argv})
    # Project validation profiles run last, so the cheap configuration checks report first.
    for profile in options.get("validation-profiles") or []:
        checks.append({"id": f"validation-{profile}", "argv": ["validation", "run", profile],
                       "validation-profile": profile})
    return checks


def run_validation_step(project: Path, profile: str) -> tuple[int, str, dict[str, Any]]:
    """Run one declared validation profile as `embraion validation run` does.

    Only a `passed` result passes the step. A declared profile must prove something, so `skipped`
    (no commands), failures, timeouts, any other status, and errors such as an unknown profile or a
    required parameter without a default all fail it. Returns the exit code, a text report, and
    the evidence summary for the JSON report.
    """
    from .project_validation import run_validation_profile

    try:
        record = run_validation_profile(profile, project=project)
    except Exception as error:  # noqa: BLE001 - one broken profile must not stop the other checks
        return 2, f"ERROR: {type(error).__name__}: {error}\n", {}
    status = record.get("status")
    lines = [f"Validation profile: {record.get('profile', profile)}", f"Status: {status}"]
    for item in record.get("commands") or []:
        exit_code = "-" if item.get("exit-code") is None else str(item["exit-code"])
        lines.append(f"[{str(item.get('status')).upper()}] {item.get('index')}/{record.get('command-count')} "
                     f"exit={exit_code} {item.get('command')}")
        lines.append(f"  log: {item.get('log-path')}")
        for stream in ("stdout", "stderr"):
            if item.get(stream) and item.get("status") != "passed":
                lines.extend(f"  {line}" for line in item[stream].rstrip().splitlines())
    lines.append(f"Evidence: {record.get('evidence-path')}")
    if status == "skipped":
        lines.append(f"A declared validation profile must run commands, and '{profile}' has none.")
    elif status != "passed":
        lines.append(f"A declared validation profile must pass, and '{profile}' did not.")
    evidence = {"profile": profile, "status": status, "evidence-path": record.get("evidence-path")}
    return (0 if status == "passed" else 1), "\n".join(lines) + "\n", evidence


def run_check(parser: argparse.ArgumentParser, argv: list[str]) -> tuple[int, str]:
    """Run one CLI command in this process and capture its output; any error fails only that check."""
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        try:
            args = parser.parse_args(argv)
            code = int(args.func(args))
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else 2
        except subprocess.CalledProcessError as error:
            print(f"ERROR: {error}")
            code = error.returncode or 2
        except Exception as error:  # noqa: BLE001 - one broken check must not stop the others
            print(f"ERROR: {type(error).__name__}: {error}")
            code = 2
    return code, output.getvalue()
