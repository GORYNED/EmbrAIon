from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from embraion.cli import main
from embraion.common import read_yaml, write_yaml
from embraion.enforcement import (
    GITHUB_ACTIONS_PATH,
    _github_actions_content,
    check_enforcement,
    install_enforcement_surface,
)
from embraion.policy import read_policy_config
from embraion.project import init_project
from embraion.protected_sources import check_base_tree


class ProtectedSourcesTestCase(unittest.TestCase):
    """Builds a base commit with a protected directory, then a work branch from it."""

    def git(self, project: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(project), *args], text=True, capture_output=True, check=True
        )
        return result.stdout.strip()

    def write(self, project: Path, relative: str, text: str) -> None:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def set_policy(self, project: Path, protected: list[str], mode: str | None = "base-tree") -> None:
        path = project / ".embraion" / "policy.yaml"
        policy = read_yaml(path)
        policy["sources"]["protected"] = protected
        policy["enforcement"] = {
            "enabled": True,
            "validation-profile": "affected",
            "require-review": False,
        }
        if mode is not None:
            policy["enforcement"]["protected-sources"] = mode
        write_yaml(path, policy)

    def move(self, project: Path, source: str, target: str) -> None:
        (project / target).parent.mkdir(parents=True, exist_ok=True)
        self.git(project, "mv", source, target)

    def commit(self, project: Path, message: str) -> str:
        self.git(project, "add", "-A")
        self.git(project, "commit", "-q", "-m", message)
        return self.git(project, "rev-parse", "HEAD")

    def make_repo(
        self, protected: list[str] | None = None, mode: str | None = "base-tree"
    ) -> tuple[Path, str]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        init_project(project, name="Consumer")
        self.git(project, "init", "-q", "-b", "main")
        self.git(project, "config", "user.email", "test@example.invalid")
        self.git(project, "config", "user.name", "EmbrAIon Test")
        self.write(project, "src/app.py", "print('ok')\n")
        self.write(project, "vendor/lib/a.txt", "alpha\n")
        self.write(project, "vendor/lib/sub/b.txt", "beta\n")
        self.set_policy(
            project, protected if protected is not None else ["vendor/lib/**"], mode=mode
        )
        base = self.commit(project, "base")
        self.git(project, "checkout", "-q", "-b", "work")
        return project, base

    def head_list(self, project: Path) -> list[str]:
        return list(read_policy_config(project)["sources"]["protected"])

    def run_guard(self, project: Path, base: str) -> dict:
        return check_base_tree(project, base, self.head_list(project))


