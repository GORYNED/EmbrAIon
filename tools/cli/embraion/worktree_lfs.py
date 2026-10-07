"""Opt-in Git LFS hydration for a newly created worktree.

A new checkout of a repository that uses Git LFS holds pointer text files until
the content is fetched. This module fetches the exact HEAD content from the
repository's own LFS remote, writes it into the worktree and verifies every
LFS-tracked file by size and SHA-256. It never deletes the worktree.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .common import project_root, read_yaml
from .environment import child_environment
from .security import redact_text
from . import worktree_registry as registry
from .worktree import parse_worktrees
from .validation_process import terminate_tree

LFS_MODES = ("none", "hydrate")
_POINTER_VERSION = "version https://git-lfs.github.com/spec/v1"
_POINTER_LIMIT = 1024  # Git LFS pointer files are always smaller than this.
# Seconds allowed for one network or checkout step; a stalled transfer fails closed.
LFS_STEP_TIMEOUT = 1800
_GIT_TIMEOUT = 300
_OID = re.compile(r"sha256:([0-9a-f]{64})")
_HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_GIT_LOCATION_VARIABLES = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE", "GIT_PREFIX",
})
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
    for name in _GIT_LOCATION_VARIABLES:
        environment.pop(name, None)
    # Git does not prompt on the terminal for credentials; a credential helper or an
    # askpass program that the user configured can still run.
    environment["GIT_TERMINAL_PROMPT"] = "0"
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
               else {"start_new_session": True})
    process = subprocess.Popen(args, cwd=str(cwd), env=environment, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    try:
        stdout, stderr = process.communicate(input=data, timeout=timeout)
    except subprocess.TimeoutExpired:
        if not terminate_tree(process):
            raise RuntimeError("Git command timed out and descendant termination is unconfirmed") from None
        raise
    except BaseException:
        terminate_tree(process)
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


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
    head = _git(worktree, "rev-parse", "--verify", "HEAD")
    if head.returncode:
        raise RuntimeError("cannot resolve committed LFS attributes")
    commit = head.stdout.decode("ascii", "replace").strip()
    if not _HEAD.fullmatch(commit):
        raise RuntimeError("cannot resolve committed LFS attributes")
    tree = _git(worktree, "ls-tree", "-r", "-l", "-z", commit)
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
    # Git check-attr reads .git/info/attributes even with --source=HEAD. A
    # sterile bare view and temporary index apply only committed rules.
    objects = _git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "objects")
    if objects.returncode:
        raise RuntimeError("cannot resolve committed LFS attributes")
    object_path = objects.stdout.decode("utf-8", "surrogateescape").strip()
    if not Path(object_path).is_dir() or "\n" in object_path:
        raise RuntimeError("cannot resolve committed LFS attributes")
    with tempfile.TemporaryDirectory(prefix="embraion-lfs-attributes-") as scratch:
        bare = Path(scratch) / "repository.git"
        empty_template = Path(scratch) / "empty-template"
        empty_template.mkdir()
        init_args = ["git", "init", "--bare", "-q", f"--template={empty_template}"]
        if len(commit) == 64:
            init_args.append("--object-format=sha256")
        init = _run([*init_args, str(bare)], worktree)
        if init.returncode:
            raise RuntimeError("cannot initialize committed LFS attribute view")
        (bare / "objects" / "info" / "alternates").write_bytes(os.fsencode(object_path) + b"\n")
        indexed = _run(["git", "-C", str(bare), "read-tree", commit], bare)
        if indexed.returncode:
            raise RuntimeError("cannot read committed LFS attribute tree")
        attributes = _run(
            ["git", "-c", f"core.attributesFile={os.devnull}", "-C", str(bare),
             "check-attr", "--cached", "-z", "--stdin", "filter"],
            bare, data=b"".join(path.encode("utf-8", "surrogateescape") + b"\0"
                                for path, _ in candidates),
        )
    if attributes.returncode:
        raise RuntimeError(_safe_reason("cannot read attributes", attributes))
    parts = attributes.stdout.split(b"\0")
    if (len(parts) != 3 * len(candidates) + 1 or parts[-1] != b""
            or any(parts[3 * index] != path.encode("utf-8", "surrogateescape")
                   or parts[3 * index + 1] != b"filter"
                   for index, (path, _) in enumerate(candidates))):
        raise RuntimeError("incomplete committed LFS attribute inventory")
    lfs_paths = {path for index, (path, _) in enumerate(candidates)
                 if parts[3 * index + 2] == b"lfs"}
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


def hydrate_lfs(worktree: Path, remote: str | None = None) -> dict[str, Any]:
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
        fetch_remote = remote or _fetch_remote(worktree)
        if fetch_remote is None:
            return failed("no remote to fetch LFS content from", missing)
        head = _git(worktree, "rev-parse", "--verify", "HEAD").stdout.decode("ascii", "replace").strip()
        try:
            fetch = _git(worktree, "lfs", "fetch", fetch_remote, head, timeout=LFS_STEP_TIMEOUT)
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


def _is_expected_pointer(path: Path, expected: tuple[str, int]) -> bool:
    """Read only a small, regular, unlinked pointer at the expected path."""
    try:
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size >= _POINTER_LIMIT
                or getattr(before, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return False
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_ino != before.st_ino
                    or opened.st_dev != before.st_dev or opened.st_size != before.st_size):
                return False
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                return _parse_pointer(stream.read(_POINTER_LIMIT)) == expected
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except OSError:
        return False


def _preflight_state(worktree: Path, expected_head: str,
                     allowed_pointers: dict[str, tuple[str, int]] | None = None) -> dict[str, Any]:
    """Observe identity and safety gates without changing Git state."""
    common = registry.common_dir(worktree)
    rows = parse_worktrees(worktree)
    matching = [row for row in rows if Path(row["path"]).resolve() == worktree]
    if len(matching) != 1 or matching[0].get("locked"):
        raise ValueError("worktree is absent, ambiguous, or locked")
    primary = [row for row in rows if registry.gitdir(Path(row["path"])) == common]
    if len(primary) != 1 or Path(primary[0]["path"]).resolve() == worktree:
        raise ValueError("a unique separate primary worktree was not proven")
    resources = [resource for resource in registry.load_registry(worktree)["resources"].values()
                 if resource.get("kind") == "worktree" and resource.get("path")
                 and Path(resource["path"]).resolve() == worktree]
    if len(resources) != 1 or not registry.verify_resource(worktree, resources[0]):
        raise ValueError("worktree registration could not be verified")
    if resources[0].get("state") != "active":
        raise ValueError("registered worktree is not active")
    head = _git(worktree, "--no-optional-locks", "rev-parse", "--verify", "HEAD")
    if head.returncode or head.stdout.decode("ascii", "replace").strip() != expected_head:
        raise ValueError("worktree HEAD differs from the expected commit")
    lock = _git(worktree, "--no-optional-locks", "rev-parse", "--path-format=absolute", "--git-path", "index.lock")
    if lock.returncode or not lock.stdout.strip():
        raise ValueError("worktree index lock state could not be read")
    if Path(lock.stdout.decode("utf-8", "surrogateescape").strip()).exists():
        raise ValueError("worktree index is locked")
    index_flags = _git(worktree, "--no-optional-locks", "ls-files", "-v", "-z")
    if index_flags.returncode:
        raise ValueError("worktree index flags could not be read")
    if any(entry and entry[:2] != b"H " for entry in index_flags.stdout.split(b"\0")):
        # skip-worktree may hide an absent LFS file, and assume-unchanged may
        # hide local edits from both status and diff. Neither is clean proof.
        raise ValueError("worktree has hidden or skipped index entries")
    status = _git(worktree, "--no-optional-locks", "-c", "core.fsmonitor=false", "status",
                  "--porcelain=v1", "-z", "--untracked-files=all")
    if status.returncode:
        raise ValueError("worktree clean state could not be read")
    if status.stdout:
        observed = [item for item in status.stdout.split(b"\0") if item]
        allowed = allowed_pointers or {}
        permitted = {b" M " + path.encode("utf-8", "surrogateescape"): (path, pointer)
                     for path, pointer in allowed.items()}
        if (len(observed) != len(set(observed)) or not set(observed) <= permitted.keys()
                or any(not _is_expected_pointer(worktree / permitted[item][0], permitted[item][1])
                       for item in observed)):
            raise ValueError("worktree is dirty")
    return {"head": expected_head, "path": str(worktree), "primary": primary[0]["path"],
            "resource-id": resources[0]["resource-id"]}


def preflight_lfs(worktree: Path, expected_head: str, remote: str | None = None) -> dict[str, Any]:
    """Hydrate and verify one registered checkout, failing on every uncertain gate.

    The caller must run this immediately before the dependent validation. The
    result is evidence of this observation, not a lock held during that command.
    """
    result: dict[str, Any] = {"state": "failed", "reason": "preflight incomplete"}
    if not _HEAD.fullmatch(expected_head):
        result["reason"] = "expected HEAD must be a full hexadecimal commit ID"
        return result
    if any(name in os.environ for name in _GIT_LOCATION_VARIABLES):
        result["reason"] = "Git repository location is overridden by the environment"
        return result
    try:
        worktree = Path(worktree).resolve()
        head = _git(worktree, "--no-optional-locks", "rev-parse", "--verify", "HEAD")
        if head.returncode or head.stdout.decode("ascii", "replace").strip() != expected_head:
            raise ValueError("worktree HEAD differs from the expected commit")
        files = _tracked_lfs_files(worktree)
        if not files:
            raise ValueError("no LFS pointer files at expected HEAD")
        before = _preflight_state(worktree, expected_head,
                                  {path: (oid, size) for path, oid, size in files})
        filter_process = _git(worktree, "config", "--get", "filter.lfs.process")
        filter_required = _git(worktree, "config", "--bool", "--get", "filter.lfs.required")
        if (filter_process.returncode or not filter_process.stdout.strip()
                or filter_required.returncode or filter_required.stdout.strip() != b"true"):
            raise ValueError("Git LFS filter is not installed")
        if _git(worktree, "lfs", "version").returncode:
            raise ValueError("Git LFS executable is unavailable")
        selected_remote = remote if remote is not None else _fetch_remote(worktree)
        if (not selected_remote or selected_remote.startswith("-")
                or not selected_remote.strip()
                or _git(worktree, "remote", "get-url", selected_remote).returncode):
            raise ValueError("Git LFS remote is unavailable")
        lfs = hydrate_lfs(worktree, remote=selected_remote)
        result["lfs"] = lfs
        if lfs["state"] != "hydrated" or lfs.get("modified") or lfs["verified"] != len(files):
            raise ValueError("LFS content could not be fully verified")
        after = _preflight_state(worktree, expected_head)
        if after != before:
            raise ValueError("worktree identity changed during preflight")
        result.update(state="passed", reason="verified", **after)
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Details from Git or registry may contain private paths or remote URLs.
        result["reason"] = str(error) if isinstance(error, ValueError) else f"preflight unavailable ({type(error).__name__})"
    return result
