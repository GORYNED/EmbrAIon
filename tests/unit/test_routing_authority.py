from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root, read_yaml, write_yaml
from embraion.execution import execute
from embraion.project import HOST_COMPONENTS, HOST_SKILL_DIRECTORIES, init_project, install
from embraion.routing_authority import _verified_projection_files, audit_routing_authority
from embraion.runtime import classify_review_assignment, resolve_task_route, route, validate_task_routes


FIXTURE = framework_root() / "tests/fixtures/routing-consumer"
REALISTIC = framework_root() / "tests/fixtures/routing-authority-realistic"


class RoutingAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="Routing Consumer")
        shutil.copytree(FIXTURE, self.project, dirs_exist_ok=True)
        shutil.copytree(REALISTIC, self.project, dirs_exist_ok=True)

    def _write_case(self, relative: str, contents: str) -> Path:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def test_effective_routes_and_fallbacks_use_only_project_config(self) -> None:
        self.assertTrue(validate_task_routes(self.project)["valid"])
        bounded = resolve_task_route("bounded-fix", project=self.project, access="write")
        self.assertEqual("bounded-write", bounded["route"])
        self.assertEqual(2, len(bounded["candidates"]))
        self.assertEqual("candidate:0:host-fallback", bounded["fallbacks"][0]["source"])
        self.assertEqual("project-deployment", bounded["selected"]["resolution"])
        self.assertEqual("project-deployment", bounded["fallbacks"][0]["resolution"])
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
        self.assertEqual("project-deployment", critical["selected"]["resolution"])
        self.assertEqual([], critical["fallbacks"])
        with self.assertRaisesRegex(RuntimeError, "requires justification"):
            resolve_task_route("protected-decision", project=self.project)
        self.assertEqual("critical", resolve_task_route(
            "protected-decision", project=self.project,
            justification="protected decision")["route"])

        peers = resolve_task_route("cost-sensitive", project=self.project)
        self.assertEqual(3, len(peers["candidates"]))
        self.assertTrue(all(candidate["resolution"] == "project-deployment" for candidate in peers["candidates"]))
        self.assertTrue(peers["candidates"][0]["source"].endswith("group:economy-peers"))
        self.assertFalse(peers["candidates"][1]["requires-handoff"])
        self.assertTrue(peers["candidates"][2]["requires-handoff"])
        wide = resolve_task_route("cost-sensitive", project=self.project, shape="wide")
        self.assertEqual(peers["candidates"][1]["deployment"], wide["selected"]["deployment"])

    def test_task_candidate_preserves_resolution_for_defaults_and_partial_overrides(self) -> None:
        routing_path = self.project / ".embraion/routing.yaml"
        task_class = "native-assignment"
        task = {"route-class": "bounded-read", "candidates": [{"host": "codex"}]}
        for override in (None, {"effort": "medium"}, {"options": {"native-setting": True}}):
            with self.subTest(override=override):
                routing = {"overrides": {}, "task-classes": {task_class: task}}
                if override is not None:
                    routing["overrides"] = {"codex": {"routes": {"bounded-read": override}}}
                write_yaml(routing_path, routing)
                expected = route("codex", "bounded-read", "PRIVATE", role="architect",
                                 access="read-only", task_class=task_class, project=self.project)
                selected = resolve_task_route(task_class, role="architect", access="read-only",
                                              project=self.project)["selected"]
                self.assertEqual(expected["resolution"], selected["resolution"])
                self.assertEqual("project-override" if override else "host-default", selected["resolution"])
                self.assertIsNone(selected["model"])
                self.assertEqual(expected["effort"], selected["effort"])
                self.assertEqual(expected["options"], selected["options"])

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

    def test_realistic_schema_code_and_historical_prose_are_not_authority(self) -> None:
        self.assertEqual([], audit_routing_authority(self.project))
        self._write_case("tools/property-names.py", "model = request.model\nprovider: Provider\neffort = selection.effort\n")
        self._write_case("tools/comments.py", "value = 1  # model: example-basic-v1\n")
        self._write_case("docs/old-decision.md",
                         "# Old routing architecture\nThe old example-basic-v1 selector was discussed historically.\n"
                         "Fallback: alphabetical directory order\n")
        self.assertEqual([], audit_routing_authority(self.project))

    def test_concrete_identity_and_new_literals_are_authority(self) -> None:
        cases = (
            ("tools/model.py", 'model = "example-basic-v1"\n'),
            ("schemas/provider.yaml", "provider: example-provider\n"),
            ("docs/deployment.md", "deployment: native-main\n"),
            ("tools/new-model.py", 'model = "project-new-model"\n'),
            ("policy/new-provider.yaml", "provider: project-new-provider\n"),
            ("runtime/new-deployment.json", '{"deployment":"project-new-deployment"}\n'),
            ("tests/selected.py", 'selected_model = "example-main-v1"\n'),
        )
        for relative, contents in cases:
            with self.subTest(relative=relative):
                path = self._write_case(relative, contents)
                self.assertEqual(relative, audit_routing_authority(
                    self.project, paths=[path])[0]["path"])

    def test_explicit_paths_use_resolved_project_relative_names(self) -> None:
        path = self._write_case("docs/routing-choice.md", "model: example-basic-v1\n")
        alias = self.project / "docs" / ".." / "docs" / path.name
        self.assertEqual("docs/routing-choice.md", audit_routing_authority(
            self.project, paths=[alias])[0]["path"])

    def test_concrete_effort_fallback_capability_billing_and_binding(self) -> None:
        cases = (
            ("docs/effort.md", "effort: high\n"),
            ("tests/fallback.json", '{"fallback":"native-spare"}\n'),
            ("schemas/capability.yaml", 'capabilities: {"data-classes": ["PRIVATE"]}\n'),
            ("policy/billing.json", '{"billing":{"plan":"example-plan"}}\n'),
            ("policy/sku.yaml", "sku: example-review-sku\n"),
            ("runtime/binding.json", '{"selector":"example/review-v1",'
             '"credentialRef":"env:EXAMPLE_ROUTING_TOKEN"}\n'),
        )
        for relative, contents in cases:
            with self.subTest(relative=relative):
                path = self._write_case(relative, contents)
                self.assertEqual(relative, audit_routing_authority(
                    self.project, paths=[path])[0]["path"])

    def test_generated_projection_exemption_requires_verified_ownership(self) -> None:
        install("codex", self.project)
        projected = self.project / HOST_SKILL_DIRECTORIES["codex"] / "routing-configuration/SKILL.md"
        self.assertEqual([], audit_routing_authority(self.project, paths=[projected]))
        projected.write_text(projected.read_text(encoding="utf-8") +
                             "\n```yaml\nmodel: example-basic-v1\n```\n", encoding="utf-8")
        findings = audit_routing_authority(self.project, paths=[projected])
        self.assertIn(projected.relative_to(self.project).as_posix(),
                      {finding["path"] for finding in findings})

    def test_byte_identical_unowned_projection_is_exempt(self) -> None:
        install("codex", self.project)
        projected = self.project / HOST_SKILL_DIRECTORIES["codex"] / "routing-configuration/SKILL.md"
        state = self.project / ".embraion/state/projections/codex/root.json"
        state.unlink()
        self.assertEqual([], audit_routing_authority(self.project, paths=[projected]))
        projected.write_text(projected.read_text(encoding="utf-8") +
                             "\n```yaml\nmodel: example-basic-v1\n```\n", encoding="utf-8")
        findings = audit_routing_authority(self.project, paths=[projected])
        self.assertIn(projected.relative_to(self.project).as_posix(),
                      {finding["path"] for finding in findings})

    def test_invalid_projection_ownership_does_not_override_canonical_comparison(self) -> None:
        install("codex", self.project)
        projected = self.project / HOST_SKILL_DIRECTORIES["codex"] / "routing-configuration/SKILL.md"
        state = self.project / ".embraion/state/projections/codex/root.json"
        state.write_text("{invalid json", encoding="utf-8")
        self.assertEqual([], audit_routing_authority(self.project, paths=[projected]))
        projected.write_text(projected.read_text(encoding="utf-8") +
                             "\n```yaml\nmodel: example-basic-v1\n```\n", encoding="utf-8")
        findings = audit_routing_authority(self.project, paths=[projected])
        self.assertIn(projected.relative_to(self.project).as_posix(),
                      {finding["path"] for finding in findings})

    def test_ledger_hash_matching_modified_projection_does_not_exempt_it(self) -> None:
        install("codex", self.project)
        projected = self.project / HOST_SKILL_DIRECTORIES["codex"] / "routing-configuration/SKILL.md"
        projected.write_text(projected.read_text(encoding="utf-8") +
                             "\n```yaml\nmodel: example-basic-v1\n```\n", encoding="utf-8")
        state_path = self.project / ".embraion/state/projections/codex/root.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        relative = projected.relative_to(self.project).as_posix()
        state["files"][relative] = hashlib.sha256(projected.read_bytes()).hexdigest()
        state_path.write_text(json.dumps(state), encoding="utf-8")
        findings = audit_routing_authority(self.project, paths=[projected])
        self.assertIn(relative, {finding["path"] for finding in findings})

    def test_nested_symlink_cannot_claim_canonical_projection_exemption(self) -> None:
        install("codex", self.project)
        projected = self.project / HOST_SKILL_DIRECTORIES["codex"] / "routing-configuration/SKILL.md"
        relative = projected.relative_to(self.project).as_posix()
        manual = self._write_case("manual-projection.md", projected.read_text(encoding="utf-8"))
        projected.unlink()
        try:
            projected.symlink_to(manual)
        except OSError as error:
            if getattr(error, "winerror", None) != 1314:
                raise
            self.skipTest("Windows symlink privilege unavailable")
        self.assertNotIn(relative, _verified_projection_files(self.project))

    def test_scoped_claude_profile_matches_canonical_bytes_without_ledger(self) -> None:
        write_yaml(self.project / ".embraion/claude-native.yaml", {
            "bindings": {"worker": "worker"},
            "assignments": [{"role": "worker", "route-class": "complex",
                             "data-class": "PRIVATE", "access": "write"}],
        })
        routing_path = self.project / ".embraion/routing.yaml"
        routing = read_yaml(routing_path)
        routing["overrides"]["claude-code"] = {
            "routes": {"complex": {"model": "claude-fable-5-1", "effort": "high"}},
        }
        write_yaml(routing_path, routing)
        install("claude-code", self.project, components=["agents", "skills", "scoped-agents"])
        scoped = next((self.project / ".claude/agents").glob("embraion-*.md"))
        metadata = self.project / ".claude/embraion-native.json"
        (self.project / ".embraion/state/projections/claude-code/root.json").unlink()
        self.assertEqual([], audit_routing_authority(self.project, paths=[scoped, metadata]))

        scoped.write_text(scoped.read_text(encoding="utf-8") +
                          "\n```yaml\nmodel: example-basic-v1\n```\n", encoding="utf-8")
        findings = audit_routing_authority(self.project, paths=[scoped, metadata])
        self.assertEqual({scoped.relative_to(self.project).as_posix()},
                         {finding["path"] for finding in findings})

    def test_generated_evidence_is_exempt_only_inside_canonical_state(self) -> None:
        self._write_case(".embraion/state/reports/route.json", '{"model":"example-basic-v1"}\n')
        manual = self._write_case("reports/route.json", '{"model":"example-basic-v1"}\n')
        self.assertEqual(["reports/route.json"], [finding["path"] for finding in
                         audit_routing_authority(self.project, paths=[manual])])
        self.assertEqual([], audit_routing_authority(
            self.project, paths=[self.project / ".embraion/state/reports/route.json"]))

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
