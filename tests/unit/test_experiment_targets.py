from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from embraion.common import framework_root
from embraion.eval_observers import CHECKPOINT_DECISION_STREAM_OBSERVER_ID, STREAM_OBSERVER_ID, reduce_output
from embraion.eval_oracles import grade
from embraion.experiment_targets import prepare_target_baseline


class TargetCases(unittest.TestCase):
    def test_consumer_target_checks_artifact_without_running_fixture_tests(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "consumer"
            prepare_target_baseline(root, output, target="consumer-evidence")
            suite = json.loads((output / "suite.json").read_bytes())
            Draft202012Validator(json.loads((root / "schemas/experiment-suite.schema.json").read_bytes())).validate(suite)
            self.assertEqual({"role": "worker", "access": "workspace-write"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual({"en", "ru"}, {case["language"] for case in suite["cases"]})
            for case in suite["cases"]:
                oracle = case["oracles"][0]
                fixture = output / case["fixture"]
                self.assertEqual(["test_contract.py"], case["allowed-paths"])
                self.assertEqual("consumer-evidence-v1", oracle["id"])
                self.assertEqual("fail" if case["polarity"] == "positive" else "pass",
                                 grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                contract = json.loads((fixture / "contract.json").read_bytes())
                if case["polarity"] == "positive":
                    sample = contract["samples"][2]
                    (fixture / "test_contract.py").write_text(
                        'from consumer import consume\ndef test_contract():\n'
                        f'    assert consume({sample["input"]}) == {sample["output"]}\n')
                self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                params = case["observer"]["params"]
                answer = json.dumps({"result": params["expected-result"], "findings": params["expected-findings"], "questions": [], "procedures": {}})
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [answer], True, params)["status"])
                if case["id"] == "consumer-evidence-01":
                    missing = json.dumps({"result": "changed", "findings": [], "questions": [], "procedures": {}})
                    result = reduce_output(STREAM_OBSERVER_ID, [missing], True, params)
                    self.assertEqual("fail", result["status"])
                    self.assertEqual(0, result["metrics"]["false-positive-rate"])

    def test_scope_fixture_exercises_actual_change_and_preservation(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "scope"
            prepare_target_baseline(root, output, target="scope-action")
            suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
            self.assertEqual({"role": "lead", "access": "workspace-write"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual(2, sum("held-out" in case["id"] for case in suite["cases"]))
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                before = grade("upgrade-scope-v1", fixture, {}, {})
                target_check = next(check for check in before["checks"] if check["id"] == "framework-target")
                self.assertEqual("fail" if case["polarity"] == "positive" else "pass", target_check["status"])
                self.assertNotIn("expected-result", (fixture / "checkpoint.json").read_text(encoding="utf-8"))
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

    def test_checkpoint_bridge_derives_truth_and_keeps_unsafe_claim_on_incomplete_stream(self):
        root = framework_root()
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "checkpoint"
            prepare_target_baseline(root, output, target="checkpoint-decision")
            suite = json.loads((output / "suite.json").read_bytes())
            schema = json.loads((root / "schemas/experiment-suite.schema.json").read_bytes())
            Draft202012Validator(schema).validate(suite)
            self.assertEqual({"role": "analyst", "access": "read-only"}, suite["execution"])
            self.assertEqual("checkpoint-decision-stream-metrics-v1", suite["metric-rubric"])
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                             {(c["language"], c["polarity"]) for c in suite["cases"]})
            self.assertEqual(2, sum(c["risk"] == "high" for c in suite["cases"]))
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                oracle = case["oracles"][0]
                self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                self.assertEqual([], case["allowed-paths"])
                self.assertEqual(5, len(list(fixture.iterdir())))
                self.assertTrue(all("expected-readiness" not in p.read_text(encoding="utf-8")
                                    for p in fixture.iterdir()))
                params = case["observer"]["params"]
                answer = {"readiness": params["expected-readiness"], "allowed-action": params["expected-action"],
                          "findings": params["expected-findings"], "facts": params["expected-facts"],
                          "evidence": params["expected-evidence"], "questions": [], "procedures": {}}
                self.assertEqual("pass", reduce_output(CHECKPOINT_DECISION_STREAM_OBSERVER_ID,
                                                        [json.dumps(answer)], True, params)["status"])
                answer["allowed-action"] = "publish"
                result = reduce_output(CHECKPOINT_DECISION_STREAM_OBSERVER_ID, [json.dumps(answer)], False, params)
                self.assertEqual("inconclusive", result["status"])
                self.assertTrue(any(c["id"] == "action-scope" and c["status"] == "fail"
                                    and c["category"] == "authority-scope" for c in result["checks"]))

    def test_security_fixture_uses_registered_source_gold_outside_workspace(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "security"
            prepare_target_baseline(root, output, target="security-flow")
            suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual({"role": "reviewer", "access": "read-only"}, suite["execution"])
            self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                             {(case["language"], case["polarity"]) for case in suite["cases"]})
            for case in suite["cases"]:
                self.assertEqual("high", case["risk"])
                fixture = output / case["fixture"]
                oracle = case["oracles"][0]
                self.assertEqual({"case": case["id"]}, oracle["params"])
                self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                self.assertEqual({"service.py", "contract.json"}, {p.name for p in fixture.iterdir()})
                self.assertNotIn("expected-paths", (fixture / "contract.json").read_text())
                params = case["observer"]["params"]
                answer = {"result": params["expected-result"], "findings": params["expected-findings"],
                          "questions": [], "procedures": params["required-procedures"]}
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])
                if case["polarity"] == "positive":
                    answer["findings"] = []
                    outcome = reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)
                    self.assertEqual("fail", outcome["status"])
                    self.assertEqual(1, outcome["metrics"]["security-privacy"])

    def test_review_fixture_preserves_actual_source_diff_and_excludes_gold(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "review"
            prepare_target_baseline(root, output, target="review-axes")
            suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
            self.assertEqual({"role": "reviewer", "access": "read-only"}, suite["execution"])
            self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                             {(case["language"], case["polarity"]) for case in suite["cases"]})
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                self.assertEqual([], case["allowed-paths"])
                self.assertNotIn("corpus-id", case)
                self.assertNotEqual((fixture / "original.py").read_bytes(), (fixture / "proposal.py").read_bytes())
                self.assertEqual("pass", grade("wiring-v1", fixture, {}, {})["status"])
                for path in fixture.iterdir():
                    text = path.read_text(encoding="utf-8")
                    self.assertNotIn("expected-result", text)
                    self.assertNotIn("gold-rationale", text)
                params = case["observer"]["params"]
                answer = {"result": params["expected-result"], "findings": params["expected-findings"],
                          "questions": [], "procedures": params["required-procedures"]}
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])
                answer["result"] = "hold" if answer["result"] == "ready" else "ready"
                self.assertEqual("fail", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])

    def test_refactor_bridge_preserves_before_contract_and_scores_actual_change(self):
        root = framework_root()
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "refactor"
            prepare_target_baseline(root, output, target="refactor-characterization")
            suite = json.loads((output / "suite.json").read_bytes())
            self.assertEqual({"role": "worker", "access": "workspace-write"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual({"en", "ru"}, {c["language"] for c in suite["cases"] if c["polarity"] == "negative"})
            case = next(c for c in suite["cases"] if c["id"] == "refactor-move-en")
            fixture = output / case["fixture"]
            oracle = case["oracles"][0]
            self.assertEqual("refactor-characterization-v1", oracle["id"])
            self.assertEqual("fail", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
            legacy = (fixture / "legacy.py").read_bytes()
            (fixture / "ops").mkdir()
            (fixture / "ops/normalizer.py").write_bytes(legacy)
            (fixture / "legacy.py").write_text("from ops.normalizer import normalize\n", encoding="utf-8")
            self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])

    def test_debug_hypothesis_bridge_keeps_records_and_gold_separate(self):
        root = framework_root()
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "debug"
            prepare_target_baseline(root, output, target="debug-hypothesis")
            suite = json.loads((output / "suite.json").read_bytes())
            self.assertEqual({"role": "analyst", "access": "read-only"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            for case in suite["cases"]:
                oracle = case["oracles"][0]
                fixture = output / case["fixture"]
                self.assertEqual("debug-hypothesis-v1", oracle["id"])
                self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                self.assertEqual([], case["allowed-paths"])
                self.assertEqual(5, len(list(fixture.iterdir())))
                self.assertTrue(all("expected-facts" not in p.read_text(encoding="utf-8")
                                    for p in fixture.iterdir()))
                params = case["observer"]["params"]
                answer = {"result": params["expected-result"], "findings": params["expected-findings"],
                          "questions": [], "procedures": copy.deepcopy(params["required-procedures"])}
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])
                answer["procedures"]["debugging"]["evidence"][0] = "source.py:invented"
                self.assertEqual("fail", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])

    def test_goal_fixture_binds_source_proof_without_exposing_gold(self):
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "goal"
            prepare_target_baseline(root, output, target="goal-flow")
            suite = json.loads((output / "suite.json").read_bytes())
            self.assertEqual({"role": "validator", "access": "read-only"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                oracle = case["oracles"][0]
                self.assertEqual("goal-flow-v1", oracle["id"])
                self.assertEqual({"case": case["id"]}, oracle["params"])
                self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                self.assertEqual([], case["allowed-paths"])
                self.assertNotIn("corpus-id", case)
                self.assertEqual(6, len(list(fixture.iterdir())))
                for path in fixture.iterdir():
                    self.assertNotIn("expected-facts", path.read_text(encoding="utf-8"))
                    self.assertNotIn("gold-rationale", path.read_text(encoding="utf-8"))
                params = case["observer"]["params"]
                answer = {"result": params["expected-result"], "findings": params["expected-findings"],
                          "questions": [], "procedures": params["required-procedures"]}
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])
                answer = copy.deepcopy(answer)
                answer["procedures"]["validation"]["end-to-end"] = "unsupported"
                self.assertEqual("fail", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])

    def test_review_gold_detects_axes_conflation_and_inert_comment_false_finding(self):
        root = framework_root()
        registry = json.loads((root / "evals/evolution/review-cases.json").read_text(encoding="utf-8"))
        by_id = {case["id"]: case for case in registry["cases"]}
        params = by_id["review-code-positive-ru"]["gold"]
        review = dict(params["required-procedures"]["review"], intent="pass")
        answer = {"result": "hold", "findings": ["implementation-defect"], "questions": [], "procedures": {"review": review}}
        result = reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)
        self.assertEqual("fail", result["status"])
        self.assertTrue(any(check["id"] == "required-procedures" and check["status"] == "fail" for check in result["checks"]))
        params = by_id["review-control-negative-ru"]["gold"]
        answer = {"result": "ready", "findings": ["implementation-defect"], "questions": [],
                  "procedures": params["required-procedures"]}
        result = reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)
        self.assertEqual("fail", result["status"])
        self.assertEqual(1, result["metrics"]["false-positive-rate"])

    def test_research_choice_uses_source_and_independent_outside_gold(self):
        root = framework_root()
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            output = Path(temporary) / "research"
            prepare_target_baseline(root, output, target="research-choice")
            suite = json.loads((output / "suite.json").read_bytes())
            self.assertEqual({"role": "researcher", "access": "read-only"}, suite["execution"])
            self.assertEqual(6, len(suite["cases"]))
            self.assertEqual({"adopt", "extend", "build"},
                             {case["observer"]["params"]["expected-result"] for case in suite["cases"]})
            for case in suite["cases"]:
                fixture = output / case["fixture"]
                oracle = case["oracles"][0]
                self.assertEqual("research-choice-v1", oracle["id"])
                self.assertEqual("pass", grade(oracle["id"], fixture, {}, oracle["params"])["status"])
                self.assertEqual([], case["allowed-paths"])
                self.assertEqual(5, len(list(fixture.iterdir())))
                for path in fixture.iterdir():
                    self.assertNotIn("expected-facts", path.read_text(encoding="utf-8"))
                params = case["observer"]["params"]
                answer = {"result": params["expected-result"], "findings": params["expected-findings"],
                          "questions": [], "procedures": params["required-procedures"]}
                self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])
                answer = copy.deepcopy(answer)
                answer["result"] = "build" if params["expected-result"] != "build" else "adopt"
                self.assertEqual("fail", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, params)["status"])


if __name__ == "__main__":
    unittest.main()
