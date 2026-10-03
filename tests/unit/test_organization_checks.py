from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from embraion.organization import check_organization


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class OrganizationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")

    def write(self, path: str, value: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding="utf-8")

    def config(self, value: dict) -> None:
        self.write(".embraion/organization.yaml", yaml.safe_dump(value))

    def commit(self) -> str:
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "fixture")
        return git(self.root, "rev-parse", "HEAD")

    def codes(self, result: dict) -> set[str]:
        return {finding["code"] for finding in result["findings"]}

    def test_namespace_strings_comments_exceptions_and_missing(self) -> None:
        self.config({"namespaces": {"rules": [{"path": "Assets/Code", "namespace": "Demo.Runtime",
                     "require_declaration": True, "exceptions": [{"path": "Assets/Code/Legacy", "namespace": "Legacy"},
                     {"path": "Assets/Code/Global", "allow_missing": True}]}]}})
        self.write("Assets/Code/Good.cs", '// namespace Wrong;\nclass X { string s = "namespace Wrong;"; }\nnamespace Demo.Runtime.Tools;')
        self.write("Assets/Code/Legacy/Old.cs", "namespace Legacy.Tools { }")
        self.write("Assets/Code/Global/Global.cs", "class Global { }")
        self.write("Assets/Code/Nested.cs", 'namespace Demo { namespace Runtime { class X { string text = """namespace Wrong;"""; } } }')
        self.write("Assets/Code/Missing.cs", "class Missing { }")
        self.write("Assets/Code/Bad.cs", "namespace Wrong;")
        result = check_organization(self.root)
        self.assertEqual({"namespace_missing", "namespace_mismatch"}, self.codes(result))
        self.assertFalse(result["passed"])

    def test_assembly_guid_resolution_boundaries_cycles_and_duplicates(self) -> None:
        self.config({"assemblies": {"roots": ["Assets"], "path_rules": [
            {"path": "Assets/Runtime", "layer": "Runtime"},
            {"path": "Assets/Editor", "layer": "Editor"},
            {"path": "Assets/Tests", "layer": "Tests"}]},
            "unity_meta": {"roots": ["Assets"], "require_for_extensions": [".asmdef"]}})
        a = "a" * 32
        b = "b" * 32
        self.write("Assets/Runtime/R.asmdef", json.dumps({"name": "R", "references": ["GUID:" + b]}))
        self.write("Assets/Runtime/R.asmdef.meta", "guid: " + a + "\n")
        self.write("Assets/Editor/E.asmdef", json.dumps({"name": "E", "references": ["R"], "includePlatforms": ["Editor"]}))
        self.write("Assets/Editor/E.asmdef.meta", "guid: " + b + "\n")
        self.write("Assets/Tests/T.asmdef", json.dumps({"name": "R", "references": []}))
        self.write("Assets/Tests/T.asmdef.meta", "guid: " + a + "\n")
        result = check_organization(self.root)
        self.assertTrue({"assembly_boundary", "assembly_cycle", "assembly_duplicate", "guid_duplicate"} <= self.codes(result))

    def test_editor_assembly_platform_is_bounded(self) -> None:
        self.config({"assemblies": {"roots": ["Assets"], "path_rules": [
            {"path": "Assets/Editor", "layer": "Editor"}]}})
        self.write("Assets/Editor/E.asmdef", json.dumps({"name": "E", "references": []}))
        self.assertIn("assembly_platform", self.codes(check_organization(self.root)))
        self.write("Assets/Editor/E.asmdef", json.dumps({"name": "E", "references": [], "includePlatforms": ["Editor"]}))
        self.assertNotIn("assembly_platform", self.codes(check_organization(self.root)))

    def test_incremental_baseline_worktree_and_missing_ref(self) -> None:
        self.config({"namespaces": {"rules": [{"path": "Assets", "namespace": "Demo"}]}})
        self.write("Assets/Old.cs", "namespace Wrong;")
        base = self.commit()
        self.write("Assets/Old.cs", "namespace Wrong; // touched")
        head = self.commit()
        result = check_organization(self.root, base_ref=base, head_ref=head)
        self.assertTrue(result["passed"])
        self.assertEqual(1, result["counts"]["preexisting"])
        self.write("Assets/New.cs", "namespace Wrong;")
        self.assertTrue(check_organization(self.root, base_ref=base, head_ref=head)["passed"])
        result = check_organization(self.root, base_ref=base, head_ref=head, include_worktree=True)
        self.assertFalse(result["passed"])
        self.assertEqual({"new": 1, "preexisting": 1}, result["counts"])
        self.assertEqual(base, result["base_commit"])
        with self.assertRaisesRegex(RuntimeError, "Git operation failed"):
            check_organization(self.root, base_ref="missing-branch")

    def test_move_compares_original_meta_guid(self) -> None:
        self.config({"unity_meta": {"roots": ["Assets"], "require_for_extensions": [".cs"]}})
        self.write("Assets/Old.cs", "class A {}")
        self.write("Assets/Old.cs.meta", "guid: " + "a" * 32)
        base = self.commit()
        git(self.root, "mv", "Assets/Old.cs", "Assets/New.cs")
        git(self.root, "mv", "Assets/Old.cs.meta", "Assets/New.cs.meta")
        self.assertTrue(check_organization(self.root, base_ref=base, include_worktree=True)["passed"])
        self.write("Assets/New.cs.meta", "guid: " + "b" * 32)
        result = check_organization(self.root, base_ref=base, include_worktree=True)
        self.assertIn("move_guid_changed", self.codes(result))

    def test_in_place_meta_identity_change(self) -> None:
        self.config({"unity_meta": {"roots": ["Assets"], "require_for_extensions": [".cs"]}})
        self.write("Assets/Thing.cs", "class Thing {}")
        self.write("Assets/Thing.cs.meta", "guid: " + "a" * 32)
        base = self.commit()
        self.write("Assets/Thing.cs.meta", "guid: " + "b" * 32)
        self.assertIn("guid_changed", self.codes(check_organization(self.root, base_ref=base, include_worktree=True)))

    def test_paths_symlink_and_lfs(self) -> None:
        self.config({"namespaces": {"rules": [{"path": "Assets", "namespace": "Demo"}]}})
        self.write("Assets/Pointer.cs", "version https://git-lfs.github.com/spec/v1\noid sha256:123\n")
        self.assertIn("lfs_pointer", self.codes(check_organization(self.root)))
        with self.assertRaisesRegex(RuntimeError, "Invalid"):
            self.config({"namespaces": {"rules": [{"path": "../outside", "namespace": "Demo"}]}})
            check_organization(self.root)
        self.config({"namespaces": {"rules": [{"path": "Assets", "namespace": "Demo"}]}})
        outside = self.root.parent / "external-organization-fixture.cs"
        try:
            (self.root / "Assets/Linked.cs").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertIn("unsafe_path", self.codes(check_organization(self.root)))

    def test_optional_config_does_not_hide_unavailable_required_base(self) -> None:
        self.assertEqual("skipped", check_organization(self.root)["status"])
        with self.assertRaisesRegex(RuntimeError, "Git operation failed"):
            check_organization(self.root, base_ref="missing-branch")


if __name__ == "__main__":
    unittest.main()
