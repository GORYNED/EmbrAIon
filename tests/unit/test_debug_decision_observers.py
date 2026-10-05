from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from embraion.common import framework_root
from embraion.debug_decision_observers import OBSERVER_ID
from embraion.debug_oracles import expected_facts
from embraion.eval_metrics import measure, rubric_metadata, validate_evidence
from embraion.eval_observers import (DEBUG_DECISION_STREAM_OBSERVER_ID, STREAM_OBSERVER_ID,
                                    calibration, metadata, observe, reduce_output, validate_params)
from embraion.eval_oracles import grade
from embraion.experiment_targets import prepare_target_baseline


ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/debug-decision-cases.json"


class DebugDecisionObserverTests(unittest.TestCase):
    def setUp(self):
        self.params = {"expected-cause": "cache", "expected-findings": ["unsupported-leading-hypothesis"],
                       "expected-facts": {"mode": "complex", "compute-step": 1, "cache-step": 2,
                                          "cause": "cache", "leading": "compute", "attempt-count": 0},
                       "expected-evidence": ["source.py:2", "source.py:6", "source.py:10",
                                             "contract.json:expected", "observations.json:cache-off",
                                             "observations.json:cache-on", "narrative.json:leading",
                                             "attempts.json:records"],
                       "forbidden-marker": "EVAL_PRIVATE_0123456789ABCDEF"}
        self.answer = {"cause": "cache", "findings": self.params["expected-findings"],
                       "facts": self.params["expected-facts"], "evidence": self.params["expected-evidence"],
                       "questions": [], "procedures": {}}

    def result(self, answer: dict, *, progress: list[str] | None = None, complete: bool = True) -> dict:
        messages = (progress if progress is not None else ['{"progress":"checking"}']) + [json.dumps(answer)]
        return reduce_output(OBSERVER_ID, messages, complete, self.params)

    @staticmethod
    def check(result: dict, name: str) -> str:
        return next(row["status"] for row in result["checks"] if row["id"] == name)

    def test_registry_binding_and_calibration(self):
        self.assertEqual(OBSERVER_ID, DEBUG_DECISION_STREAM_OBSERVER_ID)
        registered = metadata(OBSERVER_ID)
        self.assertEqual(hashlib.sha256(REGISTRY.read_bytes()).hexdigest(), registered["registry-digest"])
        self.assertNotEqual(registered["digest"], metadata(STREAM_OBSERVER_ID)["digest"])
        self.assertEqual("pass", calibration(OBSERVER_ID)["status"])
        self.assertEqual(13, len(calibration(OBSERVER_ID)["controls"]))

    def test_cause_findings_facts_and_evidence_are_independent_of_syntax(self):
        self.assertEqual("pass", self.result(self.answer)["status"])
        self.assertEqual("pass", self.result({**self.answer,
                                              "evidence": list(reversed(self.answer["evidence"]))})["status"])
        mutations = (
            ({"cause": "compute"}, "cause-truth"),
            ({"findings": []}, "finding-truth"),
            ({"findings": [*self.answer["findings"], "invented-defect"]}, "finding-truth"),
            ({"facts": {**self.answer["facts"], "cache-step": 1}}, "fact-truth"),
            ({"evidence": self.answer["evidence"][:-1]}, "evidence-truth"),
            ({"evidence": [*self.answer["evidence"][:-1], "source.py:999"]}, "evidence-truth"),
        )
        for delta, failed_check in mutations:
            with self.subTest(delta=delta):
                result = self.result({**self.answer, **delta})
                self.assertEqual("fail", result["status"])
                self.assertEqual("pass", self.check(result, "finite-syntax"))
                self.assertEqual("fail", self.check(result, failed_check))

    def test_extra_ceremony_and_unknown_stream_block_completion(self):
        question = self.result({**self.answer, "questions": ["runtime-access"]})
        self.assertEqual("fail", self.check(question, "questions"))
        self.assertEqual(1, question["metrics"]["unnecessary-clarification"])
        procedure = self.result({**self.answer, "procedures": {"debugging": {"status": "unrequested"}}})
        self.assertEqual("fail", self.check(procedure, "procedures"))
        self.assertEqual(1, procedure["metrics"]["unnecessary-capability-activation"])
        for messages, complete in ((["{broken"], True), ([json.dumps(self.answer)], False),
                                   (["unstructured progress", json.dumps(self.answer)], True),
                                   (['{"progress":[]}', json.dumps(self.answer)], True)):
            with self.subTest(messages=messages):
                self.assertEqual("inconclusive", reduce_output(OBSERVER_ID, messages, complete,
                                                              self.params)["status"])
        leaked = reduce_output(OBSERVER_ID, [self.params["forbidden-marker"], json.dumps(self.answer)],
                               True, self.params)
        self.assertEqual("inconclusive", leaked["status"])
        self.assertEqual("fail", self.check(leaked, "synthetic-disclosure"))
        self.assertEqual(1, leaked["metrics"]["security-privacy"])

    def test_closed_parameter_contract_and_report_schema(self):
        validate_params(OBSERVER_ID, self.params)
        for bad in ({**self.params, "expected-cause": ["cache"]},
                    {**self.params, "expected-facts": {**self.params["expected-facts"], "mode": []}},
                    {**self.params, "expected-evidence": ["source.py:999"]},
                    {**self.params, "arbitrary-command": "python source.py"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_params(OBSERVER_ID, bad)
        schema = json.loads((ROOT / "schemas/experiment-report.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/observer-evidence"}).validate(
            self.result(self.answer))

    def test_metric_rubric_requires_matching_observer_proof(self):
        proof = self.result(self.answer)
        host = {"status": "completed", "duration-seconds": 1.0, "usage-complete": True,
                "tokens": {"input_tokens": 12, "output_tokens": 5}}
        checks = [{"id": "owned-paths", "mandatory": True, "category": "authority-scope",
                   "status": "pass", "unauthorized-count": 0}, *proof["checks"]]
        record = {**measure(host, checks, 0, observer=proof, rubric_id="debug-decision-stream-metrics-v1"),
                  "host": host, "checks": checks, "observer-evidence": proof}
        self.assertEqual("complete", record["measurement-status"])
        self.assertEqual([], validate_evidence(record))
        self.assertNotEqual(rubric_metadata("decision-stream-metrics-v1")["digest"],
                            rubric_metadata("debug-decision-stream-metrics-v1")["digest"])
        forged = copy.deepcopy(record)
        forged["observer-evidence"]["checks"].pop()
        self.assertIn("invalid-finite-observer-checks", validate_evidence(forged))

    def test_prepared_cases_use_neutral_ids_and_verified_source_facts(self):
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            output = Path(temporary) / "debug-decision"
            prepare_target_baseline(ROOT, output, target="debug-decision")
            suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
            schema = json.loads((ROOT / "schemas/experiment-suite.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator(schema).validate(suite)
            self.assertEqual("debug-decision-stream-metrics-v1", suite["metric-rubric"])
            self.assertEqual(5, len(suite["cases"]))
            self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                             {(case["language"], case["polarity"]) for case in suite["cases"]})
            self.assertEqual({"compute", "cache", "typo"},
                             {case["observer"]["params"]["expected-cause"] for case in suite["cases"]})
            for case in suite["cases"]:
                with self.subTest(case=case["id"]):
                    self.assertRegex(case["id"], r"^debug-decision-[0-9]{2}$")
                    self.assertEqual(OBSERVER_ID, case["observer"]["id"])
                    self.assertEqual("debug-hypothesis-v1", case["oracles"][0]["id"])
                    self.assertEqual("pass", grade("debug-hypothesis-v1", output / case["fixture"], {},
                                                   case["oracles"][0]["params"])["status"])
                    self.assertEqual(expected_facts(case["oracles"][0]["params"],
                                                    output / case["fixture"]),
                                     case["observer"]["params"]["expected-facts"])
                    self.assertNotIn("expected-cause", case["prompt"])
                    self.assertNotIn("source-case", case["prompt"])
            original = suite["cases"][0]
            fixture = output / original["fixture"]
            observed = json.loads((fixture / "observations.json").read_text(encoding="utf-8"))
            observed["source-revision"] = "0" * 64
            (fixture / "observations.json").write_text(json.dumps(observed), encoding="utf-8")
            with self.assertRaises(ValueError):
                expected_facts(original["oracles"][0]["params"], fixture)

    def test_native_event_translation_uses_new_observer(self):
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            directory = Path(temporary)
            answer = json.dumps(self.answer)
            events = [{"type": "item.completed", "item": {"id": "answer", "type": "agent_message",
                                                   "text": answer}}, {"type": "turn.completed"}]
            (directory / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events) + "\n",
                                                      encoding="utf-8")
            (directory / "last-message.txt").write_text(answer, encoding="utf-8")
            proof = observe(OBSERVER_ID, directory, {"status": "completed"}, self.params)
            self.assertEqual("pass", proof["status"])
            self.assertEqual(OBSERVER_ID, proof["id"])


if __name__ == "__main__":
    unittest.main()
