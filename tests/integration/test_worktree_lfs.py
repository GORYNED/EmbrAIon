"""CLI coverage for opt-in Git LFS hydration of new worktrees."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "tools" / "cli"
CONTENT = b"synthetic large asset\n"


def pointer(content: bytes = CONTENT) -> bytes:
    return (f"version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(content).hexdigest()}\n"
            f"size {len(content)}\n").encode()


@unittest.skipUnless(shutil.which("git-lfs"), "git-lfs is not installed")
class WorktreeLfsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="worktree-lfs-cli-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name).resolve()
        self.environment = {
            **os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "EMBRAION_DISABLE_VERSION_RESOLUTION": "1", "PYTHONPATH": str(SOURCE_ROOT),
        }
        remote = self.sandbox / "remote.git"
        self.git(self.sandbox, "init", "-q", "-b", "main", "--bare", str(remote))
        author = self.sandbox / "author"
        author.mkdir()
        self.git(author, "init", "-q", "-b", "main")
        self.git(author, "lfs", "install", "--local")
        self.git(author, "lfs", "track", "*.bin")
        (author / "model.bin").write_bytes(CONTENT)
        (author / ".gitignore").write_text(".embraion/state/\n", encoding="utf-8")
        self.git(author, "add", "-A")
        self.git(author, "commit", "-q", "-m", "assets")
        self.git(author, "remote", "add", "origin", str(remote))
        self.git(author, "push", "-q", "origin", "main")
        self.repo = self.sandbox / "main"
        self.git(self.sandbox, "clone", "-q", str(remote), str(self.repo),
                 environment={**self.environment, "GIT_LFS_SKIP_SMUDGE": "1"})
        # New worktrees start with pointer files, as on a machine without LFS smudging.
        self.environment["GIT_LFS_SKIP_SMUDGE"] = "1"

    def git(self, cwd: Path, *args: str, environment: dict[str, str] | None = None) -> str:
        result = subprocess.run(["git", "-C", str(cwd), *args], check=False, capture_output=True, text=True,
                                env=environment or self.environment)
        if result.returncode:
            raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def settings(self, text: str) -> None:
        (self.repo / ".embraion").mkdir(exist_ok=True)
        (self.repo / ".embraion" / "project.yaml").write_text(
            "project:\n  name: Example\n" + text, encoding="utf-8")

    def cli(self, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
        environment = dict(self.environment)
        if path is not None:
            environment["PATH"] = path
        return subprocess.run([sys.executable, "-m", "embraion.cli", "worktree", *args], cwd=self.repo,
                              env=environment, check=False, capture_output=True, text=True)

    def create(self, name: str, **kwargs: str) -> tuple[subprocess.CompletedProcess[str], Path]:
        target = self.sandbox / name
        return self.cli("create", f"task/{name}", "--path", str(target), "--task-id", name, **kwargs), target

    def test_default_leaves_pointers_untouched(self) -> None:
        self.settings("")
        created, target = self.create("default")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertNotIn("LFS", created.stdout + created.stderr)
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())

    def test_explicit_none_leaves_pointers_untouched(self) -> None:
        self.settings("worktree:\n  lfs: none\n")
        created, target = self.create("explicit-none")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())

    def test_hydrate_fetches_and_verifies_content(self) -> None:
        self.settings("worktree:\n  lfs: hydrate\n")
        created, target = self.create("hydrate")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertIn("LFS hydrated: 1 of 1 files verified", created.stdout)
        self.assertEqual(CONTENT, (target / "model.bin").read_bytes())

    def test_detached_creation_is_hydrated_too(self) -> None:
        self.settings("worktree:\n  lfs: hydrate\n")
        target = self.sandbox / "detached"
        created = self.cli("create", "--detach", "--path", str(target), "--task-id", "detached")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertEqual(CONTENT, (target / "model.bin").read_bytes())

    def test_missing_git_lfs_fails_the_command_but_keeps_the_worktree(self) -> None:
        self.settings("worktree:\n  lfs: hydrate\n")
        bin_dir = self.sandbox / "bin"
        bin_dir.mkdir()
        (bin_dir / "git").symlink_to(shutil.which("git"))
        created, target = self.create("no-lfs", path=str(bin_dir))
        self.assertEqual(1, created.returncode)
        self.assertIn("git-lfs-unavailable", created.stderr)
        self.assertIn(str(target), created.stderr)
        self.assertTrue(target.is_dir())
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())

    def test_invalid_setting_fails_before_any_worktree_is_created(self) -> None:
        self.settings("worktree:\n  lfs: pull\n")
        created, target = self.create("invalid")
        self.assertEqual(2, created.returncode)
        self.assertIn("worktree.lfs", created.stderr)
        self.assertFalse(target.exists())

    def test_register_reports_the_lfs_result_for_a_natively_created_worktree(self) -> None:
        self.settings("worktree:\n  lfs: hydrate\n")
        target = self.sandbox / "native"
        prepared = json.loads(self.cli("prepare", "--task-id", "native", "--branch", "task/native",
                                       "--path", str(target), "--json").stdout)
        self.git(self.repo, "worktree", "add", "-q", "-b", "task/native", str(target), "origin/main")
        registered = self.cli("register", "--task-id", "native", "--host", "codex",
                              "--receipt-id", prepared["receipt-id"], "--path", str(target))
        self.assertEqual(0, registered.returncode, registered.stderr)
        report = json.loads(registered.stdout)
        self.assertEqual({"state": "hydrated", "files": 1, "verified": 1, "missing": 0, "reason": "verified"},
                         report["lfs"])
        self.assertEqual(CONTENT, (target / "model.bin").read_bytes())

    def test_register_output_is_unchanged_by_default(self) -> None:
        self.settings("")
        target = self.sandbox / "native-default"
        prepared = json.loads(self.cli("prepare", "--task-id", "native-default", "--branch", "task/native-default",
                                       "--path", str(target), "--json").stdout)
        self.git(self.repo, "worktree", "add", "-q", "-b", "task/native-default", str(target), "origin/main")
        registered = self.cli("register", "--task-id", "native-default", "--host", "codex",
                              "--receipt-id", prepared["receipt-id"], "--path", str(target))
        self.assertEqual(0, registered.returncode, registered.stderr)
        self.assertNotIn("lfs", json.loads(registered.stdout))
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())


if __name__ == "__main__":
    unittest.main()
