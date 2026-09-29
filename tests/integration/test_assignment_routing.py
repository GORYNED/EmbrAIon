from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import embraion
import jsonschema
import yaml

from embraion.common import framework_root, read_json, read_yaml, write_yaml
from embraion.project import init_project, install
from embraion.runtime import resolve_task_route, route


class AssignmentRoutingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        init_project(self.project, name="AssignmentIntegrationFixture")
        self.root = framework_root()
        self.schema = read_json(self.root / "schemas/native-plan.schema.json")
        self.environment = os.environ.copy()
        self.environment.update({
            "PYTHONPATH": str(Path(embraion.__file__).resolve().parent.parent),
            "EMBRAION_HOME": str(self.root), "EMBRAION_DISABLE_VERSION_RESOLUTION": "1",
        })
        for key in ("EMBRAION_VERSION_RESOLVED", "EMBRAION_RESOLVED_VERSION", "EMBRAION_RESOLVED_PROJECT"):
            self.environment.pop(key, None)

    def configure(self, host="codex", effort=True):
        selection = {"model": "fixture-assignment-selector"}
        if effort:
            selection["effort"] = "medium"
        write_yaml(self.project / ".embraion/routing.yaml", {
            "overrides": {host: {"routes": {"substantial": selection}}},
            "task-classes": {"fixture-assignment": {"route-class": "substantial", "role": "worker",
                "data-class": "PRIVATE", "candidates": [{"host": host}]}},
        })

    def cli(self, *arguments, expected_exit=0):
        result = subprocess.run([sys.executable, "-m", "embraion.cli", *arguments], cwd=self.project,
                                env=self.environment, capture_output=True, text=True, check=False)
        self.assertEqual(expected_exit, result.returncode, result.stdout + result.stderr)
        record = json.loads(result.stdout)
        if "native-plan" in record:
            jsonschema.validate(record["native-plan"], self.schema)
            self.assertFalse(record["native-plan"]["executed"])
        return record

    def test_cli_task_class_dispatch_applies_selected_fields_without_execution(self):
        self.configure()
        expected = resolve_task_route("fixture-assignment", access="inspect", project=self.project)
        record = self.cli("dispatch", "--task", "Bounded fixture task", "--task-class", "fixture-assignment",
                          "--native-surface", "codex-native")
        self.assertEqual("planned", record["state"])
        self.assertEqual("prepared", record["native-plan"]["status"])
        selected = expected["selected"]
        self.assertEqual(selected["resolution"], record["resolution"])
        self.assertEqual(selected["model"], record["native-plan"]["arguments"]["model"])
        self.assertEqual(selected["effort"], record["native-plan"]["arguments"]["reasoning_effort"])
        self.assertEqual(expected["role"], record["role"])
        self.assertEqual(expected["data"], record["data-class"])
        saved = read_json(self.project / ".embraion/state/dispatch" / (record["dispatch-id"] + ".json"))
        self.assertEqual(record, saved)

    def test_cli_capability_limitation_returns_one_and_handoff_stays_unexecuted(self):
        self.configure("copilot")
        record = self.cli("dispatch", "--task", "Blocked fixture", "--task-class", "fixture-assignment",
                          "--native-surface", "copilot-vscode", expected_exit=1)
        self.assertEqual("blocked", record["state"])
        self.assertEqual({}, record["native-plan"]["arguments"])
        self.assertEqual({}, record["native-plan"]["definition-overrides"])
        conditional = self.cli("dispatch", "--task", "Verified conditional field", "--task-class", "fixture-assignment",
                               "--native-surface", "copilot-vscode", "--verified-native-field", "reasoning-effort")
        selected = resolve_task_route("fixture-assignment", access="inspect", project=self.project)["selected"]
        self.assertEqual(selected["effort"], conditional["native-plan"]["definition-overrides"]["reasoning-effort"])
        self.configure("claude-code")
        handoff = self.cli("dispatch", "--task", "Scoped effort definition", "--task-class", "fixture-assignment",
                           "--native-surface", "claude-agent")
        self.assertEqual("handoff-required", handoff["state"])
        self.assertNotIn("effort", handoff["native-plan"]["arguments"])
        self.assertIn("effort", handoff["native-plan"]["definition-overrides"])

    def test_all_generated_hosts_share_core_contract_and_only_their_native_adapter(self):
        hosts = ("codex", "copilot", "claude-code", "portable")
        native_headers = {host: (self.root / f"adapters/{host}/orchestration.md").read_text(encoding="utf-8").splitlines()[0]
                          for host in hosts if host != "portable"}
        host_metadata = read_yaml(self.root / "adapters/harness-capabilities.yaml")["hosts"]
        for host in hosts:
            with self.subTest(host=host), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                init_project(project, name="ProjectionFixture")
                write_yaml(project / ".embraion/routing.yaml", {"overrides": {host: {"routes": {
                    "substantial": {"model": "fixture-projected-selector", "effort": "medium"}}}}})
                selected = route(host, "substantial", "PRIVATE", project=project)
                install(host, project)
                if host == "portable":
                    skills = project / "embraion/skills"
                    generated = list((project / "embraion").rglob("*"))
                    profiles = []
                else:
                    skills = project / host_metadata[host]["skills"]
                    profiles = list((project / host_metadata[host]["agents"]).glob("*"))
                    generated = list(skills.rglob("*")) + profiles
                    if host == "codex":
                        generated.append(project / ".codex/config.toml")
                skill = (skills / "orchestration/SKILL.md").read_text(encoding="utf-8")
                self.assertIn("## Assignment routing contract", skill)
                self.assertIn("A prepared plan or successful resolver command is not execution evidence", skill)
                for native_host, header in native_headers.items():
                    if host == native_host:
                        self.assertIn(header, skill)
                    else:
                        self.assertNotIn(header, skill)
                if host == "portable":
                    self.assertNotIn("## Native assignment settings", skill)
                    self.assertIn("they provide no runtime host or delegation mechanism", skill)
                for profile in profiles:
                    if not profile.is_file():
                        continue
                    text = profile.read_text(encoding="utf-8")
                    self.assertNotIn(selected["model"], text)
                    if profile.suffix == ".toml":
                        data = tomllib.loads(text)
                    else:
                        data = yaml.safe_load(text.split("---", 2)[1])
                    for field in ("model", "models", "effort", "reasoningEffort", "reasoning-effort", "model_reasoning_effort"):
                        self.assertNotIn(field, data)
                before = {path.relative_to(project): path.read_bytes() for path in generated if path.is_file()}
                install(host, project)
                for relative, contents in before.items():
                    self.assertEqual(contents, (project / relative).read_bytes(), str(relative))


if __name__ == "__main__":
    unittest.main()
