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
    # A shallow clone cannot prove which commit is the real merge base: a merge base found
    # above the cut-off may still be older than the true one. Fail closed on any shallow repository.
    if _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true":
        raise _Failure(
            "The repository is shallow, so the merge base cannot be proven. Fetch the full "
            "history (for example 'fetch-depth: 0' in CI)."
        )
    found = _git(root, "merge-base", "--all", base_commit, "HEAD")
    lines = found.stdout.decode().split()
    if found.returncode != 0 or not lines:
        raise _Failure(f"No single merge base exists between '{base_ref}' and HEAD.")
    if len(lines) > 1:
        raise _Failure(
            f"No single merge base exists between '{base_ref}' and HEAD: the history has "
            f"{len(lines)} equally good merge bases (a criss-cross merge). Merge the base "
            "ref into the branch first."
        )
    return lines[0]


def _base_policy(root: Path, merge_base: str) -> dict[str, Any]:
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
    return data


def base_policy_mode(root: Path, base_ref: str) -> str | None:
    """Read the proven base mode; only a missing legacy policy or mode returns None.

    An unprovable base or malformed existing policy must not silently select the weaker mode.
    """
    try:
        merge_base = _merge_base(root, base_ref)
        entry = _git(root, "ls-tree", "-z", merge_base, "--", f"./{_POLICY_PATH}")
        if entry.returncode != 0:
            raise _Failure("Cannot inspect the policy entry at the merge base.")
        if not entry.stdout:
            return None
        data = _base_policy(root, merge_base)
        enforcement = data.get("enforcement")
        if enforcement is None:
            return None
        if not isinstance(enforcement, dict):
            raise _Failure("The policy at the merge base has an unparsable 'enforcement' block.")
        mode = enforcement.get("protected-sources")
        if mode is not None and mode not in PROTECTED_SOURCE_MODES:
            raise _Failure("The policy at the merge base has an unknown protected-sources mode.")
        return mode
    except _Failure as error:
        raise RuntimeError(f"Cannot determine the protected-sources mode: {error}") from error


def _base_protected_list(root: Path, merge_base: str) -> list[str]:
    data = _base_policy(root, merge_base)
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


