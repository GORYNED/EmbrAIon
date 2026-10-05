from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root
from embraion.debug_oracles import ORACLE_ID, calibration, expected_observation, grade, oracle_metadata, validate_params
from embraion.eval_observers import STREAM_OBSERVER_ID, reduce_output, validate_params as validate_observer_params


ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/debug-cases.json"


class DebugOracleTests(unittest.TestCase):
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

    def change_json(self, name: str, field: str, value) -> None:
        path = self.project / name
        body = json.loads(path.read_text(encoding="utf-8"))
        body[field] = value
        path.write_text(json.dumps(body), encoding="utf-8")

    def check(self, report: dict, check_id: str) -> str:
        return next(row["status"] for row in report["checks"] if row["id"] == check_id)

    def test_six_registered_cases_have_finite_source_anchored_gold(self):
        self.assertEqual(6, len(self.cases))
        self.assertEqual(2, sum(case["split"] == "held-out" for case in self.cases.values()))
        self.assertEqual({"en", "ru"}, {case["language"] for case in self.cases.values()})
        expected = {
            "debug-competing-compute-en": ("compute-cause", []),
            "debug-contradictory-cache-ru": ("cache-cause", ["unsupported-leading-hypothesis"]),
            "debug-repeated-cache-en": ("cache-cause", ["unsupported-leading-hypothesis", "repeated-failed-fix"]),
            "debug-typo-control-en": ("typo-cause", []),
            "debug-competing-heldout-ru": ("cache-cause", []),
            "debug-typo-heldout-ru": ("typo-cause", []),
        }
        for case_id in sorted(self.cases):
            with self.subTest(case=case_id):
                params = self.prepare(case_id)
                self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
                gold = expected_observation(params, self.project)
                validate_observer_params(STREAM_OBSERVER_ID, gold)
                self.assertEqual(expected[case_id], (gold["expected-result"], gold["expected-findings"]))
                procedure = gold["required-procedures"]["debugging"]
                if self.cases[case_id]["expected-facts"]["mode"] == "simple":
                    self.assertEqual({"cause", "next-step", "evidence"}, set(procedure))
                    self.assertEqual(3, len(procedure["evidence"]))
                    self.assertEqual(["contract.json:expected", "observations.json:direct"],
                                     procedure["evidence"][1:])
                else:
                    self.assertEqual({"cause", "leading", "competing", "narrative", "discriminator",
                                      "attempts", "next-step", "evidence"}, set(procedure))
                    self.assertEqual(8, len(procedure["evidence"]))
                    self.assertTrue(all(anchor.startswith("source.py:") for anchor in procedure["evidence"][:3]))
                    self.assertEqual("cache-on-vs-off", procedure["discriminator"])

    def test_observer_rejects_recycled_narrative_and_fake_anchor(self):
        gold = expected_observation(self.prepare("debug-contradictory-cache-ru"), self.project)
        answer = {"result": gold["expected-result"], "findings": gold["expected-findings"],
                  "questions": [], "procedures": gold["required-procedures"]}
        self.assertEqual("pass", reduce_output(STREAM_OBSERVER_ID, [json.dumps(answer)], True, gold)["status"])
        recycled = copy.deepcopy(answer)
        recycled["result"] = "compute-cause"
        recycled["procedures"]["debugging"]["narrative"] = "retain"
        observed = reduce_output(STREAM_OBSERVER_ID, [json.dumps(recycled)], True, gold)
        self.assertEqual("fail", observed["status"])
        self.assertEqual("fail", self.check(observed, "result"))
        self.assertEqual("fail", self.check(observed, "required-procedures"))
        forged = copy.deepcopy(answer)
        forged["procedures"]["debugging"]["evidence"][4] = "observations.json:invented"
        self.assertEqual("fail", self.check(reduce_output(STREAM_OBSERVER_ID, [json.dumps(forged)], True, gold),
                                            "required-procedures"))

    def test_repeated_failed_fix_requires_checked_snapshots(self):
        params = self.prepare("debug-repeated-cache-en")
        gold = expected_observation(params, self.project)
        procedure = gold["required-procedures"]["debugging"]
        self.assertEqual("revise", procedure["narrative"])
        self.assertEqual("repeated-compute", procedure["attempts"])
        self.assertEqual("cache", procedure["cause"])
        attempts = json.loads((self.project / "attempts.json").read_text(encoding="utf-8"))
        attempts["records"][0]["observed-cache-on"] = 42
        self.change_json("attempts.json", "records", attempts["records"])
        report = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(report, "attempt-consistency"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            expected_observation(params, self.project)
        self.prepare("debug-repeated-cache-en")
        attempts = json.loads((self.project / "attempts.json").read_text(encoding="utf-8"))
        current = (self.project / "source.py").read_text(encoding="utf-8")
        attempts["records"][0]["source"] = current + "# comment-only edit\n"
        attempts["records"][0]["revision"] = hashlib.sha256(
            attempts["records"][0]["source"].encode()).hexdigest()
        self.change_json("attempts.json", "records", attempts["records"])
        self.assertEqual("fail", self.check(grade(ORACLE_ID, self.project, {}, params),
                                            "attempt-consistency"))

    def test_source_and_recorded_observation_must_agree(self):
        params = self.prepare("debug-competing-compute-en")
        source = (self.project / "source.py").read_text(encoding="utf-8")
        (self.project / "source.py").write_text(source.replace("return value + 2", "return value + 1", 1),
                                                encoding="utf-8")
        observation = json.loads((self.project / "observations.json").read_text(encoding="utf-8"))
        observation["source-revision"] = hashlib.sha256((self.project / "source.py").read_bytes()).hexdigest()
        self.change_json("observations.json", "source-revision", observation["source-revision"])
        report = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(report, "observation-consistency"))
        self.assertEqual("pass", self.check(report, "revision-freshness"))
        self.prepare("debug-competing-compute-en")
        self.change_json("observations.json", "source-revision", "0" * 64)
        report = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(report, "revision-freshness"))
        self.assertEqual("pass", self.check(report, "observation-consistency"))

    def test_wrong_target_and_narrative_do_not_override_observations(self):
        params = self.prepare("debug-contradictory-cache-ru")
        self.change_json("contract.json", "entry", "compute")
        report = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(report, "target-contract"))
        self.prepare("debug-contradictory-cache-ru")
        self.change_json("narrative.json", "leading", "cache")
        self.change_json("narrative.json", "competing", "compute")
        report = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", self.check(report, "narrative-facts"))
        self.assertEqual("pass", self.check(report, "observation-consistency"))
        for field, value in (("schema-version", True), ("input", 41.0), ("expected", 42.0)):
            with self.subTest(field=field):
                self.prepare("debug-contradictory-cache-ru")
                self.change_json("contract.json", field, value)
                report = grade(ORACLE_ID, self.project, {}, params)
                self.assertEqual("fail", self.check(report, "target-contract"))
                self.assertEqual("pass", self.check(report, "observation-consistency"))

    def test_unknown_observations_or_source_grammar_are_inconclusive_and_never_executed(self):
        params = self.prepare("debug-competing-compute-en")
        self.change_json("observations.json", "cache-off", 999)
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.prepare("debug-competing-compute-en")
        self.change_json("observations.json", "cache-on", 43)
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.prepare("debug-competing-compute-en")
        marker = self.project / "executed.txt"
        (self.project / "source.py").write_text(
            f'def compute(value):\n    return __import__("pathlib").Path({str(marker)!r}).write_text("executed")\n',
            encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.assertFalse(marker.exists())

    def test_independent_registry_facts_and_public_metadata_contract(self):
        from embraion import debug_oracles
        params = self.prepare("debug-competing-compute-en")
        altered = copy.deepcopy(self.cases)
        altered[params["case"]]["expected-facts"]["cause"] = "cache"
        with patch.object(debug_oracles, "_registry", return_value=(altered, "0" * 64)):
            self.assertEqual("fail", self.check(grade(ORACLE_ID, self.project, {}, params), "source-facts"))
        metadata = oracle_metadata(ORACLE_ID)
        self.assertEqual(hashlib.sha256(REGISTRY.read_bytes()).hexdigest(), metadata["registry-digest"])
        self.assertIn("general causal debugging", metadata["coverage"]["does_not_prove"])
        for bad in ([], {}, None, 1, True, "unknown"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                validate_params(ORACLE_ID, {"case": bad})
        with self.assertRaises(ValueError):
            validate_params(ORACLE_ID, {"case": params["case"], "command": "python source.py"})
        with patch.object(debug_oracles, "_registry", side_effect=debug_oracles._Unavailable("missing")):
            with self.assertRaisesRegex(ValueError, "unavailable debug oracle metadata"):
                oracle_metadata(ORACLE_ID)

    def test_calibration_controls(self):
        report = calibration(ORACLE_ID, ROOT)
        self.assertEqual("pass", report["status"], report)
        controls = {row["control"]: row for row in report["outcomes"]}
        for name in ("contradictory-source", "wrong-target", "stale-observed-revision",
                     "unsupported-grammar", "benign-comment", "contradictory-attempt"):
            self.assertEqual("pass", controls[name]["status"])


if __name__ == "__main__":
    unittest.main()
