"""CLI coverage for safe worktree housekeeping in disposable Git repositories."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "tools" / "cli"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


class WorktreeHousekeepingCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="worktree-housekeeping-cli-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name).resolve()
        self.repo = self.sandbox / "main"
        self.remote = self.sandbox / "remote.git"
        self.repo.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        git(self.repo, "init", "-b", "main", "--separate-git-dir", str(self.sandbox / "git-data"))
        git(self.repo, "config", "user.name", "Housekeeping Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / ".gitignore").write_text(".embraion/state/\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")
        shutil.copytree(self.sandbox / "git-data" / "objects", self.remote / "objects",
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.lock"))
        git(self.remote, "update-ref", "refs/heads/main", git(self.repo, "rev-parse", "HEAD"))
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        environment["EMBRAION_DISABLE_VERSION_RESOLUTION"] = "1"
        return subprocess.run(
            [sys.executable, "-m", "embraion.cli", "worktree", *args],
            cwd=self.repo,
            env=environment,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_gc_json_preview_and_apply_preserve_personal_worktree(self) -> None:
        personal = self.sandbox / "personal"
        git(self.repo, "worktree", "add", "-b", "task/personal", str(personal), "origin/main")

        preview = json.loads(self.cli("gc", "--json").stdout)
        applied = json.loads(self.cli("gc", "--apply", "--json").stdout)

        self.assertTrue(preview["dry-run"])
        self.assertTrue(personal.is_dir())
        self.assertFalse(applied["dry-run"])
        self.assertEqual(git(self.repo, "rev-parse", "refs/heads/task/personal"),
                         git(personal, "rev-parse", "HEAD"))

    def test_prepare_receipt_precedes_new_worktree_registration(self) -> None:
        target = self.sandbox / "new-worktree"
        prepared = json.loads(self.cli(
            "prepare", "--task-id", "task-prepare", "--host", "codex",
            "--branch", "task/prepare", "--path", str(target), "--json",
        ).stdout)

        receipt_id = prepared["receipt-id"]
        self.assertTrue(receipt_id)
        self.assertFalse(target.exists())
        self.assertNotIn("refs/heads/task/prepare", git(
            self.repo, "for-each-ref", "--format=%(refname)", "refs/heads"
        ).splitlines())

        git(self.repo, "worktree", "add", "-b", "task/prepare", str(target), "origin/main")
        registered = json.loads(self.cli(
            "register", "--task-id", "task-prepare", "--host", "codex",
            "--receipt-id", receipt_id, "--path", str(target),
        ).stdout)

        self.assertIsInstance(registered, dict)
        self.assertTrue(target.is_dir())
        self.assertEqual(git(target, "rev-parse", "HEAD"),
                         git(self.repo, "rev-parse", "refs/heads/task/prepare"))


if __name__ == "__main__":
    unittest.main()
