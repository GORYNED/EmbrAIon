from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema

from embraion.common import framework_root, read_json, write_yaml
from embraion.delegation import prepare_native_assignment
from embraion.project import init_project
from embraion.runtime import create_dispatch, resolve_task_route, route


class NativeAssignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="NativeAssignmentFixture")
        self.schema = read_json(framework_root() / "schemas/native-plan.schema.json")

    def selected(self, host="codex", shape="full"):
        fields = {"model": "fixture-native-selector", "effort": "medium"}
        if shape == "model-only":
            fields.pop("effort")
        elif shape == "effort-only":
            fields.pop("model")
        write_yaml(self.project / ".embraion/routing.yaml", {
            "overrides": {} if shape == "host-default" else {host: {"routes": {"substantial": fields}}},
            "task-classes": {"fixture-assignment": {"route-class": "substantial", "role": "worker",
                "data-class": "PRIVATE", "candidates": [{"host": host}]}},
        })
        return route(host, "substantial", "PRIVATE", role="worker", access="read-only", project=self.project)

    def plan(self, selected, surface, **kwargs):
        plan = prepare_native_assignment(selected, surface, role="worker", **kwargs)
        jsonschema.validate(plan, self.schema)
        self.assertFalse(plan["executed"])
        return plan

    def blocked(self, plan):
        self.assertEqual("capability-limitation", plan["status"])
        self.assertEqual({}, plan["arguments"])
        self.assertEqual({}, plan["definition-overrides"])
        self.assertTrue(plan["limitations"])

    def test_full_partial_and_default_native_matrix(self):
        surfaces = {"codex-native": "codex", "copilot-cli": "copilot", "copilot-vscode": "copilot",
                    "copilot-cloud": "copilot", "claude-agent": "claude-code", "portable": "portable"}
        for surface, host in surfaces.items():
            for shape in ("full", "model-only", "effort-only", "host-default"):
                with self.subTest(surface=surface, shape=shape):
                    selected = self.selected(host, shape)
                    plan = self.plan(selected, surface)
                    if surface in {"portable", "copilot-cloud"} or (
                            surface == "copilot-vscode" and selected["effort"] is not None):
                        self.blocked(plan)
                        continue
                    status = "handoff-required" if surface == "claude-agent" and selected["effort"] else "prepared"
                    self.assertEqual(status, plan["status"])
                    args, definitions = {}, {}
                    if surface == "codex-native":
                        args["agent_type"] = "worker"
                        if selected["model"] is not None:
                            args["model"] = selected["model"]
                        if selected["effort"] is not None:
                            args["reasoning_effort"] = selected["effort"]
                        if shape != "host-default":
                            args["fork_turns"] = "none"
                    elif surface == "copilot-cli":
                        if selected["model"] is not None:
                            definitions.update(model=selected["model"], modelPolicy="required")
                        if selected["effort"] is not None:
                            definitions["reasoningEffort"] = selected["effort"]
                    else:
                        if selected["model"] is not None:
                            args["model"] = selected["model"]
                        if selected["effort"] is not None:
                            definitions["effort"] = selected["effort"]
                    self.assertEqual(args, plan["arguments"])
                    self.assertEqual(definitions, plan["definition-overrides"])

    def test_vscode_effort_requires_the_exact_verified_native_field(self):
        selected = self.selected("copilot")
        self.blocked(self.plan(selected, "copilot-vscode", verified_native_fields=["reasoningEffort"]))
        plan = self.plan(selected, "copilot-vscode", verified_native_fields=["reasoning-effort"])
        self.assertEqual("prepared", plan["status"])
        self.assertEqual({"model": selected["model"]}, plan["arguments"])
        self.assertEqual({"reasoning-effort": selected["effort"]}, plan["definition-overrides"])
        self.assertTrue(any("installed-version/schema evidence" in item for item in plan["requirements"]))

    def test_unsupported_options_never_leave_partially_dispatchable_settings(self):
        for surface, host in (("codex-native", "codex"), ("copilot-cli", "copilot"),
                              ("copilot-vscode", "copilot"), ("claude-agent", "claude-code")):
            with self.subTest(surface=surface):
                selected = self.selected(host)
                selected["options"] = {"unverified-native-option": True}
                self.blocked(self.plan(selected, surface))

    def test_supported_native_options_apply_without_weakening_project_routing(self):
        for surface, host, option, value, location in (
            ("codex-native", "codex", "fork_turns", "3", "arguments"),
            ("copilot-cli", "copilot", "modelPolicy", "required", "definition-overrides"),
        ):
            with self.subTest(surface=surface):
                selected = self.selected(host)
                selected["options"] = {option: value}
                plan = self.plan(selected, surface)
                self.assertEqual("prepared", plan["status"])
                self.assertEqual(value, plan[location][option])
                selected["options"] = {option: "all" if host == "codex" else "preferred"}
                self.blocked(self.plan(selected, surface))

    def test_missing_unknown_and_malformed_resolution_fail_closed(self):
        for resolution in (None, "unknown", "", [], {}):
            with self.subTest(resolution=resolution):
                selected = self.selected()
                selected["resolution"] = resolution
                self.blocked(self.plan(selected, "codex-native"))
        selected = self.selected()
        del selected["resolution"]
        self.blocked(self.plan(selected, "codex-native"))

    def test_wrong_host_and_invalid_explicit_fields_cannot_spawn(self):
        selected = self.selected("copilot")
        plan = self.plan(selected, "codex-native")
        self.assertEqual("handoff-required", plan["status"])
        self.assertEqual({}, plan["arguments"])
        self.assertEqual({}, plan["definition-overrides"])
        for field in ("model", "effort"):
            for invalid in ("", " ", [], 7):
                with self.subTest(field=field, invalid=invalid):
                    selected = self.selected()
                    selected[field] = invalid
                    self.blocked(self.plan(selected, "codex-native"))
        selected = self.selected("claude-code")
        selected["effort"] = "unsupported-effort"
        self.blocked(self.plan(selected, "claude-agent"))
        selected = self.selected(shape="host-default")
        selected["effort"] = "medium"
        self.blocked(self.plan(selected, "codex-native"))
        selected = self.selected()
        selected.update(model=None, effort=None)
        self.blocked(self.plan(selected, "codex-native"))
        self.blocked(self.plan(self.selected(), "unknown-surface"))

    def test_reuse_requires_verified_matching_effective_settings(self):
        selected = self.selected()
        existing = {"effective-settings-verified": True, "surface": "codex-native", "role": "worker",
                    "model": selected["model"], "effort": selected["effort"], "options": {}}
        self.assertEqual("verified-existing-agent", self.plan(selected, "codex-native", existing=existing)["reuse"])
        for field, value in (("effective-settings-verified", False), ("surface", "copilot-cli"),
                             ("role", "reviewer"), ("model", None), ("effort", None),
                             ("options", {"unknown-setting": True})):
            with self.subTest(field=field):
                incompatible = {**existing, field: value}
                self.assertEqual("fresh-assignment", self.plan(selected, "codex-native", existing=incompatible)["reuse"])
        self.assertEqual("fresh-assignment", self.plan(selected, "codex-native", existing={"role": "worker"})["reuse"])
        default = self.selected(shape="host-default")
        self.assertEqual("fresh-assignment", self.plan(default, "codex-native", existing=existing)["reuse"])
        current = {**existing, "resolution": "host-default", "current-host-defaults-verified": True}
        self.assertEqual("verified-existing-agent", self.plan(default, "codex-native", existing=current)["reuse"])
        current.pop("current-host-defaults-verified")
        self.assertEqual("fresh-assignment", self.plan(default, "codex-native", existing=current)["reuse"])

    def test_task_class_dispatch_preserves_selected_candidate_and_minimum_data(self):
        self.selected()
        expected = resolve_task_route("fixture-assignment", access="inspect", project=self.project)
        record = create_dispatch("Bounded task", None, None, None, None, "inspect", [],
                                 task_class="fixture-assignment", native_surface="codex-native", project=self.project)
        for field in ("resolution", "model", "effort", "options", "host"):
            self.assertEqual(expected["selected"][field], record[field])
        self.assertEqual(expected["role"], record["role"])
        self.assertEqual(expected["data"], record["data-class"])
        jsonschema.validate(record["native-plan"], self.schema)
        self.assertFalse(record["native-plan"]["executed"])
        before = set((self.project / ".embraion/state/dispatch").glob("*.json"))
        with self.assertRaisesRegex(RuntimeError, "minimum"):
            create_dispatch("Invalid task", None, None, None, "PUBLIC", "inspect", [],
                            task_class="fixture-assignment", native_surface="codex-native", project=self.project)
        self.assertEqual(before, set((self.project / ".embraion/state/dispatch").glob("*.json")))

    def test_resolution_errors_and_write_guards_preserve_legacy_dispatch(self):
        self.selected()
        for access in ("write", "workspace-write"):
            with self.subTest(access=access):
                with self.assertRaisesRegex(RuntimeError, "owned path"):
                    create_dispatch("Write", "worker", "codex", "substantial", "PRIVATE", access, [], project=self.project)
                with patch("embraion.runtime._current_branch", return_value="main"):
                    with self.assertRaisesRegex(RuntimeError, "stable"):
                        create_dispatch("Write", "worker", "codex", "substantial", "PRIVATE", access,
                                        ["owned/**"], project=self.project)
                with patch("embraion.runtime._current_branch", return_value="feature"):
                    record = create_dispatch("Write", "worker", "codex", "substantial", "PRIVATE", access,
                                             ["owned/**"], project=self.project)
                    self.assertEqual(["owned/**"], record["owned-paths"])
                    self.assertNotIn("native-plan", record)
                    self.assertEqual("planned", record["state"])
        before = set((self.project / ".embraion/state/dispatch").glob("*.json"))
        with self.assertRaises(RuntimeError):
            create_dispatch("Unknown", "worker", "codex", "invalid-route", "PRIVATE", "inspect", [],
                            native_surface="codex-native", project=self.project)
        with self.assertRaises(RuntimeError):
            create_dispatch("Unknown", None, None, None, None, "inspect", [], task_class="missing", project=self.project)
        self.assertEqual(before, set((self.project / ".embraion/state/dispatch").glob("*.json")))

    def test_task_class_cannot_mix_legacy_selectors_or_unknown_classification(self):
        self.selected()
        for host, route_class in (("codex", None), (None, "substantial")):
            with self.subTest(host=host, route=route_class):
                with self.assertRaisesRegex(RuntimeError, "cannot be combined"):
                    create_dispatch("Mixed selectors", None, host, route_class, None, "inspect", [],
                                    task_class="fixture-assignment", project=self.project)
        with self.assertRaisesRegex(RuntimeError, "Unknown data class"):
            create_dispatch("Unknown classification", "worker", "codex", "substantial", "UNKNOWN", "inspect", [],
                            native_surface="codex-native", project=self.project)
        self.assertEqual([], list((self.project / ".embraion/state/dispatch").glob("*.json")))

    def test_deployment_role_and_access_capability_denial_records_no_dispatch(self):
        for capabilities in ({"roles": ["reviewer"]}, {"access-modes": ["workspace-write"]}):
            with self.subTest(capabilities=capabilities):
                write_yaml(self.project / ".embraion/deployments.yaml", {"providers": {}, "deployments": {"fixture": {
                    "host": "codex", "model": "fixture-restricted-selector", "capabilities": capabilities}}})
                write_yaml(self.project / ".embraion/routing.yaml", {"overrides": {"codex": {"routes": {
                    "substantial": {"deployment": "fixture"}}}}})
                with self.assertRaisesRegex(RuntimeError, "does not allow"):
                    create_dispatch("Restricted task", "worker", "codex", "substantial", "PRIVATE", "inspect", [],
                                    native_surface="codex-native", project=self.project)
                self.assertEqual([], list((self.project / ".embraion/state/dispatch").glob("*.json")))

    def test_task_profile_without_role_checks_default_worker_eligibility(self):
        write_yaml(self.project / ".embraion/deployments.yaml", {"providers": {}, "deployments": {"fixture": {
            "host": "codex", "model": "fixture-review-selector", "capabilities": {"roles": ["reviewer"]}}}})
        write_yaml(self.project / ".embraion/routing.yaml", {"overrides": {}, "task-classes": {"fixture-assignment": {
            "route-class": "substantial", "data-class": "PRIVATE",
            "candidates": [{"host": "codex", "deployment": "fixture"}]}}})
        with self.assertRaisesRegex(RuntimeError, "worker"):
            create_dispatch("Default role eligibility", None, None, None, None, "inspect", [],
                            task_class="fixture-assignment", native_surface="codex-native", project=self.project)
        self.assertEqual([], list((self.project / ".embraion/state/dispatch").glob("*.json")))

    def test_deployment_privacy_capability_denial_records_no_dispatch(self):
        write_yaml(self.project / ".embraion/deployments.yaml", {"providers": {}, "deployments": {"fixture": {
            "host": "codex", "model": "fixture-public-selector", "capabilities": {"data-classes": ["PUBLIC"]}}}})
        write_yaml(self.project / ".embraion/routing.yaml", {"overrides": {"codex": {"routes": {
            "substantial": {"deployment": "fixture"}}}}})
        with self.assertRaisesRegex(RuntimeError, "does not allow data class"):
            create_dispatch("Private task", "worker", "codex", "substantial", "PRIVATE", "inspect", [],
                            native_surface="codex-native", project=self.project)
        self.assertEqual([], list((self.project / ".embraion/state/dispatch").glob("*.json")))


if __name__ == "__main__":
    unittest.main()
