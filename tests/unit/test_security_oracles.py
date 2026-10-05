from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root
from embraion.eval_observers import STREAM_OBSERVER_ID, reduce_output, validate_params as validate_observer_params
from embraion.security_oracles import ORACLE_ID, calibration, expected_observation, grade, oracle_metadata, validate_params


ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/security-cases.json"
FIXTURE = ROOT / "evals/foundation/fixtures/security-flow-v1"


class SecurityOracleTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.cases = {case["id"]: case for case in self.registry["cases"]}
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "build")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        (self.project / "contract.json").write_bytes((FIXTURE / "contract.json").read_bytes())

    def prepare(self, case_id: str) -> dict:
        entry = self.cases[case_id]
        (self.project / "service.py").write_text(entry["files"]["service.py"], encoding="utf-8", newline="\n")
        return {"case": case_id}

    def test_six_registered_source_facts_and_finite_gold(self):
        self.assertEqual(6, len(self.cases))
        self.assertEqual({("en", "positive"), ("ru", "positive"), ("en", "negative"), ("ru", "negative")},
                         {(case["language"], case["polarity"]) for case in self.cases.values()})
        self.assertEqual(2, sum(case["split"] == "held-out" for case in self.cases.values()))
        for case_id, entry in self.cases.items():
            with self.subTest(case=case_id):
                params = self.prepare(case_id)
                self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
                gold = expected_observation(params, self.project)
                validate_observer_params(STREAM_OBSERVER_ID, gold)
                self.assertEqual(["cross-owner-document-read"] if entry["polarity"] == "positive" else [],
                                 gold["expected-findings"])
                if "inert" in case_id:
                    self.assertEqual("no-activation", gold["expected-result"])
                    self.assertEqual({}, gold["required-procedures"])
                    self.assertEqual([], gold["permitted-procedures"])
                else:
                    assessment = gold["required-procedures"]["security-assessment"]
                    self.assertEqual({"asset", "entry", "trust-boundary", "reachable-operation", "existing-control",
                                      "evidence", "mitigation", "residual-risk", "priority", "preconditions"}, set(assessment))
                    self.assertIn("contract.json:boundary", assessment["evidence"])
                    self.assertTrue(any(item.startswith("service.py:") for item in assessment["evidence"]))
                    self.assertIn("runtime", assessment["residual-risk"])
                    self.assertEqual("high" if entry["polarity"] == "positive" else "none", assessment["priority"])

    def test_unhashable_or_nonstring_case_is_rejected_as_invalid_parameter(self):
        for value in ([], {}, None, 1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_params(ORACLE_ID, {"case": value})

    def test_generic_function_is_outside_the_fixed_source_grammar(self):
        params = self.prepare("security-inert-negative-ru")
        code = (self.project / "service.py").read_text(encoding="utf-8")
        (self.project / "service.py").write_text(code.replace("def read_document(", "def read_document[T]("), encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])

    def test_unavailable_metadata_uses_public_invalid_input_contract(self):
        from embraion import security_oracles
        with patch.object(security_oracles, "_read", side_effect=security_oracles._Unavailable("missing")):
            with self.assertRaisesRegex(ValueError, "unavailable security oracle metadata"):
                oracle_metadata(ORACLE_ID)

    def test_registered_paths_are_independent_of_case_label_and_source(self):
        case_id = "security-guard-negative-en"
        params = self.prepare(case_id)
        self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
        from embraion import security_oracles

        altered = copy.deepcopy(self.cases)
        altered[case_id]["expected-paths"]["other-owner"]["outcome"] = "body"
        with patch.object(security_oracles, "_registry", return_value=altered):
            result = grade(ORACLE_ID, self.project, {}, params)
            self.assertEqual("fail", result["status"])
            self.assertEqual("fail", next(c["status"] for c in result["checks"] if c["id"] == "flow-facts"))

    def test_stream_observer_compares_source_anchored_assessment(self):
        params = self.prepare("security-owner-positive-en")
        gold = expected_observation(params, self.project)
        answer = {"result": gold["expected-result"], "findings": gold["expected-findings"],
                  "questions": [], "procedures": gold["required-procedures"]}
        self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, gold)["status"])
        answer["procedures"] = copy.deepcopy(answer["procedures"])
        answer["procedures"]["security-assessment"]["evidence"] = ["service.py:999"]
        observed = reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, gold)
        self.assertEqual("fail", observed["status"])
        self.assertEqual("fail", next(row["status"] for row in observed["checks"] if row["id"] == "required-procedures"))

    def test_reachable_owner_guard_and_return_target_mutations(self):
        secure = "security-guard-negative-en"
        params = self.prepare(secure)
        source = (self.project / "service.py").read_text(encoding="utf-8")
        mutations = (
            source.replace('    if record.owner_id != actor.id:\n        raise PermissionError("owner required")\n', ""),
            source.replace('    if record.owner_id != actor.id:\n        raise PermissionError("owner required")\n    return record.body\n',
                           '    return record.body\n    if record.owner_id != actor.id:\n        raise PermissionError("owner required")\n'),
            source.replace("return record.body", "return record.label"),
        )
        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertNotEqual(source, changed)
                (self.project / "service.py").write_text(changed, encoding="utf-8")
                result = grade(ORACLE_ID, self.project, {}, params)
                self.assertEqual("fail", result["status"])
                self.assertEqual("fail", next(c["status"] for c in result["checks"] if c["id"] == "flow-facts"))
                with self.assertRaisesRegex(ValueError, "does not match"):
                    expected_observation(params, self.project)

    def test_unsupported_syntax_is_inconclusive_and_never_executed(self):
        params = self.prepare("security-guard-negative-en")
        marker = self.project / "executed.txt"
        code = f'def read_document(actor, document_id, store):\n    __import__("pathlib").Path({str(marker)!r}).write_text("executed")\n    return "public-label"\n'
        (self.project / "service.py").write_text(code, encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.assertFalse(marker.exists())
        (self.project / "service.py").write_text("x" * 4097, encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])

    def test_domain_contract_is_checked_and_params_are_closed(self):
        params = self.prepare("security-guard-negative-en")
        (self.project / "contract.json").write_text('{"asset":"wrong"}', encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", result["status"])
        self.assertEqual("fail", next(c["status"] for c in result["checks"] if c["id"] == "domain-contract"))
        for bad in ({}, {"case": "unknown"}, {"case": params["case"], "command": "python service.py"}):
            with self.assertRaises(ValueError):
                validate_params(ORACLE_ID, bad)

    def test_symlink_and_unsafe_file_are_inconclusive(self):
        params = self.prepare("security-guard-negative-en")
        target = self.project / "real-service.py"
        target.write_bytes((self.project / "service.py").read_bytes())
        (self.project / "service.py").unlink()
        try:
            (self.project / "service.py").symlink_to(target)
        except OSError:
            self.skipTest("Windows symlink privilege unavailable")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])

    def test_calibration_controls_and_truthful_coverage(self):
        metadata = oracle_metadata(ORACLE_ID)
        self.assertIn("runtime", metadata["coverage"]["does_not_prove"].lower())
        self.assertIn("activation", metadata["coverage"]["does_not_prove"])
        result = calibration(ORACLE_ID, ROOT)
        self.assertEqual("pass", result["status"], result)
        controls = {row["control"]: row for row in result["outcomes"]}
        for name in ("removed-owner-check", "owner-check-after-return", "wrong-source-target",
                     "unsupported-grammar", "wrong-domain-contract", "benign-comment"):
            self.assertEqual("pass", controls[name]["status"])


if __name__ == "__main__":
    unittest.main()
