"""Shared, fail-closed provenance for EmbrAIon-created Git resources."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from jsonschema import Draft202012Validator

from .common import framework_root, run, write_json


_HEX_SHA = re.compile(r"[0-9a-fA-F]{40,64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _safe_components(path: Path, *, allow_missing: bool = False) -> Path:
    """Reject links and junctions at every existing metadata path component."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("metadata path must be absolute without parent traversal")
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if allow_missing:
                continue
            raise ValueError("metadata path is missing") from None
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT):
            raise ValueError("metadata path contains a link or junction")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("metadata path component is not a directory")
    return path


def _safe_file(path: Path, *, allow_missing: bool = False) -> bool:
    _safe_components(path.parent, allow_missing=allow_missing)
    try:
        info = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return False
        raise ValueError("metadata file is missing") from None
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT):
        raise ValueError("metadata file is linked or not regular")
    return True


def _read_file(path: Path) -> bytes:
    _safe_file(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_ino != path.lstat().st_ino:
            raise ValueError("metadata file changed during read")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _schema() -> dict[str, Any]:
    path = framework_root() / "schemas" / "worktree-registry.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _validate_registry(data: Any) -> dict[str, Any]:
    errors = list(Draft202012Validator(_schema()).iter_errors(data))
    if errors:
        raise ValueError("invalid worktree registry")
    if any(not _ID.fullmatch(key) for key in data["receipts"]):
        raise ValueError("invalid worktree receipt id")
    if any(not _ID.fullmatch(key) or resource["resource-id"] != key
           for key, resource in data["resources"].items()):
        raise ValueError("invalid worktree resource id")
    return data


def _validate_resource(resource: Any) -> bool:
    try:
        schema = _schema()["properties"]["resources"]["additionalProperties"]
        return (isinstance(resource, dict)
                and not list(Draft202012Validator(schema).iter_errors(resource))
                and bool(_ID.fullmatch(resource["resource-id"])))
    except (KeyError, OSError, ValueError):
        return False


def git_value(repo: Path, *args: str) -> str:
    return run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo), *args]).stdout.strip()


def common_dir(repo: Path) -> Path:
    path = Path(git_value(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return _safe_components(path)


def registry_dir(repo: Path) -> Path:
    directory = common_dir(repo) / "embraion" / "worktrees"
    return _safe_components(directory, allow_missing=True)


def empty_registry() -> dict[str, Any]:
    return {"schema-version": 2, "receipts": {}, "resources": {}, "tasks": {}}


def load_registry(repo: Path) -> dict[str, Any]:
    path = registry_dir(repo) / "registry.json"
    if not _safe_file(path, allow_missing=True):
        return empty_registry()
    return _validate_registry(json.loads(_read_file(path)))


@contextmanager
def registry_lock(repo: Path) -> Iterator[Path]:
    directory = registry_dir(repo)
    directory.mkdir(parents=True, exist_ok=True)
    _safe_components(directory)
    lock = directory / "registry.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    identity = os.fstat(descriptor).st_ino
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()} utc={timestamp()}\n")
        yield directory
    finally:
        # Never remove another process's replacement lock.
        if _safe_file(lock, allow_missing=True) and lock.lstat().st_ino == identity:
            lock.unlink()


def save_registry(repo: Path, data: dict[str, Any]) -> None:
    _validate_registry(data)
    path = registry_dir(repo) / "registry.json"
    _safe_file(path, allow_missing=True)
    write_json(path, data)


def new_id() -> str:
    return uuid4().hex


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _branch_ref(branch: str) -> str:
    if (not isinstance(branch, str) or not branch or branch.startswith("-")
            or ".." in branch or "\\" in branch or branch.startswith("/")
            or branch.endswith("/") or "//" in branch):
        raise ValueError("invalid branch name")
    result = run(["git", "check-ref-format", f"refs/heads/{branch}"], check=False)
    if result.returncode:
        raise ValueError("invalid branch name")
    return f"refs/heads/{branch}"


def _direct_branch_ref(repo: Path, branch: str) -> str:
    """Reject symbolic refs and filesystem aliases before reading or writing."""
    ref = _branch_ref(branch)
    directory = common_dir(repo)
    _safe_file(directory / "packed-refs", allow_missing=True)
    _safe_file(directory / Path(ref), allow_missing=True)
    symbolic = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                    "-C", str(repo), "symbolic-ref", "--quiet", ref], check=False)
    # Git returns 1 for an ordinary direct ref (including an absent new ref).
    # A symbolic ref returns 0; any other error is unknown ownership.
    if symbolic.returncode != 1:
        raise ValueError("branch ref is symbolic or unknown")
    return ref


