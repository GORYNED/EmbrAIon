from __future__ import annotations

import os
import shutil
import subprocess
import hashlib
import re
import fnmatch
import stat
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .common import project_root, read_json, read_yaml, run, state_root, write_json
from .environment import child_environment
from . import worktree_registry as registry
from . import worktree_github as github


def parse_worktrees(repo: Path) -> list[dict[str, Any]]:
    result = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain", "-z"],
                            check=True, capture_output=True, env=child_environment())

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in os.fsdecode(result.stdout).split("\0") + [""]:
        if not line:
            if current:
                entries.append(current)
                current = None
            continue

        if line.startswith("worktree "):
            current = {"path": line[9:], "locked": False}
        elif current is not None and line.startswith("HEAD "):
            current["head"] = line[5:]
        elif current is not None and line.startswith("branch "):
            current["branch"] = line[7:].removeprefix("refs/heads/")
        elif current is not None and line.startswith("locked"):
            current["locked"] = True

    return entries


def is_clean(path: Path) -> bool:
    result = run(
        [
            "git",
            "--no-optional-locks",
            "-c", "core.fsmonitor=false",
            "-C",
            str(path),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ]
    )
    return not result.stdout.strip()


def list_worktrees() -> list[dict[str, Any]]:
    repo = project_root()
    rows = parse_worktrees(repo)

    for row in rows:
        row["clean"] = is_clean(Path(row["path"]))

    return rows


def create_worktree(
    branch: str,
    destination: Path | None = None,
    base: str = "origin/main",
    task_id: str | None = None,
    host: str = "embraion",
    independent: bool = False,
) -> Path:
    repo = project_root()
    run(["git", "-C", str(repo), "fetch", "--no-prune", "--no-prune-tags", "origin"])

    target = destination or (repo.parent / f"{repo.name}-{branch.replace('/', '-')}")
    task = task_id or f"manual-{registry.new_id()}"
    prepared = prepare_task(task, host=host, branch=branch, path=target, base=base,
                            independent=independent, repo=repo)
    base_sha = registry.git_value(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    run(["git", "-C", str(repo), "update-ref", "--create-reflog",
         "-m", f"embraion-create:{prepared['receipt-id']}", f"refs/heads/{branch}",
         base_sha, "0" * 40])
    run(["git", "-C", str(repo), "worktree", "add", str(target), branch])
    write_json(_git_directory(target) / "embraion-worktree.json", {
        "schema-version": 1, "path": str(target.absolute()), "branch": branch,
    })
    register_worktree(task, host, path=target, receipt_id=prepared["receipt-id"],
                      creation_source="embraion-create", legacy_compatible=task_id is None,
                      repo=repo)
    return target


def create_branch(branch: str, base: str = "origin/main", task_id: str | None = None,
                  host: str = "embraion", repo: Path | None = None,
                  independent: bool = False) -> str:
    """Create a branch-only managed resource from an absent branch."""
    root = (repo or project_root()).resolve()
    run(["git", "-C", str(root), "fetch", "--no-prune", "--no-prune-tags", "origin"])
    task = task_id or f"manual-{registry.new_id()}"
    prepared = prepare_task(task, host=host, branch=branch, base=base,
                            independent=independent, repo=root)
    sha = registry.git_value(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    run(["git", "-C", str(root), "update-ref", "--create-reflog", "-m",
         f"embraion-create:{prepared['receipt-id']}", f"refs/heads/{branch}", sha, "0" * 40])
    register_worktree(task, host, receipt_id=prepared["receipt-id"], repo=root,
                      creation_source="embraion-create", legacy_compatible=task_id is None)
    return branch


def create_detached_worktree(destination: Path, base: str = "origin/main",
                             task_id: str | None = None, host: str = "embraion",
                             repo: Path | None = None, independent: bool = False) -> Path:
    """Create a detached managed worktree; its exact Git directory is registered."""
    root = (repo or project_root()).resolve()
    run(["git", "-C", str(root), "fetch", "--no-prune", "--no-prune-tags", "origin"])
    task = task_id or f"manual-{registry.new_id()}"
    target = Path(destination).absolute()
    prepared = prepare_task(task, host=host, path=target, base=base,
                            independent=independent, repo=root)
    run(["git", "-C", str(root), "worktree", "add", "--detach", str(target), base])
    register_worktree(task, host, path=target, receipt_id=prepared["receipt-id"],
                      creation_source="embraion-create", repo=root)
    return target


def _directly_integrated(path: Path, head: str, base: str) -> bool:
    result = run(
        [
            "git",
            "-C",
            str(path),
            "merge-base",
            "--is-ancestor",
            head,
            base,
        ],
        check=False,
    )
    return result.returncode == 0


def _git_directory(path: Path) -> Path:
    result = run(["git", "-C", str(path), "rev-parse", "--absolute-git-dir"])
    return Path(result.stdout.strip()).absolute()


def _inactive_owned_worktree(path: Path, branch: str | None) -> bool:
    """Require ownership and terminal local evidence; absence is not inactivity."""
    try:
        metadata = _git_directory(path)
        _assert_no_reparse(metadata)
        marker = metadata / "embraion-worktree.json"
        if json.loads(registry._read_file(marker)) != {
            "schema-version": 1, "path": str(path), "branch": branch,
        }:
            return False
        # Git operations can be in progress even with an empty status output.
        pending = ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
                   "BISECT_LOG", "BISECT_START", "MERGE_AUTOSTASH", "rebase-merge", "rebase-apply", "sequencer", "index.lock", "HEAD.lock")
        if any((metadata / name).exists() for name in pending):
            return False
        state = path / ".embraion/state"
        _assert_no_reparse(state)
        runs = state / "runs"
        if runs.exists() and not runs.is_dir():
            return False
        records = list(runs.iterdir()) if runs.exists() else []
        if any(not entry.is_file() or entry.suffix != ".json" for entry in records):
            return False
        session = state / "session.json"
        if session.exists() or session.is_symlink():
            records.append(session)
        if not records:
            return False
        for record in records:
            _assert_no_reparse(record)
            value = json.loads(registry._read_file(record))
            terminal = {"completed", "cancelled"} if record == session else {"completed", "cancelled", "failed"}
            if not isinstance(value, dict) or value.get("state") not in terminal:
                return False
        return True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return False


def housekeeping_config(repo: Path | None = None) -> dict[str, Any]:
    """Read a project-owned policy without creating project state."""
    root = repo or project_root()
    defaults = {"on-task-start": False, "local-branches": True,
                "remote-branches": False, "worktrees": True, "preserve-branches": []}
    path = root / ".embraion" / "project.yaml"
    if not path.is_file():
        return defaults
    document = read_yaml(path)
    if not isinstance(document, dict):
        raise ValueError("invalid project configuration")
    raw = document.get("housekeeping", {})
    if not isinstance(raw, dict) or set(raw) - set(defaults):
        raise ValueError("invalid housekeeping keys")
    result = defaults | raw
    if any(type(result[key]) is not bool for key in ("on-task-start", "local-branches", "remote-branches", "worktrees")):
        raise ValueError("housekeeping switches must be boolean")
    if not isinstance(result["preserve-branches"], list) or any(
            not isinstance(value, str) or not value for value in result["preserve-branches"]):
        raise ValueError("preserve-branches must be a list of branch names")
    return result


def _valid_branch(branch: str) -> bool:
    if not branch or branch.startswith("-") or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch):
        return False
    return ".." not in branch and "//" not in branch and not branch.endswith(".lock")


