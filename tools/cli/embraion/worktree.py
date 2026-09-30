from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root, read_json, run, state_root, write_json
from .environment import child_environment


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
) -> Path:
    repo = project_root()
    run(["git", "-C", str(repo), "fetch", "--prune", "origin"])

    target = destination or (repo.parent / f"{repo.name}-{branch.replace('/', '-')}")
    run(
        [
            "git",
            "-C",
            str(repo),
            "worktree",
            "add",
            "-b",
            branch,
            str(target),
            base,
        ]
    )
    write_json(_git_directory(target) / "embraion-worktree.json", {
        "schema-version": 1, "path": str(target.resolve()), "branch": branch,
    })
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
    return Path(result.stdout.strip()).resolve(strict=True)


def _inactive_owned_worktree(path: Path, branch: str | None) -> bool:
    """Require ownership and terminal local evidence; absence is not inactivity."""
    try:
        metadata = _git_directory(path)
        marker = metadata / "embraion-worktree.json"
        if marker.is_symlink() or read_json(marker) != {
            "schema-version": 1, "path": str(path), "branch": branch,
        }:
            return False
        # Git operations can be in progress even with an empty status output.
        pending = ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
                   "BISECT_LOG", "BISECT_START", "MERGE_AUTOSTASH", "rebase-merge", "rebase-apply", "sequencer", "index.lock", "HEAD.lock")
        if any((metadata / name).exists() for name in pending):
            return False
        state = path / ".embraion/state"
        if any(part.is_symlink() for part in (path / ".embraion", state, state / "runs")):
            return False
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
            if record.is_symlink():
                return False
            value = read_json(record)
            terminal = {"completed", "cancelled"} if record == session else {"completed", "cancelled", "failed"}
            if not isinstance(value, dict) or value.get("state") not in terminal:
                return False
        return True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return False


def gc_worktrees(base: str = "origin/main", apply: bool = False) -> list[dict[str, Any]]:
    repo = project_root()
    current = repo.resolve()
    candidates: list[dict[str, Any]] = []

    for item in parse_worktrees(repo):
        path = Path(item["path"]).resolve()
        branch = item.get("branch")
        head = item.get("head")

        if path == current or branch == "main" or item.get("locked") or not head:
            continue

        if not _inactive_owned_worktree(path, branch):
            continue

        clean = is_clean(path)
        integrated = _directly_integrated(path, head, base)

        if clean and integrated:
            candidates.append(item)

    if apply:
        for item in candidates:
            # Recheck immediately before removal; a preview is not authorization
            # to delete a worktree whose activity or Git state has since changed.
            path = Path(item["path"]).resolve()
            current_items = parse_worktrees(repo)
            if not any(row == item for row in current_items):
                continue
            if (not _inactive_owned_worktree(path, item.get("branch")) or not is_clean(path)
                    or not _directly_integrated(path, item["head"], base)):
                continue
            run(["git", "-C", str(repo), "worktree", "remove", item["path"]])
            if item.get("branch"):
                run(
                    ["git", "-C", str(repo), "branch", "-d", item["branch"]],
                    check=False,
                )

    return candidates


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