def branch_sha(repo: Path, branch: str) -> str | None:
    ref = _direct_branch_ref(repo, branch)
    result = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo),
                  "rev-parse", "--verify", f"{ref}^{{commit}}"], check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def gitdir(path: Path) -> Path:
    return _safe_components(Path(git_value(path, "rev-parse", "--absolute-git-dir")))


def _reflog_path(repo: Path, branch: str) -> Path:
    _branch_ref(branch)
    return common_dir(repo) / "logs" / "refs" / "heads" / Path(branch)


def _first_reflog(repo: Path, branch: str) -> bytes:
    return _read_file(_reflog_path(repo, branch)).splitlines(keepends=True)[0]


def branch_creation_identity(repo: Path, branch: str, receipt_id: str, base_sha: str) -> str:
    """Bind a newly created branch to its unique first reflog entry."""
    if not _ID.fullmatch(receipt_id) or not _HEX_SHA.fullmatch(base_sha):
        raise ValueError("invalid branch creation receipt")
    first = _first_reflog(repo, branch)
    fields = first.split(b" ", 2)
    if (len(fields) != 3 or fields[0] != b"0" * len(base_sha)
            or fields[1].lower() != base_sha.lower().encode()
            or first.split(b"\t", 1)[-1].rstrip(b"\r\n") != f"embraion-create:{receipt_id}".encode()):
        raise ValueError("branch creation reflog does not match receipt")
    return hashlib.sha256(first).hexdigest()


def mark_branch(repo: Path, resource_id: str, branch: str, base_sha: str) -> str:
    """Record the first reflog entry for this branch incarnation."""
    if not _ID.fullmatch(resource_id) or not _HEX_SHA.fullmatch(base_sha):
        raise ValueError("invalid resource marker")
    if branch_sha(repo, branch) != base_sha:
        raise ValueError("branch changed before registration")
    return hashlib.sha256(_first_reflog(repo, branch)).hexdigest()


def mark_resource(path: Path, resource_id: str, repository_common_dir: Path) -> None:
    """Create an immutable identity marker in the linked worktree's Git directory."""
    if not _ID.fullmatch(resource_id):
        raise ValueError("invalid resource id")
    _safe_components(path)
    metadata = gitdir(path)
    common = _safe_components(repository_common_dir)
    if common_dir(path) != common:
        raise ValueError("worktree belongs to a different repository")
    marker = metadata / "embraion-resource.json"
    content = {"schema-version": 1, "resource-id": resource_id,
               "gitdir": str(metadata), "common-dir": str(common)}
    descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(content, stream, sort_keys=True)
        stream.write("\n")


def verify_resource(repo: Path, resource: dict[str, Any]) -> bool:
    """A reused path or branch never inherits registry ownership."""
    try:
        if not _validate_resource(resource):
            return False
        common = common_dir(repo)
        if resource["common-dir"] != str(common):
            return False
        branch = resource["branch"]
        if branch is not None:
            if branch_sha(repo, branch) is None:
                return False
            first_id = hashlib.sha256(_first_reflog(repo, branch)).hexdigest()
            if resource.get("branch-reflog-id") != first_id:
                return False
            creation_id = resource.get("creation-reflog-id")
            if resource["creation-source"] == "embraion-create":
                if not isinstance(creation_id, str) or first_id != creation_id:
                    return False
        elif resource.get("creation-reflog-id") is not None or resource.get("branch-reflog-id") is not None:
            return False
        if resource["kind"] == "branch":
            return resource["path"] is None and resource["gitdir"] is None and branch is not None
        path = Path(resource["path"])
        _safe_components(path)
        if not path.is_dir() or common_dir(path) != common:
            return False
        metadata = gitdir(path)
        if str(metadata) != resource["gitdir"]:
            return False
        if branch is None:
            symbolic = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(path),
                            "symbolic-ref", "--quiet", "HEAD"], check=False)
            if symbolic.returncode == 0:
                return False
        elif git_value(path, "symbolic-ref", "--quiet", "--short", "HEAD") != branch:
            return False
        marker = json.loads(_read_file(metadata / "embraion-resource.json"))
        return marker == {"schema-version": 1, "resource-id": resource["resource-id"],
                          "gitdir": str(metadata), "common-dir": str(common)}
    except (OSError, KeyError, TypeError, ValueError, IndexError, subprocess.SubprocessError):
        return False