def _origin_identity(repo: Path) -> str:
    # Bind authority to this remote without storing URL credentials.
    url = registry.git_value(repo, "remote", "get-url", "origin")
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _push_endpoint(repo: Path) -> str:
    """Bind a remote mutation to the single endpoint used for fresh reads."""
    # Git can rewrite an explicit URL again when pushing. Without a stable
    # server-side endpoint identity, any effective URL rewrite is ambiguous.
    rewrites = run(["git", "-C", str(repo), "config", "--name-only", "--get-regexp",
                    r"^url\..*\.(insteadof|pushinsteadof)$"], check=False)
    if rewrites.returncode not in {0, 1} or rewrites.stdout.strip():
        raise ValueError("origin URL rewrite is unsupported for remote mutation")
    fetch = registry.git_value(repo, "remote", "get-url", "--all", "origin").splitlines()
    push = registry.git_value(repo, "remote", "get-url", "--push", "--all", "origin").splitlines()
    if len(fetch) != 1 or len(push) != 1 or not fetch[0] or fetch[0] != push[0]:
        raise ValueError("origin has ambiguous or different fetch/push endpoints")
    endpoint = urlsplit(fetch[0])
    if (endpoint.password is not None
            or (endpoint.scheme in {"http", "https"} and endpoint.username is not None)
            or endpoint.query or endpoint.fragment):
        raise ValueError("origin contains embedded credentials or unsupported URL parameters")
    return fetch[0]


