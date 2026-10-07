from __future__ import annotations

import json
import subprocess
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_allowed_layer_edge_still_requires_platform_compatibility(self) -> None:
        config = {"assemblies": {"roots": ["Assets"], "path_rules": [
            {"path": "Assets/Runtime", "layer": "Runtime"},
            {"path": "Assets/Editor", "layer": "Editor"}],
            "allowed_edges": [{"from": "R", "to": "E"}]}}
        self.config(config)
        self.write("Assets/Runtime/R.asmdef", json.dumps({"name": "R", "references": ["E"]}))
        self.write("Assets/Editor/E.asmdef", json.dumps({"name": "E", "includePlatforms": ["Editor"]}))
        result = check_organization(self.root)
        self.assertEqual({"assembly_platform"}, self.codes(result))
        self.assertFalse(result["passed"])
        config["assemblies"]["enforce_platforms"] = False
        self.config(config)
        self.assertTrue(check_organization(self.root)["passed"])

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
        self.assertEqual({"lfs_pointer"}, self.codes(check_organization(self.root)))
        (self.root / "Assets/Pointer.cs").write_bytes(
            b"version https://git-lfs.github.com/spec/v1\r\n"
            b"oid sha256:123\r\nnamespace Wrong;\r\n"
        )
        self.assertEqual({"lfs_pointer"}, self.codes(check_organization(self.root)))
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

    def test_invalid_yaml_does_not_expose_values(self) -> None:
        canary = "fixture-credential-canary-7392"
        self.write(".embraion/organization.yaml", "namespaces: [\n  credential: " + canary + "\n")
        with self.assertRaisesRegex(RuntimeError, "Invalid organization configuration YAML") as caught:
            check_organization(self.root)
        self.assertNotIn(canary, "".join(traceback.format_exception(caught.exception)))

    def test_schema_error_reports_location_without_values(self) -> None:
        canary = "fixture-credential-canary-7392"
        self.config({"namespaces": {"rules": [{"path": "Assets", "namespace": canary}]}})
        with self.assertRaisesRegex(RuntimeError, "at namespaces.rules.0.namespace") as caught:
            check_organization(self.root)
        self.assertNotIn(canary, "".join(traceback.format_exception(caught.exception)))

    def test_symlinked_configuration_parent_is_rejected(self) -> None:
        self.write("settings/organization.yaml", "namespaces:\n  rules: []\n")
        try:
            (self.root / ".embraion").symlink_to(self.root / "settings", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            check_organization(self.root)

    def test_symlinked_source_directory_fails_worktree_and_git_scans(self) -> None:
        self.config({"exclude": ["Assets/Vendor/**"], "namespaces": {"rules": [
            {"path": "Assets/Code", "namespace": "Demo", "require_declaration": True}]}})
        self.write("Assets/Code/Good.cs", "namespace Demo;")
        base = self.commit()
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        external = Path(outside.name)
        (external / "Bad.cs").write_text("namespace Wrong;", encoding="utf-8")
        (self.root / "Assets/Code/Good.cs").unlink()
        (self.root / "Assets/Code").rmdir()
        try:
            (self.root / "Assets/Code").symlink_to(external, target_is_directory=True)
            (self.root / "Assets/Vendor").symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        current = check_organization(self.root, base_ref=base, include_worktree=True)
        self.assertFalse(current["passed"])
        self.assertEqual(["Assets/Code"], [finding["path"] for finding in current["findings"]])
        head = self.commit()
        committed = check_organization(self.root, base_ref=base, head_ref=head)
        self.assertFalse(committed["passed"])
        self.assertEqual(["Assets/Code"], [finding["path"] for finding in committed["findings"]])

    def test_symlinked_ancestor_of_source_scope_fails(self) -> None:
        self.config({"namespaces": {"rules": [
            {"path": "Assets/Code", "namespace": "Demo", "require_declaration": True}]}})
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        external = Path(outside.name)
        try:
            (self.root / "Assets").symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        result = check_organization(self.root)
        self.assertEqual(["Assets"], [finding["path"] for finding in result["findings"]])
        self.assertFalse(result["passed"])

    def test_configured_nested_temp_directory_is_scanned(self) -> None:
        self.config({"namespaces": {"rules": [
            {"path": "Assets/Project/Temp", "namespace": "Demo", "require_declaration": True}]}})
        self.write("Assets/Project/Temp/Bad.cs", "namespace Wrong;")
        result = check_organization(self.root)
        self.assertEqual(["Assets/Project/Temp/Bad.cs"], [finding["path"] for finding in result["findings"]])
        self.assertFalse(result["passed"])

    def test_clean_checkout_and_filled_tree_count_only_declared_unignored_sources(self) -> None:
        self.config({"namespaces": {"rules": [{"path": "Assets/Project", "namespace": "Demo"}]}})
        self.write(".gitignore", "Builds/Validation/\nLibrary/\n")
        self.write("Assets/Project/Good.cs", "namespace Demo;")
        self.write("Assets/Other/Wrong.cs", "namespace Wrong;")
        base = self.commit()
        with patch("embraion.organization.MAX_FILES", 1):
            clean = check_organization(self.root, base_ref=base, head_ref=base)
            self.assertTrue(clean["passed"])
            self.assertTrue(check_organization(self.root)["passed"])
            for index in range(4):
                self.write(f"Builds/Validation/result-{index}.cs", "namespace Wrong;")
                self.write(f"Library/cache-{index}.cs", "namespace Wrong;")
                self.write(f"Assets/Other/extra-{index}.cs", "namespace Wrong;")
            self.assertTrue(check_organization(self.root)["passed"])
            self.write("Assets/Project/Bad.cs", "namespace Wrong;")
            with self.assertRaisesRegex(RuntimeError, "exceeds 1 files"):
                check_organization(self.root)

    def test_non_git_scopes_inside_conventional_cache_names_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".embraion").mkdir()
            (root / ".embraion/organization.yaml").write_text(yaml.safe_dump({
                "namespaces": {"rules": [{"path": "Assets/Temp", "namespace": "Demo"}]}
            }), encoding="utf-8")
            (root / "Assets/Temp").mkdir(parents=True)
            (root / "Assets/Temp/Bad.cs").write_text("namespace Wrong;", encoding="utf-8")
            (root / "Library").mkdir()
            (root / "Library/Cache.cs").write_text("namespace Wrong;", encoding="utf-8")
            with patch("embraion.organization.MAX_FILES", 1):
                result = check_organization(root)
            self.assertEqual(["Assets/Temp/Bad.cs"], [item["path"] for item in result["findings"]])

    def test_filenames_follow_style_with_canonical_host_and_configured_exemptions(self) -> None:
        self.config({"filenames": {"roots": ["docs", "tools", ".github", ".claude"],
                                   "extensions": [".md", ".py", ".yml"], "allow": ["README_RU.md"],
                                   "suffixes": [{"path": "tools/hooks", "suffix": ".hook.md"}]}})
        for path in ("docs/coding-standard.md", "docs/migration-1.0.0.md", "docs/README.md", "docs/README_RU.md",
                     "docs/AGENTS.md", "docs/Image.PNG", "tools/.flake8", "tools/hooks/pre-commit.hook.md",
                     ".github/agents/reviewer.agent.md", ".github/workflows/validation.yml",
                     ".claude/agents/embraion--reviewer-0123456789ab.md", ".claude/agents/embraion--reviewer.md",
                     "tools/Other_Tool.toml", "Assets/Free_Name.md"):
            self.write(path, "x")
        self.assertTrue(check_organization(self.root)["passed"])
        self.write("docs/Coding_Standard.md", "x")
        self.write("docs/notes.MD", "x")
        self.write("tools/some.random.py", "x")
        self.write(".github/agents/Bad_Name.agent.md", "x")
        self.write(".claude/agents/embraion--Bad_Name.md", "x")
        result = check_organization(self.root)
        self.assertEqual({
            ("filename_style", "docs/Coding_Standard.md"), ("filename_extension_case", "docs/notes.MD"),
            ("filename_style", "tools/some.random.py"), ("filename_style", ".github/agents/Bad_Name.agent.md"),
            ("filename_style", ".claude/agents/embraion--Bad_Name.md"),
        }, {(item["code"], item["path"]) for item in result["findings"]})

    def test_filename_incremental_baseline(self) -> None:
        self.config({"filenames": {"roots": ["docs"], "extensions": [".md"]}})
        self.write("docs/Old_Name.md", "x")
        base = self.commit()
        self.write("docs/New_Name.md", "x")
        result = check_organization(self.root, base_ref=base, include_worktree=True)
        status = {(item["code"], item["path"]): item["status"] for item in result["findings"]}
        self.assertEqual({("filename_style", "docs/Old_Name.md"): "preexisting",
                          ("filename_style", "docs/New_Name.md"): "new"}, status)
        self.assertFalse(result["passed"])

    def test_filename_case_collisions_in_a_commit(self) -> None:
        # Case-insensitive file systems cannot hold both paths, so they are added to the index only.
        self.config({"filenames": {"roots": ["docs"], "extensions": [".md"]}})
        self.write("docs/guide.md", "x")
        base = self.commit()
        blob = git(self.root, "hash-object", "-w", "docs/guide.md")
        for path in ("Assets/Readme.txt", "Assets/README.txt"):
            git(self.root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
        git(self.root, "commit", "-m", "collision")
        result = check_organization(self.root, base_ref=base)
        self.assertEqual([("filename_collision", "Assets/Readme.txt", "new")],
                         [(item["code"], item["path"], item["status"]) for item in result["findings"]])

    def test_meta_required_for_all_files_and_orphans(self) -> None:
        self.config({"unity_meta": {"roots": ["Assets/Project"], "require_for_all": True, "check_orphans": True}})
        self.write("Assets/Project.meta", "guid: " + "c" * 32 + "\n")
        self.write("Assets/Project/Scenes.meta", "guid: " + "d" * 32 + "\n")
        self.write("Assets/Project/Scenes/Main.unity", "x")
        self.write("Assets/Project/Scenes/Main.unity.meta", "guid: " + "e" * 32 + "\n")
        self.write("Assets/Project/Docs~/notes.md", "x")
        self.write("Assets/Project/.hidden/file.txt", "x")
        self.write("Assets/Other/NoMeta.txt", "x")
        self.write(".gitignore", "Assets/Project/Ignored.bin\n")
        self.write("Assets/Project/Ignored.bin", "x")
        self.assertTrue(check_organization(self.root)["passed"])
        self.write("Assets/Project/Scenes/Data.bytes", "x")
        self.write("Assets/Project/Gone.png.meta", "guid: " + "f" * 32 + "\n")
        self.assertEqual({("meta_missing", "Assets/Project/Scenes/Data.bytes"),
                          ("meta_orphan", "Assets/Project/Gone.png.meta")},
                         {(item["code"], item["path"]) for item in check_organization(self.root)["findings"]})
        base = self.commit()
        self.write("Assets/Project/Scenes/Data.bytes.meta", "guid: " + "1" * 32 + "\n")
        self.write("Assets/Project/Gone.png", "x")
        self.write("Assets/Project/Added.txt", "x")
        result = check_organization(self.root, base_ref=base, include_worktree=True)
        self.assertEqual([("meta_missing", "Assets/Project/Added.txt", "new")],
                         [(item["code"], item["path"], item["status"]) for item in result["findings"]])
        committed = check_organization(self.root, base_ref=base)
        self.assertEqual(2, committed["counts"]["preexisting"])
        self.assertTrue(committed["passed"])

    def test_missing_configuration_can_be_required(self) -> None:
        self.assertEqual("skipped", check_organization(self.root)["status"])
        result = check_organization(self.root, require_config=True)
        self.assertEqual(("failed", False), (result["status"], result["passed"]))


if __name__ == "__main__":
    unittest.main()
