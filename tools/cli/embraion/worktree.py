from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import project_root, run, state_root, write_json


def parse_worktrees(repo: Path) -> list[dict[str, Any]]:
    result = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])

    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in result.stdout.splitlines() + [""]:
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

        clean = is_clean(path)
        integrated = _directly_integrated(path, head, base)

        if clean and integrated:
            candidates.append(item)

    if apply:
        for item in candidates:
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