def prepare_task(task_id: str, host: str = "codex", branch: str | None = None,
                 path: Path | None = None, base: str = "origin/main", writable: bool = True,
                 independent: bool = True, repo: Path | None = None) -> dict[str, Any]:
    root = (repo or project_root()).resolve()
    if not task_id or not host:
        raise ValueError("task id and host are required")
    config = housekeeping_config(root)
    report = {"schema-version": 1, "dry-run": True, "cleanup-id": None, "resources": []}
    if config["on-task-start"] and writable is True and independent is True:
        with registry.registry_lock(root):
            data = registry.load_registry(root)
            task = data["tasks"].setdefault(task_id, {"state": "active"})
            first = not task.get("gc-run")
            if first:
                # Claim before releasing the lock so concurrent starts cannot
                # run cleanup twice. A failed run is recorded, never retried.
                task["gc-run"] = True
                registry.save_registry(root, data)
        if first:
            report = gc_report(base=base, apply=True, repo=root, include_legacy=False)
    if branch is None and path is None:
        return report
    if branch is not None and not _valid_branch(branch):
        raise ValueError("invalid branch for provenance")
    target = Path(path).absolute() if path is not None else None
    if target is not None:
        _assert_no_reparse(target)
    if (target is not None and (target.exists() or target.is_symlink())) or (branch is not None and registry.branch_sha(root, branch) is not None):
        raise ValueError("worktree branch and path must be absent before creation")
    base_sha = registry.git_value(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    origin_id = _origin_identity(root)
    remote_absent = False
    if branch is not None:
        try:
            remote_absent = github.remote_head(root, branch) is None
        except (OSError, ValueError, subprocess.SubprocessError):
            pass  # Local creation remains possible; remote authority is withheld.
    receipt_id = registry.new_id()
    with registry.registry_lock(root):
        data = registry.load_registry(root)
        if (target is not None and (target.exists() or target.is_symlink())) or (branch is not None and registry.branch_sha(root, branch) is not None):
            raise ValueError("worktree branch or path appeared during preparation")
        data["receipts"][receipt_id] = {
            "task-id": task_id, "host": host, "branch": branch,
            "path": str(target) if target is not None else None,
            "base-sha": base_sha, "created-utc": registry.timestamp(),
            "origin-id": origin_id, "remote-absent": remote_absent,
        }
        data["tasks"].setdefault(task_id, {"state": "active"})
        registry.save_registry(root, data)
    return report | {"receipt-id": receipt_id}


def register_worktree(task_id: str, host: str, path: Path | None = None,
                      receipt_id: str | None = None, repo: Path | None = None,
                      creation_source: str = "host-native",
                      legacy_compatible: bool = False) -> dict[str, Any]:
    root = (repo or project_root()).resolve()
    if not receipt_id:
        raise ValueError("registration requires a creation receipt")
    if creation_source not in {"host-native", "embraion-create"}:
        raise ValueError("unknown creation source")
    target = Path(path).absolute() if path is not None else None
    if target is not None:
        _assert_no_reparse(target)
    with registry.registry_lock(root):
        data = registry.load_registry(root)
        receipt = data["receipts"].get(receipt_id)
        if (not receipt or receipt.get("task-id") != task_id or receipt.get("host") != host
                or receipt.get("path") != (str(target) if target is not None else None)):
            raise ValueError("creation receipt does not match worktree")
        branch = receipt["branch"]
        if target is not None:
            if registry.common_dir(target) != registry.common_dir(root):
                raise ValueError("worktree belongs to a different repository")
            symbolic = run(["git", "-C", str(target), "symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
            if (symbolic.stdout.strip() if symbolic.returncode == 0 else None) != branch:
                raise ValueError("worktree branch differs from receipt")
            actual_head = registry.git_value(target, "rev-parse", "HEAD")
            gitdir = registry.gitdir(target)
        else:
            if branch is None:
                raise ValueError("branch-only registration needs a branch")
            actual_head = registry.branch_sha(root, branch)
            gitdir = None
        if actual_head != receipt["base-sha"]:
            raise ValueError("resource HEAD differs from creation receipt")
        if receipt.get("origin-id") != _origin_identity(root):
            raise ValueError("origin changed since resource preparation")
        if any((target is not None and value.get("path") and Path(value["path"]).absolute() == target)
               or (gitdir is not None and value.get("gitdir") == str(gitdir))
               or (target is None and value.get("kind") == "branch" and value.get("branch") == branch)
               for value in data["resources"].values()):
            raise ValueError("worktree was already registered")
        creation_identity = None
        if creation_source == "embraion-create" and branch is not None:
            creation_identity = registry.branch_creation_identity(root, branch, receipt_id, receipt["base-sha"])
        resource_id = registry.new_id()
        if target is not None:
            registry.mark_resource(target, resource_id, registry.common_dir(root))
        branch_identity = None
        if branch is not None:
            branch_identity = registry.mark_branch(root, resource_id, branch, actual_head)
        resource = {"kind": "worktree" if target is not None else "branch",
                    "resource-id": resource_id, "task-ids": [task_id], "host": host,
                    "creation-source": creation_source,
                    "legacy-compatible": legacy_compatible,
                    "path": str(target) if target is not None else None,
                    "branch": branch, "gitdir": str(gitdir) if gitdir is not None else None,
                    "common-dir": str(registry.common_dir(root)),
                    "head-at-registration": actual_head,
                    "origin-id": receipt["origin-id"],
                    # Absence observed before local creation is not remote
                    # ownership. Only publish_branch can establish that.
                    "remote-owned": False,
                    "remote": "origin", "pr": None,
                    "created-utc": registry.timestamp(), "state": "active"}
        if creation_identity is not None:
            resource["creation-reflog-id"] = creation_identity
        if branch_identity is not None:
            resource["branch-reflog-id"] = branch_identity
        data["resources"][resource_id] = resource
        del data["receipts"][receipt_id]
        registry.save_registry(root, data)
        return resource.copy()


def _published_head(resource: dict[str, Any], branch: str, origin_id: str) -> str | None:
    """Return the last positively published SHA from a contiguous receipt chain."""
    receipt = resource.get("remote-publish")
    if (resource.get("remote-owned") is not True or not isinstance(receipt, dict)
            or receipt.get("method") != "expected-empty-lease"
            or receipt.get("resource-id") != resource.get("resource-id")
            or receipt.get("branch") != branch or receipt.get("origin-id") != origin_id
            or not isinstance(receipt.get("publish-id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", receipt["publish-id"])
            or not isinstance(receipt.get("head-sha"), str)
            or not re.fullmatch(r"[0-9a-f]{40,64}", receipt["head-sha"])
            or not isinstance(receipt.get("published-utc"), str)
            or not receipt["published-utc"]):
        return None
    head = receipt["head-sha"]
    updates = receipt.get("updates", [])
    if not isinstance(updates, list):
        return None
    ids = {receipt["publish-id"]}
    for update in updates:
        if (not isinstance(update, dict) or update.get("method") != "expected-sha-lease"
                or update.get("previous-sha") != head
                or not isinstance(update.get("publish-id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", update["publish-id"])
                or update["publish-id"] in ids
                or not isinstance(update.get("head-sha"), str)
                or not re.fullmatch(r"[0-9a-f]{40,64}", update["head-sha"])
                or update["head-sha"] == head
                or not isinstance(update.get("published-utc"), str)
                or not update["published-utc"]):
            return None
        ids.add(update["publish-id"])
        head = update["head-sha"]
    return head


def _published_remote(resource: dict[str, Any], branch: str, head: str,
                      origin_id: str) -> bool:
    """A prior absence observation or legacy remote-owned flag grants nothing."""
    return _published_head(resource, branch, origin_id) == head


def _confirmed_new_branch(output: str, ref: str) -> bool:
    """Git can report success for an already equal ref; require creation."""
    updates = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            updates.append(fields)
    return (len(updates) == 1 and updates[0][0] == "*"
            and updates[0][1].rsplit(":", 1)[-1] == ref
            and "[new branch]" in updates[0][2])


def _confirmed_fast_forward(output: str, head: str, ref: str) -> bool:
    """Only a single normal porcelain fast-forward proves this update."""
    updates = [line.split("\t") for line in output.splitlines() if "\t" in line]
    return (len(updates) == 1 and len(updates[0]) == 3
            and updates[0][0] == " " and updates[0][1] == f"{head}:{ref}"
            and bool(re.fullmatch(r"[0-9a-fA-F]+\.\.[0-9a-fA-F]+", updates[0][2])))


def publish_branch(task_id: str, branch: str, repo: Path | None = None) -> dict[str, Any]:
    """Create or advance an owned remote branch using an exact Git SHA lease."""
    root = (repo or project_root()).resolve()
    if not task_id or not _valid_branch(branch):
        raise ValueError("valid task id and branch are required")
    with registry.registry_lock(root):
        data = registry.load_registry(root)
        matches = [resource for resource in data["resources"].values()
                   if resource.get("branch") == branch and task_id in resource.get("task-ids", [])]
        if len(matches) != 1:
            raise ValueError("registered task branch is missing or ambiguous")
        resource = matches[0]
        if (resource.get("state") != "active" or resource.get("creation-source") != "embraion-create"
                or resource.get("legacy-compatible") or not registry.verify_resource(root, resource)):
            raise ValueError("branch lacks source-created publication provenance")
        origin_id = _origin_identity(root)
        if resource.get("origin-id") != origin_id:
            raise ValueError("origin changed since registration")
        endpoint = _push_endpoint(root)
        head = registry.branch_sha(root, branch)
        if head is None:
            raise ValueError("registered local branch is missing")
        ref = f"refs/heads/{branch}"
        receipt = resource.get("remote-publish")
        if receipt is None:
            if resource.get("remote-owned") is True:
                raise ValueError("remote branch lacks publication receipt")
            if github.remote_head(root, branch) is not None:
                raise ValueError("remote branch already exists; adoption is forbidden")
            # An equal ref created concurrently may report up-to-date success;
            # the porcelain creation flag prevents adopting that ref.
            pushed = run(["git", "-C", str(root), "push", "--porcelain",
                          f"--force-with-lease={ref}:", endpoint, f"{head}:{ref}"])
            if not _confirmed_new_branch(pushed.stdout, ref):
                raise ValueError("remote did not confirm new branch creation")
            previous = None
        else:
            previous = _published_head(resource, branch, origin_id)
            if previous is None:
                raise ValueError("remote publication receipt is invalid")
            if previous == head:
                raise ValueError("branch head was already published")
            if github.remote_head(root, branch) != previous:
                raise ValueError("remote branch differs from last managed publication")
            ancestor = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                            "-C", str(root), "merge-base", "--is-ancestor", previous, head],
                           check=False)
            if ancestor.returncode != 0:
                raise ValueError("branch does not fast-forward from last publication")
            pushed = run(["git", "-C", str(root), "push", "--porcelain",
                          f"--force-with-lease={ref}:{previous}", endpoint, f"{head}:{ref}"])
            if not _confirmed_fast_forward(pushed.stdout, head, ref):
                raise ValueError("remote did not confirm fast-forward publication")
        if (registry.branch_sha(root, branch) != head or not registry.verify_resource(root, resource)
                or _origin_identity(root) != origin_id or _push_endpoint(root) != endpoint
                or github.remote_head(root, branch) != head.lower()):
            raise ValueError("published branch changed before verification")
        if registry.load_registry(root)["resources"].get(resource["resource-id"]) != resource:
            raise ValueError("publication registry changed during push")
        if previous is None:
            publication = {"method": "expected-empty-lease", "publish-id": registry.new_id(),
                           "resource-id": resource["resource-id"], "branch": branch,
                           "head-sha": head, "origin-id": origin_id,
                           "published-utc": registry.timestamp()}
            resource["remote-publish"] = publication
            resource["remote-owned"] = True
        else:
            publication = {"method": "expected-sha-lease", "publish-id": registry.new_id(),
                           "previous-sha": previous, "head-sha": head,
                           "published-utc": registry.timestamp()}
            receipt.setdefault("updates", []).append(publication)
        registry.save_registry(root, data)
        recorded = registry.load_registry(root)["resources"].get(resource["resource-id"])
        if recorded != resource or not _published_remote(recorded, branch, head, origin_id):
            raise ValueError("remote publication receipt was not persisted")
        return publication.copy()


def update_task_state(task_id: str, state: str, repo: Path | None = None) -> dict[str, Any]:
    if state not in {"queued", "active", "blocked", "review", "completed", "cancelled", "failed", "incomplete"}:
        raise ValueError("unknown task state")
    root = (repo or project_root()).resolve()
    with registry.registry_lock(root):
        data = registry.load_registry(root)
        task = data["tasks"].setdefault(task_id, {})
        task["state"] = state
        task["updated-utc"] = registry.timestamp()
        if state == "active":
            current = run(["git", "--no-optional-locks", "-C", str(root),
                           "symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
            current_branch = current.stdout.strip() if current.returncode == 0 else None
            for resource in data["resources"].values():
                same_worktree = (resource.get("path") is not None
                                 and Path(resource["path"]).absolute() == root.absolute())
                same_branch = (resource.get("kind") == "branch" and current_branch is not None
                               and resource.get("branch") == current_branch
                               and registry.verify_resource(root, resource))
                if (resource.get("state") == "active" and (same_worktree or same_branch)
                        and task_id not in resource["task-ids"]):
                    # Reusing a managed checkout links the new task, without
                    # importing ownership of any unmanaged resource.
                    resource["task-ids"].append(task_id)
        registry.save_registry(root, data)
        return task.copy()


_PENDING = ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
            "BISECT_LOG", "BISECT_START", "MERGE_AUTOSTASH", "rebase-merge",
            "rebase-apply", "sequencer", "index.lock", "HEAD.lock")


def _safe_local_state(path: Path) -> tuple[bool, str]:
    metadata = _git_directory(path)
    if any((metadata / name).exists() for name in _PENDING):
        return False, "git-operation-in-progress"
    status = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                  "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"]).stdout
    if status.strip():
        return False, "dirty-worktree"
    ignored = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
                   "-C", str(path), "ls-files", "--others", "--ignored", "--exclude-standard", "-z"]).stdout
    for name in ignored.split("\0"):
        if name and not name.replace("\\", "/").startswith(".embraion/state/"):
            return False, "unmanaged-ignored-files"
    state = path / ".embraion" / "state"
    if state.exists():
        _assert_no_reparse(state)
        for entry in state.rglob("*"):
            _assert_no_reparse(entry)
            if (not entry.is_file() and not entry.is_dir()) or (entry.is_file() and entry.lstat().st_nlink != 1):
                return False, "unsafe-state-file"
    return True, "clean"


