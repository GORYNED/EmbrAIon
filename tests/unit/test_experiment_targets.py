from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root
from embraion.eval_observers import STREAM_OBSERVER_ID, reduce_output
from embraion.eval_oracles import grade
from embraion.experiment_targets import prepare_target_baseline


class TargetCases(unittest.TestCase):
    def test_scope_fixture_exercises_actual_change_and_preservation(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "scope"
            prepare_target_baseline(root, output, target="scope-action")
            suite = json.loads((output / "suite.json").read_text())
            self.assertEqual({"role": "lead", "access": "workspace-write"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual(2, sum("held-out" in case["id"] for case in suite["cases"]))
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                before = grade("upgrade-scope-v1", fixture, {}, {})
                target_check = next(check for check in before["checks"] if check["id"] == "framework-target")
                self.assertEqual("fail" if case["polarity"] == "positive" else "pass", target_check["status"])
                self.assertNotIn("expected-result", (fixture / "checkpoint.json").read_text())
                (fixture / "framework-pin.json").write_text('{"version":"0.22.0","external_action":"unverified"}')
                self.assertEqual("pass", grade("upgrade-scope-v1", fixture, {}, {})["status"])
                gold = case["observer"]["params"]
                answer = json.dumps({"result": gold["expected-result"], "findings": [], "questions": [], "procedures": {}})
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, ['{"progress":"checking"}', answer], True, gold)["status"])
                (fixture / "release-request.json").write_text('{}')
                result = grade("upgrade-scope-v1", fixture, {}, {})
                self.assertTrue(any(check["id"] == "release-request-absent" and check["status"] == "fail" for check in result["checks"]))
            with self.assertRaises(ValueError):
                prepare_target_baseline(root, output, target="scope-action")

    def test_unknown_target_cannot_select_paths_or_execution(self):
        with self.assertRaises(ValueError):
            prepare_target_baseline(framework_root(), Path("unused"), target="../../arbitrary")


if __name__ == "__main__":
    unittest.main()
