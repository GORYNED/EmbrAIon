from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from embraion.common import framework_root
from embraion.response_contracts import CONTRACTS, resolve_response_contract
from embraion.eval_observers import reduce_output
from embraion.experiment_targets import RESPONSE_CONTRACTS, prepare_target_baseline


class ResponseContractTests(unittest.TestCase):
    def test_source_derived_correct_controls_fit_schema_and_observer(self) -> None:
        # Independent source-derived gold must remain achievable under the public
        # shape. This catches syntax constraints that silently forbid correctness.
        root = framework_root()
        (root / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / "build") as temporary:
            for target in RESPONSE_CONTRACTS:
                output = Path(temporary) / target
                prepare_target_baseline(root, output, target=target, structured_output=True)
                suite = json.loads((output / "suite.json").read_bytes())
                for case in suite["cases"]:
                    observer = case["observer"]
                    params = observer["params"]
                    if observer["id"] == "finite-stream-v1":
                        correct = {"result": params["expected-result"], "findings": params["expected-findings"],
                                   "questions": params["expected-questions"], "procedures": params["required-procedures"]}
                    else:
                        selected = {"decision-stream-v1": ("decision", "expected-decision"),
                                    "debug-decision-stream-v1": ("cause", "expected-cause"),
                                    "checkpoint-decision-stream-v1": ("readiness", "expected-readiness")}[observer["id"]]
                        correct = {selected[0]: params[selected[1]], "findings": params["expected-findings"],
                                   "facts": params["expected-facts"], "evidence": params["expected-evidence"],
                                   "questions": [], "procedures": {}}
                        if observer["id"] == "checkpoint-decision-stream-v1":
                            correct["allowed-action"] = params["expected-action"]
                    with self.subTest(target=target, case=case["id"]):
                        schema = resolve_response_contract(case["response-contract"], observer)
                        self.assertFalse(list(Draft202012Validator(schema).iter_errors(correct)))
                        self.assertEqual("pass", reduce_output(observer["id"], [json.dumps(correct)], True, params)["status"])

    def test_fixed_registry_and_public_schema_shapes(self) -> None:
        self.assertEqual(5, len(CONTRACTS))
        for contract_id in CONTRACTS:
            schema = resolve_response_contract(contract_id)
            self.assertEqual("object", schema["type"])
            self.assertFalse(schema["additionalProperties"])
            self.assertNotIn("expected", json.dumps(schema))
            self.assertNotIn("EVAL_PRIVATE", json.dumps(schema))
            self.assertTrue((framework_root() / "schemas" / CONTRACTS[contract_id][0]).is_file())
        for invalid in ("response-research.schema.json", "../response-research.schema.json", "codex exec", "unknown"):
            with self.assertRaisesRegex(ValueError, "unknown response contract"):
                resolve_response_contract(invalid)

    def test_wrong_semantic_answers_remain_well_shaped(self) -> None:
        checkpoint = resolve_response_contract("checkpoint-response-v1")
        answer = {"readiness": "reuse", "allowed-action": "publish", "findings": [],
                  "facts": {"session": "resumed", "checkpoint": "stale", "candidate-match": "mismatch",
                            "environment-match": "absent", "request-match": "mismatch",
                            "approval-state": "canceled", "approval-candidate-match": "absent",
                            "approval-request-match": "mismatch"},
                  "evidence": ["arbitrary:1"] * 4, "questions": ["publish-approval"], "procedures": {}}
        self.assertFalse(list(Draft202012Validator(checkpoint).iter_errors(answer)))
        answer["evidence"] = ["too-short"]
        self.assertTrue(list(Draft202012Validator(checkpoint).iter_errors(answer)))
        security = resolve_response_contract("security-response-v1")
        body = {key: "wrong-but-well-shaped" for key in (
            "asset", "entry", "trust-boundary", "reachable-operation", "existing-control",
            "mitigation", "residual-risk", "priority")}
        body.update({"evidence": ["wrong:1"], "preconditions": ["wrong"]})
        base = {"result": "wrong", "findings": ["wrong"], "questions": ["wrong"]}
        for procedures in ({}, {"security-assessment": body}):
            self.assertFalse(list(Draft202012Validator(security).iter_errors({**base, "procedures": procedures})))
        self.assertTrue(list(Draft202012Validator(security).iter_errors(
            {**base, "procedures": {"other": {}}})))

    def test_observer_compatibility_is_prevalidated(self) -> None:
        compatible = {"id": "finite-stream-v1", "mandatory": True,
                      "params": {"required-procedures": {}}}
        resolve_response_contract("artifact-response-v1", compatible)
        for observer in (
            {**compatible, "id": "finite-answer-v1"},
            {**compatible, "mandatory": False},
            {**compatible, "params": {"required-procedures": {"review": {"result": "done"}}}},
        ):
            with self.assertRaises(ValueError):
                resolve_response_contract("artifact-response-v1", observer)