def _backup(repo: Path, item: dict[str, Any], cleanup_id: str) -> Path:
    """Retain a verified Git bundle and local state before any removal."""
    backup = registry.registry_dir(repo) / "recovery" / cleanup_id / item["resource-id"]
    _assert_no_reparse(backup)
    backup.mkdir(parents=True, exist_ok=False)
    sha = item["head"]
    recovery_ref = f"refs/embraion/recovery/{cleanup_id}/{item['resource-id']}"
    run(["git", "-C", str(repo), "update-ref", recovery_ref, sha, "0" * len(sha)])
    bundle = backup / "head.bundle"
    run(["git", "-C", str(repo), "bundle", "create", str(bundle), recovery_ref])
    run(["git", "-C", str(repo), "bundle", "verify", str(bundle)])
    state = Path(item["path"]) / ".embraion" / "state" if item.get("path") else None
    hashes: dict[str, str] = {}
    if state is not None and state.exists():
        _assert_no_reparse(state)
        for source in state.rglob("*"):
            _assert_no_reparse(source)
            if source.is_file():
                relative = source.relative_to(state)
                destination = backup / "state" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                _assert_no_reparse(destination.parent)
                content = registry._read_file(source)
                with os.fdopen(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
                    stream.write(content)
                digest = hashlib.sha256(content).hexdigest()
                if hashlib.sha256(registry._read_file(destination)).hexdigest() != digest:
                    raise ValueError("state backup verification failed")
                hashes[str(relative)] = digest
    write_json(backup / "manifest.json", {
        "schema-version": 1, "cleanup-id": cleanup_id, "resource-id": item["resource-id"],
        "path": item.get("path"), "branch": item.get("branch"), "head": sha,
        "recovery-ref": recovery_ref, "state-sha256": hashes,
        "bundle-sha256": hashlib.sha256(registry._read_file(bundle)).hexdigest(),
    })
    return backup


def _verify_state_snapshot(item: dict[str, Any], backup: Path) -> None:
    manifest = json.loads(registry._read_file(backup / "manifest.json"))
    state = Path(item["path"]) / ".embraion" / "state" if item.get("path") else None
    hashes: dict[str, str] = {}
    if state is not None:
        _assert_no_reparse(state)
        if state.exists():
            for source in state.rglob("*"):
                _assert_no_reparse(source)
                if source.is_file():
                    hashes[str(source.relative_to(state))] = hashlib.sha256(registry._read_file(source)).hexdigest()
    if manifest.get("state-sha256") != hashes:
        raise ValueError("local state changed after backup")


def _recheck_branch_operation(repo: Path, row: dict[str, Any], resource: dict[str, Any] | None,
                              base: str, *, remote: bool) -> str | None:
    """Refresh task, checkout, policy and provider evidence before each ref operation."""
    branch = row["branch"]
    endpoint = _push_endpoint(repo) if remote else None
    run(["git", "-C", str(repo), "fetch", "--no-prune", "--no-prune-tags", "origin"])
    config = housekeeping_config(repo)
    enabled = "remote-branches" if remote else "local-branches"
    if (not config[enabled] or branch in {"main", "master"}
            or any(fnmatch.fnmatchcase(branch, pattern) for pattern in config["preserve-branches"])):
        raise ValueError("branch deletion is no longer enabled")
    if any(item.get("branch") == branch for item in parse_worktrees(repo)):
        raise ValueError("branch is checked out")
    current = registry.branch_sha(repo, branch)
    if current != row["head"] and not (remote and current is None and row.get("removed-local-branch")):
        raise ValueError("local branch changed before deletion")
    if resource and current is not None:
        branch_resource = resource | {"kind": "branch", "path": None, "gitdir": None}
        if not registry.verify_resource(repo, branch_resource):
            raise ValueError("branch incarnation changed")
    if not resource or resource.get("legacy-compatible"):
        if remote or not _directly_integrated(repo, row["head"], base):
            raise ValueError("legacy branch is not directly integrated")
        return
    data = registry.load_registry(repo)
    recorded = data["resources"].get(resource["resource-id"])
    if recorded != resource or any(data["tasks"].get(task, {}).get("state") != "completed"
                                   for task in resource["task-ids"]):
        raise ValueError("resource task or provenance changed")
    if resource.get("origin-id") != _origin_identity(repo):
        raise ValueError("origin changed before deletion")
    if remote and not _published_remote(resource, branch, row["head"], _origin_identity(repo)):
        raise ValueError("remote ownership is unproven")
    evidence = github.github_evidence(repo)
    if branch == evidence["default-branch"] or base != f"origin/{evidence['default-branch']}":
        raise ValueError("default branch or target changed")
    if github.branch_rules(evidence, branch):
        raise ValueError("branch protection changed")
    integrated, _ = github.integration_proof(repo, branch, row["head"], base, evidence)
    if not integrated:
        raise ValueError("pull request evidence changed")
    expected = row.get("remote-head")
    if github.remote_head(repo, branch) != expected:
        raise ValueError("remote branch changed before deletion")
    if remote and _push_endpoint(repo) != endpoint:
        raise ValueError("origin endpoint changed during remote verification")
    return endpoint


def _assert_no_reparse(path: Path) -> None:
    """Reject symlinks and Windows junctions in an existing path chain."""
    for component in (path, *path.parents):
        if not component.exists() and not component.is_symlink():
            continue
        mode = component.lstat()
        if stat.S_ISLNK(mode.st_mode) or (getattr(mode, "st_file_attributes", 0)
                                           & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("reparse path is not eligible")


def _nonterminal_local_records(path: Path) -> bool:
    state = path / ".embraion" / "state"
    runs = state / "runs"
    try:
        _assert_no_reparse(state)
        _assert_no_reparse(runs)
    except (OSError, ValueError):
        return True
    if runs.exists() and not runs.is_dir():
        return True
    records = list(runs.iterdir()) if runs.exists() else []
    for record in records:
        try:
            _assert_no_reparse(record)
            if not record.is_file() or record.suffix != ".json":
                return True
        except (OSError, ValueError):
            return True
    for record in [state / "session.json", *records]:
        if record.exists() or record.is_symlink():
            try:
                value = json.loads(registry._read_file(record))
            except (OSError, ValueError):
                return True
            if not isinstance(value, dict) or value.get("state") != "completed":
                return True
    return False


def _resource_row(repo: Path, item: dict[str, Any], resource: dict[str, Any] | None,
                  data: dict[str, Any], config: dict[str, Any], base: str,
                  evidence: dict[str, Any] | None, evidence_error: str | None,
                  include_legacy: bool) -> dict[str, Any]:
    path = Path(item["path"])
    branch = item.get("branch")
    head = item.get("head")
    result: dict[str, Any] = {"kind": "worktree", "path": str(path), "branch": branch,
                              "resource-id": resource.get("resource-id") if resource else None,
                              "status": "preserved", "reason": "unowned"}
    if path.is_symlink() or not path.is_dir():
        result["reason"] = "path-unknown"
        return result
    if path.absolute() == repo.absolute() or branch in {"main", "master"} or not head:
        result["reason"] = "primary-or-unknown"
        return result
    if item.get("locked") or (branch is not None and any(fnmatch.fnmatchcase(branch, pattern)
                                                          for pattern in config["preserve-branches"])):
        result["reason"] = "locked-or-preserved"
        return result
    if not config["worktrees"]:
        result["reason"] = "worktree-cleanup-disabled"
        return result
    if resource:
        if not registry.verify_resource(repo, resource):
            result["reason"] = "ownership-identity-mismatch"
            return result
        if resource.get("creation-source") != "embraion-create":
            result["reason"] = "host-archive-required"
            return result
        if not resource.get("legacy-compatible") and resource.get("origin-id") != _origin_identity(repo):
            result["reason"] = "origin-identity-mismatch"
            return result
        if resource.get("state") == "removed":
            result["reason"] = "previously-removed"
            return result
        if resource.get("legacy-compatible"):
            if not include_legacy:
                result["reason"] = "legacy-manual-only"
                return result
            if branch is None or not _inactive_owned_worktree(path, branch):
                result["reason"] = "legacy-terminal-evidence-missing"
                return result
            if not _directly_integrated(path, head, base):
                result["reason"] = "not-directly-integrated"
                return result
            resource = None  # no GitHub or remote deletion authority
        else:
            if not resource.get("task-ids") or any(data["tasks"].get(task_id, {}).get("state") != "completed"
                                                   for task_id in resource["task-ids"]):
                result["reason"] = "task-not-completed"
                return result
            if _nonterminal_local_records(path):
                result["reason"] = "local-task-active-or-unknown"
                return result
            if branch is not None:
                if evidence_error or evidence is None:
                    result["reason"] = "github-evidence-unavailable"
                    return result
                if branch == evidence["default-branch"] or base != f"origin/{evidence['default-branch']}":
                    result["reason"] = "default-or-unverified-base"
                    return result
                try:
                    protected = github.branch_rules(evidence, branch)
                except (OSError, ValueError, subprocess.SubprocessError, KeyError):
                    result["reason"] = "branch-rules-unknown"
                    return result
                if protected:
                    result["reason"] = "protected-branch"
                    return result
                try:
                    integrated, reason = github.integration_proof(repo, branch, head, base, evidence)
                except (TypeError, AttributeError, KeyError, ValueError):
                    integrated, reason = False, "github-pr-metadata-unknown"
                if not integrated:
                    result["reason"] = reason
                    return result
                result["pr"] = github.pr_identity(evidence, branch, head)
                try:
                    remote_sha = github.remote_head(repo, branch)
                except (OSError, ValueError, subprocess.SubprocessError):
                    result["reason"] = "remote-head-unknown"
                    return result
                if remote_sha is not None and remote_sha != head.lower():
                    result["reason"] = "remote-head-changed"
                    return result
                if (remote_sha is not None and config["remote-branches"]
                        and not _published_remote(resource, branch, head, _origin_identity(repo))):
                    result["reason"] = "remote-ownership-unproven"
                    return result
                if remote_sha is not None and config["remote-branches"]:
                    try:
                        _push_endpoint(repo)
                    except (OSError, ValueError, subprocess.SubprocessError):
                        result["reason"] = "remote-endpoint-unproven"
                        return result
                result["remote-head"] = remote_sha
            elif not _directly_integrated(path, head, base):
                result["reason"] = "detached-head-not-integrated"
                return result
    elif not include_legacy or not _inactive_owned_worktree(path, branch):
        result["reason"] = "unowned-or-active"
        return result
    elif not _directly_integrated(path, head, base):
        result["reason"] = "not-directly-integrated"
        return result
    try:
        safe, reason = _safe_local_state(path)
    except (OSError, ValueError, subprocess.SubprocessError):
        safe, reason = False, "local-state-unknown"
    if not safe:
        result["reason"] = reason
        return result
    result.update({"status": "candidate", "reason": "eligible", "head": head,
                   "resource-id": result["resource-id"] or f"legacy-{hashlib.sha256(str(path).encode()).hexdigest()[:16]}"})
    return result


def _branch_row(repo: Path, resource: dict[str, Any], data: dict[str, Any],
                config: dict[str, Any], base: str, evidence: dict[str, Any] | None) -> dict[str, Any]:
    branch = resource.get("branch")
    row: dict[str, Any] = {"kind": "branch", "path": None, "branch": branch,
                           "resource-id": resource.get("resource-id"),
                           "status": "preserved", "reason": "unproven"}
    if not branch or not registry.verify_resource(repo, resource):
        row["reason"] = "ownership-identity-mismatch"
        return row
    if resource.get("creation-source") != "embraion-create":
        row["reason"] = "host-managed-or-unproven-branch"
        return row
    if resource.get("origin-id") != _origin_identity(repo):
        row["reason"] = "origin-identity-mismatch"
        return row
    if resource.get("state") == "removed":
        row["reason"] = "previously-removed"
        return row
    if resource.get("legacy-compatible"):
        row["reason"] = "legacy-branch-unproven"
        return row
    if branch in {"main", "master"} or any(fnmatch.fnmatchcase(branch, pattern)
                                             for pattern in config["preserve-branches"]):
        row["reason"] = "preserved-branch"
        return row
    if not config["local-branches"] and not config["remote-branches"]:
        row["reason"] = "branch-cleanup-disabled"
        return row
    if any(data["tasks"].get(task, {}).get("state") != "completed"
           for task in resource.get("task-ids", [])) or not resource.get("task-ids"):
        row["reason"] = "task-not-completed"
        return row
    if evidence is None:
        row["reason"] = "github-evidence-unavailable"
        return row
    if branch == evidence["default-branch"] or base != f"origin/{evidence['default-branch']}":
        row["reason"] = "default-or-unverified-base"
        return row
    try:
        if any(item.get("branch") == branch for item in parse_worktrees(repo)):
            row["reason"] = "branch-checked-out"
            return row
        if github.branch_rules(evidence, branch):
            row["reason"] = "protected-branch"
            return row
        head = registry.branch_sha(repo, branch)
        if not head:
            row["reason"] = "local-branch-missing"
            return row
        merged, reason = github.integration_proof(repo, branch, head, base, evidence)
        if not merged:
            row["reason"] = reason
            return row
        remote = github.remote_head(repo, branch)
        if remote is not None and remote != head.lower():
            row["reason"] = "remote-head-changed"
            return row
        if (remote is not None and config["remote-branches"]
                and not _published_remote(resource, branch, head, _origin_identity(repo))):
            row["reason"] = "remote-ownership-unproven"
            return row
        if remote is not None and config["remote-branches"]:
            try:
                _push_endpoint(repo)
            except (OSError, ValueError, subprocess.SubprocessError):
                row["reason"] = "remote-endpoint-unproven"
                return row
        if not config["local-branches"] and remote is None:
            row["reason"] = "no-enabled-branch-operation"
            return row
    except (OSError, ValueError, KeyError, TypeError, AttributeError,
            subprocess.SubprocessError):
        row["reason"] = "remote-evidence-unknown"
        return row
    row.update(status="candidate", reason="eligible", head=head, **{"remote-head": remote})
    row["pr"] = github.pr_identity(evidence, branch, head)
    return row


def _assess(repo: Path, config: dict[str, Any], base: str, data: dict[str, Any],
            include_legacy: bool, inventory: bool = True) -> list[dict[str, Any]]:
    resources = data["resources"]
    evidence: dict[str, Any] | None = None
    error: str | None = None
    if any(value.get("state") != "removed" for value in resources.values()):
        try:
            evidence = github.github_evidence(repo)
        except (OSError, ValueError, KeyError, TypeError, AttributeError,
                subprocess.SubprocessError, TimeoutError) as exc:
            error = type(exc).__name__
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(parse_worktrees(repo)):
        resource = next((value for value in resources.values() if value.get("path")
                         and Path(value["path"]).absolute() == Path(item["path"]).absolute()), None)
        if index == 0:
            rows.append({"kind": "worktree", "path": item["path"], "branch": item.get("branch"),
                         "resource-id": resource.get("resource-id") if resource else None,
                         "status": "preserved", "reason": "primary-checkout"})
        else:
            rows.append(_resource_row(repo, item, resource, data, config, base, evidence, error,
                                      include_legacy))
    for resource in resources.values():
        if resource.get("kind") == "branch":
            rows.append(_branch_row(repo, resource, data, config, base, evidence))
    if not inventory:
        return _report_provenance(repo, rows, resources)
    known = {row.get("branch") for row in rows if row.get("branch")}
    local = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo),
                 "for-each-ref", "--format=%(refname:short)", "refs/heads"]).stdout.splitlines()
    for branch in local:
        if branch not in known:
            rows.append({"kind": "branch", "path": None, "branch": branch,
                         "resource-id": None, "status": "preserved", "reason": "unowned-local-branch"})
            known.add(branch)
    try:
        remote = run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo),
                      "ls-remote", "--heads", "origin"]).stdout.splitlines()
        for line in remote:
            fields = line.split("\t", 1)
            if len(fields) != 2 or not fields[1].startswith("refs/heads/"):
                continue
            branch = fields[1].removeprefix("refs/heads/")
            if branch not in known:
                rows.append({"kind": "branch", "path": None, "branch": branch,
                             "resource-id": None, "status": "preserved", "reason": "unowned-remote-branch"})
                known.add(branch)
    except (OSError, subprocess.SubprocessError):
        rows.append({"kind": "branch", "path": None, "branch": None,
                     "resource-id": None, "status": "preserved", "reason": "remote-inventory-unavailable"})
    return _report_provenance(repo, rows, resources)


