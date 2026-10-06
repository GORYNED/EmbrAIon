from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion import cli


SOURCE = Path(__file__).resolve().parents[2]


class CapabilityCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        (self.project / ".embraion").mkdir()

    def parse(self, *arguments: str):
        return cli.build_parser().parse_args(list(arguments))

    def eval_args(self, *extra: str):
        return self.parse("eval", "skills", "run", "--suite", "suite.json", "--output",
                          str(self.project / "report.json"), "--path", str(self.project), *extra)

    @staticmethod
    def selected(**changes: object) -> dict[str, object]:
        route = {"resolution": "project-override", "model": "codex-sol", "effort": "high",
                 "provider": None, "options": {}}
        route.update(changes)
        return route

    def test_capability_inventory_error_does_not_echo_secret(self) -> None:
        inventory = self.project / ".embraion/external-capabilities.yaml"
        inventory.write_text("schema-version: 1\ncapabilities:\n  - id: secret\n    token: sensitive-value\n",
                             encoding="utf-8")
        args = self.parse("capabilities", "--path", str(self.project), "--json")
        with patch.object(cli, "framework_root", return_value=SOURCE), \
             patch.object(cli, "diagnose_external_capabilities", wraps=cli.diagnose_external_capabilities):
            with self.assertRaises(RuntimeError) as failure:
                args.func(args)
        self.assertIn("Invalid external capability inventory", str(failure.exception))
        self.assertNotIn("sensitive-value", str(failure.exception))

    def test_live_eval_rejects_project_model_or_effort_mismatch_before_launch(self) -> None:
        with patch.object(cli, "route", return_value=self.selected()) as resolve, \
             patch.object(cli, "run_suite") as launch:
            for flags in (("--model", "different-model"), ("--effort", "low")):
                with self.subTest(flags=flags):
                    args = self.eval_args(*flags)
                    with self.assertRaisesRegex(RuntimeError, "must match"):
                        args.func(args)
            launch.assert_not_called()
            self.assertEqual("worker", resolve.call_args.kwargs["role"])
            self.assertEqual("workspace-write", resolve.call_args.kwargs["access"])

    def test_live_eval_rejects_provider_and_options_before_launch(self) -> None:
        with patch.object(cli, "route") as resolve, patch.object(cli, "run_suite") as launch:
            for changes in ({"provider": "external-provider"}, {"options": {"unsafe": True}}):
                with self.subTest(changes=changes):
                    resolve.return_value = self.selected(**changes)
                    args = self.eval_args()
                    with self.assertRaisesRegex(RuntimeError, "provider or additional options"):
                        args.func(args)
            launch.assert_not_called()

    def test_live_eval_applies_resolved_route_or_explicit_host_defaults(self) -> None:
        report = {"runs": [{"variant": "candidate", "behavior-passed": True}]}
        output = io.StringIO()
        with patch.object(cli, "route", return_value=self.selected()) as resolve, \
             patch.object(cli, "run_suite", return_value=report) as launch, \
             contextlib.redirect_stdout(output):
            args = self.eval_args("--model", "codex-sol", "--effort", "high", "--route-class", "complex")
            self.assertEqual(0, args.func(args))
            self.assertEqual("codex-sol", launch.call_args.kwargs["model"])
            self.assertEqual("high", launch.call_args.kwargs["effort"])
            self.assertEqual("complex", resolve.call_args.args[1])
            resolve.return_value = self.selected(resolution="host-default", model=None, effort=None)
            args = self.eval_args("--model", "host-model", "--effort", "medium")
            self.assertEqual(0, args.func(args))
            self.assertEqual("host-model", launch.call_args.kwargs["model"])
            self.assertEqual("medium", launch.call_args.kwargs["effort"])

    def test_live_eval_rejects_a_host_command_that_is_not_an_argument_vector(self) -> None:
        host_default = self.selected(resolution="host-default", model=None, effort=None)
        with patch.object(cli, "route", return_value=host_default) as resolve, \
             patch.object(cli, "run_suite") as launch:
            args = self.eval_args("--host", "portable", "--host-command", "not json [")
            with self.assertRaisesRegex(RuntimeError, "JSON array of strings"):
                args.func(args)
            resolve.assert_not_called()
            launch.assert_not_called()
        suite = self.project / "suite.json"
        suite.write_text("{}", encoding="utf-8")
        with patch.object(cli, "route", return_value=host_default):
            args = self.parse("eval", "skills", "run", "--suite", str(suite), "--output", str(self.project / "report.json"),
                              "--path", str(self.project), "--host", "portable", "--host-command", '"my-agent run"')
            with self.assertRaisesRegex(RuntimeError, "argument vector") as failure:
                args.func(args)
            self.assertNotIn("my-agent", str(failure.exception))

    def test_organization_finding_fails_and_skipped_passes(self) -> None:
        args = self.parse("organization", "check", "--path", str(self.project), "--json")
        output = io.StringIO()
        with patch.object(cli, "check_organization") as inspect, contextlib.redirect_stdout(output):
            inspect.return_value = {"passed": False, "status": "failed", "mode": "configured",
                                    "findings": [{"code": "namespace_mismatch", "path": "src/Foo.cs"}]}
            self.assertEqual(1, args.func(args))
            self.assertEqual("namespace_mismatch", json.loads(output.getvalue())["findings"][0]["code"])
            output.seek(0)
            output.truncate(0)
            inspect.return_value = {"passed": True, "status": "skipped", "mode": "unconfigured", "findings": []}
            self.assertEqual(0, args.func(args))
            self.assertEqual("skipped", json.loads(output.getvalue())["status"])

    def test_doctor_invalid_controls_fail_without_claiming_readiness(self) -> None:
        args = self.parse("doctor", "--json")
        output = io.StringIO()
        with patch.object(cli, "framework_root", return_value=SOURCE), \
             patch.object(cli, "find_project_root", return_value=self.project), \
             patch.object(cli, "collect_issues", return_value=[]), \
             patch.object(cli, "collect_findings", return_value=[]), \
             patch.object(cli, "diagnose_external_capabilities", side_effect=RuntimeError("Invalid inventory")), \
             patch.object(cli, "check_organization", return_value={"passed": False, "status": "failed"}), \
             patch.object(cli, "audit_knowledge", return_value={"status": "skipped"}), \
             patch.object(cli, "save_mcp_inventory", return_value={"servers": []}), \
             patch.object(cli, "list_worktrees", return_value=[]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(1, args.func(args))
        report = json.loads(output.getvalue())
        self.assertEqual("error", report["project-controls"]["capabilities"]["status"])
        self.assertTrue(any("organization" in message for message in report["project-control-errors"]))
        self.assertTrue(any("capabilities" in message for message in report["project-control-errors"]))
        self.assertNotIn('"ready": true', output.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