def _read_tree(root: Path, revision: str) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Return (files, trees) of a revision: path -> (mode, object ID) and path -> tree object ID."""
    result = _git(root, "ls-tree", "-r", "-t", "-z", revision)
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise _Failure(f"Cannot list the tree of {revision[:12]}: {detail}")
    files: dict[str, tuple[str, str]] = {}
    trees: dict[str, str] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        meta, _, name = record.partition(b"\t")
        try:
            mode, kind, oid = meta.decode("ascii").split(" ")
        except ValueError as error:
            raise _Failure(f"Unreadable tree entry at {revision[:12]}.") from error
        path = os.fsdecode(name)
        if kind == "tree":
            trees[path] = oid
        else:
            files[path] = (mode, oid)
    return files, trees


def _literal_prefix(pattern: str) -> str:
    cut = min((pattern.find(char) for char in _GLOB_CHARACTERS if char in pattern), default=len(pattern))
    return pattern[:cut]


def _matching(files: dict[str, tuple[str, str]], pattern: str) -> dict[str, tuple[str, str]]:
    prefix = _literal_prefix(pattern)
    return {
        path: value
        for path, value in files.items()
        if path.startswith(prefix) and path_matches(path, [pattern])
    }


def _directory_root(pattern: str) -> str | None:
    """Return the literal directory of a `<directory>/**` pattern, else None."""
    if not pattern.endswith("/**"):
        return None
    directory = pattern[:-3]
    if not directory or any(char in directory for char in _GLOB_CHARACTERS):
        return None
    return directory.rstrip("/") or None


def _relocation_target(
    directory: str,
    base_files: dict[str, tuple[str, str]],
    base_trees: dict[str, str],
    head_trees: dict[str, str],
    head_patterns: list[str],
) -> str | None:
    """Return the new location of a directory whose tree object ID is unchanged, if protected."""
    tree = base_trees.get(directory)
    if tree is None or directory in head_trees:
        return None
    relative = [path[len(directory) + 1:] for path in base_files if path.startswith(directory + "/")]
    # The target must be new: an identical directory that already existed elsewhere at the
    # merge base would make a plain deletion look like a move.
    candidates = sorted(
        path for path, oid in head_trees.items()
        if oid == tree and path != directory and path not in base_trees
    )
    for target in candidates:
        if all(path_matches(f"{target}/{item}", head_patterns) for item in relative):
            return target
    return None


def _summarize(base: dict[str, tuple[str, str]], head: dict[str, tuple[str, str]]) -> tuple[list[str], str]:
    modified = sorted(path for path in base.keys() & head.keys() if base[path] != head[path])
    added = sorted(head.keys() - base.keys())
    deleted = sorted(base.keys() - head.keys())
    summary = f"{len(modified)} modified, {len(added)} added, {len(deleted)} deleted"
    return sorted({*modified, *added, *deleted}), summary


def _uncommitted_paths(root: Path) -> list[str]:
    tracked = _git(root, "diff", "--name-only", "-z", "--no-renames", "--relative", "HEAD")
    untracked = _git(root, "ls-files", "-z", "--others", "--exclude-standard")
    if tracked.returncode != 0 or untracked.returncode != 0:
        raise _Failure("Cannot inspect uncommitted changes in the working tree.")
    return sorted(
        {os.fsdecode(item) for item in tracked.stdout.split(b"\0") + untracked.stdout.split(b"\0") if item}
    )


def check_base_tree(root: Path, base_ref: str, head_protected: list[str]) -> dict[str, Any]:
    """Return the `protected-sources` gate check for the base-tree mode.

    Every unusable input is a failed check with a clear finding, never a pass.
    """
    findings: list[str] = []
    changed: set[str] = set()
    relocated: list[dict[str, str]] = []
    check: dict[str, Any] = {"id": "protected-sources", "mode": BASE_TREE_MODE}
    try:
        merge_base = _merge_base(root, base_ref)
        check["merge-base"] = merge_base
        base_patterns = _normalized(_base_protected_list(root, merge_base))
        head_patterns = _normalized(head_protected)
        base_files, base_trees = _read_tree(root, merge_base)
        head_files, head_trees = _read_tree(root, "HEAD")
        moved_entries: set[str] = set()
        for pattern in base_patterns:
            before = _matching(base_files, pattern)
            after = _matching(head_files, pattern)
            if before == after:
                continue
            paths, summary = _summarize(before, after)
            directory = _directory_root(pattern)
            target = None
            if directory is not None and before and not after:
                target = _relocation_target(directory, before, base_trees, head_trees, head_patterns)
            if target is not None:
                relocated.append({"from": directory, "to": target})
                moved_entries.add(pattern)
                continue
            changed.update(paths)
            findings.append(
                f"Protected entry '{pattern}' differs from the merge base ({summary}). "
                "Only a complete, byte-identical move of a whole directory to another "
                "protected location is allowed."
            )
        for pattern in base_patterns:
            if pattern not in head_patterns and pattern not in moved_entries:
                findings.append(
                    f"Protected entry '{pattern}' was removed or narrowed in the head "
                    "policy. Keep the base entry and add a new entry beside it."
                )
        # Uncommitted edits are not part of HEAD, so they are matched by name.
        union = list(dict.fromkeys(base_patterns + head_patterns))
        for path in _uncommitted_paths(root):
            if path_matches(path, union):
                changed.add(path)
                findings.append(
                    f"Uncommitted change to protected path '{path}'. Commit it so its "
                    "content can be compared with the merge base."
                )
    except (_Failure, RuntimeError) as failure:
        findings.append(str(failure))
    check["status"] = "failed" if findings else "passed"
    check["changed-paths"] = sorted(changed)
    check["findings"] = findings
    if relocated:
        check["relocated"] = relocated
    return check
