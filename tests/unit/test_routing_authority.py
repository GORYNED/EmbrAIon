from __future__ import annotations

import shutil
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root, read_yaml, write_yaml
from embraion.execution import execute
from embraion.project import HOST_COMPONENTS, HOST_SKILL_DIRECTORIES, init_project, install
from embraion.routing_authority import audit_routing_authority
from embraion.runtime import classify_review_assignment, resolve_task_route, route, validate_task_routes


FIXTURE = framework_root() / "tests/fixtures/routing-consumer"


class RoutingAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="Routing Consumer")
        shutil.copytree(FIXTURE, self.project, dirs_exist_ok=True)

    def test_effective_routes_and_fallbacks_use_only_project_config(self) -> None:
        self.assertTrue(validate_task_routes(self.project)["valid"])
        bounded = resolve_task_route("bounded-fix", project=self.project, access="write")
        self.assertEqual("bounded-write", bounded["route"])
        self.assertEqual(2, len(bounded["candidates"]))
        self.assertEqual("candidate:0:host-fallback", bounded["fallbacks"][0]["source"])
        self.assertNotEqual("complex", bounded["fallbacks"][0]["route"])

        routine = resolve_task_route("routine-review", project=self.project)
        difficult = resolve_task_route("difficult-review", project=self.project)
        self.assertEqual("substantial", routine["route"])
        self.assertEqual("complex", difficult["route"])
        self.assertNotEqual(routine["selected"]["deployment"], difficult["selected"]["deployment"])

        # A re-review is independently classified from its bounded delta.
        narrow = resolve_task_route("narrow-re-review", project=self.project)
        contract = resolve_task_route("contract-re-review", project=self.project)
        self.assertEqual("complex", classify_review_assignment(difficult=True))
        self.assertEqual("substantial", classify_review_assignment(
            delta_semantics=["targeted-fix"], previous_route="complex"))
        self.assertEqual("complex", classify_review_assignment(
            delta_semantics=["concurrency"], previous_route="complex"))
        self.assertEqual("substantial", narrow["route"])
        self.assertEqual("complex", contract["route"])

        cross = resolve_task_route("cross-host-review", project=self.project)
        self.assertTrue(cross["fallbacks"][0]["requires-handoff"])
        self.assertEqual("substantial", cross["fallbacks"][0]["route"])
        self.assertEqual("initial", cross["selection-reason"])
        with self.assertRaisesRegex(RuntimeError, "requires justification"):
            resolve_task_route("cross-host-review", project=self.project, escalation="critical")
        critical = resolve_task_route("cross-host-review", project=self.project,
                                      escalation="critical", justification="protected decision")
        self.assertEqual("critical", critical["selected"]["route"])
        self.assertEqual([], critical["fallbacks"])
        with self.assertRaisesRegex(RuntimeError, "requires justification"):
            resolve_task_route("protected-decision", project=self.project)
        self.assertEqual("critical", resolve_task_route(
            "protected-decision", project=self.project,
            justification="protected decision")["route"])

        peers = resolve_task_route("cost-sensitive", project=self.project)
        self.assertEqual(3, len(peers["candidates"]))
        self.assertTrue(peers["candidates"][0]["source"].endswith("group:economy-peers"))
        self.assertFalse(peers["candidates"][1]["requires-handoff"])
        self.assertTrue(peers["candidates"][2]["requires-handoff"])
        wide = resolve_task_route("cost-sensitive", project=self.project, shape="wide")
        self.assertEqual(peers["candidates"][1]["deployment"], wide["selected"]["deployment"])

    def test_role_route_task_precedence_and_fail_closed(self) -> None:
        reviewed = route("alpha-host", "complex", "PRIVATE", role="reviewer",
                         task_class="difficult-review", project=self.project)
        self.assertEqual("project-deployment", reviewed["resolution"])
        routing_path = self.project / ".embraion/routing.yaml"
        routing = read_yaml(routing_path)
        routing["task-classes"]["bounded-fix"]["candidates"].append(
            {"host": "alpha-host", "deployment": "native-basic"})
        write_yaml(routing_path, routing)
        with self.assertRaisesRegex(RuntimeError, "Duplicate effective route"):
            validate_task_routes(self.project)

    def test_authority_lint_covers_manual_consumer_files(self) -> None:
        self.assertEqual([], audit_routing_authority(self.project))
        mutations = (
            ("tools/route.py", "model: example-basic-v1\n"),
            ("policy/current.json", '{"billing":{"plan":"example-plan"}}\n'),
            ("tests/routing.md", "api-review\n"),
            ("docs/routing.md", "example-review-sku\n"),
            ("docs/requests.md", 'capabilities: {"data-classes": ["PRIVATE"]}\n'),
            ("runtime/current.json", '{"provider":"example-provider"}\n'),
            ("runtime/current.json", '{"effort":"high"}\n'),
            ("runtime/current.json", '{"fallback":"native-spare"}\n'),
            ("runtime/current.json", '{"selector":"example/review-v1"}\n'),
            ("runtime/current.json", '{"credentialRef":"env:EXAMPLE_ROUTING_TOKEN"}\n'),
        )
        for relative, duplicate in mutations:
            with self.subTest(relative=relative, duplicate=duplicate):
                path = self.project / relative
                original = path.read_text(encoding="utf-8")
                path.write_text(original + duplicate, encoding="utf-8")
                findings = audit_routing_authority(self.project)
                self.assertIn(relative, {finding["path"] for finding in findings})
                path.write_text(original, encoding="utf-8")

    def test_execution_uses_task_route_without_binding_aliases_and_hands_off(self) -> None:
        class FailingAdapter:
            def preflight(self, request, deployment, binding):
                pass

            def execute(self, request, deployment, binding, credential):
                return {"status": "failed", "failure": "rate-limited",
                        "terminationConfirmed": True, "mutationConfirmed": True,
                        "observedModel": None, "usage": None}

        class Resolver:
            def resolve(self, reference, deployment, adapter):
                return "test-only"

        request = {
            "schemaVersion": 1, "runId": "run", "workItemId": "item", "taskId": "task",
            "taskClass": "cross-host-review", "role": "reviewer",
            "routeClass": "substantial", "host": "beta-host", "dataClass": "PRIVATE",
            "sourceIds": ["project-source"], "trustLevel": "verified",
            "access": "read-only", "ownedPaths": [], "contextRef": "context",
            "timeoutSeconds": 30, "maxAttempts": 2,
            "candidates": [{"deployment": "api-review"}, {"deployment": "native-main"}],
            "preserveCandidateOrder": True,
        }
        result = execute(request, project=self.project, adapters={"example-adapter": FailingAdapter()},
                         resolver=Resolver())
        self.assertEqual("handoff-required", result["status"])
        self.assertEqual("host-boundary", result["handoff"]["reason"])
        self.assertEqual(1, len(result["attempts"]))
        self.assertEqual("rate-limited", result["attempts"][0]["failure"])
        request["candidates"] = [{"deployment": "native-critical"}]
        with self.assertRaisesRegex(RuntimeError, "do not follow"):
            execute(request, project=self.project, adapters={"example-adapter": FailingAdapter()},
                    resolver=Resolver())

    def test_all_host_projections_inherit_natural_language_rule(self) -> None:
        source = (framework_root() / "core/skills/routing-configuration/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("only manually maintained source of truth", source)
        self.assertIn("any Product Owner request", source)
        self.assertIn("execution-binding facts", source)
        self.assertIn("Generated host projections", source)
        requests = (FIXTURE / "docs/requests.md").read_text(encoding="utf-8")
        for phrase in ("Configure routing", "Change models", "cheaper model", "effort and fallback",
                       "deployment capabilities", "pricing/SKU", "execution bindings"):
            self.assertIn(phrase, requests)
        for host in ("codex", "copilot", "claude-code"):
            with self.subTest(host=host):
                self.assertIn("skills", HOST_COMPONENTS[host])
                install(host, self.project)
                projected = self.project / HOST_SKILL_DIRECTORIES[host] / "routing-configuration/SKILL.md"
                self.assertEqual(source, projected.read_text(encoding="utf-8"))
        self.assertEqual([], audit_routing_authority(self.project))
        for host, components in HOST_COMPONENTS.items():
            if host != "portable":
                self.assertIn("skills", components)
                self.assertIn(host, HOST_SKILL_DIRECTORIES)

    def test_cli_validation_and_authority_audit(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(framework_root() / "tools/cli")
        for arguments in (("--validate",), ("--audit-authority",),
                          ("--task-class", "routine-review")):
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, "-m", "embraion.cli", "route", *arguments],
                                        cwd=self.project, env=environment, capture_output=True,
                                        text=True, check=True)
                payload = json.loads(result.stdout)
                self.assertTrue(payload)
