from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root
from embraion.eval_observers import STREAM_OBSERVER_ID, reduce_output, validate_params as validate_observer_params
from embraion.goal_oracles import ORACLE_ID, calibration, expected_observation, grade, oracle_metadata, validate_params


ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/goal-cases.json"
FIXTURE = ROOT / "evals/foundation/fixtures/goal-flow-v1"
SOURCES = ("service.py", "router.py", "consumer.py")


class GoalOracleTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.cases = {item["id"]: item for item in self.registry["cases"]}
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "build")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)

    def prepare(self, case_id: str) -> dict[str, str]:
        for name, content in self.cases[case_id]["files"].items():
            (self.project / name).write_text(content, encoding="utf-8", newline="\n")
        return {"case": case_id}

    def rewrite_source(self, name: str, old: str, new: str) -> None:
        path = self.project / name
        content = path.read_text(encoding="utf-8")
        self.assertIn(old, content)
        path.write_text(content.replace(old, new, 1), encoding="utf-8", newline="\n")
        checkpoint = json.loads((self.project / "checkpoint.json").read_text(encoding="utf-8"))
        checkpoint["current"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.project / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")

    def check_status(self, result: dict, check_id: str) -> str:
        return next(row["status"] for row in result["checks"] if row["id"] == check_id)

    def test_registered_case_proofs_and_finite_gold(self):
        self.assertEqual(6, len(self.cases))
        self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                         {(case["language"], case["polarity"]) for case in self.cases.values()})
        self.assertEqual(2, sum(case["split"] == "held-out" for case in self.cases.values()))
        expected = {
            "goal-dispatch-positive-en": ["broken-dispatcher"],
            "goal-target-positive-ru": ["wrong-route-target"],
            "goal-clean-negative-en": [],
            "goal-comment-negative-ru": [],
            "goal-claims-heldout-en": ["missing-obligation", "unsupported-completion-claim", "stale-checkpoint"],
            "goal-clean-heldout-ru": [],
        }
        for case_id in sorted(self.cases):
            with self.subTest(case=case_id):
                params = self.prepare(case_id)
                self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
                gold = expected_observation(params, self.project)
                validate_observer_params(STREAM_OBSERVER_ID, gold)
                self.assertEqual(expected[case_id], gold["expected-findings"])
                self.assertEqual("hold" if expected[case_id] else "ready", gold["expected-result"])
                evidence = gold["required-procedures"]["validation"]["evidence"]
                self.assertEqual(8, len(evidence))
                self.assertTrue(evidence[0].startswith("service.py:"))
                self.assertTrue(evidence[1].startswith("router.py:"))
                self.assertTrue(evidence[2].startswith("router.py:"))
                self.assertTrue(evidence[3].startswith("consumer.py:"))
                self.assertEqual(["contract.json:required-routes", "actions.json:external-publication",
                                  "checkpoint.json:before", "checkpoint.json:current"], evidence[4:])

    def test_observer_requires_source_anchored_validation(self):
        gold = expected_observation(self.prepare("goal-dispatch-positive-en"), self.project)
        answer = {"result": gold["expected-result"], "findings": gold["expected-findings"],
                  "questions": [], "procedures": gold["required-procedures"]}
        self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, gold)["status"])
        tampered = copy.deepcopy(answer)
        tampered["procedures"]["validation"]["evidence"][2] = "router.py:999"
        observed = reduce_output(STREAM_OBSERVER_ID, [json.dumps(tampered)], True, gold)
        self.assertEqual("fail", observed["status"])
        self.assertEqual("fail", self.check_status(observed, "required-procedures"))

    def test_symbolic_integer_proof_and_actual_consumer_reachability(self):
        params = self.prepare("goal-clean-negative-en")
        self.rewrite_source("service.py", "return value + 1", "return value")
        self.assertEqual("fail", self.check_status(grade(ORACLE_ID, self.project, {}, params), "source-facts"))
        self.prepare("goal-clean-negative-en")
        self.rewrite_source("service.py", "return value + 1", "return 42")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.prepare("goal-clean-negative-en")
        self.rewrite_source("consumer.py", 'return dispatch("process", value)',
                            'return value\n    return dispatch("process", value)')
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", result["status"])
        self.assertEqual("fail", self.check_status(result, "source-facts"))
        self.assertEqual("pass", self.check_status(result, "checkpoint-facts"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            expected_observation(params, self.project)

    def test_registered_facts_are_independent_of_case_label_and_source(self):
        from embraion import goal_oracles
        params = self.prepare("goal-clean-negative-en")
        self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
        altered = copy.deepcopy(self.cases)
        altered[params["case"]]["expected-facts"]["consumer"] = "return-input"
        with patch.object(goal_oracles, "_registry", return_value=(altered, "0" * 64)):
            result = grade(ORACLE_ID, self.project, {}, params)
            self.assertEqual("fail", self.check_status(result, "source-facts"))
        altered = copy.deepcopy(self.cases)
        altered[params["case"]]["expected-facts"]["obligation-retained"] = False
        with patch.object(goal_oracles, "_registry", return_value=(altered, "0" * 64)):
            result = grade(ORACLE_ID, self.project, {}, params)
            self.assertEqual("fail", self.check_status(result, "obligation-facts"))

    def test_removed_duty_and_local_completed_claim_are_separate_failures(self):
        params = self.prepare("goal-clean-negative-en")
        contract = json.loads((self.project / "contract.json").read_text(encoding="utf-8"))
        contract["required-routes"] = []
        (self.project / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check_status(result, "obligation-facts"))
        self.assertEqual("pass", self.check_status(result, "source-facts"))
        self.prepare("goal-clean-negative-en")
        actions = {"external-publication": {"status": "completed"}}
        (self.project / "actions.json").write_text(json.dumps(actions), encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check_status(result, "claim-facts"))
        self.assertEqual("pass", self.check_status(result, "source-facts"))
        heldout = self.prepare("goal-claims-heldout-en")
        gold = expected_observation(heldout, self.project)
        self.assertEqual("hold", gold["expected-result"])
        self.assertIn("unsupported-completion-claim", gold["expected-findings"])
        self.assertEqual("proved", gold["required-procedures"]["validation"]["end-to-end"])

    def test_checkpoint_binds_original_before_and_current_bytes(self):
        params = self.prepare("goal-clean-negative-en")
        checkpoint = json.loads((self.project / "checkpoint.json").read_text(encoding="utf-8"))
        original_before = {name: hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() for name in SOURCES}
        self.assertEqual(original_before, checkpoint["before"])
        checkpoint["before"]["router.py"] = "0" * 64
        (self.project / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
        self.assertEqual("fail", self.check_status(grade(ORACLE_ID, self.project, {}, params), "checkpoint-facts"))
        self.prepare("goal-clean-negative-en")
        checkpoint = json.loads((self.project / "checkpoint.json").read_text(encoding="utf-8"))
        checkpoint["current"]["router.py"] = "0" * 64
        (self.project / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
        self.assertEqual("fail", self.check_status(grade(ORACLE_ID, self.project, {}, params), "checkpoint-facts"))

    def test_domain_and_retained_obligation_are_independent(self):
        params = self.prepare("goal-clean-negative-en")
        contract = json.loads((self.project / "contract.json").read_bytes())
        contract["goal"]["output"] = "value+2"
        (self.project / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check_status(result, "domain-contract"))
        self.assertEqual("pass", self.check_status(result, "obligation-facts"))
        for malformed in ({}, [], {"required-routes": ["process"]}):
            with self.subTest(contract=malformed):
                (self.project / "contract.json").write_text(json.dumps(malformed), encoding="utf-8")
                result = grade(ORACLE_ID, self.project, {}, params)
                self.assertEqual("fail", self.check_status(result, "domain-contract"))
    def test_unsupported_ast_is_inconclusive_and_not_executed(self):
        params = self.prepare("goal-clean-negative-en")
        marker = self.project / "executed.txt"
        source = f'__import__("pathlib").Path({str(marker)!r}).write_text("executed")\n'
        (self.project / "service.py").write_text(source, encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.assertFalse(marker.exists())
        (self.project / "service.py").write_text("x" * 4097, encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.prepare("goal-clean-negative-en")
        self.rewrite_source("service.py", "def process(", "def process[T](")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])

    def test_metadata_digest_and_closed_typed_params(self):
        from embraion import goal_oracles
        metadata = oracle_metadata(ORACLE_ID)
        self.assertEqual(hashlib.sha256(REGISTRY.read_bytes()).hexdigest(), metadata["registry-digest"])
        self.assertIn("arbitrary Python", metadata["coverage"]["does_not_prove"])
        for value in ([], {}, None, 1, True, "unknown"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_params(ORACLE_ID, {"case": value})
        with self.assertRaises(ValueError):
            validate_params(ORACLE_ID, {"case": "goal-clean-negative-en", "command": "python service.py"})
        with patch.object(goal_oracles, "_registry", side_effect=goal_oracles._Unavailable("missing")):
            with self.assertRaisesRegex(ValueError, "unavailable goal oracle metadata"):
                oracle_metadata(ORACLE_ID)

    def test_calibration_isolates_each_defect(self):
        result = calibration(ORACLE_ID, ROOT)
        self.assertEqual("pass", result["status"], result)
        controls = {row["control"]: row for row in result["outcomes"]}
        for name in ("no-op-service", "wrong-route-target", "broken-dispatcher", "dead-consumer",
                     "removed-obligation", "unsupported-completion-claim", "stale-checkpoint",
                     "rewritten-before-baseline", "unsupported-grammar", "benign-comment"):
            self.assertEqual("pass", controls[name]["status"])


if __name__ == "__main__":
    unittest.main()