def _report_provenance(repo: Path, rows: list[dict[str, Any]],
                       resources: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose recorded host/task identity without expanding cleanup authority."""
    for row in rows:
        resource = resources.get(row.get("resource-id"))
        identified = resource is not None and registry.verify_resource(repo, resource)
        row["provenance"] = {
            "status": "registered" if identified else "unknown",
            "host": resource["host"] if identified else None,
            "task-ids": list(resource["task-ids"]) if identified else [],
            "creation-source": resource["creation-source"] if identified else None,
        }
    return rows


def gc_report(base: str = "origin/main", apply: bool = False,
              repo: Path | None = None, include_legacy: bool = True) -> dict[str, Any]:
    root = (repo or project_root()).resolve()
    config = housekeeping_config(root)
    report: dict[str, Any] = {"schema-version": 1, "dry-run": not apply,
                              "cleanup-id": None, "resources": []}
    def unavailable_registry() -> dict[str, Any]:
        rows = _assess(root, config, base, registry.empty_registry(), False)
        for row in rows:
            row.update(status="preserved", reason="registry-unavailable")
        report["resources"] = rows
        return report
    if not apply:
        try:
            data = registry.load_registry(root)
        except (OSError, ValueError, RuntimeError):
            return unavailable_registry()
        report["resources"] = _assess(root, config, base, data, include_legacy)
        return report
    with registry.registry_lock(root):
        try:
            data = registry.load_registry(root)
        except (OSError, ValueError, RuntimeError):
            return unavailable_registry()
        # Refresh without pruning refs; candidate identity is recomputed after refresh.
        fetch = run(["git", "-C", str(root), "fetch", "--no-prune", "--no-prune-tags", "origin"], check=False)
        report["cleanup-id"] = registry.new_id()
        rows = _assess(root, config, base, data, include_legacy)
        if fetch.returncode:
            for row in rows:
                if row["status"] == "candidate":
                    row.update(status="preserved", reason="origin-fetch-unavailable")
        journal = registry.registry_dir(root) / "journals" / f"{report['cleanup-id']}.json"
        journal.parent.mkdir(parents=True, exist_ok=True)
        report["resources"] = rows
        write_json(journal, report)
        for row in rows:
            if row["status"] != "candidate":
                continue
            path = Path(row["path"]) if row.get("path") else None
            branch = row["branch"]
            resource = data["resources"].get(row["resource-id"])
            operation = "recheck"
            try:
                # Re-evaluate under the registry lock immediately before the
                # snapshot and once more after it. Git and GitHub can change
                # independently of a prior dry-run or assessment.
                def fresh() -> dict[str, Any] | None:
                    run(["git", "-C", str(root), "fetch", "--no-prune", "--no-prune-tags", "origin"])
                    current = _assess(root, housekeeping_config(root), base, registry.load_registry(root), include_legacy,
                                      inventory=False)
                    return next((value for value in current
                                 if value.get("resource-id") == row["resource-id"]
                                 and value.get("kind") == row["kind"]), None)
                checked = fresh()
                if checked is None or checked.get("status") != "candidate" or checked.get("head") != row["head"]:
                    row.update(status="preserved", reason="changed-before-snapshot")
                    write_json(journal, report)
                    continue
                operation = "backup"
                backup = _backup(root, row, report["cleanup-id"])
                row["recovery"] = str(backup)
                write_json(journal, report)
                operation = "recheck"
                checked = fresh()
                if checked is None or checked.get("status") != "candidate" or checked.get("head") != row["head"]:
                    row.update(status="preserved", reason="changed-after-snapshot")
                    write_json(journal, report)
                    continue
                _verify_state_snapshot(row, backup)
                if path is not None:
                    operation = "worktree-remove"
                    run(["git", "-C", str(root), "worktree", "remove", str(path)])
                    row["removed-worktree"] = True
                    row.update(status="removed", reason="worktree-removed")
                    write_json(journal, report)
                if (branch and config["local-branches"] and resource is not None
                        and not resource.get("legacy-compatible")):
                    # Compare-and-delete prevents branch advancement between
                    # proof and deletion, including a squash-merged branch.
                    operation = "local-branch-delete"
                    _recheck_branch_operation(root, row, resource, base, remote=False)
                    run(["git", "-C", str(root), "update-ref", "--no-deref", "-d",
                         f"refs/heads/{branch}", row["head"]])
                    row["removed-local-branch"] = True
                    row.update(status="removed", reason="local-branch-removed")
                    write_json(journal, report)
                elif branch and config["local-branches"]:
                    row["preserved-local-branch"] = "legacy-ownership-unproven"
                    write_json(journal, report)
                if resource and not resource.get("legacy-compatible") and branch and config["remote-branches"] and row.get("remote-head"):
                    # A deletion lease rejects any new remote commit after assessment.
                    operation = "remote-branch-delete"
                    endpoint = _recheck_branch_operation(root, row, resource, base, remote=True)
                    run(["git", "-C", str(root), "push",
                         f"--force-with-lease=refs/heads/{branch}:{row['remote-head']}",
                         endpoint, f":refs/heads/{branch}"])
                    row["removed-remote-branch"] = True
                    row.update(status="removed", reason="remote-branch-removed")
                    write_json(journal, report)
                    # An explicit endpoint push does not update origin's cached
                    # ref. Remove only the direct ref at the verified old tip.
                    operation = "remote-tracking-delete"
                    if _push_endpoint(root) != endpoint:
                        raise ValueError("origin changed after remote deletion")
                    if github.remote_head(root, branch) is not None:
                        row["preserved-tracking-ref"] = "remote-ref-reappeared"
                    else:
                        tracking = f"refs/remotes/origin/{branch}"
                        directory = registry.common_dir(root)
                        registry._safe_file(directory / "packed-refs", allow_missing=True)
                        registry._safe_file(directory / Path(tracking), allow_missing=True)
                        present = run(["git", "-C", str(root), "show-ref", "--verify",
                                       "--quiet", tracking], check=False)
                        if present.returncode not in {0, 1}:
                            raise ValueError("tracking ref state is unknown")
                        if present.returncode == 0:
                            symbolic = run(["git", "-C", str(root), "symbolic-ref",
                                            "--quiet", tracking], check=False)
                            if symbolic.returncode == 0:
                                row["preserved-tracking-ref"] = "symbolic-tracking-ref"
                            elif symbolic.returncode != 1:
                                raise ValueError("tracking ref identity is unknown")
                            elif registry.git_value(root, "rev-parse", "--verify", tracking) != row["remote-head"]:
                                row["preserved-tracking-ref"] = "tracking-head-changed"
                            else:
                                if _push_endpoint(root) != endpoint:
                                    raise ValueError("origin changed before tracking deletion")
                                run(["git", "-C", str(root), "update-ref", "--no-deref",
                                     "-d", tracking, row["remote-head"]])
                                row["removed-tracking-ref"] = True
                    write_json(journal, report)
                if resource:
                    operation = "registry-update"
                    data = registry.load_registry(root)
                    resource = data["resources"][resource["resource-id"]]
                    if branch and registry.branch_sha(root, branch) is not None:
                        # Releasing a checkout must not orphan a retained local branch.
                        resource.update(kind="branch", path=None, gitdir=None)
                    else:
                        resource["state"] = "removed"
                    resource["cleanup-id"] = report["cleanup-id"]
                    resource["pr"] = row.get("pr")
                    registry.save_registry(root, data)
            except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError, KeyError) as exc:
                row.update(status="failed", reason=f"operation-failed:{type(exc).__name__}")
                row["failed-operation"] = operation
                write_json(journal, report)
        return report


def gc_worktrees(base: str = "origin/main", apply: bool = False) -> list[dict[str, Any]]:
    """Compatibility wrapper for the original candidate-list CLI."""
    report = gc_report(base=base, apply=apply)
    return [row | {"locked": False, "clean": True} for row in report["resources"]
            if row["kind"] == "worktree" and row["status"] in {"candidate", "removed"}]


def restore_cleanup(cleanup_id: str, repo: Path | None = None) -> dict[str, Any]:
    """Restore local branch and worktree from verified recovery; never overwrite."""
    root = (repo or project_root()).resolve()
    if not re.fullmatch(r"[0-9a-f]{32}", cleanup_id):
        raise ValueError("invalid cleanup id")
    with registry.registry_lock(root):
        journal = registry.registry_dir(root) / "journals" / f"{cleanup_id}.json"
        _assert_no_reparse(journal)
        report = json.loads(registry._read_file(journal))
        if (not isinstance(report, dict) or report.get("schema-version") != 1
                or report.get("cleanup-id") != cleanup_id
                or not isinstance(report.get("resources"), list)):
            raise ValueError("invalid cleanup journal")
        restored: list[dict[str, Any]] = []
        for row in report.get("resources", []):
            if not isinstance(row, dict):
                restored.append({"kind": "worktree", "status": "preserved",
                                 "reason": "invalid-cleanup-row"})
                continue
            if not row.get("recovery"):
                continue
            path: Path | None = None
            try:
                resource_id = row["resource-id"]
                if not re.fullmatch(r"[0-9a-f]{32}|legacy-[0-9a-f]{16}", resource_id):
                    raise ValueError("invalid resource id")
                backup = registry.registry_dir(root) / "recovery" / cleanup_id / resource_id
                if Path(row["recovery"]).absolute() != backup.absolute():
                    raise ValueError("recovery path mismatch")
                _assert_no_reparse(backup)
                manifest = json.loads(registry._read_file(backup / "manifest.json"))
                if not isinstance(manifest, dict):
                    raise ValueError("invalid recovery manifest")
                if (manifest.get("cleanup-id") != cleanup_id
                        or manifest.get("resource-id") != resource_id
                        or manifest.get("path") != row.get("path")
                        or manifest.get("branch") != row.get("branch")
                        or manifest.get("head") != row.get("head")
                        or manifest.get("recovery-ref") != f"refs/embraion/recovery/{cleanup_id}/{resource_id}"):
                    raise ValueError("recovery manifest mismatch")
                path = Path(manifest["path"]) if manifest.get("path") else None
                branch = manifest.get("branch")
                sha = manifest["head"]
                if (path is None and branch is None) or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
                    raise ValueError("invalid recovery identity")
                if path is not None and (not path.is_absolute() or ".." in path.parts):
                    raise ValueError("invalid recovery path")
                if branch is not None and (not isinstance(branch, str) or not _valid_branch(branch)):
                    raise ValueError("invalid recovery branch")
                if (not isinstance(manifest.get("bundle-sha256"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", manifest["bundle-sha256"])
                        or not isinstance(manifest.get("state-sha256"), dict)):
                    raise ValueError("invalid recovery hashes")
                bundle = backup / "head.bundle"
                if hashlib.sha256(registry._read_file(bundle)).hexdigest() != manifest["bundle-sha256"]:
                    raise ValueError("bundle changed")
                run(["git", "-C", str(root), "bundle", "verify", str(bundle)])
                if registry.git_value(root, "rev-parse", "--verify", manifest["recovery-ref"]) != sha:
                    raise ValueError("recovery ref changed")
                if path is not None:
                    _assert_no_reparse(path)
                    if path.exists() or path.is_symlink():
                        raise ValueError("restore path conflict")
                if branch is not None:
                    existing = registry.branch_sha(root, branch)
                    if row.get("removed-local-branch"):
                        if existing is not None:
                            raise ValueError("branch was recreated")
                    elif existing != sha:
                        raise ValueError("existing branch changed")
                if path is None and not row.get("removed-local-branch"):
                    raise ValueError("no local state to restore")
                state_files: list[tuple[Path, Path]] = []
                for name, digest in manifest["state-sha256"].items():
                    relative = Path(name)
                    if (not isinstance(name, str) or not isinstance(digest, str)
                            or not re.fullmatch(r"[0-9a-f]{64}", digest)
                            or relative.is_absolute() or ".." in relative.parts
                            or not relative.parts or path is None):
                        raise ValueError("invalid state backup path")
                    source = backup / "state" / relative
                    _assert_no_reparse(source)
                    if hashlib.sha256(registry._read_file(source)).hexdigest() != digest:
                        raise ValueError("state backup changed")
                    state_files.append((source, path / ".embraion" / "state" / relative))
                # All local conflicts and backup hashes are checked before
                # creating a branch or worktree. Remote state is never changed.
                if branch is not None and row.get("removed-local-branch"):
                    run(["git", "-C", str(root), "branch", branch, sha])
                if path is not None:
                    if branch is None:
                        run(["git", "-C", str(root), "worktree", "add", "--detach", str(path), sha])
                    else:
                        run(["git", "-C", str(root), "worktree", "add", str(path), branch])
                    for source, destination in state_files:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        _assert_no_reparse(destination.parent)
                        with os.fdopen(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
                            stream.write(registry._read_file(source))
                restored.append({"kind": row["kind"], "path": str(path) if path else None,
                                 "branch": branch, "status": "restored", "reason": "local-state-restored"})
            except (OSError, ValueError, TypeError, AttributeError, KeyError,
                    subprocess.SubprocessError) as exc:
                restored.append({"kind": row.get("kind", "worktree"),
                                 "path": str(path) if path else None, "status": "preserved",
                                 "reason": f"restore-conflict:{type(exc).__name__}"})
        return {"schema-version": 1, "dry-run": False, "cleanup-id": cleanup_id,
                "resources": restored}


def salvage_worktree(path: Path, output: Path | None = None) -> Path:
    source = path.resolve()
    destination = output or (state_root(project_root()) / "salvage" / source.name)
    destination.mkdir(parents=True, exist_ok=True)

    (destination / "diff.patch").write_text(
        run(["git", "-C", str(source), "diff"]).stdout,
        encoding="utf-8",
    )
    (destination / "staged.patch").write_text(
        run(["git", "-C", str(source), "diff", "--cached"]).stdout,
        encoding="utf-8",
    )

    untracked = run(
        [
            "git",
            "-C",
            str(source),
            "ls-files",
            "--others",
            "--exclude-standard",
        ]
    ).stdout.splitlines()

    copied: list[str] = []

    for relative in untracked:
        source_file = source / relative
        if source_file.is_file():
            target_file = destination / "untracked" / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            copied.append(relative)

    write_json(
        destination / "manifest.json",
        {
            "source": str(source),
            "untracked": copied,
            "captured-utc": datetime.now(timezone.utc).isoformat(),
        },
    )

    return destination
