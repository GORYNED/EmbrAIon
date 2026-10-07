"""Protected-source guard that compares Git object identity against the merge base.

The default protected-path check matches the names of changed files against the policy
of the checked-out tree. This opt-in guard (`enforcement.protected-sources: base-tree`)
reads the protected list from the policy at the merge base instead, and compares what the
patterns match at the merge base and at HEAD by Git object ID, not by file name.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .environment import child_environment
from .policy import normalize_project_path, path_matches

NAME_MODE = "name"
BASE_TREE_MODE = "base-tree"
PROTECTED_SOURCE_MODES = (NAME_MODE, BASE_TREE_MODE)

_POLICY_PATH = ".embraion/policy.yaml"
_GLOB_CHARACTERS = "*?["


class _Failure(Exception):
    """A fail-closed condition; the message is reported as a finding."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        env=child_environment(),
        check=False,
    )


def _git_text(root: Path, *args: str, failure: str) -> str:
    result = _git(root, *args)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or b"").decode("utf-8", "replace").strip()
        raise _Failure(f"{failure}: {detail}" if detail else failure)
    return result.stdout.decode("utf-8", "replace").strip()


def _merge_base(root: Path, base_ref: str) -> str:
    resolved = _git(root, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}")
    if resolved.returncode != 0:
        raise _Failure(f"Cannot resolve the base ref '{base_ref}' to a commit.")
    base_commit = resolved.stdout.decode().strip()
    head = _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if head.returncode != 0:
        raise _Failure("Cannot resolve HEAD to a commit.")
    shallow = _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true"
    found = _git(root, "merge-base", base_commit, "HEAD")
    lines = found.stdout.decode().split()
    if found.returncode != 0 or len(lines) != 1:
        hint = (
            " The repository is shallow; fetch the full history (for example "
            "'fetch-depth: 0') so the merge base is available."
            if shallow
            else ""
        )
        raise _Failure(
            f"No single merge base exists between '{base_ref}' and HEAD.{hint}"
        )
    merge_base = lines[0]
    if shallow:
        # A shallow boundary commit is not proof of the real merge base.
        shallow_file = _git(root, "rev-parse", "--git-path", "shallow").stdout.decode().strip()
        if shallow_file:
            path = Path(shallow_file)
            path = path if path.is_absolute() else root / path
            if path.is_file() and merge_base in path.read_text(encoding="utf-8").split():
                raise _Failure(
                    "The merge base is a shallow-history boundary, so the real merge base "
                    "is unavailable. Fetch the full history (for example 'fetch-depth: 0')."
                )
    return merge_base


def _base_protected_list(root: Path, merge_base: str) -> list[str]:
    result = _git(root, "show", f"{merge_base}:./{_POLICY_PATH}")
    if result.returncode != 0:
        raise _Failure(
            f"The policy at the merge base is unreadable: {_POLICY_PATH} is missing at "
            f"{merge_base[:12]}. The base-tree guard needs a committed policy at the merge base."
        )
    try:
        data = yaml.safe_load(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise _Failure(f"The policy at the merge base cannot be parsed: {error}") from error
    if not isinstance(data, dict):
        raise _Failure("The policy at the merge base is not a mapping.")
    sources = data.get("sources")
    if sources is None:
        return []
    if not isinstance(sources, dict):
        raise _Failure("The policy at the merge base has an unparsable 'sources' block.")
    protected = sources.get("protected")
    if protected is None:
        return []
    if not isinstance(protected, list) or not all(
        isinstance(item, str) and item.strip() for item in protected
    ):
        raise _Failure(
            "The policy at the merge base has an unparsable 'sources.protected' list: "
            "expected a list of non-empty strings."
        )
    return list(protected)


def _normalized(patterns: list[str]) -> list[str]:
    return [normalize_project_path(item) for item in patterns]


def check_base_tree(root: Path, base_ref: str, head_protected: list[str]) -> dict[str, Any]:
    """Return the `protected-sources` gate check for the base-tree mode.

    Every unusable input is a failed check with a clear finding, never a pass.
    """
    findings: list[str] = []
    changed: set[str] = set()
    check: dict[str, Any] = {"id": "protected-sources", "mode": BASE_TREE_MODE}
    try:
        merge_base = _merge_base(root, base_ref)
        check["merge-base"] = merge_base
        base_patterns = _normalized(_base_protected_list(root, merge_base))
        head_patterns = _normalized(head_protected)
        for pattern in base_patterns:
            if pattern not in head_patterns:
                findings.append(
                    f"Protected entry '{pattern}' was removed or narrowed in the head "
                    "policy. Keep the base entry and add a new entry beside it."
                )
    except _Failure as failure:
        findings.append(str(failure))
    check["status"] = "failed" if findings else "passed"
    check["changed-paths"] = sorted(changed)
    check["findings"] = findings
    return check
