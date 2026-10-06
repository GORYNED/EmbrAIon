from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.cli import main
from embraion.common import framework_root, read_yaml, write_yaml
from embraion.project import init_project
from embraion.validation import collect_project_config_issues


class ProjectConfigCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "consumer"
        self.project.mkdir()
        init_project(self.project, name="Consumer")
        self.config = self.project / ".embraion"

    def issues(self) -> set[tuple[str, str, str]]:
        return {(item["code"], item["path"], item["message"])
                for item in collect_project_config_issues(self.project, framework_root())}

    def run_validate(self, *arguments: str) -> tuple[int, str]:
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        stdout = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), patch("sys.stdout", stdout):
            code = main(["validate", *arguments])
        os.chdir(previous)
        return code, stdout.getvalue()

    def break_configuration(self) -> None:
        project = read_yaml(self.config / "project.yaml")
        project["houskeeping"] = {"worktrees": True}
        project["housekeeping"]["local-branch"] = True
        project["capabilities"] = None
        write_yaml(self.config / "project.yaml", project)
        policy = read_yaml(self.config / "policy.yaml")
        policy["sources"]["vendor"] = ["Vendor/**"]
        write_yaml(self.config / "policy.yaml", policy)
        write_yaml(self.config / "routing.yaml", {"overrides": {}, "override": {}})
        write_yaml(self.config / "agents.yaml", {"agents": [{
            "id": "domain-expert", "purpose": "Explain the domain.", "access": "read-only",
            "responsibilities": ["Explain"]}]})
        (self.project / "docs").mkdir()
        (self.project / "docs" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
        write_yaml(self.config / "knowledge.yaml", {
            "slots": {"architecture": "docs/architecture.md", "constitutoin": "docs/architecture.md",
                      "persistence": None},
            "domain": {"path": "docs/architecture.md", "roles": ["domain-expert", "reviewer", "revewer"]},
            "missing": {"path": "docs/missing.md"},
            "outside": "../outside.md",
            "inert-entry": None,
        })
        (self.project / "Assets").mkdir()
        write_yaml(self.config / "organization.yaml", {
            "filenames": {"roots": ["Assets", "Packages/missing", "."], "extensions": [".md"]}})
        (self.config / "pricing.yaml").write_text("# nothing configured\n", encoding="utf-8")
        (self.config / "routes.yaml").write_text("overrides: {}\n", encoding="utf-8")

    def test_fresh_project_has_no_findings_and_keeps_pass_output(self) -> None:
        self.assertEqual(set(), self.issues())
        code, stdout = self.run_validate()
        self.assertEqual(0, code)
        self.assertEqual("PASS: no validation issues.\n", stdout)

    def test_declared_integrations_file_is_read_configuration(self) -> None:
        write_yaml(self.config / "integrations.yaml", {"schema-version": 1, "servers": [{
            "id": "docs", "host": "codex", "command": "docs-server", "args": ["--stdio"],
            "transport": "stdio", "access": "read-only", "env-vars": []}]})
        self.assertEqual(set(), self.issues())

        write_yaml(self.config / "integrations.yaml", {"schema-version": 1, "servers": [], "extra": True})
        self.assertIn(("config-unknown-key", ".embraion/integrations.yaml", "'extra' is not a known key here"),
                      {(code, path, message) for code, path, message in self.issues()})

    def test_structural_findings_cover_keys_paths_roles_and_inert_content(self) -> None:
        self.break_configuration()
        self.assertEqual({
            ("config-unknown-key", ".embraion/project.yaml", "'houskeeping' is not a known key here"),
            ("config-unknown-key", ".embraion/project.yaml", "'housekeeping.local-branch' is not a known key here"),
            ("config-inert", ".embraion/project.yaml", "'capabilities' is empty and has no effect"),
            ("config-unknown-key", ".embraion/policy.yaml", "'sources.vendor' is not a known key here"),
            ("config-unknown-key", ".embraion/routing.yaml", "'override' is not a known key here"),
            ("config-unknown-key", ".embraion/knowledge.yaml", "'slots.constitutoin' is not a known key here"),
            ("config-inert", ".embraion/knowledge.yaml", "'inert-entry' is empty and has no effect"),
            ("config-role", ".embraion/knowledge.yaml",
             "knowledge 'domain' role 'revewer' matches no Core role or declared agent"),
            ("config-path", ".embraion/knowledge.yaml",
             "knowledge 'missing' points to a missing file: docs/missing.md"),
            ("config-path", ".embraion/knowledge.yaml", "knowledge 'outside' points outside the project"),
            ("config-path", ".embraion/organization.yaml",
             "filenames.roots entry 'Packages/missing' does not exist"),
            ("config-inert", ".embraion/pricing.yaml", "File is empty and has no effect"),
            ("config-inert", ".embraion/routes.yaml", "EmbrAIon does not read this file"),
        }, self.issues())

    def test_findings_are_warnings_unless_strict(self) -> None:
        self.break_configuration()
        # An unknown policy key also fails the existing policy ceiling check, which stays an error.
        code, stdout = self.run_validate()
        self.assertEqual(1, code)
        self.assertIn("ERROR   policy-ceiling", stdout)
        policy = read_yaml(self.config / "policy.yaml")
        del policy["sources"]["vendor"]
        write_yaml(self.config / "policy.yaml", policy)
        code, stdout = self.run_validate()
        self.assertEqual(0, code)
        self.assertNotIn("PASS", stdout)
        self.assertIn("WARNING config-unknown-key", stdout)
        code, stdout = self.run_validate("--strict", "--json")
        self.assertEqual(1, code)
        report = json.loads(stdout)
        self.assertEqual(12, report["count"])
        self.assertEqual({"error"}, {item["severity"] for item in report["issues"]})

    def test_unparsable_or_non_mapping_files_are_reported_without_raising(self) -> None:
        (self.config / "routing.yaml").write_text("overrides: [unclosed\n", encoding="utf-8")
        (self.config / "report.yaml").write_text("- a list\n", encoding="utf-8")
        self.assertEqual({
            ("config-parse", ".embraion/routing.yaml", "File is not valid YAML"),
            ("config-parse", ".embraion/report.yaml", "Expected a mapping at the top level"),
        }, self.issues())


if __name__ == "__main__":
    unittest.main()
