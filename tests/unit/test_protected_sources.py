from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.common import read_yaml, write_yaml
from embraion.enforcement import check_enforcement, install_enforcement_surface
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

    def commit(self, project: Path, message: str) -> str:
        self.git(project, "add", "-A")
        self.git(project, "commit", "-q", "-m", message)
        return self.git(project, "rev-parse", "HEAD")

    def make_repo(self, protected: list[str] | None = None) -> tuple[Path, str]:
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
        self.set_policy(project, protected if protected is not None else ["vendor/lib/**"])
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
        project, base = self.make_repo()
        self.enable_validation(project)
        self.set_policy(project, [], mode=None)
        self.commit(project, "drop protection and the option")
        off = check_enforcement(base_ref=base, project=project)
        self.assertEqual("passed", self.protected_check(off)["status"])
        pinned = check_enforcement(base_ref=base, project=project, protected_sources="base-tree")
        self.assertEqual("failed", self.protected_check(pinned)["status"])

    def test_unknown_mode_is_rejected(self) -> None:
        project, base = self.make_repo()
        with self.assertRaisesRegex(RuntimeError, "Unknown protected-sources mode"):
            check_enforcement(base_ref=base, project=project, protected_sources="loose")

    def test_policy_schema_rejects_an_unknown_value(self) -> None:
        project, _ = self.make_repo()
        self.set_policy(project, ["vendor/lib/**"], mode="loose")
        with self.assertRaisesRegex(RuntimeError, "Invalid .embraion/policy.yaml"):
            read_policy_config(project)

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


if __name__ == "__main__":
    unittest.main()
