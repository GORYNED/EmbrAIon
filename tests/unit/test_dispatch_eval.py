from __future__ import annotations

import copy
import unittest

from embraion.common import framework_root, read_json, read_yaml
from embraion.evals import evaluate_case


class DispatchEvalTests(unittest.TestCase):
    def test_routing_eval_rejects_each_missing_or_violated_host_contract(self) -> None:
        root = framework_root()
        case = read_yaml(root / "evals/cases/assignment-routing.yaml")
        record = read_json(root / "tests/fixtures/evals/assignment-routing.json")
        passed, failures = evaluate_case(case, record)
        self.assertTrue(passed, failures)
        for check in case["checks"]:
            with self.subTest(field=check["field"]):
                broken = copy.deepcopy(record)
                target = broken
                parts = check["field"].split(".")
                for part in parts[:-1]:
                    target = target[part]
                expected = check["value"]
                target[parts[-1]] = (
                    not expected if isinstance(expected, bool) else "unsupported-value"
                )
                passed, failures = evaluate_case(case, broken)
                self.assertFalse(passed)
                self.assertEqual(1, len(failures))
                self.assertIn(check["field"], failures[0])
        passed, failures = evaluate_case(case, {})
        self.assertFalse(passed)
        self.assertEqual(len(case["checks"]), len(failures))

    def test_routing_eval_is_explicitly_synthetic_and_covers_all_host_boundaries(self) -> None:
        root = framework_root()
        case = read_yaml(root / "evals/cases/assignment-routing.yaml")
        record = read_json(root / "tests/fixtures/evals/assignment-routing.json")
        self.assertEqual("synthetic-grading-fixture", case["context"]["evidence-kind"])
        self.assertFalse(case["context"]["live-host-execution"])
        self.assertEqual({"codex", "copilot", "claude-code", "portable"}, set(case["context"]["hosts"]))
        self.assertEqual({"cli", "vscode", "cloud"}, set(record["copilot"]))
        self.assertFalse(record["portable"]["runtime-available"])
        self.assertEqual({}, record["portable"]["runtime-arguments"])

    def test_routing_eval_runs_in_validation_and_both_release_build_gates(self) -> None:
        root = framework_root()
        command = (
            "python tools/source.py eval run --case assignment-routing "
            "--record tests/fixtures/evals/assignment-routing.json "
            "--output build/evals/assignment-routing.json"
        )
        profile = read_yaml(root / ".embraion/validation.yaml")
        self.assertIn(command, profile["profiles"]["full"])
        for filename, jobs in (
            ("validate.yml", ("validate",)),
            ("release.yml", ("prepare-release", "build")),
        ):
            workflow = read_yaml(root / ".github/workflows" / filename)
            for job in jobs:
                with self.subTest(workflow=filename, job=job):
                    runs = [step.get("run", "") for step in workflow["jobs"][job]["steps"]]
                    self.assertEqual(1, sum(command in run for run in runs))


if __name__ == "__main__":
    unittest.main()
