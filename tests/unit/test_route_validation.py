from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root, read_yaml, write_yaml
from embraion.project import init_project
from embraion.runtime import validate_task_routes


class RouteValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="Route Validation")
        shutil.copytree(framework_root() / "tests/fixtures/routing-consumer",
                        self.project, dirs_exist_ok=True)
        self.routing_path = self.project / ".embraion/routing.yaml"
        self.base = read_yaml(self.routing_path)

    def validate_with(self, mutate) -> dict:
        routing = copy.deepcopy(self.base)
        mutate(routing)
        write_yaml(self.routing_path, routing)
        return validate_task_routes(self.project)

    def test_reports_all_direct_override_selections_without_route_events(self) -> None:
        def add_overrides(routing):
            host = routing["overrides"]["alpha-host"]
            host["roles"] = {"steward": {"deployment": "native-critical"}}
            host["route-roles"]["substantial"] = {"reviewer": {"model": "project-model"}}
            host["task-classes"]["protected-decision"] = {"model": "task-model"}

        result = self.validate_with(add_overrides)
        self.assertTrue(result["valid"])
        self.assertIn("overrides.alpha-host.roles.steward", result["override-selections"])
        self.assertIn("overrides.alpha-host.route-roles.substantial.reviewer", result["override-selections"])
        self.assertIn("overrides.alpha-host.task-classes.protected-decision", result["override-selections"])
        self.assertEqual(len(result["override-selections"]), result["override-selection-count"])
        self.assertFalse((self.project / ".embraion/state/telemetry.jsonl").exists())

    def test_each_direct_override_kind_rejects_invalid_deployment(self) -> None:
        selectors = (
            lambda host: host["routes"].update({"bounded-read": {"deployment": "missing"}}),
            lambda host: host.setdefault("roles", {}).update({"analyst": {"deployment": "missing"}}),
            lambda host: host.setdefault("route-roles", {}).update(
                {"ordinary": {"analyst": {"deployment": "missing"}}}),
            lambda host: host["task-classes"].update({"routine-review": {"deployment": "missing"}}),
        )
        for mutate_host in selectors:
            with self.subTest(mutate=mutate_host):
                with self.assertRaisesRegex(RuntimeError, "unknown project deployment 'missing'"):
                    self.validate_with(lambda routing: mutate_host(routing["overrides"]["alpha-host"]))

    def test_override_references_and_deployment_structure_are_checked(self) -> None:
        cases = (
            (lambda routing: routing["overrides"]["alpha-host"]["routes"].update(
                {"unknown-route": {"model": "project-model"}}), "unknown route class"),
            (lambda routing: routing["overrides"]["alpha-host"].setdefault("route-roles", {}).update(
                {"unknown-route": {"reviewer": {"model": "project-model"}}}), "unknown route class"),
            (lambda routing: routing["overrides"]["alpha-host"]["task-classes"].update(
                {"missing-task": {"model": "project-model"}}), "unknown project task class"),
            (lambda routing: routing["overrides"]["alpha-host"]["routes"].update(
                {"bounded-read": {"deployment": "api-review"}}), "belongs to host"),
            (lambda routing: routing["overrides"]["alpha-host"]["routes"].update(
                {"bounded-read": {"deployment": "native-main", "effort": "low"}}), "does not support effort"),
            (lambda routing: routing["overrides"]["alpha-host"]["routes"].update(
                {"bounded-read": {"model": "project-model", "fallbacks": [
                    {"deployment": "native-main", "effort": "low"}]}}), "does not support effort"),
            (lambda routing: routing["overrides"]["alpha-host"]["routes"].update(
                {"bounded-read": {"deployment": "native-main", "fallbacks": [
                    {"deployment": "native-main"}]}}), "duplicate deployment"),
        )
        for mutate, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                self.validate_with(mutate)

    def test_disabled_deployment_in_unused_group_or_direct_override_is_rejected(self) -> None:
        deployments_path = self.project / ".embraion/deployments.yaml"
        definitions = read_yaml(deployments_path)
        definitions["deployments"]["native-critical"]["enabled"] = False
        write_yaml(deployments_path, definitions)
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            self.validate_with(lambda routing: routing["overrides"]["alpha-host"].setdefault(
                "roles", {}).update({"reviewer": {"deployment": "native-critical"}}))
        definitions["deployments"]["native-critical"]["enabled"] = True
        definitions["deployments"]["api-alternate"]["enabled"] = False
        write_yaml(deployments_path, definitions)
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            self.validate_with(lambda routing: routing["candidate-groups"].update(
                {"unused": {"deployments": [{"deployment": "api-alternate"}]}}))


if __name__ == "__main__":
    unittest.main()
