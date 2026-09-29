from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.bootstrap import apply_bootstrap, plan_bootstrap
from embraion.common import framework_root, write_yaml
from embraion.project import init_project
from embraion.project_validation import run_validation_profile


class BootstrapIntegrationTests(unittest.TestCase):
    def run_cli(self, *arguments, cwd):
        environment = dict(os.environ, EMBRAION_DISABLE_VERSION_RESOLUTION="1")
        return subprocess.run([sys.executable, "-m", "embraion.cli", *arguments], cwd=cwd, env=environment, text=True, capture_output=True)

    def test_cli_plan_apply_and_reapply_with_explicit_state_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_project(root)
            (root / "ARCHITECTURE.md").write_text("# Architecture\nA small command line library.\n", encoding="utf-8")
            output = root / ".embraion/state/bootstrap-plan.json"
            result = self.run_cli("bootstrap", "plan", "--output", str(output), cwd=root)
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(plan["requires-review"])
            result = self.run_cli("bootstrap", "apply", "--plan", str(output), cwd=root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(json.loads(result.stdout)["validation-executed"])
            result = self.run_cli("bootstrap", "apply", "--plan", str(output), cwd=root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Stale", result.stderr)

    def test_self_host_plan_preserves_project_contract(self):
        root = framework_root()
        before = {p: p.read_bytes() for p in (root / ".embraion").glob("*.yaml")}
        plan = plan_bootstrap(root)
        self.assertEqual([], plan["changes"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_empty_profile_remains_skipped_and_real_profile_can_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_project(root)
            apply_bootstrap(root, plan_bootstrap(root))
            skipped = run_validation_profile("fast", project=root)
            self.assertEqual("skipped", skipped["status"])
            # Explicitly reviewed source commands can be exercised separately;
            # the helper never claims their execution as part of apply.
            write_yaml(root / ".embraion/validation.yaml", {"profiles": {"fast": [f'"{sys.executable}" -c "assert 2 + 2 == 4"']}})
            passed = run_validation_profile("fast", project=root)
            self.assertEqual("passed", passed["status"])

    def test_help_explains_execution_and_model_boundary(self):
        result = self.run_cli("bootstrap", "apply", "--help", cwd=framework_root())
        self.assertEqual(0, result.returncode)
        self.assertIn("Does not execute validation or configure models", " ".join(result.stdout.split()))

    def test_discovered_ci_profile_executes_and_missing_tool_reports_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init_project(root)
            (root / "tests/unit").mkdir(parents=True)
            (root / "tests/unit/test_example.py").write_text("import unittest\nclass Example(unittest.TestCase):\n    def test_sum(self):\n        self.assertEqual(4, 2 + 2)\n", encoding="utf-8")
            workflow = root / ".github/workflows/check.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("jobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m unittest discover -s tests/unit\n", encoding="utf-8")
            plan = plan_bootstrap(root)
            apply_bootstrap(root, plan)
            self.assertEqual("passed", run_validation_profile("fast", project=root)["status"])
            write_yaml(root / ".embraion/validation.yaml", {"profiles": {"fast": ["embraion-nonexistent-check-tool"]}})
            self.assertEqual("failed", run_validation_profile("fast", project=root)["status"])
