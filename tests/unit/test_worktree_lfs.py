"""Opt-in Git LFS hydration for new worktrees, in disposable repositories."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

from jsonschema import Draft202012Validator

from embraion import worktree, worktree_lfs

ROOT = Path(__file__).resolve().parents[2]
CONTENT = b"synthetic large asset\n"
OID = hashlib.sha256(CONTENT).hexdigest()


def pointer(content: bytes = CONTENT) -> bytes:
    return (f"version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(content).hexdigest()}\n"
            f"size {len(content)}\n").encode()


def isolated(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Ignore the machine's Git configuration, including any global LFS filter."""
    return {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid", **(extra or {})}


def git(repo: Path, *args: str, check: bool = True, environment: dict[str, str] | None = None
        ) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", "-C", str(repo), *args], check=False, capture_output=True, text=True,
                            env=environment or isolated())
    if check and result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def make_repo(root: Path, files: dict[str, bytes], attributes: str | None) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    if attributes is not None:
        (repo / ".gitattributes").write_text(attributes, encoding="utf-8")
    for name, data in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_bytes(data)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fixture")
    return repo


class LfsModeTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="worktree-lfs-mode-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        (self.repo / ".embraion").mkdir()

    def write(self, text: str) -> None:
        (self.repo / ".embraion" / "project.yaml").write_text(text, encoding="utf-8")

    def test_default_is_off(self) -> None:
        self.assertEqual("none", worktree_lfs.lfs_mode(self.repo))
        self.write("project:\n  name: Example\n")
        self.assertEqual("none", worktree_lfs.lfs_mode(self.repo))
        self.write("worktree:\n  lfs: none\n")
        self.assertEqual("none", worktree_lfs.lfs_mode(self.repo))

    def test_hydrate_is_accepted(self) -> None:
        self.write("worktree:\n  lfs: hydrate\n")
        self.assertEqual("hydrate", worktree_lfs.lfs_mode(self.repo))

    def test_invalid_values_fail_closed(self) -> None:
        for text in ("worktree:\n  lfs: true\n", "worktree:\n  lfs: pull\n", "worktree:\n  other: 1\n",
                     "worktree: hydrate\n", "worktree:\n  lfs: [hydrate]\n"):
            with self.subTest(text=text):
                self.write(text)
                with self.assertRaises(ValueError):
                    worktree_lfs.lfs_mode(self.repo)

    def test_schema_matches_the_runtime_validation(self) -> None:
        validator = Draft202012Validator(json.loads((ROOT / "schemas/project.schema.json").read_text("utf-8")))
        base = {"framework": {"repository": "Example/Repo", "version": "0.0.0"}, "project": {"name": "Example"}}
        self.assertEqual([], list(validator.iter_errors(base | {"worktree": {"lfs": "hydrate"}})))
        self.assertEqual([], list(validator.iter_errors(base | {"worktree": {"lfs": "none"}})))
        for bad in ({"lfs": "pull"}, {"lfs": True}, {"other": 1}):
            self.assertTrue(list(validator.iter_errors(base | {"worktree": bad})), bad)

    def test_git_timeout_requires_confirmed_descendant_termination(self) -> None:
        process = Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired(["git", "lfs", "fetch"], 1)
        with patch.object(worktree_lfs.subprocess, "Popen", return_value=process), \
             patch.object(worktree_lfs, "terminate_tree", return_value=False) as terminate:
            with self.assertRaisesRegex(RuntimeError, "termination is unconfirmed"):
                worktree_lfs._run(["git", "lfs", "fetch"], self.repo, timeout=1)
        terminate.assert_called_once_with(process)


