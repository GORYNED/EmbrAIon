from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import jsonschema
from pathlib import Path
from unittest.mock import patch

from embraion.cli import _cmd_dispatch, _cmd_route, _cmd_run_start, build_parser
from embraion.common import framework_root, read_json, read_yaml, write_yaml
from embraion.evidence import start_run, read_run, attach_validation_evidence, complete_run
from embraion.execution import execute
from embraion.project import init_project
from embraion.runtime import create_dispatch, resolve_task_route, route, validate_task_routes


class CriticalJustificationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="Critical Justification")
        shutil.copytree(framework_root() / "tests/fixtures/routing-consumer",
                        self.project, dirs_exist_ok=True)

    def test_public_route_requires_reason_but_optional_escalation_can_be_enumerated(self) -> None:
        for reason in (None, "   "):
            with self.subTest(reason=reason), self.assertRaisesRegex(RuntimeError, "requires justification"):
                route("alpha-host", "critical", "PRIVATE", role="reviewer",
                      project=self.project, justification=reason)
        selected = route("alpha-host", "critical", "PRIVATE", role="reviewer",
                         project=self.project, justification="protected decision")
        self.assertEqual("critical", selected["route"])
        optional = resolve_task_route("cross-host-review", project=self.project)
        self.assertEqual("substantial", optional["selected"]["route"])
        self.assertEqual("critical", optional["escalations"]["critical"]["route"])
        self.assertTrue(validate_task_routes(self.project)["valid"])
        events = [json.loads(line) for line in
                  (self.project / ".embraion/state/telemetry.jsonl").read_text(encoding="utf-8").splitlines()]
        selections = [item for item in events if item["event"] == "route-selected"]
        self.assertEqual(["critical", "substantial"], [item["route"] for item in selections])
        self.assertEqual("protected decision", selections[0]["justification"])
        self.assertNotIn("justification", selections[1])

    def test_dispatch_requires_reason_for_direct_and_task_class_critical_routes(self) -> None:
        for task_class in (None, "protected-decision"):
            for reason in (None, "   "):
                with self.subTest(task_class=task_class, reason=reason):
                    with self.assertRaisesRegex(RuntimeError, "requires justification"):
                        create_dispatch("Protected task", "reviewer",
                                        None if task_class else "alpha-host",
                                        None if task_class else "critical",
                                        "PRIVATE", "inspect", [], task_class=task_class,
                                        project=self.project, justification=reason)
            record = create_dispatch("Protected task", "reviewer",
                                     None if task_class else "alpha-host",
                                     None if task_class else "critical",
                                     "PRIVATE", "inspect", [], task_class=task_class,
                                     project=self.project, justification="protected decision")
            self.assertEqual("critical", record["route"])
            self.assertEqual("protected decision", record["justification"])
            self.assertEqual("planned", record["state"])

    def test_optional_host_route_critical_escalation_needs_reason_only_when_selected(self) -> None:
        path = self.project / ".embraion/routing.yaml"
        config = read_yaml(path)
        config["overrides"]["alpha-host"]["routes"]["critical"] = {"deployment": "native-critical"}
        config["task-classes"]["cross-host-review"]["escalations"]["critical"] = {
            "host": "alpha-host", "route-class": "critical",
        }
        write_yaml(path, config)
        optional = resolve_task_route("cross-host-review", project=self.project)
        self.assertEqual("substantial", optional["selected"]["route"])
        self.assertEqual("native-critical", optional["escalations"]["critical"]["deployment"])
        with self.assertRaisesRegex(RuntimeError, "requires justification"):
            resolve_task_route("cross-host-review", project=self.project, escalation="critical")
        selected = resolve_task_route("cross-host-review", project=self.project,
                                      escalation="critical", justification="protected decision")
        self.assertEqual("protected decision", selected["selected"]["justification"])

    def test_direct_execution_requires_reason_before_handoff(self) -> None:
        request = {
            "schemaVersion": 1, "runId": "run", "workItemId": "item", "taskId": "task",
            "role": "reviewer", "routeClass": "critical", "host": "alpha-host",
            "dataClass": "PRIVATE", "sourceIds": ["project-source"],
            "trustLevel": "verified", "access": "read-only", "ownedPaths": [],
            "contextRef": "context", "timeoutSeconds": 30, "maxAttempts": 1,
            "candidates": [{"deployment": "native-critical"}],
        }
        for reason in (None, "   "):
            with self.subTest(reason=reason), self.assertRaisesRegex(RuntimeError, "requires justification"):
                execute({**request, **({"justification": reason} if reason is not None else {})},
                        project=self.project)
        result = execute({**request, "justification": "protected decision"}, project=self.project)
        self.assertEqual("handoff-required", result["status"])
        events = [json.loads(line) for line in
                  (self.project / ".embraion/state/telemetry.jsonl").read_text().splitlines()]
        critical = [event for event in events if event["event"] == "critical-execution-requested"]
        self.assertEqual(1, len(critical))
        self.assertEqual("protected decision", critical[0]["justification"])
        self.assertEqual("run", critical[0]["run-id"])
        self.assertNotIn("prompt", critical[0])
        secret = "fixture-" + "s" * 24
        execute({**request, "justification": "protected decision; token=" + secret}, project=self.project)
        audit_text = (self.project / ".embraion/state/telemetry.jsonl").read_text()
        self.assertNotIn(secret, audit_text)
        self.assertIn("<REDACTED>", audit_text)
        ordinary = {**request, "routeClass": "substantial", "candidates": [{"deployment": "native-main"}]}
        self.assertEqual("handoff-required", execute({**ordinary, "justification": "review reason"},
                                                      project=self.project)["status"])
        with self.assertRaisesRegex(RuntimeError, "requires justification"):
            execute({**request, "taskClass": "protected-decision"}, project=self.project)

    def test_rejected_execution_preflight_does_not_record_route_selection(self) -> None:
        request = {
            "schemaVersion": 1, "runId": "run", "workItemId": "item", "taskId": "task",
            "role": "reviewer", "routeClass": "ordinary", "host": "alpha-host",
            "taskClass": "cross-host-review", "dataClass": "PRIVATE",
            "sourceIds": ["project-source"], "trustLevel": "verified",
            "access": "read-only", "ownedPaths": [], "contextRef": "context",
            "timeoutSeconds": 30, "maxAttempts": 1, "candidates": [{"deployment": "native-main"}],
        }
        telemetry = self.project / ".embraion/state/telemetry.jsonl"
        before = telemetry.read_bytes() if telemetry.exists() else b""
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            execute(request, project=self.project)
        self.assertEqual(before, telemetry.read_bytes() if telemetry.exists() else b"")

    def test_critical_run_requires_and_retains_redacted_reason(self) -> None:
        for reason in (None, "  "):
            with self.assertRaisesRegex(RuntimeError, "requires justification"):
                start_run("critical-run", "Protected", "reviewer", "alpha-host", "critical",
                          "PRIVATE", "inspect", [], project=self.project, justification=reason)
            self.assertFalse((self.project / ".embraion/state/runs/critical-run.json").exists())
        secret = "fixture-" + "s" * 24
        record = start_run("critical-run", "Protected", "reviewer", "alpha-host", "critical",
                           "PRIVATE", "inspect", [], project=self.project,
                           justification="protected decision; token=" + secret)
        persisted = read_run("critical-run", self.project)
        self.assertEqual(record, persisted)
        self.assertIn("protected decision", persisted["route"]["justification"])
        self.assertNotIn(secret, json.dumps(persisted))
        self.assertIn("<REDACTED>", persisted["route"]["justification"])
        jsonschema.validate(persisted, read_json(framework_root() / "schemas/execution.schema.json"))
        attach_validation_evidence("critical-run", profile="fast", status="passed", evidence_id="validation-1",
                                   project=self.project)
        completed = complete_run("critical-run", changed_paths=[], validation=[], review="not-required",
                                 outcome="completed", residual_risks=[], project=self.project)
        self.assertEqual(persisted["route"]["justification"], completed["route"]["justification"])
        self.assertEqual("validation-1", completed["validation"][0]["evidence-id"])
        jsonschema.validate(completed, read_json(framework_root() / "schemas/execution.schema.json"))

    def test_cli_threads_justification_and_native_agent_separately(self) -> None:
        parser = build_parser()
        run_args = parser.parse_args(["run", "start", "--run-id", "critical-run", "--task", "Protected",
                                      "--host", "codex", "--route-class", "critical",
                                      "--justification", "protected decision"])
        with patch("embraion.cli.start_run", return_value={}) as start, patch("embraion.cli._print_json"):
            _cmd_run_start(run_args)
        self.assertEqual("protected decision", start.call_args.kwargs["justification"])
        route_args = parser.parse_args(["route", "--host", "alpha-host", "--route-class",
                                        "critical", "--justification", "protected decision"])
        with patch("embraion.cli.route", return_value={}) as mocked_route, patch("embraion.cli._print_json"):
            self.assertEqual(0, _cmd_route(route_args))
        self.assertEqual("protected decision", mocked_route.call_args.kwargs["justification"])

        dispatch_args = parser.parse_args(["dispatch", "--task", "Protected task", "--role", "reviewer",
                                           "--host", "alpha-host", "--route-class", "critical",
                                           "--justification", "protected decision", "--native-surface",
                                           "claude-agent", "--native-agent", "reviewer"])
        with patch("embraion.cli.create_dispatch", return_value={"state": "planned"}) as mocked_dispatch, \
                patch("embraion.cli._print_json"):
            self.assertEqual(0, _cmd_dispatch(dispatch_args))
        self.assertEqual("protected decision", mocked_dispatch.call_args.kwargs["justification"])
        self.assertEqual("reviewer", mocked_dispatch.call_args.kwargs["native_agent"])
        self.assertEqual("reviewer", mocked_dispatch.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
