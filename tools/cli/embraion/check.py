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
    fail_on: str = "high",
    all_files: bool = False,
) -> list[dict[str, Any]]:
    """Return the checks the project configuration selects, in run order."""
    root = project_root(project)
    policy = read_policy_config(root) if (root / ".embraion" / "policy.yaml").is_file() else {}
    projection = policy.get("projection") or {}
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
        if base_ref:
            argv += ["--base-ref", base_ref]
        checks.append({"id": "organization", "argv": argv})
    argv = ["security", "scan", "--path", ".", "--fail-on", fail_on]
    if all_files:
        argv.append("--all-files")
    checks.append({"id": "security", "argv": argv})
    return checks


def run_check(parser: argparse.ArgumentParser, argv: list[str]) -> tuple[int, str]:
    """Run one CLI command in this process and capture its output."""
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        try:
            args = parser.parse_args(argv)
            code = int(args.func(args))
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else 2
        except (RuntimeError, ValueError) as error:
            print(f"ERROR: {error}")
            code = 2
        except subprocess.CalledProcessError as error:
            print(f"ERROR: {error}")
            code = error.returncode or 2
    return code, output.getvalue()