class HydrationDetectionTests(unittest.TestCase):
    """Pointer versus content detection with a stubbed Git LFS client."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="worktree-lfs-unit-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name).resolve()
        self.calls: list[list[str]] = []
        self.lfs_available = True
        self.filter_available = True
        self.fetch_stderr = b""
        self.fetch_code = 0
        self.checkout_content: bytes | None = CONTENT

    def runner(self, args, cwd, data=None, timeout=300):  # noqa: ANN001 - mirrors worktree_lfs._run
        self.calls.append(list(args))
        words = list(args[1:])
        while words[:1] == ["-c"]:
            words = words[2:]  # Per-command configuration is not part of the subcommand.
        if words == ["config", "--get", "filter.lfs.process"]:
            return subprocess.CompletedProcess(args, 0 if self.filter_available else 1,
                                               b"git-lfs filter-process\n" if self.filter_available else b"", b"")
        if words[:1] == ["lfs"]:
            if words[1] == "version":
                return subprocess.CompletedProcess(args, 0 if self.lfs_available else 1, b"git-lfs/3\n", b"")
            if words[1] == "fetch":
                return subprocess.CompletedProcess(args, self.fetch_code, b"", self.fetch_stderr)
            if words[1] == "checkout":
                if self.checkout_content is not None:
                    (Path(cwd) / "assets" / "model.bin").write_bytes(self.checkout_content)
                return subprocess.CompletedProcess(args, 0, b"", b"")
        return subprocess.run(args, cwd=str(cwd), input=data, capture_output=True, check=False, env=isolated())

    def lfs_repo(self, remote: bool = True) -> Path:
        repo = make_repo(self.sandbox, {"assets/model.bin": pointer(), "notes.txt": b"plain\n"},
                         "*.bin filter=lfs diff=lfs merge=lfs -text\n")
        if remote:
            git(repo, "remote", "add", "origin", "https://example.invalid/org/repo.git")
        return repo

    def hydrate(self, repo: Path) -> dict:
        with patch.object(worktree_lfs, "_run", self.runner):
            return worktree_lfs.hydrate_lfs(repo)

    def test_repository_without_lfs_is_not_applicable(self) -> None:
        repo = make_repo(self.sandbox, {"notes.txt": b"plain\n"}, None)
        result = self.hydrate(repo)
        self.assertEqual("not-applicable", result["state"])
        self.assertEqual(0, result["files"])
        self.assertFalse([call for call in self.calls if call[:2] == ["git", "lfs"]])

    def test_lfs_attributes_without_lfs_files_are_not_applicable_even_without_git_lfs(self) -> None:
        self.lfs_available = False
        repo = make_repo(self.sandbox, {"notes.txt": b"plain\n"}, "*.bin filter=lfs -text\n")
        result = self.hydrate(repo)
        self.assertEqual("not-applicable", result["state"])
        self.assertEqual(0, result["files"])

    def test_large_ordinary_file_matching_an_lfs_attribute_is_not_an_lfs_file(self) -> None:
        repo = make_repo(self.sandbox, {"raw.bin": CONTENT}, "*.bin filter=lfs -text\n")
        self.assertEqual("not-applicable", self.hydrate(repo)["state"])

    def test_missing_git_lfs_fails_with_an_actionable_reason_when_lfs_files_exist(self) -> None:
        self.lfs_available = False
        result = self.hydrate(self.lfs_repo())
        self.assertEqual("failed", result["state"])
        self.assertEqual((1, 0, 1), (result["files"], result["verified"], result["missing"]))
        self.assertIn("git-lfs-unavailable", result["reason"])
        self.assertIn("git lfs pull", result["reason"])

    @unittest.skipUnless(os.name == "posix", "hiding git-lfs through PATH needs a POSIX layout; the stubbed test covers Windows")
    def test_missing_git_lfs_is_detected_through_the_path(self) -> None:
        repo = self.lfs_repo()
        empty = self.sandbox / "bin"
        empty.mkdir()
        (empty / "git").symlink_to(shutil.which("git"))
        with patch.dict(os.environ, {"PATH": str(empty)}):
            probe = subprocess.run(["git", "lfs", "version"], capture_output=True, check=False)
            if probe.returncode == 0:
                self.skipTest("git-lfs is installed next to Git itself, so PATH cannot hide it")
            result = worktree_lfs.hydrate_lfs(repo)
        self.assertEqual("failed", result["state"])
        self.assertIn("git-lfs-unavailable", result["reason"])

    def test_pointer_is_replaced_by_verified_content(self) -> None:
        repo = self.lfs_repo()
        self.assertEqual(pointer(), (repo / "assets/model.bin").read_bytes())
        result = self.hydrate(repo)
        self.assertEqual({"state": "hydrated", "files": 1, "verified": 1, "missing": 0, "reason": "verified"},
                         result)
        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        fetch = next(call for call in self.calls if call[:3] == ["git", "lfs", "fetch"])
        self.assertEqual(head, fetch[-1])
        self.assertEqual(CONTENT, (repo / "assets/model.bin").read_bytes())

    def test_content_already_present_needs_no_git_lfs(self) -> None:
        self.lfs_available = False
        repo = self.lfs_repo()
        (repo / "assets/model.bin").write_bytes(CONTENT)
        result = self.hydrate(repo)
        self.assertEqual("hydrated", result["state"])
        self.assertEqual("already-present", result["reason"])

    def test_wrong_size_or_wrong_oid_content_is_reported_missing(self) -> None:
        for content in (CONTENT + b"x", b"x" * len(CONTENT)):
            with self.subTest(size=len(content)):
                self.checkout_content = content
                with tempfile.TemporaryDirectory(prefix="worktree-lfs-wrong-") as scratch:
                    repo = make_repo(Path(scratch), {"assets/model.bin": pointer()}, "*.bin filter=lfs -text\n")
                    git(repo, "remote", "add", "origin", "https://example.invalid/org/repo.git")
                    result = self.hydrate(repo)
                self.assertEqual("failed", result["state"])
                self.assertEqual(1, result["missing"])
                self.assertEqual("lfs-content-missing-after-checkout", result["reason"])

    def test_fetch_failure_reason_never_carries_credentials(self) -> None:
        self.fetch_code = 2
        parameter = "to" + "ken=" + "abcd1234" + "efgh5678"  # Assembled so the source holds no secret-shaped text.
        self.fetch_stderr = (f"batch request: https://user:s3cretpass@example.invalid/org/repo.git/info/lfs"
                             f"/objects/batch?{parameter} failed\n").encode()
        result = self.hydrate(self.lfs_repo())
        self.assertEqual("failed", result["state"])
        self.assertTrue(result["reason"].startswith("git-lfs-fetch-failed"))
        for secret in ("s3cretpass", "user:", "abcd1234efgh5678", "ken="):
            self.assertNotIn(secret, result["reason"])

    def test_repository_without_a_remote_fails_before_fetching(self) -> None:
        result = self.hydrate(self.lfs_repo(remote=False))
        self.assertEqual("failed", result["state"])
        self.assertEqual("no remote to fetch LFS content from", result["reason"])
        self.assertEqual(1, result["missing"])
        self.assertFalse([call for call in self.calls if "fetch" in call])

    def test_password_containing_an_at_sign_is_fully_removed(self) -> None:
        self.fetch_code = 2
        self.fetch_stderr = b"cannot reach https://person:pa@ss@example.invalid/org/repo.git/info/lfs\n"
        result = self.hydrate(self.lfs_repo())
        for secret in ("person", "pa@ss", "@"):
            self.assertNotIn(secret, result["reason"])
        self.assertIn("https://example.invalid/org/repo.git/info/lfs", result["reason"])

    def test_fetch_timeout_fails_closed_and_keeps_the_pointer(self) -> None:
        repo = self.lfs_repo()
        original = self.runner

        def slow(args, cwd, data=None, timeout=300):  # noqa: ANN001
            if "fetch" in args:
                raise subprocess.TimeoutExpired(args, timeout)
            return original(args, cwd, data, timeout)

        with patch.object(worktree_lfs, "_run", slow):
            result = worktree_lfs.hydrate_lfs(repo)
        self.assertEqual("failed", result["state"])
        self.assertIn("timed out after", result["reason"])
        self.assertEqual(1, result["missing"])
        self.assertEqual(pointer(), (repo / "assets/model.bin").read_bytes())

    def test_locally_modified_lfs_file_is_reported_not_failed(self) -> None:
        repo = make_repo(self.sandbox, {"assets/model.bin": pointer(), "assets/other.bin": pointer(b"other\n")},
                         "*.bin filter=lfs -text\n")
        (repo / "assets/other.bin").write_bytes(b"edited by hand\n")
        git(repo, "remote", "add", "origin", "https://example.invalid/org/repo.git")
        result = self.hydrate(repo)
        self.assertEqual("hydrated", result["state"])
        self.assertEqual((2, 1, 0, 1), (result["files"], result["verified"], result["missing"], result["modified"]))
        self.assertIn("modified locally", result["reason"])
        self.assertEqual(b"edited by hand\n", (repo / "assets/other.bin").read_bytes())

    def test_content_that_hydration_left_wrong_is_still_a_failure_when_other_files_are_modified(self) -> None:
        repo = make_repo(self.sandbox, {"assets/model.bin": pointer(), "assets/other.bin": pointer(b"other\n")},
                         "*.bin filter=lfs -text\n")
        (repo / "assets/other.bin").write_bytes(b"edited by hand\n")
        git(repo, "remote", "add", "origin", "https://example.invalid/org/repo.git")
        self.checkout_content = b"wrong content, wrong size\n"
        result = self.hydrate(repo)
        self.assertEqual("failed", result["state"])
        self.assertEqual((1, 1), (result["missing"], result["modified"]))

    def test_fetch_uses_the_tracking_remote_only(self) -> None:
        repo = self.lfs_repo()
        git(repo, "remote", "add", "mirror", "https://example.invalid/org/mirror.git")
        git(repo, "config", "branch.main.remote", "mirror")
        self.hydrate(repo)
        fetch = next(call for call in self.calls if call[:3] == ["git", "lfs", "fetch"])
        self.assertEqual("mirror", fetch[3])

    def test_sparse_excluded_files_are_not_counted_missing(self) -> None:
        repo = self.lfs_repo()
        git(repo, "update-index", "--skip-worktree", "assets/model.bin")
        (repo / "assets/model.bin").unlink()
        self.checkout_content = None
        result = self.hydrate(repo)
        self.assertEqual("hydrated", result["state"])
        self.assertEqual(0, result["missing"])

    def _preflight_worktree(self) -> tuple[Path, str]:
        repo = self.sandbox / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "lfs", "install", "--local")
        (repo / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
        (repo / "assets").mkdir()
        (repo / "assets" / "model.bin").write_bytes(CONTENT)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "fixture")
        git(repo, "remote", "add", "origin", "https://example.invalid/org/repo.git")
        target = self.sandbox / "validation-worktree"
        git(repo, "worktree", "add", "--detach", str(target), "HEAD")
        (target / "assets" / "model.bin").write_bytes(pointer())
        return target, git(repo, "rev-parse", "HEAD").stdout.strip()

    def preflight(self, target: Path, head: str, **options: object) -> dict:
        resource = {"kind": "worktree", "path": str(target), "resource-id": "fixture", "state": "active"}
        with patch.object(worktree_lfs, "_run", self.runner), \
             patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {"fixture": resource}}), \
             patch.object(worktree_lfs.registry, "verify_resource", return_value=True):
            return worktree_lfs.preflight_lfs(target, head, **options)

    def test_preflight_hydrates_and_verifies_exact_registered_worktree(self) -> None:
        target, head = self._preflight_worktree()
        result = self.preflight(target, head)
        self.assertEqual("passed", result["state"], (result, git(target, "status", "--porcelain").stdout))
        self.assertEqual(1, result["lfs"]["verified"])
        self.assertEqual(head, result["head"])

    def test_preflight_rejects_dirty_locked_or_wrong_head_before_hydration(self) -> None:
        target, head = self._preflight_worktree()
        (target / "scratch.txt").write_text("dirty", encoding="utf-8")
        self.assertIn("dirty", self.preflight(target, head)["reason"])
        (target / "scratch.txt").unlink()
        git(target, "worktree", "lock", str(target))
        self.assertIn("locked", self.preflight(target, head)["reason"])
        git(target, "worktree", "unlock", str(target))
        lock = git(target, "rev-parse", "--path-format=absolute", "--git-path", "index.lock").stdout.strip()
        Path(lock).write_text("", encoding="utf-8")
        self.assertIn("index is locked", self.preflight(target, head)["reason"])
        Path(lock).unlink()
        self.assertIn("HEAD differs", self.preflight(target, "0" * len(head))["reason"])
        self.assertEqual(pointer(), (target / "assets/model.bin").read_bytes())

    def test_preflight_rejects_unverified_lfs_content(self) -> None:
        target, head = self._preflight_worktree()
        self.checkout_content = b"wrong data"
        result = self.preflight(target, head)
        self.assertEqual("failed", result["state"])
        self.assertEqual("failed", result["lfs"]["state"])

    def test_preflight_rejects_linked_or_oversized_pointer_without_reading_it(self) -> None:
        target, head = self._preflight_worktree()
        path = target / "assets/model.bin"
        path.write_bytes(b"x" * 4096)
        self.assertIn("dirty", self.preflight(target, head)["reason"])
        path.unlink()
        outside = self.sandbox / "outside-pointer"
        outside.write_bytes(pointer())
        try:
            path.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertIn("dirty", self.preflight(target, head)["reason"])

    def test_preflight_rejects_git_location_override(self) -> None:
        target, head = self._preflight_worktree()
        with patch.dict(os.environ, {"GIT_DIR": str(self.sandbox / "unrelated.git")}):
            result = self.preflight(target, head)
        self.assertEqual("failed", result["state"])
        self.assertIn("overridden", result["reason"])

    def test_preflight_rejects_assume_unchanged_and_skipped_index_entries(self) -> None:
        target, head = self._preflight_worktree()
        git(target, "update-index", "--assume-unchanged", ".gitattributes")
        (target / ".gitattributes").write_text("*.bin -filter\n", encoding="utf-8")
        self.assertIn("hidden or skipped", self.preflight(target, head)["reason"])
        git(target, "update-index", "--no-assume-unchanged", ".gitattributes")
        (target / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
        git(target, "update-index", "--skip-worktree", "assets/model.bin")
        (target / "assets/model.bin").unlink()
        self.assertIn("hidden or skipped", self.preflight(target, head)["reason"])

    def test_committed_attributes_ignore_info_override_for_all_pointers(self) -> None:
        repo = make_repo(self.sandbox, {
            "assets/one.bin": pointer(b"one"), "assets/two.bin": pointer(b"two"),
        }, "*.bin filter=lfs -text\n")
        (repo / ".git/info/attributes").write_text("assets/two.bin -filter\n", encoding="utf-8")
        self.assertEqual({"assets/one.bin", "assets/two.bin"},
                         {path for path, _, _ in worktree_lfs._tracked_lfs_files(repo)})

    def test_preflight_rejects_unregistered_worktree(self) -> None:
        target, head = self._preflight_worktree()
        with patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {}}):
            result = worktree_lfs.preflight_lfs(target, head)
        self.assertEqual("failed", result["state"])
        self.assertIn("registration", result["reason"])

    def test_unmanaged_preflight_is_explicit_and_has_no_lifecycle_authority(self) -> None:
        target, head = self._preflight_worktree()
        with patch.object(worktree_lfs, "_run", self.runner), \
             patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {}}):
            result = worktree_lfs.preflight_lfs(
                target, head, allow_unmanaged=True, primary_branch="main",
            )
        self.assertEqual("passed", result["state"], result)
        self.assertEqual("unmanaged", result["ownership"])
        self.assertIsNone(result["resource-id"])
        self.assertEqual(head, result["head"])

    def test_unmanaged_preflight_cli_requires_an_explicit_flag(self) -> None:
        from embraion.cli import build_parser

        base = ["worktree", "lfs-preflight", "--path", str(self.sandbox), "--expected-head", "a" * 40]
        self.assertFalse(build_parser().parse_args(base).allow_unmanaged)
        requested = build_parser().parse_args(base + ["--allow-unmanaged", "--primary-branch", "main"])
        self.assertTrue(requested.allow_unmanaged)
        self.assertEqual("main", requested.primary_branch)

    def test_unmanaged_preflight_rejects_orphan_marker_and_wrong_primary_branch(self) -> None:
        target, head = self._preflight_worktree()
        marker = worktree_lfs.registry.gitdir(target) / "embraion-resource.json"
        marker.write_text("{}", encoding="utf-8")
        with patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {}}):
            orphan = worktree_lfs.preflight_lfs(target, head, allow_unmanaged=True)
        self.assertIn("orphan", orphan["reason"])
        marker.unlink()
        with patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {}}):
            wrong = worktree_lfs.preflight_lfs(target, head, allow_unmanaged=True, primary_branch="other")
        self.assertIn("primary branch", wrong["reason"])

    def test_unmanaged_preflight_keeps_clean_lock_and_head_gates(self) -> None:
        target, head = self._preflight_worktree()
        with patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {}}):
            (target / "scratch.txt").write_text("dirty", encoding="utf-8")
            self.assertIn("dirty", worktree_lfs.preflight_lfs(target, head, allow_unmanaged=True)["reason"])
            (target / "scratch.txt").unlink()
            git(target, "worktree", "lock", str(target))
            self.assertIn("locked", worktree_lfs.preflight_lfs(target, head, allow_unmanaged=True)["reason"])
            git(target, "worktree", "unlock", str(target))
            self.assertIn("HEAD differs", worktree_lfs.preflight_lfs(
                target, "0" * len(head), allow_unmanaged=True,
            )["reason"])

    def test_preflight_with_no_lfs_files_still_checks_filters_and_identity(self) -> None:
        target, _ = self._preflight_worktree()
        git(target, "rm", "-f", "assets/model.bin")
        git(target, "commit", "-q", "-m", "no lfs files")
        head = git(target, "rev-parse", "HEAD").stdout.strip()
        result = self.preflight(target, head)
        self.assertEqual("passed", result["state"], result)
        self.assertEqual("not-applicable", result["lfs"]["state"])
        self.assertEqual(0, result["lfs"]["files"])
        self.filter_available = False
        self.assertIn("filter is not installed", self.preflight(target, head)["reason"])

    def test_preflight_requires_installed_filter_and_executable(self) -> None:
        target, head = self._preflight_worktree()
        self.filter_available = False
        self.assertIn("filter is not installed", self.preflight(target, head)["reason"])
        self.filter_available = True
        self.lfs_available = False
        self.assertIn("executable is unavailable", self.preflight(target, head)["reason"])

    def test_preflight_requires_the_named_remote(self) -> None:
        target, head = self._preflight_worktree()
        with patch.object(worktree_lfs, "_run", self.runner), \
             patch.object(worktree_lfs.registry, "load_registry", return_value={"resources": {
                 "fixture": {"kind": "worktree", "path": str(target), "resource-id": "fixture", "state": "active"}}}), \
             patch.object(worktree_lfs.registry, "verify_resource", return_value=True):
            result = worktree_lfs.preflight_lfs(target, head, remote="missing")
        self.assertEqual("failed", result["state"])
        self.assertIn("remote is unavailable", result["reason"])

    def test_preflight_rechecks_head_after_hydration(self) -> None:
        target, head = self._preflight_worktree()
        hydrate = worktree_lfs.hydrate_lfs

        def advance(path: Path, remote: str | None = None) -> dict:
            result = hydrate(path, remote=remote)
            git(path, "commit", "--allow-empty", "-q", "-m", "advance")
            return result

        with patch.object(worktree_lfs, "hydrate_lfs", side_effect=advance):
            result = self.preflight(target, head)
        self.assertEqual("failed", result["state"])
        self.assertIn("HEAD differs", result["reason"])


@unittest.skipUnless(shutil.which("git-lfs"), "git-lfs is not installed")
class RealGitLfsTests(unittest.TestCase):
    """End to end against a local bare repository that acts as the LFS remote."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="worktree-lfs-real-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name).resolve()
        self.environment = isolated()
        patcher = patch.dict(os.environ, self.environment)
        patcher.start()
        self.addCleanup(patcher.stop)
        remote = self.sandbox / "remote.git"
        subprocess.run(["git", "init", "-q", "-b", "main", "--bare", str(remote)], check=True)
        author = self.sandbox / "author"
        author.mkdir()
        git(author, "init", "-q", "-b", "main")
        git(author, "lfs", "install", "--local")
        git(author, "lfs", "track", "*.bin")
        (author / "model.bin").write_bytes(CONTENT)
        (author / "notes.txt").write_text("plain\n", encoding="utf-8")
        git(author, "add", "-A")
        git(author, "commit", "-q", "-m", "assets")
        git(author, "remote", "add", "origin", str(remote))
        git(author, "push", "-q", "origin", "main")
        # The consumer clone has pointers only: no LFS objects are stored locally.
        self.clone = self.sandbox / "clone"
        subprocess.run(["git", "clone", "-q", str(remote), str(self.clone)], check=True,
                       env={**self.environment, "GIT_LFS_SKIP_SMUDGE": "1"})

    def new_worktree(self) -> Path:
        target = self.sandbox / "task"
        git(self.clone, "worktree", "add", "-q", "--detach", str(target), "origin/main",
            environment={**self.environment, "GIT_LFS_SKIP_SMUDGE": "1"})
        return target

    def test_pointer_checkout_is_hydrated_from_the_lfs_remote(self) -> None:
        target = self.new_worktree()
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())
        result = worktree_lfs.hydrate_lfs(target)
        self.assertEqual({"state": "hydrated", "files": 1, "verified": 1, "missing": 0, "reason": "verified"},
                         result)
        self.assertEqual(CONTENT, (target / "model.bin").read_bytes())

    def test_registered_preflight_hydrates_and_leaves_exact_head_clean(self) -> None:
        git(self.clone, "lfs", "install", "--local")
        expected = git(self.clone, "rev-parse", "origin/main").stdout.strip()
        target = self.sandbox / "registered-task"
        with patch.dict(os.environ, {"GIT_LFS_SKIP_SMUDGE": "1"}):
            worktree.create_detached_worktree(target, base="origin/main", task_id="fixture-task",
                                              host="codex", repo=self.clone)
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())
        result = worktree_lfs.preflight_lfs(target, expected)
        self.assertEqual("passed", result["state"], result)
        self.assertEqual(expected, git(target, "rev-parse", "HEAD").stdout.strip())
        self.assertEqual("", git(target, "status", "--porcelain", "--untracked-files=all").stdout.strip())
        self.assertEqual(CONTENT, (target / "model.bin").read_bytes())

    def test_unmanaged_git_worktree_preflight_hydrates_without_registering(self) -> None:
        git(self.clone, "lfs", "install", "--local")
        target = self.new_worktree()
        expected = git(target, "rev-parse", "HEAD").stdout.strip()
        result = worktree_lfs.preflight_lfs(target, expected, allow_unmanaged=True, primary_branch="main")
        self.assertEqual("passed", result["state"], result)
        self.assertEqual("unmanaged", result["ownership"])
        self.assertIsNone(result["resource-id"])
        self.assertEqual(CONTENT, (target / "model.bin").read_bytes())
        self.assertEqual("", git(target, "status", "--porcelain", "--untracked-files=all").stdout.strip())

    def test_unreachable_lfs_remote_fails_but_keeps_the_worktree(self) -> None:
        target = self.new_worktree()
        shutil.rmtree(self.sandbox / "remote.git" / "lfs")
        result = worktree_lfs.hydrate_lfs(target)
        self.assertEqual("failed", result["state"])
        self.assertEqual(1, result["missing"])
        self.assertTrue(result["reason"].startswith("git-lfs-fetch-failed"))
        self.assertTrue(target.is_dir())
        self.assertEqual(pointer(), (target / "model.bin").read_bytes())


if __name__ == "__main__":
    unittest.main()
