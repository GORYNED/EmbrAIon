from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from embraion.ceilings import check_policy_ceilings, enforce_critical_justification
from embraion.cli import build_parser
from embraion.common import read_yaml, write_yaml
from embraion.project import init_project
from embraion.runtime import resolve_task_route, validate_task_routes


DEPLOYMENTS = {
    "providers": {"open": {}, "public": {}, "review": {}},
    "deployments": {
        "native": {
            "host": "native-host", "provider": "open", "model": "native-model",
            "capabilities": {"data-classes": ["PUBLIC", "PRIVATE", "CONFIDENTIAL"],
                             "access-modes": ["read-only", "workspace-write"],
                             "roles": ["research", "implementation", "diagnostic", "independent-review"]},
        },
        "public-api": {
            "host": "api-host", "provider": "public", "model": "public-model",
            "billing": {"mode": "api"},
            "capabilities": {"data-classes": ["PUBLIC"], "access-modes": ["read-only"],
                             "roles": ["research"], "task-classes": ["public-research"]},
        },
        "review-api": {
            "host": "api-host", "provider": "review", "model": "review-model",
            "billing": {"mode": "api"},
            "capabilities": {"data-classes": ["PUBLIC", "PRIVATE"], "access-modes": ["read-only"],
                             "roles": ["independent-review"], "task-classes": ["review"]},
        },
    },
}
EXECUTION = {
    "schemaVersion": 1,
    "bindings": {
        "public-api": {"adapter": "example", "selector": "public/model", "credentialRef": "env:PUBLIC_TOKEN",
                       "sourceIds": ["PublicDocs"], "trustLevels": ["verified"], "taskClasses": ["public-research"]},
        "review-api": {"adapter": "example", "selector": "review/model", "credentialRef": "env:REVIEW_TOKEN",
                       "sourceIds": ["Project"], "trustLevels": ["verified"], "taskClasses": ["review"]},
    },
}
ROUTING = {
    "overrides": {},
    "task-classes": {
        "public-research": {"route-class": "bounded-read", "role": "research", "data-class": "PUBLIC",
                            "candidates": [{"host": "api-host", "deployment": "public-api"},
                                           {"host": "native-host", "deployment": "native"}]},
        "review": {"route-class": "substantial", "role": "independent-review", "data-class": "PRIVATE",
                   "candidates": [{"host": "api-host", "deployment": "review-api"}]},
        "diagnostic": {"route-class": "ordinary", "role": "diagnostic", "data-class": "CONFIDENTIAL",
                       "candidates": [{"host": "native-host", "deployment": "native"}]},
        "protected": {"route-class": "critical", "role": "independent-review", "data-class": "PRIVATE",
                      "candidates": [{"host": "native-host", "deployment": "native"}]},
    },
}
CEILINGS = {
    "providers": {
        "public": {"data-classes": ["PUBLIC"], "access-modes": ["read-only"], "roles": ["research"],
                   "sources": ["PublicDocs"]},
        "review": {"data-classes": ["PUBLIC", "PRIVATE"], "access-modes": ["read-only"],
                   "roles": ["independent-review"], "binding-required-billing-modes": ["api"]},
    },
    "data-classes": {"CONFIDENTIAL": {"providers": ["open"]}},
    "sources": {"ProtectedSdk": {"providers": ["open"]}},
    "task-classes": {"protected": {"route-class": "critical"},
                     "diagnostic": {"route-class": "ordinary", "role": "diagnostic", "data-class": "CONFIDENTIAL"}},
    "critical": {"justifications": ["security-critical", "migration-data-loss"]},
}


class PolicyCeilingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="Ceilings")
        config = self.project / ".embraion"
        write_yaml(config / "deployments.yaml", DEPLOYMENTS)
        write_yaml(config / "execution.yaml", EXECUTION)
        write_yaml(config / "routing.yaml", ROUTING)
        policy = read_yaml(config / "policy.yaml")
        policy["ceilings"] = CEILINGS
        write_yaml(config / "policy.yaml", policy)

    def edit(self, name: str, change) -> None:
        path = self.project / ".embraion" / name
        data = read_yaml(path)
        change(data)
        write_yaml(path, data)

    def codes(self) -> set[tuple[str, str]]:
        return {(item["code"], item["path"]) for item in check_policy_ceilings(self.project)}

    def test_configuration_within_ceilings_passes_and_routes_still_validate(self) -> None:
        self.assertEqual(set(), self.codes())
        self.assertTrue(validate_task_routes(self.project)["valid"])

    def test_widened_deployment_capabilities_fail_with_location(self) -> None:
        self.edit("deployments.yaml", lambda data: data["deployments"]["public-api"]["capabilities"]
                  ["data-classes"].append("CONFIDENTIAL"))
        self.assertEqual({
            ("ceiling-exceeded", "deployments.public-api.capabilities.data-classes"),
            ("ceiling-data-class-provider", "deployments.public-api"),
        }, self.codes())

    def test_removed_capability_dimension_counts_as_unbounded(self) -> None:
        self.edit("deployments.yaml", lambda data: data["deployments"]["review-api"]["capabilities"].pop("roles"))
        self.assertIn(("ceiling-unbounded", "deployments.review-api.capabilities.roles"), self.codes())

    def test_unrestricted_data_classes_cannot_reach_confidential_provider_limit(self) -> None:
        def widen(data: dict) -> None:
            data["deployments"]["other"] = {"host": "native-host", "provider": "review", "model": "x"}
        self.edit("deployments.yaml", widen)
        codes = self.codes()
        self.assertIn(("ceiling-data-class-provider", "deployments.other"), codes)
        self.assertIn(("ceiling-unbounded", "deployments.other.capabilities.data-classes"), codes)

    def test_unverifiable_binding_task_classes_and_missing_provider_fail(self) -> None:
        self.edit("execution.yaml", lambda data: data["bindings"]["review-api"].update({"taskClasses": ["complex"]}))
        self.assertIn(("ceiling-unbounded", "execution.bindings.review-api.taskClasses"), self.codes())
        def drop(data: dict) -> None:
            data["deployments"]["other"] = {"host": "native-host", "model": "x"}
        self.edit("deployments.yaml", drop)
        self.assertIn(("ceiling-provider-missing", "deployments.other"), self.codes())

    def test_disabled_deployments_are_ignored(self) -> None:
        def disable(data: dict) -> None:
            data["deployments"]["other"] = {"host": "native-host", "provider": "review", "model": "x", "enabled": False}
        self.edit("deployments.yaml", disable)
        self.assertEqual(set(), self.codes())

    def test_binding_sources_task_classes_and_required_binding(self) -> None:
        def widen(data: dict) -> None:
            data["bindings"]["public-api"]["sourceIds"].append("Project")
            data["bindings"]["public-api"].pop("taskClasses")
            data["bindings"]["review-api"]["sourceIds"].append("ProtectedSdk")
        self.edit("execution.yaml", widen)
        self.assertEqual({
            ("ceiling-source", "execution.bindings.public-api.sourceIds"),
            ("ceiling-unbounded", "execution.bindings.public-api.taskClasses"),
            ("ceiling-source-provider", "execution.bindings.review-api.sourceIds"),
        }, self.codes())
        self.edit("execution.yaml", lambda data: data["bindings"].pop("review-api"))
        self.assertIn(("ceiling-binding-missing", "deployments.review-api"), self.codes())

    def test_routing_cannot_send_higher_task_classes_to_a_ceilinged_deployment(self) -> None:
        self.edit("routing.yaml", lambda data: data["task-classes"]["review"].update({"data-class": "CONFIDENTIAL"}))
        self.assertIn(("ceiling-data-class", "routing.task-classes.review"), self.codes())
        self.assertIn(("ceiling-data-class", "execution.bindings.review-api.taskClasses"), self.codes())

    def test_host_overrides_cannot_bypass_provider_ceilings(self) -> None:
        def widen(data: dict) -> None:
            data["overrides"] = {"api-host": {
                "routes": {"complex": {"deployment": "review-api"},
                           "ordinary": {"deployment": "native", "fallbacks": [{"deployment": "public-api"}]}},
                "route-roles": {"substantial": {"implementation": {"deployment": "review-api"},
                                                "independent-review": {"deployment": "review-api"}}},
                "task-classes": {"diagnostic": {"deployment": "review-api"}},
            }}
        self.edit("routing.yaml", widen)
        self.assertEqual({
            ("ceiling-unbounded", "routing.overrides.api-host.routes.complex"),
            ("ceiling-unbounded", "routing.overrides.api-host.routes.ordinary"),
            ("ceiling-role", "routing.overrides.api-host.route-roles.substantial.implementation"),
            ("ceiling-unbounded", "routing.overrides.api-host.route-roles.substantial.implementation"),
            ("ceiling-unbounded", "routing.overrides.api-host.route-roles.substantial.independent-review"),
            ("ceiling-data-class", "routing.overrides.api-host.task-classes.diagnostic"),
            ("ceiling-role", "routing.overrides.api-host.task-classes.diagnostic"),
        }, self.codes())

    def test_narrow_overrides_within_ceiling_pass(self) -> None:
        self.edit("routing.yaml", lambda data: data.update({"overrides": {"api-host": {
            "task-classes": {"review": {"deployment": "review-api"}},
            "roles": {"diagnostic": {"deployment": "native"}},
            "routes": {"complex": {"deployment": "native"}}}}}))
        self.assertEqual(set(), self.codes())

    def test_role_overrides_cannot_cover_every_data_class_under_a_data_ceiling(self) -> None:
        self.edit("routing.yaml", lambda data: data.update({"overrides": {"api-host": {
            "roles": {"independent-review": {"deployment": "review-api"}}}}}))
        self.assertEqual({("ceiling-unbounded", "routing.overrides.api-host.roles.independent-review")},
                         self.codes())

    def test_pinned_task_classes_cannot_be_lowered(self) -> None:
        self.edit("routing.yaml", lambda data: data["task-classes"]["protected"].update({"route-class": "complex"}))
        self.assertEqual({("ceiling-task-class", "routing.task-classes.protected.route-class")}, self.codes())

    def test_closed_critical_justifications_are_enforced_at_routing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "security-critical, migration-data-loss"):
            resolve_task_route("protected", justification="feels risky", project=self.project)
        selected = resolve_task_route("protected", justification="security-critical: token handling",
                                      project=self.project)
        self.assertEqual("critical", selected["selected"]["route"])
        enforce_critical_justification("migration-data-loss", self.project)

    def test_projects_without_ceilings_keep_free_text_justification(self) -> None:
        self.edit("policy.yaml", lambda data: data.pop("ceilings"))
        self.assertEqual([], check_policy_ceilings(self.project))
        enforce_critical_justification("any documented reason", self.project)

    def test_policy_check_and_validate_commands_fail_on_widening(self) -> None:
        def run(arguments: list[str]) -> tuple[int, str]:
            parsed = build_parser().parse_args(arguments)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = parsed.func(parsed)
            return code, output.getvalue()

        code, output = run(["policy", "check", "--path", str(self.project), "--json"])
        self.assertEqual((0, True), (code, json.loads(output)["valid"]))
        self.edit("deployments.yaml", lambda data: data["deployments"]["public-api"]["capabilities"]
                  ["access-modes"].append("workspace-write"))
        code, output = run(["policy", "check", "--path", str(self.project)])
        self.assertEqual(1, code)
        self.assertIn("ceiling-exceeded", output)
        previous = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, previous)
        code, output = run(["validate", "--json"])
        self.assertEqual(1, code)
        self.assertIn("policy-ceiling", {item["code"] for item in json.loads(output)["issues"]})


if __name__ == "__main__":
    unittest.main()