class PolicyAtBaseTests(ProtectedSourcesTestCase):
    def test_unchanged_policy_and_content_pass(self) -> None:
        project, base = self.make_repo()
        self.write(project, "src/app.py", "print('changed')\n")
        self.commit(project, "touch unprotected file")
        result = self.run_guard(project, base)
        self.assertEqual("passed", result["status"], result["findings"])
        self.assertEqual(base, result["merge-base"])
        self.assertEqual("base-tree", result["mode"])

    def test_removed_base_entry_is_a_finding_naming_it(self) -> None:
        project, base = self.make_repo()
        self.set_policy(project, [])
        self.commit(project, "drop protection")
        result = self.run_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("'vendor/lib/**'" in item for item in result["findings"]))

    def test_narrowed_base_entry_is_a_finding_naming_it(self) -> None:
        project, base = self.make_repo()
        self.set_policy(project, ["vendor/lib/sub/**"])
        self.commit(project, "narrow protection")
        result = self.run_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("'vendor/lib/**'" in item for item in result["findings"]))

    def test_widened_policy_passes(self) -> None:
        project, base = self.make_repo()
        self.set_policy(project, ["vendor/lib/**", "src/**"])
        self.commit(project, "add protection")
        result = self.run_guard(project, base)
        self.assertEqual("passed", result["status"], result["findings"])

    def test_policy_is_read_from_the_merge_base_not_the_head(self) -> None:
        # The head policy lists nothing, so a name-only check on the head list sees no protection.
        project, base = self.make_repo()
        self.set_policy(project, [])
        self.commit(project, "drop protection")
        self.assertEqual([], self.head_list(project))
        self.assertEqual("failed", self.run_guard(project, base)["status"])

    def test_policy_missing_at_base_fails_closed(self) -> None:
        project, _ = self.make_repo()
        self.git(project, "rm", "-q", ".embraion/policy.yaml")
        no_policy = self.commit(project, "no policy")
        self.git(project, "checkout", "-q", "HEAD~1", "--", ".embraion/policy.yaml")
        self.commit(project, "policy back")
        # The merge base of the base ref and HEAD is the commit without a policy.
        result = check_base_tree(project, no_policy, self.head_list(project))
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("unreadable" in item for item in result["findings"]))

    def test_unparsable_list_at_base_fails_closed(self) -> None:
        project, _ = self.make_repo()
        self.git(project, "checkout", "-q", "main")
        self.write(project, ".embraion/policy.yaml", "sources:\n  protected: vendor/lib/**\n")
        broken = self.commit(project, "scalar list")
        self.git(project, "checkout", "-q", "-b", "work2")
        result = check_base_tree(project, broken, ["vendor/lib/**"])
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("unparsable" in item for item in result["findings"]))

    def test_unknown_base_ref_fails_closed(self) -> None:
        project, _ = self.make_repo()
        result = check_base_tree(project, "no-such-ref", ["vendor/lib/**"])
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("no-such-ref" in item for item in result["findings"]))

    def test_no_merge_base_in_shallow_clone_fails_closed(self) -> None:
        origin, base = self.make_repo()
        self.write(origin, "src/app.py", "print('work')\n")
        self.commit(origin, "work commit")
        self.git(origin, "checkout", "-q", "main")
        self.write(origin, "src/other.py", "x = 1\n")
        self.commit(origin, "main moves on")
        self.git(origin, "checkout", "-q", "work")
        clone_dir = tempfile.TemporaryDirectory()
        self.addCleanup(clone_dir.cleanup)
        clone = Path(clone_dir.name) / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", "--branch", "work",
             origin.resolve().as_uri(), str(clone)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(clone), "fetch", "-q", "--depth", "1", "origin", "main"],
            check=True, capture_output=True,
        )
        result = check_base_tree(clone, "FETCH_HEAD", ["vendor/lib/**"])
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("shallow" in item for item in result["findings"]), result["findings"])


