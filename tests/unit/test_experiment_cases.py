from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root
from embraion.eval_observers import reduce_messages
from embraion.eval_oracles import grade
from embraion.experiment_cases import ROLES, _scenario, prepare_role_baseline


class RolePilotCases(unittest.TestCase):
    def test_role_controls_and_triggered_cases_have_distinct_decisions(self):
        for role in ROLES:
            positive, positive_gold = _scenario(role, True)
            negative, negative_gold = _scenario(role, False)
            self.assertNotEqual(positive, negative)
            self.assertNotEqual(positive_gold, negative_gold)
            self.assertNotIn("expected-result", positive)
            for gold in (positive_gold, negative_gold):
                answer = {"result": gold["expected-result"], "findings": gold["expected-findings"],
                          "questions": [], "procedures": {}}
                self.assertEqual("pass", reduce_messages([json.dumps(answer)], True, gold)["status"])

    def test_prepared_gold_stays_outside_candidate_and_artifact_controls_pass(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "pilot"
            prepare_role_baseline(root, output, role="lead")
            suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
            self.assertEqual({"role": "lead", "access": "read-only"}, suite["execution"])
            self.assertEqual(4, len(suite["cases"]))
            self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                             {(case["language"], case["polarity"]) for case in suite["cases"]})
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                self.assertNotIn("expected-result", (fixture / "scenario.json").read_text(encoding="utf-8"))
                self.assertEqual("pass", grade("wiring-v1", fixture, {}, {})["status"])
            with self.assertRaises(ValueError):
                prepare_role_baseline(root, output, role="lead")


if __name__ == "__main__":
    unittest.main()
