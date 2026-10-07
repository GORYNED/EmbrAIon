from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from embraion.check import planned_checks
from embraion.cli import main
from embraion.common import read_yaml, write_yaml
from embraion.policy import check_source_classes, read_policy_config, source_data_classes
from embraion.project import init_project


class CheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="Check")
        self.policy = self.project / ".embraion/policy.yaml"

    def update_policy(self, **sections: object) -> None:
        data = read_yaml(self.policy)
        data.update(sections)
        write_yaml(self.policy, data)

    def ids(self, **options: object) -> list[str]:
        return [item["id"] for item in planned_checks(self.project, **options)]

    def test_default_project_runs_configuration_routing_and_security_checks(self) -> None:
        self.assertEqual(["validate", "routes", "routing-authority", "security"], self.ids())
        security = planned_checks(self.project)[-1]["argv"]
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "high"], security)

    def test_declared_projections_organization_and_options_select_their_checks(self) -> None:
        self.update_policy(projection={
            "codex": {"components": ["config", "agents"], "config-mode": "merge", "strict-root": True},
            "copilot": {"components": ["skills"]},
            "claude-code": {"components": ["agents", "scoped-agents", "hooks"]},
        })
        (self.project / ".embraion/organization.yaml").write_text("{}\n", encoding="utf-8")
        checks = {item["id"]: item["argv"] for item in
                  planned_checks(self.project, base_ref="origin/main", fail_on="medium", all_files=True)}
        self.assertEqual(
            ["validate", "routes", "routing-authority", "projection-codex", "projection-copilot",
             "projection-claude-code", "claude-native", "organization", "security"],
            list(checks),
        )
        self.assertEqual(["projection", "verify", "--host", "codex", "--json", "--component", "config",
                          "--component", "agents", "--config-mode", "merge"], checks["projection-codex"])
        self.assertEqual(["claude-native", "status", "--require", "installed,hooks"], checks["claude-native"])
        self.assertEqual(["organization", "check", "--require-config", "--path", ".", "--json",
                          "--base-ref", "origin/main"], checks["organization"])
        self.assertEqual(["organization", "check", "--require-config", "--path", ".", "--json"],
                         {item["id"]: item["argv"] for item in planned_checks(self.project)}["organization"])
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "medium", "--all-files"],
                         checks["security"])

    def test_declared_organization_modes_select_full_and_compare_checks(self) -> None:
        (self.project / ".embraion/organization.yaml").write_text("{}\n", encoding="utf-8")
        base = ["organization", "check", "--require-config", "--path", ".", "--json"]
        self.update_policy(check={"organization": ["full", "compare"]})
        checks = {item["id"]: item for item in planned_checks(self.project, base_ref="origin/main")}
        self.assertEqual(["validate", "routes", "routing-authority", "organization-full",
                          "organization-compare", "security"], list(checks))
        self.assertEqual(base, checks["organization-full"]["argv"])
        self.assertEqual(base + ["--base-ref", "origin/main"], checks["organization-compare"]["argv"])
        without_ref = {item["id"]: item for item in planned_checks(self.project)}
        self.assertEqual(base, without_ref["organization-full"]["argv"])
        self.assertIsNone(without_ref["organization-compare"]["argv"])
        self.assertEqual("needs --base-ref", without_ref["organization-compare"]["not-run"])

    def test_single_declared_organization_mode_ignores_the_base_ref_for_full(self) -> None:
        (self.project / ".embraion/organization.yaml").write_text("{}\n", encoding="utf-8")
        self.update_policy(check={"organization": ["full"]})
        checks = {item["id"]: item["argv"] for item in planned_checks(self.project, base_ref="origin/main")}
        self.assertEqual(["organization", "check", "--require-config", "--path", ".", "--json"],
                         checks["organization-full"])
        self.assertNotIn("organization-compare", checks)
        self.update_policy(check={"organization": ["compare"]})
        self.assertEqual(["validate", "routes", "routing-authority", "organization-compare", "security"],
                         self.ids())

    def test_organization_modes_are_not_planned_without_an_organization_configuration(self) -> None:
        self.update_policy(check={"organization": ["full", "compare"]})
        self.assertEqual(["validate", "routes", "routing-authority", "security"], self.ids(base_ref="origin/main"))

    def test_declared_security_options_apply_unless_flags_override_them(self) -> None:
        self.update_policy(check={"fail-on": "medium", "all-files": True})
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "medium", "--all-files"],
                         planned_checks(self.project)[-1]["argv"])
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "low", "--all-files"],
                         planned_checks(self.project, fail_on="low")[-1]["argv"])
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "medium"],
                         planned_checks(self.project, all_files=False)[-1]["argv"])

    def test_invalid_check_declaration_fails_closed(self) -> None:
        for declaration in ({"organization": []}, {"organization": ["both"]},
                            {"organization": ["full", "full"]}, {"fail-on": "severe"},
                            {"all-files": "yes"}, {"unknown": True}):
            with self.subTest(check=declaration):
                self.update_policy(check=declaration)
                with self.assertRaises(RuntimeError):
                    read_policy_config(self.project)

    def test_command_applies_declared_options_and_reports_compare_as_not_run(self) -> None:
        (self.project / ".embraion/organization.yaml").write_text("{}\n", encoding="utf-8")
        self.update_policy(check={"organization": ["full", "compare"], "fail-on": "medium", "all-files": True})
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        planned: list[list[str]] = []

        def fake_run(parser, argv):
            planned.append(argv)
            return 0, "ok\n"

        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check", side_effect=fake_run), redirect_stdout(output):
            self.assertEqual(0, main(["check"]))
        self.assertIn("NOT RUN  organization-compare", output.getvalue())
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "medium", "--all-files"], planned[-1])
        planned.clear()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check", side_effect=fake_run), redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["check", "--fail-on", "low"]))
        self.assertEqual(["security", "scan", "--path", ".", "--fail-on", "low", "--all-files"], planned[-1])

    def test_invalid_check_declaration_fails_the_command_before_any_check_runs(self) -> None:
        self.update_policy(check={"organization": ["both"]})
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check") as run, redirect_stdout(io.StringIO()), \
                patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(2, main(["check"]))
        run.assert_not_called()

    def test_schema_severity_choices_match_the_security_scan(self) -> None:
        from embraion.common import framework_root, read_json
        from embraion.security import SEVERITY_ORDER

        schema = read_json(framework_root() / "schemas" / "policy.schema.json")
        self.assertEqual(list(SEVERITY_ORDER), schema["properties"]["check"]["properties"]["fail-on"]["enum"])

    def test_codex_config_defaults_to_replace_mode_and_hooks_alone_require_only_hooks(self) -> None:
        self.update_policy(projection={"codex": {"components": ["config"]},
                                       "claude-code": {"components": ["hooks"]}})
        checks = {item["id"]: item["argv"] for item in planned_checks(self.project)}
        self.assertEqual("replace", checks["projection-codex"][-1])
        self.assertEqual(["claude-native", "status", "--require", "hooks"], checks["claude-native"])

    def test_invalid_projection_declaration_fails_closed(self) -> None:
        for projection in ({"copilot": {"components": ["config"]}},
                           {"codex": {"config-mode": "append"}},
                           {"portable": {"components": ["bundle"]}}):
            with self.subTest(projection=projection):
                self.update_policy(projection=projection)
                with self.assertRaises(RuntimeError):
                    read_policy_config(self.project)

    def test_command_reports_every_check_and_fails_when_one_fails(self) -> None:
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        outcomes = {"routes": (2, "ERROR: broken routes\n")}

        def fake_run(parser, argv):
            check = {"validate": "validate", "route": "routes" if "--validate" in argv else "routing-authority",
                     "security": "security"}[argv[0]]
            return outcomes.get(check, (0, "ok\n"))

        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check", side_effect=fake_run), redirect_stdout(output):
            self.assertEqual(1, main(["check", "--json"]))
        report = json.loads(output.getvalue())
        self.assertFalse(report["passed"])
        self.assertEqual(["routes"], report["failed"])
        self.assertEqual(4, len(report["checks"]))

        outcomes.clear()
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check", side_effect=fake_run), redirect_stdout(output):
            self.assertEqual(0, main(["check"]))
        self.assertIn("Check: passed", output.getvalue())

    def test_decisions_check_is_reported_as_not_run_without_a_base_ref(self) -> None:
        (self.project / ".embraion/decisions.yaml").write_text("{}\n", encoding="utf-8")
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check", return_value=(0, "ok\n")), redirect_stdout(output):
            self.assertEqual(0, main(["check"]))
        self.assertIn("NOT RUN  decisions", output.getvalue())
        self.assertIn("needs --base-ref", output.getvalue())
        self.assertIn("Check: passed", output.getvalue())
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), \
                patch("embraion.check.run_check", return_value=(0, "ok\n")), redirect_stdout(output):
            main(["check", "--json"])
        entry = next(item for item in json.loads(output.getvalue())["checks"] if item["id"] == "decisions")
        self.assertIsNone(entry["passed"])

    def test_command_runs_real_checks_from_the_project_root(self) -> None:
        nested = self.project / "nested"
        nested.mkdir()
        (self.project / "notes.md").write_text("token = ghp_" + "a" * 36 + "\n", encoding="utf-8")
        previous = Path.cwd()
        os.chdir(nested)
        self.addCleanup(os.chdir, previous)
        output = io.StringIO()
        with patch("embraion.cli.resolve_project_runtime", return_value=None), redirect_stdout(output):
            code = main(["check", "--json", "--all-files"])
        report = json.loads(output.getvalue())
        self.assertEqual(["validate", "routes", "routing-authority", "security"],
                         [item["id"] for item in report["checks"]])
        self.assertIn("security", report["failed"])
        self.assertEqual(1, code)
        self.assertEqual(nested, Path.cwd())

    def test_run_check_fails_only_the_broken_check(self) -> None:
        from embraion.check import run_check
        from embraion.cli import build_parser

        parser = build_parser()
        code, output = run_check(parser, ["route", "--no-such-option"])
        self.assertEqual(2, code)
        self.assertIn("unrecognized arguments", output)
        with patch("embraion.cli._cmd_validate", side_effect=KeyError("missing")):
            code, output = run_check(build_parser(), ["validate", "--strict"])
        self.assertEqual(2, code)
        self.assertIn("KeyError", output)


class SourceClassTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        init_project(self.project, name="Sources")
        self.policy = self.project / ".embraion/policy.yaml"

    def declare(self, sources: object) -> None:
        data = read_yaml(self.policy)
        data["privacy"]["sources"] = sources
        write_yaml(self.policy, data)

    def test_undeclared_sources_keep_previous_behavior(self) -> None:
        self.assertIsNone(source_data_classes(self.project))
        check_source_classes("PUBLIC", ["Anything"], self.project)

    def test_declared_sources_fail_closed_for_unknown_ids_and_lower_classes(self) -> None:
        self.declare({"Docs": "PUBLIC", "App": "PRIVATE", "Vendor": "CONFIDENTIAL"})
        self.assertEqual({"Docs": "PUBLIC", "App": "PRIVATE", "Vendor": "CONFIDENTIAL"},
                         source_data_classes(self.project))
        check_source_classes("PRIVATE", ["Docs", "App"], self.project)
        check_source_classes("CONFIDENTIAL", ["Vendor", "App"], self.project)
        self.declare({"repo:App/main": "PRIVATE"})
        check_source_classes("PRIVATE", ["repo:App/main"], self.project)
        self.declare({"Docs": "PUBLIC", "App": "PRIVATE", "Vendor": "CONFIDENTIAL"})
        with self.assertRaisesRegex(RuntimeError, "without a declared data class: Other"):
            check_source_classes("CONFIDENTIAL", ["App", "Other"], self.project)
        with self.assertRaisesRegex(RuntimeError, r"PRIVATE is below the declared class of: Vendor \(CONFIDENTIAL\)"):
            check_source_classes("PRIVATE", ["App", "Vendor"], self.project)

    def test_execution_requests_are_checked_against_declared_sources(self) -> None:
        from embraion.execution import check_request_consistency

        self.declare({"App": "PRIVATE", "Vendor": "CONFIDENTIAL"})
        request = {"routeClass": "ordinary", "candidates": [], "dataClass": "PRIVATE", "sourceIds": ["App"]}
        self.assertEqual(self.project, check_request_consistency(request, self.project))
        with self.assertRaisesRegex(RuntimeError, "below the declared class"):
            check_request_consistency({**request, "sourceIds": ["Vendor"]}, self.project)

    def test_invalid_source_class_is_rejected(self) -> None:
        for sources in ({"App": "SECRET"}, {"": "PRIVATE"}, ["App"]):
            with self.subTest(sources=sources):
                self.declare(sources)
                with self.assertRaises(RuntimeError):
                    read_policy_config(self.project)


if __name__ == "__main__":
    unittest.main()
