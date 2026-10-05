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
from embraion.research_oracles import ORACLE_ID, calibration, expected_observation, grade, oracle_metadata, validate_params


ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/research-cases.json"


class ResearchOracleTests(unittest.TestCase):
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

    def check(self, result: dict, name: str) -> str:
        return next(row["status"] for row in result["checks"] if row["id"] == name)

    def test_registered_cases_have_source_grounded_finite_decisions(self):
        self.assertEqual(6, len(self.cases))
        self.assertEqual(2, sum(case["split"] == "held-out" for case in self.cases.values()))
        self.assertEqual({"adopt": 2, "extend": 2, "build": 2},
                         {decision: sum(case["expected-facts"]["decision"] == decision
                                        for case in self.cases.values()) for decision in ("adopt", "extend", "build")})
        expected_findings = {
            "complete": [], "partial": ["partial-capability"],
            "incompatible": ["incompatible-api"], "absent": ["missing-capability"],
        }
        for case_id, entry in self.cases.items():
            with self.subTest(case=case_id):
                params = self.prepare(case_id)
                self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
                gold = expected_observation(params, self.project)
                validate_observer_params(STREAM_OBSERVER_ID, gold)
                facts = entry["expected-facts"]
                self.assertEqual(facts["decision"], gold["expected-result"])
                self.assertEqual(expected_findings[facts["capability"]], gold["expected-findings"])
                procedure = gold["required-procedures"]["research"]
                self.assertEqual(facts["decision"], procedure["decision"])
                self.assertEqual("local-evidence-sufficient", procedure["stop"])
                self.assertEqual("fixed-static-fixture", procedure["limit"])
                evidence = procedure["evidence"]
                self.assertEqual(6, len(evidence))
                self.assertTrue(all(anchor.startswith("existing.py:") for anchor in evidence[:2]))
                self.assertTrue(evidence[2].startswith("consumer.py:"))
                self.assertEqual(["request.json:required", "inventory.json:declared-signature",
                                  "ownership.json:existing-editable"], evidence[3:])
                if facts["capability"] == "absent":
                    self.assertEqual(["existing.py:absent", "existing.py:absent"], evidence[:2])

    def test_observer_rejects_unsupported_decision_and_fake_anchor(self):
        gold = expected_observation(self.prepare("research-incompatible-calibration-en"), self.project)
        answer = {"result": gold["expected-result"], "findings": gold["expected-findings"],
                  "questions": [], "procedures": gold["required-procedures"]}
        self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, gold)["status"])
        changed = copy.deepcopy(answer)
        changed["result"] = "adopt"
        self.assertEqual("fail", self.check(reduce_output(STREAM_OBSERVER_ID, [json.dumps(changed)], True, gold),
                                            "result"))
        changed = copy.deepcopy(answer)
        changed["procedures"]["research"]["evidence"][0] = "existing.py:999"
        self.assertEqual("fail", self.check(reduce_output(STREAM_OBSERVER_ID, [json.dumps(changed)], True, gold),
                                            "required-procedures"))

    def test_source_mutations_cannot_reuse_a_matching_name_as_proof(self):
        params = self.prepare("research-adopt-calibration-en")
        (self.project / "existing.py").write_text("def slugify(text):\n    return text.lower()\n", encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(result, "source-facts"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            expected_observation(params, self.project)
        self.prepare("research-adopt-calibration-en")
        (self.project / "existing.py").write_text("# slugify exists only in this comment\n", encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(result, "source-facts"))
        self.assertEqual("fail", self.check(result, "inventory-consistency"))
        self.prepare("research-adopt-calibration-en")
        (self.project / "existing.py").write_text(
            'def slugify(text, separator):\n    return text.lower().replace(" ", separator)\n', encoding="utf-8")
        (self.project / "inventory.json").write_text(
            '{"component":"existing.py","declared-signature":"two-arg"}', encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(result, "source-facts"))
        self.assertEqual("pass", self.check(result, "inventory-consistency"))

    def test_consumer_request_inventory_and_ownership_are_checked_separately(self):
        params = self.prepare("research-adopt-calibration-en")
        (self.project / "consumer.py").write_text(
            'from existing import slugify\n\n\ndef publish(text):\n    return slugify(text, "-")\n',
            encoding="utf-8")
        self.assertEqual("fail", self.check(grade(ORACLE_ID, self.project, {}, params), "consumer-contract"))
        self.prepare("research-adopt-calibration-en")
        (self.project / "request.json").write_text('{"required":{"output":"wrong"}}', encoding="utf-8")
        self.assertEqual("fail", self.check(grade(ORACLE_ID, self.project, {}, params), "request-contract"))
        self.prepare("research-adopt-calibration-en")
        request = json.loads((self.project / "request.json").read_bytes())
        request["schema-version"] = True
        (self.project / "request.json").write_text(json.dumps(request), encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(result, "request-contract"))
        self.assertEqual("pass", self.check(result, "source-facts"))
        self.prepare("research-adopt-calibration-en")
        (self.project / "inventory.json").write_text(
            '{"component":"existing.py","declared-signature":"two-arg"}', encoding="utf-8")
        self.assertEqual("fail", self.check(grade(ORACLE_ID, self.project, {}, params), "inventory-consistency"))
        params = self.prepare("research-extend-calibration-ru")
        (self.project / "ownership.json").write_text(
            '{"existing-editable":false,"new-module-allowed":true}', encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(result, "ownership-facts"))
        self.assertEqual("pass", self.check(result, "source-facts"))

    def test_expected_facts_are_independent_of_source_and_case_label(self):
        from embraion import research_oracles
        params = self.prepare("research-extend-calibration-ru")
        altered = copy.deepcopy(self.cases)
        altered[params["case"]]["expected-facts"]["decision"] = "adopt"
        with patch.object(research_oracles, "_registry", return_value=(altered, "0" * 64)):
            self.assertEqual("fail", self.check(grade(ORACLE_ID, self.project, {}, params), "recommendation-facts"))

    def test_unsupported_grammar_is_inconclusive_and_never_executed(self):
        params = self.prepare("research-adopt-calibration-en")
        marker = self.project / "executed.txt"
        (self.project / "existing.py").write_text(
            f'def slugify(text):\n    return __import__("pathlib").Path({str(marker)!r}).write_text("executed")\n',
            encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.assertFalse(marker.exists())
        (self.project / "existing.py").write_text("x" * 4097, encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.prepare("research-adopt-calibration-en")
        (self.project / "existing.py").write_text("def slugify[T](text):\n    return text.lower()\n", encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])

    def test_registry_digest_and_public_parameter_contract(self):
        from embraion import research_oracles
        metadata = oracle_metadata(ORACLE_ID)
        self.assertEqual(hashlib.sha256(REGISTRY.read_bytes()).hexdigest(), metadata["registry-digest"])
        self.assertIn("general repository reuse", metadata["coverage"]["does_not_prove"])
        for bad in ([], {}, None, 1, True, "unregistered"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                validate_params(ORACLE_ID, {"case": bad})
        with self.assertRaises(ValueError):
            validate_params(ORACLE_ID, {"case": "research-adopt-calibration-en", "command": "python existing.py"})
        with patch.object(research_oracles, "_registry", side_effect=research_oracles._Unavailable("missing")):
            with self.assertRaisesRegex(ValueError, "unavailable research oracle metadata"):
                oracle_metadata(ORACLE_ID)

    def test_calibration_controls(self):
        result = calibration(ORACLE_ID, ROOT)
        self.assertEqual("pass", result["status"], result)
        controls = {row["control"]: row for row in result["outcomes"]}
        for name in ("contradictory-source", "missing-capability", "incompatible-api",
                     "contradictory-inventory", "wrong-consumer-api", "benign-comment",
                     "unsupported-grammar", "partial-frozen"):
            self.assertEqual("pass", controls[name]["status"])


if __name__ == "__main__":
    unittest.main()
