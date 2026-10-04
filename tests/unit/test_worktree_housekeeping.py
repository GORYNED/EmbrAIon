"""Safety regressions for managed worktree housekeeping.

Every Git mutation in this module is confined to a temporary repository.
"""
from __future__ import annotations

import shutil
import json
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from embraion import worktree
from embraion import worktree_github


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def copy_missing_objects(source: Path, destination: Path) -> None:
    for object_file in source.rglob("*"):
        if not object_file.is_file() or object_file.name.endswith(".lock"):
            continue
        target = destination / object_file.relative_to(source)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(object_file, target)


class TemporaryGitRepository(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="worktree-housekeeping-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name).resolve()
        self.remote = self.sandbox / "remote.git"
        self.repo = self.sandbox / "main"
        self.repo.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        git(self.repo, "init", "-b", "main", "--separate-git-dir", str(self.sandbox / "git-data"))
        git(self.repo, "config", "user.name", "Housekeeping Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / ".gitignore").write_text(".embraion/state/\n", encoding="utf-8")
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")
        copy_missing_objects(self.sandbox / "git-data" / "objects", self.remote / "objects")
        git(self.remote, "update-ref", "refs/heads/main", self.head())
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")
        # The fixture pins origin/main locally. Windows sandboxes intermittently
        # deny Git's local transport helper, so no test depends on a real fetch.
        real_run = worktree.run

        def fixture_run(command, *args, **kwargs):
            if len(command) > 3 and command[3] == "fetch":
                return subprocess.CompletedProcess(command, 0, "", "")
            return real_run(command, *args, **kwargs)

        run_patch = patch.object(worktree, "run", side_effect=fixture_run)
        run_patch.start()
        self.addCleanup(run_patch.stop)

    def head(self, ref: str = "HEAD") -> str:
        return git(self.repo, "rev-parse", ref).stdout.strip()

    def branches(self) -> list[str]:
        return git(self.repo, "for-each-ref", "--format=%(refname)", "refs/heads").stdout.splitlines()

    def worktrees(self) -> list[dict[str, object]]:
        return worktree.parse_worktrees(self.repo)


class HousekeepingSafetyTests(TemporaryGitRepository):
    def assert_report_schema(self, report: dict[str, object]) -> None:
        schema = json.loads((Path(__file__).resolve().parents[2] /
                             "schemas" / "worktree-report.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)

    def managed_worktree(self, task_id: str = "managed-task") -> Path:
        target = self.sandbox / task_id
        with patch.object(worktree, "project_root", return_value=self.repo):
            worktree.create_worktree(f"task/{task_id}", target, task_id=task_id,
                                     host="codex")
        return target

    def bare_head(self, _repo: Path, branch: str) -> str | None:
        result = git(self.remote, "rev-parse", "--verify", f"refs/heads/{branch}", check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def publish_managed_branch(self, task_id: str = "managed-task") -> dict[str, object]:
        branch = f"task/{task_id}"
        real_run = worktree.run

        def receive_create(command, *args, **kwargs):
            if "push" not in command:
                return real_run(command, *args, **kwargs)
            ref = f"refs/heads/{branch}"
            self.assertIn(f"--force-with-lease={ref}:", command)
            self.assertIsNone(self.bare_head(self.repo, branch))
            head = self.head(branch)
            self.assertIn(f"{head}:{ref}", command)
            copy_missing_objects(self.sandbox / "git-data" / "objects", self.remote / "objects")
            git(self.remote, "update-ref", ref, head, "0" * 40)
            return subprocess.CompletedProcess(command, 0,
                                               f"*\t{head}:{ref}\t[new branch]\n", "")

        with patch.object(worktree.github, "remote_head", side_effect=self.bare_head), \
                patch.object(worktree, "run", side_effect=receive_create):
            return worktree.publish_branch(task_id, branch, repo=self.repo)

    def github_evidence(self):
        return (
            patch.object(worktree.github, "github_evidence", return_value={"default-branch": "main"}),
            patch.object(worktree.github, "branch_rules", return_value=False),
            patch.object(worktree.github, "integration_proof", return_value=(True, "merged-pr")),
            patch.object(worktree.github, "remote_head", return_value=None),
        )

    def test_housekeeping_defaults_and_invalid_overlay_fail_closed(self) -> None:
        self.assertEqual(
            {"on-task-start": False, "local-branches": True, "remote-branches": False,
             "worktrees": True, "preserve-branches": []},
            worktree.housekeeping_config(self.repo),
        )
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  remote-branches: maybe\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            worktree.housekeeping_config(self.repo)

    def test_default_preview_does_not_write_refs_registry_or_worktrees(self) -> None:
        before_refs = self.branches()
        before_worktrees = self.worktrees()
        common = Path(git(self.repo, "rev-parse", "--git-common-dir").stdout.strip())
        if not common.is_absolute():
            common = (self.repo / common).resolve()
        before_files = {path.relative_to(common): path.read_bytes() for path in common.rglob("*") if path.is_file()}

        report = worktree.gc_report(repo=self.repo)

        self.assertIsInstance(report, dict)
        self.assert_report_schema(report)
        self.assertEqual(before_refs, self.branches())
        self.assertEqual(before_worktrees, self.worktrees())
        after_files = {path.relative_to(common): path.read_bytes() for path in common.rglob("*") if path.is_file()}
        self.assertEqual(before_files, after_files)

    def test_prepare_rejects_preexisting_branch_without_adopting_it(self) -> None:
        branch = "task/preexisting"
        git(self.repo, "branch", branch)
        target = self.sandbox / "proposed-worktree"

        with self.assertRaises((ValueError, RuntimeError, FileExistsError)):
            worktree.prepare_task(
                "task-1", host="codex", branch=branch, path=target, base="origin/main", repo=self.repo
            )

        self.assertFalse(target.exists())
        self.assertEqual(self.head(), self.head(branch))
        self.assertEqual(1, len(self.worktrees()))

    def test_report_identifies_registered_host_and_never_guesses_reused_or_user_branch(self) -> None:
        target = self.managed_worktree()
        personal = "codex/personal"
        git(self.repo, "branch", personal)
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(repo=self.repo)
        self.assert_report_schema(report)
        managed = next(row for row in report["resources"] if row.get("path") == str(target))
        self.assertEqual({"status": "registered", "host": "codex",
                          "task-ids": ["managed-task"], "creation-source": "embraion-create"},
                         managed["provenance"])
        user = next(row for row in report["resources"] if row.get("branch") == personal)
        self.assertEqual("unknown", user["provenance"]["status"])
        self.assertIsNone(user["provenance"]["host"])
        data = worktree.registry.load_registry(self.repo)
        resource = next(iter(data["resources"].values()))
        resource["branch-reflog-id"] = "0" * 64
        worktree.registry.save_registry(self.repo, data)
        with self.github_evidence()[0]:
            report = worktree.gc_report(repo=self.repo)
        managed = next(row for row in report["resources"] if row.get("path") == str(target))
        self.assertEqual("unknown", managed["provenance"]["status"])
        self.assertIsNone(managed["provenance"]["host"])
        self.assertTrue(target.is_dir())
        self.assertEqual(2, len(self.worktrees()))

    def test_prepare_rejects_preexisting_path_without_touching_its_content(self) -> None:
        target = self.sandbox / "existing"
        target.mkdir()
        marker = target / "personal.txt"
        marker.write_text("preserve", encoding="utf-8")

        with self.assertRaises((ValueError, RuntimeError, FileExistsError)):
            worktree.prepare_task(
                "task-2", host="codex", branch="task/new", path=target, base="origin/main", repo=self.repo
            )

        self.assertEqual("preserve", marker.read_text(encoding="utf-8"))
        self.assertNotIn("refs/heads/task/new", self.branches())
        self.assertEqual(1, len(self.worktrees()))

    def test_unregistered_personal_worktree_is_preserved_even_with_managed_prefix(self) -> None:
        target = self.sandbox / "embraion-task-personal"
        git(self.repo, "worktree", "add", "-b", "task/personal", str(target), "origin/main")

        worktree.gc_report(base="origin/main", apply=True, repo=self.repo)

        self.assertTrue(target.is_dir())
        self.assertIn("refs/heads/task/personal", self.branches())

    def test_legacy_marker_never_grants_local_branch_deletion_authority(self) -> None:
        branch = "codex/legacy"
        target = self.sandbox / "legacy"
        git(self.repo, "worktree", "add", "-b", branch, str(target), "origin/main")
        worktree.write_json(worktree.registry.gitdir(target) / "embraion-worktree.json", {
            "schema-version": 1, "path": str(target), "branch": branch,
        })
        worktree.write_json(target / ".embraion/state/runs/old.json", {"state": "completed"})
        # A recreated ref must not inherit branch ownership from the old marker.
        head = self.head(branch)
        git(self.repo, "update-ref", "-d", f"refs/heads/{branch}", head)
        git(self.repo, "update-ref", "--create-reflog", f"refs/heads/{branch}", head)
        report = worktree.gc_report(apply=True, repo=self.repo)
        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertEqual("removed", row["status"])
        self.assertEqual("legacy-ownership-unproven", row["preserved-local-branch"])
        self.assertEqual(head, self.head(branch))

    def test_receipt_binds_exact_task_host_path_and_branch(self) -> None:
        target = self.sandbox / "managed"
        receipt = worktree.prepare_task(
            "task-3", branch="task/managed", path=target, repo=self.repo
        )["receipt-id"]
        git(self.repo, "worktree", "add", "-b", "task/managed", str(target), "origin/main")

        for task, host, path in (
            ("other-task", "codex", target),
            ("task-3", "portable", target),
            ("task-3", "codex", self.repo),
        ):
            with self.subTest(task=task, host=host, path=path):
                with self.assertRaises(ValueError):
                    worktree.register_worktree(task, host, path=path,
                                               receipt_id=receipt, repo=self.repo)

        resource = worktree.register_worktree(
            "task-3", "codex", path=target, receipt_id=receipt, repo=self.repo
        )
        self.assertEqual("task/managed", resource["branch"])
        with self.assertRaises(ValueError):
            worktree.register_worktree(
                "task-3", "codex", path=target, receipt_id=receipt, repo=self.repo
            )

    def test_branch_only_receipt_registers_only_a_new_branch(self) -> None:
        receipt = worktree.prepare_task(
            "branch-task", host="codex", branch="task/branch-only", repo=self.repo
        )["receipt-id"]
        self.assertNotIn("refs/heads/task/branch-only", self.branches())
        git(self.repo, "branch", "task/branch-only", "origin/main")

        resource = worktree.register_worktree(
            "branch-task", "codex", receipt_id=receipt, repo=self.repo
        )

        self.assertEqual("branch", resource["kind"])
        self.assertEqual("task/branch-only", resource["branch"])
        self.assertIsNone(resource["path"])

    def test_detached_worktree_receipt_registers_without_adopting_a_branch(self) -> None:
        target = self.sandbox / "detached"
        receipt = worktree.prepare_task(
            "detached-task", host="codex", path=target, repo=self.repo
        )["receipt-id"]
        git(self.repo, "worktree", "add", "--detach", str(target), "origin/main")

        resource = worktree.register_worktree(
            "detached-task", "codex", path=target, receipt_id=receipt, repo=self.repo
        )

        self.assertEqual("worktree", resource["kind"])
        self.assertIsNone(resource["branch"])
        worktree.update_task_state("detached-task", "completed", repo=self.repo)
        applied = worktree.gc_report(apply=True, repo=self.repo)
        self.assertEqual("host-archive-required", next(
            row["reason"] for row in applied["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_on_task_start_is_opt_in_once_and_only_for_writable_independent_tasks(self) -> None:
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  on-task-start: true\n", encoding="utf-8")
        report = {"schema-version": 1, "dry-run": False, "cleanup-id": None, "resources": []}

        with patch.object(worktree, "gc_report", return_value=report) as gc:
            worktree.prepare_task("read-only", writable=False, repo=self.repo)
            worktree.prepare_task("subtask", independent=False, repo=self.repo)
            worktree.prepare_task("unknown-scope", independent="unknown", repo=self.repo)
            worktree.prepare_task("unknown-access", writable="unknown", repo=self.repo)
            worktree.prepare_task("writable", repo=self.repo)
            worktree.prepare_task("writable", repo=self.repo)

        gc.assert_called_once_with(base="origin/main", apply=True, repo=self.repo,
                                   include_legacy=False)

    def test_parallel_starts_claim_housekeeping_only_once(self) -> None:
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  on-task-start: true\n", encoding="utf-8")
        entered, release = threading.Event(), threading.Event()

        def cleanup(**_kwargs):
            entered.set()
            if not release.wait(10):
                raise AssertionError("second task start did not finish")
            return {"schema-version": 1, "dry-run": False, "cleanup-id": None, "resources": []}

        with patch.object(worktree, "gc_report", side_effect=cleanup) as gc, \
                ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(worktree.prepare_task, "same-task", repo=self.repo)
            try:
                self.assertTrue(entered.wait(10))
                second = pool.submit(worktree.prepare_task, "same-task", repo=self.repo)
                self.assertTrue(second.result(timeout=10)["dry-run"])
            finally:
                release.set()
            first.result(timeout=10)
            gc.assert_called_once()

    def test_unknown_ignored_files_and_pending_git_operation_are_preserved(self) -> None:
        exclude = self.sandbox / "git-data" / "info" / "exclude"
        exclude.write_text("*.cache\n", encoding="utf-8")
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        ignored = target / "important.cache"
        ignored.write_text("recoverable local work", encoding="utf-8")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)
            row = next(row for row in report["resources"] if row["path"] == str(target))
            self.assertEqual("unmanaged-ignored-files", row["reason"])
            self.assertEqual("recoverable local work", ignored.read_text(encoding="utf-8"))
            ignored.unlink()
            pending = worktree.registry.gitdir(target) / "CHERRY_PICK_HEAD"
            pending.write_text(self.head(), encoding="utf-8")
            report = worktree.gc_report(apply=True, repo=self.repo)
            row = next(row for row in report["resources"] if row["path"] == str(target))
            self.assertEqual("git-operation-in-progress", row["reason"])
            self.assertTrue(target.is_dir())

    def test_reused_checkout_links_all_tasks_and_noncompleted_states_preserve(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        worktree.update_task_state("second-task", "active", repo=target)
        resource = next(iter(worktree.registry.load_registry(self.repo)["resources"].values()))
        self.assertEqual(["managed-task", "second-task"], resource["task-ids"])
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            for state in ("active", "queued", "incomplete", "cancelled", "failed"):
                worktree.update_task_state("second-task", state, repo=target)
                report = worktree.gc_report(apply=True, repo=self.repo)
                row = next(row for row in report["resources"] if row["path"] == str(target))
                self.assertEqual("task-not-completed", row["reason"], state)
                self.assertTrue(target.is_dir())

    def test_remote_only_unregistered_branch_is_reported_and_preserved(self) -> None:
        branch = "codex/user-remote-only"
        git(self.remote, "update-ref", f"refs/heads/{branch}", self.head())
        real_run = worktree.run

        def bare_inventory(command, *args, **kwargs):
            if "ls-remote" in command and "--heads" in command and "origin" in command:
                return subprocess.CompletedProcess(
                    command, 0, f"{self.head()}\trefs/heads/{branch}\n", ""
                )
            return real_run(command, *args, **kwargs)

        with patch.object(worktree, "run", side_effect=bare_inventory):
            report = worktree.gc_report(apply=True, repo=self.repo)
        row = next(row for row in report["resources"] if row["branch"] == branch)
        self.assertEqual("unowned-remote-branch", row["reason"])
        self.assertEqual(self.head(), git(self.remote, "rev-parse", f"refs/heads/{branch}").stdout.strip())

    def test_hardlinked_local_state_is_preserved_without_touching_external_file(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        outside = self.sandbox / "outside-state.json"
        outside.write_text('{"state":"completed"}\n', encoding="utf-8")
        state = target / ".embraion" / "state" / "runs" / "run.json"
        state.parent.mkdir(parents=True)
        try:
            state.hardlink_to(outside)
        except PermissionError:
            self.skipTest("Windows sandbox forbids creating fixture hardlinks")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)
        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertEqual("preserved", row["status"])
        self.assertTrue(target.is_dir())
        self.assertEqual('{"state":"completed"}\n', outside.read_text(encoding="utf-8"))

    def test_managed_worktree_requires_completed_task_and_preserves_dirty_and_locked(self) -> None:
        target = self.managed_worktree()
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            active = worktree.gc_report(repo=self.repo)
            self.assertEqual("task-not-completed", next(
                row["reason"] for row in active["resources"] if row["path"] == str(target)
            ))

            worktree.update_task_state("managed-task", "completed", repo=self.repo)
            dirty = target / "untracked.txt"
            dirty.write_text("unsaved", encoding="utf-8")
            worktree.gc_report(apply=True, repo=self.repo)
            self.assertTrue(target.exists())
            dirty.unlink()

            git(self.repo, "worktree", "lock", str(target))
            worktree.gc_report(apply=True, repo=self.repo)
            self.assertTrue(target.exists())
            git(self.repo, "worktree", "unlock", str(target))

            candidate = worktree.gc_report(repo=self.repo)
            self.assertEqual("candidate", next(
                row["status"] for row in candidate["resources"] if row["path"] == str(target)
            ))

    def test_host_native_registration_stays_for_host_archive(self) -> None:
        target = self.sandbox / "host-native"
        receipt = worktree.prepare_task(
            "host-task", branch="task/host-native", path=target, repo=self.repo
        )["receipt-id"]
        git(self.repo, "worktree", "add", "-b", "task/host-native", str(target), "origin/main")
        worktree.register_worktree("host-task", "codex", path=target,
                                   receipt_id=receipt, repo=self.repo)
        worktree.update_task_state("host-task", "completed", repo=self.repo)
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            applied = worktree.gc_report(apply=True, repo=self.repo)
        self.assertEqual("host-archive-required", next(
            row["reason"] for row in applied["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_removed_and_recreated_resource_never_inherits_prior_ownership(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        git(self.repo, "worktree", "remove", str(target))
        git(self.repo, "branch", "-D", "task/managed-task")
        git(self.repo, "worktree", "add", "-b", "task/managed-task", str(target),
            "origin/main")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("ownership-identity-mismatch", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_backup_failure_preserves_branch_and_worktree(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        head = self.head("task/managed-task")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3], \
                patch.object(worktree, "_backup", side_effect=OSError("fixture backup failure")):
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("failed", next(
            row["status"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertEqual(head, self.head("task/managed-task"))
        self.assertTrue(target.is_dir())

    def test_changed_head_between_assessment_and_removal_is_preserved(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        real_rows = worktree.parse_worktrees(self.repo)
        raced_rows = [dict(row) for row in real_rows]
        for row in raced_rows:
            if Path(row["path"]) == target:
                row["head"] = "0" * 40
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3], \
                patch.object(worktree, "parse_worktrees", side_effect=[real_rows, raced_rows]):
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("changed-before-snapshot", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())
        self.assertIn("refs/heads/task/managed-task", self.branches())

    def test_preserve_branch_policy_blocks_completed_managed_worktree(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  preserve-branches: [task/managed-task]\n",
                           encoding="utf-8")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("locked-or-preserved", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_unknown_github_evidence_preserves_completed_managed_worktree(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)

        report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("github-evidence-unavailable", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_unknown_branch_rules_preserve_completed_managed_worktree(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        with patch.object(worktree.github, "github_evidence",
                          return_value={"default-branch": "main"}), \
                patch.object(worktree.github, "branch_rules", side_effect=ValueError("unknown")):
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("branch-rules-unknown", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_corrupted_registry_fails_closed_without_removing_worktree(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        registry_file = worktree.registry.registry_dir(self.repo) / "registry.json"
        registry_file.write_text('{"schema-version":999}', encoding="utf-8")
        invalid = registry_file.read_bytes()

        report = worktree.gc_report(apply=True, repo=self.repo)

        self.assert_report_schema(report)
        self.assertTrue(all(row["status"] == "preserved" and row["reason"] == "registry-unavailable"
                            for row in report["resources"]))
        self.assertEqual(invalid, registry_file.read_bytes())
        self.assertTrue(target.is_dir())
        self.assertIn("refs/heads/task/managed-task", self.branches())

    def test_remote_deletion_uses_sha_lease_and_retains_recovery_on_race(self) -> None:
        target = self.managed_worktree()
        publication = self.publish_managed_branch()
        self.assertEqual(self.head("task/managed-task"), publication["head-sha"])
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        head = self.head("task/managed-task")
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  remote-branches: true\n", encoding="utf-8")
        real_run = worktree.run
        pushed: list[list[str]] = []

        def fail_lease(command, *args, **kwargs):
            if "push" in command:
                pushed.append(command)
                raise subprocess.CalledProcessError(1, command, stderr="lease mismatch")
            return real_run(command, *args, **kwargs)

        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], \
                patch.object(worktree.github, "remote_head", return_value=head), \
                patch.object(worktree, "run", side_effect=fail_lease):
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual(1, len(pushed))
        self.assertIn(f"--force-with-lease=refs/heads/task/managed-task:{head}", pushed[0])
        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertEqual("failed", row["status"])
        self.assertTrue(Path(row["recovery"]).is_dir())
        self.assertTrue(report["cleanup-id"])

    def test_git_sha_lease_rejects_advanced_bare_remote_and_accepts_exact_head(self) -> None:
        branch = "task/lease"
        original = self.head()
        git(self.remote, "update-ref", f"refs/heads/{branch}", original)
        (self.repo / "advance.txt").write_text("new commit\n", encoding="utf-8")
        git(self.repo, "add", "advance.txt")
        git(self.repo, "commit", "-m", "advance remote")
        advanced = self.head()
        copy_missing_objects(self.sandbox / "git-data" / "objects", self.remote / "objects")
        git(self.remote, "update-ref", f"refs/heads/{branch}", advanced)

        stale = git(self.repo, "push", f"--force-with-lease=refs/heads/{branch}:{original}",
                    "origin", f":refs/heads/{branch}", check=False)
        if "NtCreateDirectoryObject" in stale.stderr:
            self.skipTest("Windows sandbox blocks Git's local transport helper")
        self.assertNotEqual(0, stale.returncode)
        self.assertEqual(advanced, git(self.remote, "rev-parse", f"refs/heads/{branch}").stdout.strip())

        current = git(self.repo, "push", f"--force-with-lease=refs/heads/{branch}:{advanced}",
                      "origin", f":refs/heads/{branch}", check=False)
        self.assertEqual(0, current.returncode, current.stderr)
        self.assertNotEqual(0, git(self.remote, "rev-parse", "--verify",
                                   f"refs/heads/{branch}", check=False).returncode)

    def test_git_expected_empty_lease_creates_once_without_adopting_existing_ref(self) -> None:
        branch = "task/create-only"
        git(self.repo, "branch", branch, "HEAD")
        ref = f"refs/heads/{branch}"
        command = ("push", "--porcelain", f"--force-with-lease={ref}:", "origin", f"{ref}:{ref}")
        created = git(self.repo, *command, check=False)
        if "NtCreateDirectoryObject" in created.stderr:
            self.skipTest("Windows sandbox blocks Git's local transport helper")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertTrue(worktree._confirmed_new_branch(created.stdout, ref), created.stdout)
        self.assertEqual(self.head(branch), self.bare_head(self.repo, branch))

        repeated = git(self.repo, *command, check=False)
        # Git may report an already equal ref as success despite the empty
        # lease. The porcelain status distinguishes creation from adoption.
        self.assertFalse(worktree._confirmed_new_branch(repeated.stdout, ref))
        self.assertEqual(self.head(branch), self.bare_head(self.repo, branch))

    def test_removed_managed_worktree_can_restore_and_path_conflict_fails_closed(self) -> None:
        target = self.managed_worktree()
        state = target / ".embraion" / "state" / "runs" / "run.json"
        state.parent.mkdir(parents=True)
        state.write_text('{"state":"completed"}\n', encoding="utf-8")
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        head = self.head("task/managed-task")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            removed = worktree.gc_report(apply=True, repo=self.repo)
        self.assert_report_schema(removed)

        self.assertEqual("removed", next(
            row["status"] for row in removed["resources"] if row["path"] == str(target)
        ))
        self.assertFalse(target.exists())
        self.assertNotIn("refs/heads/task/managed-task", self.branches())
        self.assertTrue(removed["cleanup-id"])

        repeated = worktree.gc_report(apply=True, repo=self.repo)
        self.assertFalse(any(row["status"] == "removed" for row in repeated["resources"]))
        self.assertFalse(target.exists())

        target.mkdir()
        marker = target / "someone-else.txt"
        marker.write_text("preserve", encoding="utf-8")
        conflict = worktree.restore_cleanup(removed["cleanup-id"], repo=self.repo)
        self.assertEqual("preserved", conflict["resources"][0]["status"])
        self.assertEqual("preserve", marker.read_text(encoding="utf-8"))
        marker.unlink()
        target.rmdir()

        restored = worktree.restore_cleanup(removed["cleanup-id"], repo=self.repo)
        self.assert_report_schema(restored)
        self.assertEqual("restored", restored["resources"][0]["status"])
        self.assertEqual(head, self.head("task/managed-task"))
        self.assertEqual('{"state":"completed"}\n', state.read_text(encoding="utf-8"))

    def test_matching_preexisting_remote_head_never_grants_remote_ownership(self) -> None:
        branch = "task/managed-task"
        head = self.head()
        git(self.remote, "update-ref", f"refs/heads/{branch}", head)

        def bare_head(_repo, name):
            result = git(self.remote, "rev-parse", "--verify", f"refs/heads/{name}", check=False)
            return result.stdout.strip() if result.returncode == 0 else None

        with patch.object(worktree.github, "remote_head", side_effect=bare_head):
            target = self.managed_worktree()
        data = worktree.registry.load_registry(self.repo)
        resource = next(iter(data["resources"].values()))
        self.assertFalse(resource["remote-owned"])
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  remote-branches: true\n", encoding="utf-8")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patch.object(
                worktree.github, "remote_head", side_effect=bare_head):
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("remote-ownership-unproven", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())
        self.assertEqual(head, bare_head(self.repo, branch))

    def test_user_published_remote_after_local_receipt_is_never_adopted(self) -> None:
        target = self.managed_worktree()
        branch = "task/managed-task"
        head = self.head(branch)
        copy_missing_objects(self.sandbox / "git-data" / "objects", self.remote / "objects")
        git(self.remote, "update-ref", f"refs/heads/{branch}", head, "0" * 40)

        with patch.object(worktree.github, "remote_head", side_effect=self.bare_head):
            with self.assertRaisesRegex(ValueError, "already exists"):
                worktree.publish_branch("managed-task", branch, repo=self.repo)

        data = worktree.registry.load_registry(self.repo)
        resource = next(iter(data["resources"].values()))
        self.assertFalse(resource["remote-owned"])
        self.assertNotIn("remote-publish", resource)
        # A legacy flag alone cannot upgrade the later user-created ref.
        resource["remote-owned"] = True
        worktree.registry.save_registry(self.repo, data)
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  remote-branches: true\n", encoding="utf-8")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], \
                patch.object(worktree.github, "remote_head", side_effect=self.bare_head):
            report = worktree.gc_report(apply=True, repo=self.repo)
        row = next(row for row in report["resources"] if row.get("path") == str(target))
        self.assertEqual("remote-ownership-unproven", row["reason"])
        self.assertTrue(target.exists())
        self.assertIn(f"refs/heads/{branch}", self.branches())
        self.assertEqual(head, self.bare_head(self.repo, branch))

    def test_verified_publish_creates_receipt_and_remote_candidate(self) -> None:
        target = self.managed_worktree()
        publication = self.publish_managed_branch()
        branch = "task/managed-task"
        self.assertEqual("expected-empty-lease", publication["method"])
        data = worktree.registry.load_registry(self.repo)
        resource = next(iter(data["resources"].values()))
        self.assertTrue(resource["remote-owned"])
        self.assertEqual(publication, resource["remote-publish"])
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  remote-branches: true\n", encoding="utf-8")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], \
                patch.object(worktree.github, "remote_head", side_effect=self.bare_head):
            report = worktree.gc_report(repo=self.repo)
        self.assert_report_schema(report)
        row = next(row for row in report["resources"] if row.get("path") == str(target))
        self.assertEqual("candidate", row["status"])
        self.assertEqual(self.head(branch), row["remote-head"])

    def test_publish_create_race_never_records_or_adopts_remote(self) -> None:
        target = self.managed_worktree()
        branch = "task/managed-task"
        head = self.head(branch)
        real_run = worktree.run

        def concurrent_create(command, *args, **kwargs):
            if "push" in command:
                copy_missing_objects(self.sandbox / "git-data" / "objects", self.remote / "objects")
                git(self.remote, "update-ref", f"refs/heads/{branch}", head, "0" * 40)
                return real_run(command, *args, **kwargs)
            return real_run(command, *args, **kwargs)

        with patch.object(worktree.github, "remote_head", side_effect=self.bare_head), \
                patch.object(worktree, "run", side_effect=concurrent_create):
            with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                worktree.publish_branch("managed-task", branch, repo=self.repo)
        data = worktree.registry.load_registry(self.repo)
        resource = next(iter(data["resources"].values()))
        self.assertFalse(resource["remote-owned"])
        self.assertNotIn("remote-publish", resource)
        with patch.object(worktree.github, "remote_head", side_effect=self.bare_head):
            with self.assertRaisesRegex(ValueError, "already exists"):
                worktree.publish_branch("managed-task", branch, repo=self.repo)
        self.assertTrue(target.exists())
        self.assertEqual(head, self.bare_head(self.repo, branch))

    def test_publish_requires_porcelain_new_branch_not_up_to_date(self) -> None:
        ref = "refs/heads/task/same-sha"
        head = self.head()
        self.assertFalse(worktree._confirmed_new_branch(
            f"=\t{head}:{ref}\t[up to date]\n", ref))
        self.assertFalse(worktree._confirmed_new_branch("", ref))
        self.assertTrue(worktree._confirmed_new_branch(
            f"*\t{head}:{ref}\t[new branch]\n", ref))

    def test_pushurl_mismatch_refuses_publication_without_touching_either_remote(self) -> None:
        self.managed_worktree()
        other = self.sandbox / "other.git"
        subprocess.run(["git", "init", "--bare", str(other)], check=True, capture_output=True)
        git(self.repo, "config", "remote.origin.pushurl", str(other))
        branch = "task/managed-task"

        with self.assertRaisesRegex(ValueError, "fetch/push endpoints"):
            worktree.publish_branch("managed-task", branch, repo=self.repo)

        self.assertIsNone(self.bare_head(self.repo, branch))
        self.assertNotEqual(0, git(other, "rev-parse", "--verify", f"refs/heads/{branch}",
                                   check=False).returncode)
        resource = next(iter(worktree.registry.load_registry(self.repo)["resources"].values()))
        self.assertFalse(resource["remote-owned"])
        self.assertNotIn("remote-publish", resource)

    def test_url_rewrite_chain_refuses_publication_before_any_remote_push(self) -> None:
        redirected = self.sandbox / "redirected.git"
        chained = self.sandbox / "chained.git"
        for bare in (redirected, chained):
            subprocess.run(["git", "init", "--bare", str(bare)], check=True,
                           capture_output=True)
        copy_missing_objects(self.sandbox / "git-data" / "objects", redirected / "objects")
        git(redirected, "update-ref", "refs/heads/main", self.head())
        git(self.repo, "config", "--add", f"url.{redirected}.insteadOf", str(self.remote))
        git(self.repo, "config", "--add", f"url.{chained}.pushInsteadOf", str(redirected))
        with patch.object(worktree.github, "remote_head", return_value=None):
            self.managed_worktree()
        with self.assertRaisesRegex(ValueError, "URL rewrite"):
            worktree.publish_branch("managed-task", "task/managed-task", repo=self.repo)
        for bare in (self.remote, redirected, chained):
            self.assertNotEqual(0, git(bare, "rev-parse", "--verify",
                                       "refs/heads/task/managed-task", check=False).returncode)

    def test_origin_change_preserves_registered_worktree(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        git(self.repo, "remote", "set-url", "origin", str(self.sandbox / "different-origin.git"))
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertEqual("origin-identity-mismatch", next(
            row["reason"] for row in report["resources"] if row["path"] == str(target)
        ))
        self.assertTrue(target.is_dir())

    def test_state_content_change_during_backup_blocks_removal(self) -> None:
        target = self.managed_worktree()
        state = target / ".embraion" / "state" / "runs" / "run.json"
        state.parent.mkdir(parents=True)
        state.write_text('{"state":"completed","revision":1}\n', encoding="utf-8")
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        real_backup = worktree._backup

        def change_after_backup(*args):
            backup = real_backup(*args)
            state.write_text('{"state":"completed","revision":2}\n', encoding="utf-8")
            return backup

        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3], \
                patch.object(worktree, "_backup", side_effect=change_after_backup):
            report = worktree.gc_report(apply=True, repo=self.repo)

        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertEqual("failed", row["status"])
        self.assertTrue(target.is_dir())
        self.assertIn("refs/heads/task/managed-task", self.branches())

    def test_task_reactivation_after_worktree_removal_retains_branch(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        real_run = worktree.run

        def reactivate_after_remove(command, *args, **kwargs):
            result = real_run(command, *args, **kwargs)
            if "worktree" in command and "remove" in command:
                data = worktree.registry.load_registry(self.repo)
                data["tasks"]["managed-task"]["state"] = "active"
                worktree.registry.save_registry(self.repo, data)
            return result

        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3], \
                patch.object(worktree, "run", side_effect=reactivate_after_remove):
            report = worktree.gc_report(apply=True, repo=self.repo)

        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertEqual("failed", row["status"])
        self.assertFalse(target.exists())
        self.assertIn("refs/heads/task/managed-task", self.branches())
        self.assertTrue(Path(row["recovery"]).is_dir())

    def provider_change_after_local_delete(self, change: str) -> None:
        branch = "task/managed-task"
        target = self.managed_worktree()
        self.publish_managed_branch()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        head = self.head(branch)
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  remote-branches: true\n", encoding="utf-8")
        phase = {"local-deleted": False}
        pushes: list[list[str]] = []
        real_run = worktree.run

        def observe_local_delete(command, *args, **kwargs):
            if "push" in command:
                pushes.append(command)
                raise subprocess.CalledProcessError(1, command, stderr="unexpected push")
            result = real_run(command, *args, **kwargs)
            if ("update-ref" in command and "-d" in command
                    and f"refs/heads/{branch}" in command):
                phase["local-deleted"] = True
            return result

        def branch_rules(_evidence, _branch):
            return phase["local-deleted"] and change == "protected"

        def pr_proof(_repo, _branch, _head, _base, _evidence):
            if phase["local-deleted"] and change == "open-pr":
                return False, "open-pr"
            return True, "merged-pr"

        with patch.object(worktree.github, "github_evidence",
                          return_value={"default-branch": "main"}), \
                patch.object(worktree.github, "branch_rules", side_effect=branch_rules), \
                patch.object(worktree.github, "integration_proof", side_effect=pr_proof), \
                patch.object(worktree.github, "remote_head", return_value=head), \
                patch.object(worktree, "run", side_effect=observe_local_delete):
            report = worktree.gc_report(apply=True, repo=self.repo)

        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertTrue(phase["local-deleted"])
        self.assertEqual([], pushes)
        self.assertEqual("failed", row["status"])
        self.assertNotIn(f"refs/heads/{branch}", self.branches())
        self.assertEqual(head, git(self.remote, "rev-parse", f"refs/heads/{branch}").stdout.strip())
        self.assertTrue(Path(row["recovery"]).is_dir())

    def test_new_protection_after_local_delete_blocks_remote_delete(self) -> None:
        self.provider_change_after_local_delete("protected")

    def test_open_pr_after_local_delete_blocks_remote_delete(self) -> None:
        self.provider_change_after_local_delete("open-pr")

    def test_disabled_local_deletion_retains_registered_branch_after_checkout_removal(self) -> None:
        target = self.managed_worktree()
        worktree.update_task_state("managed-task", "completed", repo=self.repo)
        project = self.repo / ".embraion" / "project.yaml"
        project.parent.mkdir()
        project.write_text("housekeeping:\n  local-branches: false\n", encoding="utf-8")
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)

        self.assertFalse(target.exists())
        self.assertIn("refs/heads/task/managed-task", self.branches())
        resource = next(iter(worktree.registry.load_registry(self.repo)["resources"].values()))
        self.assertEqual("branch", resource["kind"])
        self.assertIsNone(resource["path"])
        self.assertEqual("removed", next(
            row["status"] for row in report["resources"] if row["path"] == str(target)
        ))

    def test_embraion_branch_only_removal_and_restore(self) -> None:
        branch = "task/managed-branch"
        worktree.create_branch(branch, task_id="branch-task", host="codex", repo=self.repo)
        worktree.update_task_state("branch-task", "completed", repo=self.repo)
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(apply=True, repo=self.repo)

        row = next(row for row in report["resources"] if row["branch"] == branch)
        self.assertEqual("removed", row["status"])
        self.assertNotIn(f"refs/heads/{branch}", self.branches())
        restored = worktree.restore_cleanup(report["cleanup-id"], repo=self.repo)
        self.assertEqual("restored", restored["resources"][0]["status"])
        self.assertIn(f"refs/heads/{branch}", self.branches())

    def test_reused_registered_branch_links_new_active_task_after_checkout_is_released(self) -> None:
        branch = "task/branch-reuse"
        worktree.create_branch(branch, task_id="original", host="codex", repo=self.repo)
        worktree.update_task_state("original", "completed", repo=self.repo)
        git(self.repo, "switch", branch)
        worktree.update_task_state("new-task", "active", repo=self.repo)
        git(self.repo, "switch", "main")
        resource = next(iter(worktree.registry.load_registry(self.repo)["resources"].values()))
        self.assertEqual(["original", "new-task"], resource["task-ids"])
        patches = self.github_evidence()
        with patches[0], patches[1], patches[2], patches[3]:
            report = worktree.gc_report(repo=self.repo)
        row = next(row for row in report["resources"] if row.get("branch") == branch)
        self.assertEqual("preserved", row["status"])
        self.assertEqual("task-not-completed", row["reason"])
        self.assertIn(f"refs/heads/{branch}", self.branches())

    def test_embraion_detached_removal_and_restore(self) -> None:
        target = self.sandbox / "managed-detached"
        worktree.create_detached_worktree(target, task_id="detached-task", host="codex", repo=self.repo)
        worktree.update_task_state("detached-task", "completed", repo=self.repo)
        report = worktree.gc_report(apply=True, repo=self.repo)

        row = next(row for row in report["resources"] if row["path"] == str(target))
        self.assertEqual("removed", row["status"])
        self.assertFalse(target.exists())
        restored = worktree.restore_cleanup(report["cleanup-id"], repo=self.repo)
        self.assertEqual("restored", restored["resources"][0]["status"])
        self.assertTrue(target.is_dir())
        self.assertEqual(self.head(), git(target, "rev-parse", "HEAD").stdout.strip())


class GitHubProofTests(TemporaryGitRepository):
    def evidence(self, branch: str, head: str, merge_sha: str) -> dict[str, object]:
        return {
            "name": "owner/project",
            "default-branch": "main",
            "pulls": [{
                "state": "closed", "merged_at": "2026-10-03T00:00:00Z",
                "merge_commit_sha": merge_sha,
                "head": {"ref": branch, "sha": head,
                         "repo": {"full_name": "owner/project"}},
                "base": {"ref": "main", "repo": {"full_name": "owner/project"}},
            }],
        }

    def test_exact_head_merged_pr_and_squash_commit_on_base_are_accepted(self) -> None:
        branch = "task/squash"
        target = self.sandbox / "squash"
        git(self.repo, "worktree", "add", "-b", branch, str(target), "origin/main")
        (target / "change.txt").write_text("same content\n", encoding="utf-8")
        git(target, "add", "change.txt")
        git(target, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-m", "task change")
        branch_head = git(target, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "change.txt").write_text("same content\n", encoding="utf-8")
        git(self.repo, "add", "change.txt")
        git(self.repo, "commit", "-m", "squash task")
        merge_sha = self.head()
        git(self.repo, "update-ref", "refs/remotes/origin/main", merge_sha)
        self.assertNotEqual(branch_head, merge_sha)

        proved, reason = worktree_github.integration_proof(
            self.repo, branch, branch_head, "origin/main",
            self.evidence(branch, branch_head, merge_sha),
        )
        self.assertTrue(proved, reason)

    def test_pr_source_base_open_dependents_and_branch_reuse_fail_closed(self) -> None:
        branch = "task/proof"
        head = self.head()
        valid = self.evidence(branch, head, head)
        self.assertEqual((True, "merged-pr-ancestry"), worktree_github.integration_proof(
            self.repo, branch, head, "origin/main", valid
        ))

        wrong_source = self.evidence(branch, head, head)
        wrong_source["pulls"][0]["head"]["repo"]["full_name"] = "other/fork"
        wrong_base = self.evidence(branch, head, head)
        wrong_base["pulls"][0]["base"]["ref"] = "other"
        reused = self.evidence(branch, "0" * 40, head)
        open_dependent = self.evidence(branch, head, head)
        open_dependent["pulls"].append({
            "state": "open", "base": {"ref": branch}, "head": {"ref": "task/dependent"}
        })
        duplicate = self.evidence(branch, head, head)
        duplicate["pulls"].append(dict(duplicate["pulls"][0]))
        unknown_state = self.evidence(branch, head, head)
        unknown_state["pulls"][0]["state"] = None
        closed_reuse = self.evidence(branch, head, head)
        closed_reuse["pulls"].append(closed_reuse["pulls"][0] | {"merged_at": None})

        for name, evidence in (
            ("wrong-source", wrong_source), ("wrong-base", wrong_base),
            ("reused", reused), ("open-dependent", open_dependent),
            ("duplicate", duplicate), ("unknown-state", unknown_state),
            ("closed-name-reuse", closed_reuse),
        ):
            with self.subTest(name=name):
                proved, _ = worktree_github.integration_proof(
                    self.repo, branch, head, "origin/main", evidence
                )
                self.assertFalse(proved)


if __name__ == "__main__":
    unittest.main()
