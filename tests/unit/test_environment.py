from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from embraion.common import run, write_yaml
from embraion.environment import child_environment
from embraion.project_validation import run_validation_profile


class ChildEnvironmentTests(unittest.TestCase):
    def test_runtime_state_is_private_to_its_interpreter(self) -> None:
        parent = {
            "EMBRAION_VERSION_RESOLVED": "1",
            "EMBRAION_RESOLVED_VERSION": "0.16.0",
            "EMBRAION_RESOLVED_PROJECT": "/project/.embraion/project.yaml",
            "EMBRAION_HOME": "/cache/share/embraion",
            "EMBRAION_CACHE_HOME": "/cache",
            "PYTHONPATH": "/source/tools/cli",
            "PROJECT_SETTING": "keep",
        }
        original = parent.copy()
        self.assertEqual({key: parent[key] for key in (
            "EMBRAION_CACHE_HOME", "PYTHONPATH", "PROJECT_SETTING"
        )}, child_environment(parent))
        self.assertEqual(original, parent)

    def test_explicit_development_overrides_survive(self) -> None:
        parent = {"EMBRAION_HOME": "/checkout", "EMBRAION_DISABLE_VERSION_RESOLUTION": "1"}
        self.assertEqual(parent, child_environment(parent))

    def test_validation_and_common_children_do_not_inherit_resolver_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            script = project / "probe.py"
            script.write_text(
                "import json,os\n"
                "names = ['EMBRAION_HOME', 'EMBRAION_VERSION_RESOLVED', "
                "'EMBRAION_RESOLVED_VERSION', 'EMBRAION_RESOLVED_PROJECT']\n"
                "print(json.dumps({name: os.getenv(name) for name in names}))\n",
                encoding="utf-8",
            )
            write_yaml(project / ".embraion/validation.yaml", {
                "profiles": {"fast": [f'"{sys.executable}" "{script}"']},
            })
            with patch.dict(os.environ, {
                "EMBRAION_VERSION_RESOLVED": "1",
                "EMBRAION_RESOLVED_VERSION": "0.16.0",
                "EMBRAION_RESOLVED_PROJECT": str(project / ".embraion/project.yaml"),
                "EMBRAION_HOME": str(project / "pinned"),
            }):
                generic = run([sys.executable, str(script)], cwd=project)
                profile = run_validation_profile("fast", project=project)
                self.assertEqual("1", os.environ["EMBRAION_VERSION_RESOLVED"])
            self.assertEqual("passed", profile["status"])
            for output in (generic.stdout, profile["commands"][0]["stdout"]):
                self.assertTrue(all(value is None for value in json.loads(output).values()))


if __name__ == "__main__":
    unittest.main()
