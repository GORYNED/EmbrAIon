"""Opt-in Git LFS hydration for a newly created worktree.

A new checkout of a repository that uses Git LFS holds pointer text files until
the content is fetched. This module fetches the exact HEAD content from the
repository's own LFS remote, writes it into the worktree and verifies every
LFS-tracked file by size and SHA-256. It never deletes the worktree.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

from .common import project_root, read_yaml
from .environment import child_environment
from .security import redact_text

LFS_MODES = ("none", "hydrate")
_POINTER_VERSION = "version https://git-lfs.github.com/spec/v1"
_POINTER_LIMIT = 1024  # Git LFS pointer files are always smaller than this.
# Seconds allowed for one network or checkout step; a stalled transfer fails closed.
LFS_STEP_TIMEOUT = 1800
_GIT_TIMEOUT = 300
_OID = re.compile(r"sha256:([0-9a-f]{64})")
# `git lfs checkout` refuses to run unless the LFS filter is configured. A fresh
# machine or an isolated Git configuration may lack it, so supply it for this one
# command only; nothing is written to any Git configuration.
_FILTER_CONFIG = ("-c", "filter.lfs.clean=git-lfs clean -- %f", "-c", "filter.lfs.smudge=git-lfs smudge -- %f",
                  "-c", "filter.lfs.process=git-lfs filter-process", "-c", "filter.lfs.required=true")
_URL_USERINFO = re.compile(r"(://)[^/\s]*@")  # Greedy: user info may contain "@".
_URL_PARAMETERS = re.compile(r"(://[^\s?#]*)[?#]\S*")


def lfs_mode(repo: Path | None = None) -> str:
    """Return the project's `worktree.lfs` setting; unknown values fail closed."""
    root = repo or project_root()
    path = root / ".embraion" / "project.yaml"
    if not path.is_file():
        return "none"
    document = read_yaml(path)
    if not isinstance(document, dict):
        raise ValueError("invalid project configuration")
    section = document.get("worktree", {})
    if section is None:
        section = {}
    if not isinstance(section, dict) or set(section) - {"lfs"}:
        raise ValueError("invalid worktree keys")
    mode = section.get("lfs", "none")
    if mode not in LFS_MODES:
        raise ValueError(f"worktree.lfs must be one of: {', '.join(LFS_MODES)}")
    return mode


