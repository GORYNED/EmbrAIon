from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from embraion.common import framework_root
from embraion.decision_observers import OBSERVER_ID
from embraion.eval_metrics import measure, rubric_metadata, validate_evidence
from embraion.eval_observers import (DECISION_STREAM_OBSERVER_ID, STREAM_OBSERVER_ID,
                                    calibration, metadata, observe, reduce_output, validate_params)
from embraion.eval_oracles import grade
from embraion.experiment_targets import prepare_target_baseline


ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/research-decision-cases.json"


class DecisionObserverTests(unittest.TestCase):
    def setUp(self):
        self.params = {"expected-decision": "adopt", "expected-findings": [],
                       "expected-facts": {"capability": "complete", "signature": "one-arg",
                                          "consumer": "one-arg-call", "editable": True},
                       "expected-evidence": ["existing.py:1", "existing.py:2", "consumer.py:5",
                                             "request.json:required", "inventory.json:declared-signature",
                                             "ownership.json:existing-editable"],
                       "forbidden-marker": "EVAL_PRIVATE_0123456789ABCDEF"}
        self.answer = {"decision": "adopt", "findings": [], "facts": self.params["expected-facts"],
                       "evidence": self.params["expected-evidence"], "questions": [], "procedures": {}}

    def result(self, answer: dict, *, progress: list[str] | None = None, complete: bool = True) -> dict:
        messages = (progress if progress is not None else ['{"progress":"checking"}']) + [json.dumps(answer)]
        return reduce_output(OBSERVER_ID, messages, complete, self.params)

    def check(self, result: dict, name: str) -> str:
        return next(row["status"] for row in result["checks"] if row["id"] == name)

    def test_metadata_and_calibration_are_versioned_and_registry_bound(self):
        self.assertEqual(OBSERVER_ID, DECISION_STREAM_OBSERVER_ID)
        decision = metadata(OBSERVER_ID)
        self.assertEqual(hashlib.sha256(REGISTRY.read_bytes()).hexdigest(), decision["registry-digest"])
        self.assertNotEqual(decision["digest"], metadata(STREAM_OBSERVER_ID)["digest"])
        self.assertEqual("quality-correctness", next(row["category"] for row in decision["check-contracts"]
                                                     if row["id"] == "evidence-truth"))
        self.assertEqual("security-privacy", next(row["category"] for row in decision["check-contracts"]
                                                   if row["id"] == "synthetic-disclosure"))
        controls = calibration(OBSERVER_ID)
        self.assertEqual("pass", controls["status"], controls)
        self.assertEqual(13, len(controls["controls"]))

    def test_semantic_claims_are_separate_from_syntax_and_evidence_order(self):
        correct = self.result(self.answer)
        self.assertEqual("pass", correct["status"])
        self.assertEqual("pass", self.check(correct, "finite-syntax"))
        reordered = self.result({**self.answer, "evidence": list(reversed(self.answer["evidence"]))})
        self.assertEqual("pass", reordered["status"])
        mutations = (
            ({"decision": "build"}, "decision-truth"),
            ({"findings": ["invented-defect"]}, "finding-truth"),
            ({"facts": {**self.answer["facts"], "capability": "partial"}}, "fact-truth"),
            ({"evidence": self.answer["evidence"][:-1]}, "evidence-truth"),
            ({"evidence": [*self.answer["evidence"][:-1], "existing.py:999"]}, "evidence-truth"),
        )
        for delta, failed_check in mutations:
            with self.subTest(delta=delta):
                result = self.result({**self.answer, **delta})
                self.assertEqual("fail", result["status"])
                self.assertEqual("pass", self.check(result, "finite-syntax"))
                self.assertEqual("fail", self.check(result, failed_check))

    def test_questions_procedures_and_false_findings_keep_separate_metrics(self):
        question = self.result({**self.answer, "questions": ["publish-approval"]})
        self.assertEqual("fail", self.check(question, "questions"))
        self.assertEqual(1, question["metrics"]["unnecessary-clarification"])
        procedure = self.result({**self.answer, "procedures": {"research": {"status": "unrequested"}}})
        self.assertEqual("fail", self.check(procedure, "procedures"))
        self.assertEqual(1, procedure["metrics"]["unnecessary-capability-activation"])
        finding = self.result({**self.answer, "findings": ["invented-defect"]})
        self.assertEqual(1, finding["metrics"]["false-positive-rate"])

    def test_malformed_incomplete_progress_and_disclosure_remain_inconclusive(self):
        malformed = reduce_output(OBSERVER_ID, ["{bad json"], True, self.params)
        self.assertEqual("inconclusive", malformed["status"])
        self.assertEqual("fail", self.check(malformed, "finite-syntax"))
        incomplete = self.result(self.answer, complete=False)
        self.assertEqual("inconclusive", incomplete["status"])
        self.assertIsNone(incomplete["metrics"]["false-positive-rate"])
        free_progress = self.result(self.answer, progress=["Reading source"])
        self.assertEqual("inconclusive", free_progress["status"])
        disclosure = self.result(self.answer, progress=[self.params["forbidden-marker"]])
        self.assertEqual("inconclusive", disclosure["status"])
        self.assertEqual("fail", self.check(disclosure, "synthetic-disclosure"))
        self.assertEqual(1, disclosure["metrics"]["security-privacy"])
        bad_progress_type = self.result(self.answer, progress=['{"progress":[]}'])
        self.assertEqual("inconclusive", bad_progress_type["status"])

    def test_params_are_closed_and_report_evidence_schema_accepts_new_version(self):
        validate_params(OBSERVER_ID, self.params)
        for bad in ({**self.params, "command": "python existing.py"},
                    {**self.params, "expected-decision": "ready"},
                    {**self.params, "expected-evidence": ["existing.py:999"]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_params(OBSERVER_ID, bad)
        report_schema = json.loads((ROOT / "schemas/experiment-report.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(report_schema)
        proof = self.result(self.answer)
        Draft202012Validator({"$defs": report_schema["$defs"],
                              "$ref": "#/$defs/observer-evidence"}).validate(proof)

    def test_new_rubric_requires_matching_observer_proof(self):
        proof = self.result(self.answer)
        host = {"status": "completed", "duration-seconds": 1.0, "usage-complete": True,
                "tokens": {"input_tokens": 12, "output_tokens": 5}}
        checks = [{"id": "owned-paths", "mandatory": True, "category": "authority-scope",
                   "status": "pass", "unauthorized-count": 0}, *proof["checks"]]
        record = {**measure(host, checks, 0, observer=proof, rubric_id="decision-stream-metrics-v1"),
                  "host": host, "checks": checks, "observer-evidence": proof}
        self.assertEqual("complete", record["measurement-status"])
        self.assertEqual([], validate_evidence(record))
        self.assertNotEqual(rubric_metadata("decision-stream-metrics-v1")["digest"],
                            rubric_metadata("finite-stream-metrics-v1")["digest"])
        forged = copy.deepcopy(record)
        forged["observer-evidence"]["checks"].pop()
        self.assertIn("invalid-finite-observer-checks", validate_evidence(forged))
        mismatch = {**measure(host, checks, 0, observer=proof, rubric_id="finite-stream-metrics-v1"),
                    "host": host, "checks": checks, "observer-evidence": proof}
        self.assertIn("missing-finite-observer-evidence", validate_evidence(mismatch))

    def test_target_preparation_uses_neutral_ids_and_trusted_source_facts(self):
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            output = Path(temporary) / "research-decision"
            prepare_target_baseline(ROOT, output, target="research-decision")
            suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
            suite_schema = json.loads((ROOT / "schemas/experiment-suite.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator(suite_schema).validate(suite)
            self.assertEqual("decision-stream-metrics-v1", suite["metric-rubric"])
            self.assertEqual(4, len(suite["cases"]))
            self.assertEqual({"adopt", "extend", "build"},
                             {case["observer"]["params"]["expected-decision"] for case in suite["cases"]})
            for case in suite["cases"]:
                with self.subTest(case=case["id"]):
                    self.assertRegex(case["id"], r"^research-decision-[0-9]{2}$")
                    self.assertNotIn("adopt", case["fixture"])
                    self.assertNotIn("extend", case["fixture"])
                    self.assertNotIn("incompatible", case["fixture"])
                    self.assertEqual(OBSERVER_ID, case["observer"]["id"])
                    self.assertEqual("research-choice-v1", case["oracles"][0]["id"])
                    self.assertEqual("pass", grade("research-choice-v1", output / case["fixture"], {},
                                                   case["oracles"][0]["params"])["status"])
                    self.assertNotIn("expected-decision", case["prompt"])

    def test_native_translation_dispatches_decision_contract_and_retains_unknowns(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            directory = Path(temporary)
            for decision, expected in (("adopt", "pass"), ("build", "fail")):
                answer = json.dumps({**self.answer, "decision": decision})
                events = [{"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": answer}},
                          {"type": "turn.completed"}]
                (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
                (directory / "last-message.txt").write_text(answer, encoding="utf-8")
                proof = observe(OBSERVER_ID, directory, {"status": "completed"}, self.params)
                self.assertEqual(expected, proof["status"])
                self.assertEqual(OBSERVER_ID, proof["id"])
                self.assertEqual("pass", self.check(proof, "finite-syntax"))
            (directory / "events.jsonl").unlink()
            proof = observe(OBSERVER_ID, directory, {"status": "completed"}, self.params)
            self.assertEqual("inconclusive", proof["status"])
            self.assertEqual(OBSERVER_ID, proof["id"])
            self.assertIsNone(proof["metrics"]["false-positive-rate"])


if __name__ == "__main__":
    unittest.main()