class ObjectIdentityTests(ProtectedSourcesTestCase):
    def assert_failed(self, result: dict, *paths: str) -> None:
        self.assertEqual("failed", result["status"], result)
        for path in paths:
            self.assertIn(path, result["changed-paths"])

    def test_modified_file_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.write(project, "vendor/lib/a.txt", "alpha!\n")
        self.commit(project, "edit")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_added_file_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.write(project, "vendor/lib/new.txt", "new\n")
        self.commit(project, "add")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/new.txt")

    def test_deleted_file_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.git(project, "rm", "-q", "vendor/lib/sub/b.txt")
        self.commit(project, "delete")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/sub/b.txt")

    def test_renamed_file_inside_the_directory_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib/a.txt", "vendor/lib/renamed.txt")
        self.commit(project, "rename inside")
        self.assert_failed(
            self.run_guard(project, base), "vendor/lib/a.txt", "vendor/lib/renamed.txt"
        )

    def test_mode_change_is_a_violation(self) -> None:
        project, base = self.make_repo()
        # The index stores the mode independently of the file system; do not re-add the file.
        self.git(project, "update-index", "--chmod=+x", "--", "vendor/lib/a.txt")
        self.git(project, "commit", "-q", "-m", "chmod")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_history_rewrite_with_identical_tree_is_not_a_change(self) -> None:
        project, base = self.make_repo()
        self.write(project, "vendor/lib/a.txt", "alpha!\n")
        self.commit(project, "edit")
        self.write(project, "vendor/lib/a.txt", "alpha\n")
        self.commit(project, "revert the edit")
        self.assertEqual("passed", self.run_guard(project, base)["status"])

    def test_uncommitted_change_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.write(project, "vendor/lib/a.txt", "dirty\n")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_directory_moved_intact_to_a_protected_location_is_allowed(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib", "third_party/lib")
        self.set_policy(project, ["third_party/lib/**"])
        self.commit(project, "relocate")
        result = self.run_guard(project, base)
        self.assertEqual("passed", result["status"], result["findings"])
        self.assertEqual([{"from": "vendor/lib", "to": "third_party/lib"}], result["relocated"])

    def test_directory_moved_intact_but_keeping_the_old_entry_is_allowed(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib", "third_party/lib")
        self.set_policy(project, ["vendor/lib/**", "third_party/lib/**"])
        self.commit(project, "relocate")
        self.assertEqual("passed", self.run_guard(project, base)["status"])

    def test_directory_moved_to_an_unprotected_location_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib", "elsewhere/lib")
        self.set_policy(project, ["vendor/lib/**"])
        self.commit(project, "relocate without protection")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_directory_moved_with_one_byte_changed_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib", "third_party/lib")
        self.write(project, "third_party/lib/a.txt", "alphA\n")
        self.set_policy(project, ["third_party/lib/**"])
        self.commit(project, "relocate and edit")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_directory_moved_in_part_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib/sub", "third_party/sub")
        self.set_policy(project, ["vendor/lib/**", "third_party/**"])
        self.commit(project, "partial move")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/sub/b.txt")

    def test_directory_moved_with_an_extra_file_is_a_violation(self) -> None:
        project, base = self.make_repo()
        self.move(project, "vendor/lib", "third_party/lib")
        self.write(project, "third_party/lib/extra.txt", "extra\n")
        self.set_policy(project, ["third_party/lib/**"])
        self.commit(project, "relocate and add")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_file_pattern_cannot_be_relocated(self) -> None:
        project, base = self.make_repo(["vendor/lib/a.txt"])
        self.move(project, "vendor/lib/a.txt", "vendor/lib/moved.txt")
        self.set_policy(project, ["vendor/lib/a.txt", "vendor/lib/moved.txt"])
        self.commit(project, "move a file")
        self.assert_failed(self.run_guard(project, base), "vendor/lib/a.txt")

    def test_name_check_alone_would_miss_a_covert_move(self) -> None:
        # Moving the directory and listing only the new path leaves nothing for the
        # name check to match in the head policy; the identity check still sees the change.
        project, base = self.make_repo()
        self.move(project, "vendor/lib", "third_party/lib")
        self.write(project, "third_party/lib/a.txt", "swapped\n")
        self.set_policy(project, ["unrelated/**"])
        self.commit(project, "covert move")
        result = self.run_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("vendor/lib/**" in item for item in result["findings"]))


class HardeningTests(ProtectedSourcesTestCase):
    def blob(self, project: Path, text: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(project), "hash-object", "-w", "--stdin"],
            input=text.encode("utf-8"), capture_output=True, check=True,
        )
        return result.stdout.decode().strip()

    def stage(self, project: Path, mode: str, oid: str, path: str) -> None:
        # Index-only entries work on every platform, whatever the file system allows.
        self.git(project, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}")

    def commit_index(self, project: Path, message: str) -> str:
        self.git(project, "commit", "-q", "-m", message)
        return self.git(project, "rev-parse", "HEAD")

    def run_index_guard(self, project: Path, base: str) -> dict:
        # Index-only entries have no file in the working tree, which would read as uncommitted.
        with patch("embraion.protected_sources._uncommitted_paths", return_value=[]):
            return self.run_guard(project, base)

    def test_duplicate_directory_at_the_merge_base_does_not_make_a_deletion_a_move(self) -> None:
        project, _ = self.make_repo()
        self.write(project, "copy/lib/a.txt", "alpha\n")
        self.write(project, "copy/lib/sub/b.txt", "beta\n")
        base = self.commit(project, "an identical copy already exists")
        self.git(project, "rm", "-rq", "vendor/lib")
        self.set_policy(project, ["vendor/lib/**", "copy/lib/**"])
        self.commit(project, "delete the original")
        result = self.run_guard(project, base)
        self.assertEqual("failed", result["status"], result)
        self.assertNotIn("relocated", result)

    def test_directory_that_stays_in_place_is_not_a_relocation(self) -> None:
        project, base = self.make_repo()
        self.write(project, "third_party/lib/a.txt", "alpha\n")
        self.write(project, "third_party/lib/sub/b.txt", "beta\n")
        self.set_policy(project, ["vendor/lib/**", "third_party/lib/**"])
        self.commit(project, "copy the directory")
        self.assertEqual("passed", self.run_guard(project, base)["status"])

    def test_overlapping_file_pattern_reports_a_moved_directory_as_changed(self) -> None:
        project, base = self.make_repo(["vendor/lib/**", "**/*.txt"])
        self.move(project, "vendor/lib", "third_party/lib")
        self.set_policy(project, ["third_party/lib/**", "**/*.txt"])
        self.commit(project, "relocate")
        result = self.run_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("'**/*.txt'" in item for item in result["findings"]))
        self.assertFalse(any("'vendor/lib/**'" in item for item in result["findings"]))

    def test_project_in_a_repository_subdirectory(self) -> None:
        # EmbrAIon resolves the project root to the Git top level, so the gate never starts
        # in a subdirectory; this pins the guard's own path handling when it is called from one.
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        project = root / "proj"
        project.mkdir()
        init_project(project, name="Consumer")
        self.git(root, "init", "-q", "-b", "main")
        self.git(root, "config", "user.email", "test@example.invalid")
        self.git(root, "config", "user.name", "EmbrAIon Test")
        self.write(project, "vendor/lib/a.txt", "alpha\n")
        self.write(root, "outside.txt", "outside\n")
        self.set_policy(project, ["vendor/lib/**"])
        self.git(root, "add", "-A")
        self.git(root, "commit", "-q", "-m", "base")
        base = self.git(root, "rev-parse", "HEAD")
        self.git(root, "checkout", "-q", "-b", "work")

        self.assertEqual("passed", check_base_tree(project, base, ["vendor/lib/**"])["status"])
        self.write(root, "outside.txt", "dirty\n")
        self.assertEqual("passed", check_base_tree(project, base, ["vendor/lib/**"])["status"])
        self.git(root, "checkout", "-q", "--", "outside.txt")

        self.git(project, "mv", "vendor/lib/a.txt", "vendor/lib/b.txt")
        self.git(root, "commit", "-q", "-m", "rename")
        result = check_base_tree(project, base, ["vendor/lib/**"])
        self.assertEqual("failed", result["status"])
        self.assertEqual(["vendor/lib/a.txt", "vendor/lib/b.txt"], result["changed-paths"])

        self.git(root, "reset", "-q", "--hard", base)
        (project / "third_party").mkdir()
        self.git(project, "mv", "vendor/lib", "third_party/lib")
        self.set_policy(project, ["third_party/lib/**"])
        self.git(root, "add", "-A")
        self.git(root, "commit", "-q", "-m", "relocate")
        result = check_base_tree(project, base, ["third_party/lib/**"])
        self.assertEqual("passed", result["status"], result["findings"])
        self.assertEqual([{"from": "vendor/lib", "to": "third_party/lib"}], result["relocated"])

    def test_symlink_and_gitlink_entries_are_compared_by_object_id(self) -> None:
        project, _ = self.make_repo()
        link = self.blob(project, "a.txt")
        self.stage(project, "120000", link, "vendor/lib/link")
        self.stage(project, "160000", self.git(project, "rev-parse", "HEAD"), "vendor/lib/module")
        base = self.commit_index(project, "add a symlink and a gitlink")
        self.assertEqual("passed", self.run_index_guard(project, base)["status"])

        self.stage(project, "120000", self.blob(project, "sub/b.txt"), "vendor/lib/link")
        self.commit_index(project, "retarget the symlink")
        result = self.run_index_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertEqual(["vendor/lib/link"], result["changed-paths"])

        self.git(project, "reset", "-q", "--hard", base)
        self.stage(project, "160000", "1" * 40, "vendor/lib/module")
        self.commit_index(project, "move the gitlink")
        result = self.run_index_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertEqual(["vendor/lib/module"], result["changed-paths"])

    def test_paths_with_spaces_quotes_and_non_ascii_characters(self) -> None:
        project, _ = self.make_repo()
        directory = "ven dor/ünï lib"
        name = f'{directory}/we ird "q" é.txt'
        self.set_policy(project, [f"{directory}/**"])
        self.git(project, "add", ".embraion/policy.yaml")
        self.stage(project, "100644", self.blob(project, "one\n"), name)
        base = self.commit_index(project, "add awkward names")
        self.assertEqual("passed", self.run_index_guard(project, base)["status"])

        self.stage(project, "100644", self.blob(project, "two\n"), name)
        self.commit_index(project, "modify")
        result = self.run_index_guard(project, base)
        self.assertEqual("failed", result["status"])
        self.assertEqual([name], result["changed-paths"])

        self.stage(project, "100644", self.blob(project, "one\n"), name)
        self.stage(project, "100644", self.blob(project, "new\n"), f"{directory}/näme with space.txt")
        self.commit_index(project, "restore and add")
        result = self.run_index_guard(project, base)
        self.assertEqual([f"{directory}/näme with space.txt"], result["changed-paths"])

    def test_criss_cross_merge_base_fails_closed(self) -> None:
        project, _ = self.make_repo()
        self.git(project, "checkout", "-q", "-b", "x", "main")
        self.write(project, "src/x.txt", "x\n")
        self.commit(project, "x1")
        self.git(project, "checkout", "-q", "-b", "y", "main")
        self.write(project, "src/y.txt", "y\n")
        self.commit(project, "y1")
        self.git(project, "checkout", "-q", "-b", "mx", "x")
        self.git(project, "merge", "-q", "--no-edit", "y")
        self.git(project, "checkout", "-q", "-b", "my", "y")
        self.git(project, "merge", "-q", "--no-edit", "x")
        self.assertEqual(2, len(self.git(project, "merge-base", "--all", "mx", "my").split()))
        result = self.run_guard(project, "mx")
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("criss-cross" in item for item in result["findings"]), result["findings"])

    def test_shallow_clone_fails_even_when_a_merge_base_is_found(self) -> None:
        origin, _ = self.make_repo()
        hashes = []
        for number in range(3):
            self.write(origin, f"src/w{number}.txt", f"{number}\n")
            hashes.append(self.commit(origin, f"work {number}"))
        clone_dir = tempfile.TemporaryDirectory()
        self.addCleanup(clone_dir.cleanup)
        clone = Path(clone_dir.name) / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "3", "--branch", "work",
             origin.resolve().as_uri(), str(clone)],
            check=True, capture_output=True,
        )
        # The middle commit is present and is not the shallow boundary.
        self.assertEqual(hashes[1], self.git(clone, "rev-parse", hashes[1]))
        self.assertEqual("true", self.git(clone, "rev-parse", "--is-shallow-repository"))
        result = check_base_tree(clone, hashes[1], ["vendor/lib/**"])
        self.assertEqual("failed", result["status"])
        self.assertTrue(any("shallow" in item for item in result["findings"]), result["findings"])


