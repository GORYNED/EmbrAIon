"""CLI execution through a one-shot loopback fixture and native host boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


class MixedExecutionIntegrationTests(unittest.TestCase):
    def test_cli_external_fallback_and_native_handoff(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "mixed-route-host.py"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            folder = project / ".embraion"
            folder.mkdir()
            definitions = {name: {
                "host": "native-host" if name == "native" else "api-host", "model": name,
                "capabilities": {"data-classes": ["PRIVATE"], "access-modes": ["read-only"],
                                 "roles": ["worker"], "task-classes": ["ordinary"]},
            } for name in ("first", "second", "native")}
            bindings = {name: {
                "adapter": "litellm-loopback", "selector": "example/" + name,
                "expectedProvider": "example", "expectedResponseModels": [name],
                "contextBoundary": "Context/v1", "sourceIds": ["project-source"], "trustLevels": ["verified"],
            } for name in ("first", "second")}
            (folder / "deployments.yaml").write_text(yaml.safe_dump({
                "providers": {}, "deployments": definitions}), encoding="utf-8")
            (folder / "execution.yaml").write_text(yaml.safe_dump({
                "schemaVersion": 1, "bindings": bindings}), encoding="utf-8")
            environment = {**os.environ, "EMBRAION_TEST_MODE": "1",
                           "EMBRAION_LITELLM_TEST_SERVER_SCRIPT": str(fixture),
                           "EMBRAION_DISABLE_VERSION_RESOLUTION": "1"}
            for candidates, status in ((["second", "native"], "completed"),
                                       (["first", "native"], "handoff-required"),
                                       (["first", "second"], "completed"),
                                       (["native"], "handoff-required")):
                with self.subTest(candidates=candidates):
                    inputs = {}
                    for name in candidates:
                        if name == "native":
                            continue
                        envelope = {"schemaVersion": 1, "boundary": "Context/v1", "context": [],
                                    "workItem": {"workItemId": "work", "deploymentId": name, "model": name,
                                                 "role": "worker", "sourceIds": ["project-source"],
                                                 "access": "read-only", "dataClass": "PRIVATE"}}
                        inputs[name] = [{"role": "user", "content": [
                            {"type": "input_text", "text": json.dumps(envelope)}]}]
                    request = {"schemaVersion": 1, "runId": "run", "workItemId": "work", "taskId": "task",
                               "role": "worker", "routeClass": "ordinary", "host": "api-host", "dataClass": "PRIVATE",
                               "sourceIds": ["project-source"], "trustLevel": "verified", "access": "read-only",
                               "ownedPaths": [], "contextRef": "context", "timeoutSeconds": 5, "maxAttempts": 3,
                               "preserveCandidateOrder": True,
                               "candidates": [{"deployment": name} for name in candidates],
                               "payload": {"inputsByDeployment": inputs}}
                    process = subprocess.run([sys.executable, "-m", "embraion.cli", "execute"],
                                             cwd=project, env=environment, input=json.dumps(request),
                                             text=True, capture_output=True, timeout=30)
                    self.assertEqual(0, process.returncode, process.stderr)
                    result = json.loads(process.stdout)
                    self.assertEqual(status, result["status"], result)
                    self.assertEqual([name for name in candidates if name != "native"][:len(result["attempts"])],
                                     [item["deployment"] for item in result["attempts"]])
                    if status == "handoff-required":
                        self.assertEqual("native", result["handoff"]["deployment"])


if __name__ == "__main__":
    unittest.main()
