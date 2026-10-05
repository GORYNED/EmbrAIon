from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from embraion.checkpoint_oracles import expected_observation
from embraion.common import framework_root
from embraion.eval_metrics import measure, validate_evidence
from embraion.eval_observers import CHECKPOINT_DECISION_STREAM_OBSERVER_ID as OBSERVER_ID
from embraion.eval_observers import observe, reduce_output


class CheckpointBridgeTests(unittest.TestCase):
    def setUp(self):
        self.root = framework_root()
        registry = json.loads((self.root / "evals/evolution/checkpoint-cases.json").read_bytes())
        with tempfile.TemporaryDirectory(dir=self.root / "build") as temporary:
            fixture = Path(temporary)
            for name, content in registry["cases"][0]["files"].items():
                (fixture / name).write_text(content, encoding="utf-8", newline="\n")
            self.params = expected_observation({"case": registry["cases"][0]["id"]}, fixture)
        self.answer = {"readiness": self.params["expected-readiness"],
                       "allowed-action": self.params["expected-action"],
                       "findings": self.params["expected-findings"], "facts": self.params["expected-facts"],
                       "evidence": self.params["expected-evidence"], "questions": [], "procedures": {}}

    def test_schema_and_metrics_retain_authority_failure_without_cost_compensation(self):
        schema = json.loads((self.root / "schemas/experiment-report.schema.json").read_bytes())
        validator = Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/observer-evidence"})
        for action in (self.params["expected-action"], "publish"):
            with self.subTest(action=action):
                proof = reduce_output(OBSERVER_ID, [json.dumps({**self.answer, "allowed-action": action})],
                                      True, self.params)
                validator.validate(proof)
                checks = [{"id": "owned-paths", "mandatory": True, "category": "authority-scope",
                           "status": "pass", "unauthorized-count": 0}, *proof["checks"]]
                host = {"status": "completed", "duration-seconds": 1.0, "usage-complete": True,
                        "tokens": {"input_tokens": 12, "output_tokens": 5}}
                record = {**measure(host, checks, 0, observer=proof,
                                   rubric_id="checkpoint-decision-stream-metrics-v1"),
                          "host": host, "checks": checks, "observer-evidence": proof}
                self.assertEqual("complete", record["measurement-status"])
                self.assertEqual([], validate_evidence(record))
                # The existing authority metric counts local files only; the
                # independent action-scope check remains a mandatory gate.
                self.assertEqual(0, record["metrics"]["authority-scope"])
                self.assertEqual(int(action == "publish"), record["metrics"]["security-privacy"])
                self.assertEqual("fail" if action == "publish" else "pass",
                                 next(c["status"] for c in proof["checks"] if c["id"] == "action-scope"))
                forged = copy.deepcopy(record)
                forged["observer-evidence"]["checks"].pop()
                self.assertIn("invalid-finite-observer-checks", validate_evidence(forged))

    def test_native_partial_update_violation_survives_missing_or_replaced_answer(self):
        unsafe = json.dumps({"allowed-action": "publish"})
        safe = json.dumps(self.answer)
        for final in ("absent", "invalid", "unfinished", "replaced"):
            with self.subTest(final=final), tempfile.TemporaryDirectory(dir=self.root / "build") as temporary:
                directory = Path(temporary)
                events = [{"type": "item.updated", "item": {"id": "answer", "type": "agent_message",
                                                              "text": unsafe}}]
                if final == "replaced":
                    events += [{"type": "item.completed", "item": {"id": "answer", "type": "agent_message",
                                                                     "text": safe}}, {"type": "turn.completed"}]
                (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n",
                                                       encoding="utf-8")
                if final == "invalid":
                    (directory / "last-message.txt").write_bytes(b"\xff")
                elif final != "absent":
                    (directory / "last-message.txt").write_text(safe, encoding="utf-8")
                proof = observe(OBSERVER_ID, directory, {"status": "completed"}, self.params)
                self.assertEqual("inconclusive", proof["status"])
                self.assertTrue(any(c["id"] == "action-scope" and c["status"] == "fail"
                                    for c in proof["checks"]))
                self.assertEqual(1, proof["metrics"]["security-privacy"])

    def test_native_complete_answer_is_assessed_by_checkpoint_observer(self):
        answer = json.dumps(self.answer)
        with tempfile.TemporaryDirectory(dir=self.root / "build") as temporary:
            directory = Path(temporary)
            events = [{"type": "item.completed", "item": {"id": "answer", "type": "agent_message",
                                                           "text": answer}}, {"type": "turn.completed"}]
            (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n",
                                                   encoding="utf-8")
            (directory / "last-message.txt").write_text(answer, encoding="utf-8")
            proof = observe(OBSERVER_ID, directory, {"status": "completed"}, self.params)
            self.assertEqual("pass", proof["status"])


if __name__ == "__main__":
    unittest.main()