def _run(args: list[str], cwd: Path, data: bytes | None = None,
         timeout: int = _GIT_TIMEOUT) -> subprocess.CompletedProcess[bytes]:
    environment = child_environment()
    # Git does not prompt on the terminal for credentials; a credential helper or an
    # askpass program that the user configured can still run.
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(args, cwd=str(cwd), env=environment, input=data, timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git(worktree: Path, *args: str, data: bytes | None = None,
         timeout: int = _GIT_TIMEOUT) -> subprocess.CompletedProcess[bytes]:
    return _run(["git", *args], worktree, data, timeout)


def _result(state: str, reason: str, files: int = 0, missing: int = 0, modified: int = 0) -> dict[str, Any]:
    result = {"state": state, "files": files, "verified": files - missing - modified,
              "missing": missing, "reason": reason}
    if modified:
        result["modified"] = modified  # Additive: only present when local edits were found.
    return result


def _safe_reason(prefix: str, process: subprocess.CompletedProcess[bytes] | None = None) -> str:
    """Build a short reason without credentials or URL parameters."""
    if process is None:
        return prefix
    lines = [line.strip() for line in process.stderr.decode("utf-8", "replace").splitlines() if line.strip()]
    if not lines:
        return prefix
    detail = redact_text(_URL_PARAMETERS.sub(r"\1", _URL_USERINFO.sub(r"\1", lines[-1])))
    return f"{prefix}: {detail[:200]}"


def _parse_pointer(content: bytes) -> tuple[str, int] | None:
    if len(content) >= _POINTER_LIMIT:
        return None
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    if not lines or lines[0] != _POINTER_VERSION:
        return None
    fields = {key: value for key, _, value in (line.partition(" ") for line in lines[1:])}
    oid = _OID.fullmatch(fields.get("oid", ""))
    size = fields.get("size", "")
    if oid is None or not size.isascii() or not size.isdigit():
        return None
    return oid.group(1), int(size)


def _uses_lfs_attributes(worktree: Path) -> bool:
    found = _git(worktree, "grep", "-l", "-F", "filter=lfs", "HEAD", "--", ":(glob)**/.gitattributes")
    if found.returncode == 0 and found.stdout.strip():
        return True
    if found.returncode not in {0, 1}:
        raise RuntimeError(_safe_reason("cannot read .gitattributes", found))
    return False


def _tracked_lfs_files(worktree: Path) -> list[tuple[str, str, int]]:
    """List (path, oid, size) for committed pointer files that an LFS attribute covers."""
    tree = _git(worktree, "ls-tree", "-r", "-l", "-z", "HEAD")
    if tree.returncode:
        raise RuntimeError(_safe_reason("cannot list HEAD", tree))
    candidates: list[tuple[str, str]] = []
    for entry in tree.stdout.split(b"\0"):
        meta, _, raw_path = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) != 4 or fields[1] != b"blob" or fields[0] == b"120000":
            continue
        if fields[3].isdigit() and int(fields[3]) < _POINTER_LIMIT:
            candidates.append((raw_path.decode("utf-8", "surrogateescape"), fields[2].decode("ascii")))
    if not candidates:
        return []
    attributes = _git(worktree, "check-attr", "-z", "--stdin", "filter",
                      data=b"".join(path.encode("utf-8", "surrogateescape") + b"\0" for path, _ in candidates))
    if attributes.returncode:
        raise RuntimeError(_safe_reason("cannot read attributes", attributes))
    parts = attributes.stdout.split(b"\0")
    lfs_paths = {parts[index].decode("utf-8", "surrogateescape")
                 for index in range(0, len(parts) - 2, 3) if parts[index + 2] == b"lfs"}
    covered = [(path, blob) for path, blob in candidates if path in lfs_paths]
    if not covered:
        return []
    blobs = _git(worktree, "cat-file", "--batch", data="".join(f"{blob}\n" for _, blob in covered).encode("ascii"))
    if blobs.returncode:
        raise RuntimeError(_safe_reason("cannot read pointer blobs", blobs))
    output, cursor, files = blobs.stdout, 0, []
    for path, _ in covered:
        header_end = output.index(b"\n", cursor)
        header = output[cursor:header_end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise RuntimeError("unexpected git cat-file output")
        length = int(header[2])
        content = output[header_end + 1:header_end + 1 + length]
        cursor = header_end + length + 2
        pointer = _parse_pointer(content)
        if pointer is not None:
            files.append((path, *pointer))
    return files


def _excluded_by_sparse_checkout(worktree: Path) -> set[str]:
    listing = _git(worktree, "ls-files", "-t", "-z")
    if listing.returncode:
        return set()
    return {entry[2:].decode("utf-8", "surrogateescape")
            for entry in listing.stdout.split(b"\0") if entry[:2] == b"S "}


def _is_modified_locally(path: Path) -> bool:
    """A regular file that is neither the expected content nor a pointer was edited locally."""
    try:
        if path.is_symlink() or not path.is_file():
            return False
        if path.stat().st_size < _POINTER_LIMIT:
            return _parse_pointer(path.read_bytes()) is None
        return True
    except OSError:
        return False


def _has_content(path: Path, oid: str, size: int) -> bool:
    try:
        status = path.lstat()
        if not path.is_file() or path.is_symlink() or status.st_size != size:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest() == oid
    except OSError:
        return False


def _check(worktree: Path, files: list[tuple[str, str, int]],
           allowed: set[str] | None = None) -> tuple[int, set[str]]:
    """Return (missing count, locally modified paths).

    A file that differs from its pointer but is not a pointer is "modified", not
    missing. After hydration `allowed` holds the paths already modified before it,
    so content that hydration itself left wrong still counts as missing.
    """
    skipped = _excluded_by_sparse_checkout(worktree)
    missing, modified = 0, set()
    for path, oid, size in files:
        if path in skipped or _has_content(worktree / path, oid, size):
            continue
        if _is_modified_locally(worktree / path) and (allowed is None or path in allowed):
            modified.add(path)
        else:
            missing += 1
    return missing, modified


def _fetch_remote(worktree: Path) -> str | None:
    remotes = _git(worktree, "remote").stdout.decode("utf-8", "replace").split()
    if not remotes:
        return None
    branch = _git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.decode("utf-8", "replace").strip()
    tracked = _git(worktree, "config", "--get", f"branch.{branch}.remote").stdout.decode("utf-8", "replace").strip() if branch else ""
    return tracked if tracked in remotes else ("origin" if "origin" in remotes else remotes[0])


def hydrate_lfs(worktree: Path) -> dict[str, Any]:
    """Fetch and check out LFS content for the worktree's HEAD, then verify it.

    Returns `{state, files, verified, missing, reason}` plus `modified` when LFS
    files were edited locally (reported, never a failure, never overwritten).
    `state` is `hydrated`, `failed` or `not-applicable`. Nothing is removed on failure.
    """
    worktree = Path(worktree)
    try:
        if not _uses_lfs_attributes(worktree):
            return _result("not-applicable", "no-lfs-attributes")
        files = _tracked_lfs_files(worktree)
        if not files:
            return _result("not-applicable", "no-lfs-files-at-head")
        total = len(files)
        missing, modified = _check(worktree, files)
        note = f" ({len(modified)} modified locally, not checked)" if modified else ""
        if missing == 0:
            return _result("hydrated", "already-present" + note, total, 0, len(modified))

        def failed(reason: str, count: int | None = None) -> dict[str, Any]:
            return _result("failed", reason, total, _check(worktree, files, modified)[0] if count is None else count,
                           len(modified))

        if _git(worktree, "lfs", "version").returncode:
            return failed("git-lfs-unavailable: install Git LFS (https://git-lfs.com), "
                          "then run `git lfs pull` in the worktree", missing)
        remote = _fetch_remote(worktree)
        if remote is None:
            return failed("no remote to fetch LFS content from", missing)
        head = _git(worktree, "rev-parse", "--verify", "HEAD").stdout.decode("ascii", "replace").strip()
        try:
            fetch = _git(worktree, "lfs", "fetch", remote, head, timeout=LFS_STEP_TIMEOUT)
        except subprocess.TimeoutExpired:
            return failed(f"git-lfs-fetch-failed: timed out after {LFS_STEP_TIMEOUT} seconds")
        if fetch.returncode:
            return failed(_safe_reason("git-lfs-fetch-failed", fetch))
        try:
            checkout = _git(worktree, *_FILTER_CONFIG, "lfs", "checkout", timeout=LFS_STEP_TIMEOUT)
        except subprocess.TimeoutExpired:
            return failed(f"git-lfs-checkout-failed: timed out after {LFS_STEP_TIMEOUT} seconds")
        if checkout.returncode:
            return failed(_safe_reason("git-lfs-checkout-failed", checkout))
        missing, _ = _check(worktree, files, modified)
        if missing:
            return failed("lfs-content-missing-after-checkout", missing)
        return _result("hydrated", "verified" + note, total, 0, len(modified))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        return _result("failed", _safe_reason(f"lfs-check-failed ({type(error).__name__})"))