class EnforcementWiringTests(ProtectedSourcesTestCase):
    def enable_validation(self, project: Path) -> None:
        path = project / ".embraion" / "validation.yaml"
        validation = read_yaml(path)
        validation["profiles"]["affected"] = [f'"{sys.executable}" -c "print(1)"']
        write_yaml(path, validation)

    def protected_check(self, record: dict) -> dict:
        return next(item for item in record["checks"] if item["id"] == "protected-sources")

    def test_option_off_keeps_the_name_check_exactly(self) -> None:
        project, base = self.make_repo()
        self.set_policy(project, ["vendor/lib/**"], mode=None)
        self.enable_validation(project)
        self.commit(project, "policy without the option")
        base = self.git(project, "rev-parse", "HEAD")
        self.write(project, "src/app.py", "print('changed')\n")
        record = check_enforcement(base_ref=base, project=project)
        check = self.protected_check(record)
        self.assertEqual({"id", "status", "changed-paths"}, set(check))
        self.assertEqual("passed", check["status"])
        self.write(project, "vendor/lib/a.txt", "changed\n")
        record = check_enforcement(base_ref=base, project=project)
        check = self.protected_check(record)
        self.assertEqual("failed", check["status"])
        self.assertEqual(["vendor/lib/a.txt"], check["changed-paths"])

    def test_policy_option_enables_the_guard(self) -> None:
        project, base = self.make_repo()
        self.enable_validation(project)
        self.set_policy(project, [])
        self.commit(project, "drop protection and enable validation")
        record = check_enforcement(base_ref=base, project=project)
        check = self.protected_check(record)
        self.assertEqual("base-tree", check["mode"])
        self.assertEqual("failed", check["status"])
        self.assertFalse(record["passed"])

    def test_flag_overrides_a_policy_that_turned_the_guard_off(self) -> None:
        # The base policy does not pin the mode, so only the flag can turn the guard on.
        project, base = self.make_repo(mode=None)
        self.enable_validation(project)
        self.set_policy(project, [], mode=None)
        self.commit(project, "drop protection and the option")
        off = check_enforcement(base_ref=base, project=project)
        self.assertEqual("passed", self.protected_check(off)["status"])
        pinned = check_enforcement(base_ref=base, project=project, protected_sources="base-tree")
        self.assertEqual("failed", self.protected_check(pinned)["status"])

    def test_base_policy_pins_the_mode_when_the_head_turns_it_off(self) -> None:
        project, base = self.make_repo()
        self.enable_validation(project)
        self.set_policy(project, [], mode=None)
        self.commit(project, "drop protection and the option")
        record = check_enforcement(base_ref=base, project=project)
        check = self.protected_check(record)
        self.assertEqual("base-tree", check["mode"])
        self.assertEqual("merge-base-policy", check["mode-source"])
        self.assertEqual("failed", check["status"])
        self.assertFalse(record["passed"])

    def test_flag_still_wins_over_the_base_policy(self) -> None:
        project, base = self.make_repo()
        self.enable_validation(project)
        self.set_policy(project, [], mode=None)
        self.commit(project, "drop protection and the option")
        record = check_enforcement(base_ref=base, project=project, protected_sources="name")
        check = self.protected_check(record)
        self.assertEqual({"id", "status", "changed-paths"}, set(check))

    def test_unusable_base_policy_leaves_the_default_mode_alone(self) -> None:
        project, _ = self.make_repo(mode=None)
        self.enable_validation(project)
        self.git(project, "rm", "-q", ".embraion/policy.yaml")
        no_policy = self.commit(project, "no policy")
        self.git(project, "checkout", "-q", "HEAD~1", "--", ".embraion/policy.yaml")
        self.commit(project, "policy back")
        record = check_enforcement(base_ref=no_policy, project=project)
        self.assertEqual({"id", "status", "changed-paths"}, set(self.protected_check(record)))

    def test_unknown_mode_is_rejected(self) -> None:
        project, base = self.make_repo()
        with self.assertRaisesRegex(RuntimeError, "Unknown protected-sources mode"):
            check_enforcement(base_ref=base, project=project, protected_sources="loose")

    def test_policy_schema_rejects_an_unknown_value(self) -> None:
        project, _ = self.make_repo()
        self.set_policy(project, ["vendor/lib/**"], mode="loose")
        with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/policy.yaml"):
            read_policy_config(project)

    def run_cli(self, project: Path, *argv: str) -> tuple[int, str]:
        previous = Path.cwd()
        os.chdir(project)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            code = main(list(argv))
        return code, output.getvalue()

    def test_cli_flag_reports_findings_and_fails(self) -> None:
        project, base = self.make_repo()
        self.enable_validation(project)
        self.write(project, "vendor/lib/a.txt", "changed\n")
        self.commit(project, "edit protected file")
        code, text = self.run_cli(
            project, "enforcement", "check", "--base-ref", base, "--protected-sources", "base-tree"
        )
        self.assertEqual(1, code, text)
        self.assertIn("protected-sources: failed", text)
        self.assertIn("vendor/lib/a.txt", text)
        self.assertIn("differs from the merge base", text)

    def test_cli_passes_an_untouched_protected_tree(self) -> None:
        project, base = self.make_repo()
        self.enable_validation(project)
        self.write(project, "src/app.py", "print('changed')\n")
        self.commit(project, "edit unprotected file")
        code, text = self.run_cli(project, "enforcement", "check", "--base-ref", base)
        self.assertEqual(0, code, text)
        self.assertIn("protected-sources: passed", text)

    def test_status_shows_the_mode_only_when_it_is_set(self) -> None:
        project, _ = self.make_repo()
        _, text = self.run_cli(project, "enforcement", "status")
        self.assertIn("Protected sources: base-tree", text)
        self.set_policy(project, ["vendor/lib/**"], mode=None)
        _, text = self.run_cli(project, "enforcement", "status")
        self.assertNotIn("Protected sources", text)

    def test_install_keeps_the_configured_mode(self) -> None:
        project, _ = self.make_repo()
        self.set_policy(project, ["vendor/lib/**"])
        pin = project / ".embraion" / "project.yaml"
        self.assertTrue(pin.is_file())
        try:
            install_enforcement_surface(surface="github-actions", project=project)
        except RuntimeError as error:  # the temporary project may lack an exact framework pin
            self.skipTest(str(error))
        policy = read_yaml(project / ".embraion" / "policy.yaml")
        self.assertEqual("base-tree", policy["enforcement"]["protected-sources"])
        workflow = (project / GITHUB_ACTIONS_PATH).read_text(encoding="utf-8")
        self.assertIn("--protected-sources base-tree", workflow)

    def test_default_workflow_text_has_no_protected_sources_flag(self) -> None:
        content = _github_actions_content(action_version="1.2.3", require_review=False)
        self.assertNotIn("protected-sources", content)
        self.assertEqual(
            content,
            _github_actions_content(
                action_version="1.2.3", require_review=False, protected_sources="name"
            ),
        )


if __name__ == "__main__":
    unittest.main()
