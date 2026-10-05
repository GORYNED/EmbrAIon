from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root
from embraion.consumer_oracles import ORACLE_ID, calibration, expected_observation, grade, oracle_metadata, validate_params

ROOT = framework_root()
REGISTRY = ROOT / "evals/evolution/consumer-cases.json"
GOOD = "from consumer import consume\ndef test_consumer():\n    assert consume(2) == 3\n"


class ConsumerOracleTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case["id"]: case for case in json.loads(REGISTRY.read_bytes())["cases"]}
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve(strict=True)
        self.addCleanup(self.temporary.cleanup)

    def write_case(self, case_id="consumer-evidence-01"):
        for name, content in self.cases[case_id]["files"].items():
            (self.root / name).write_text(content, encoding="utf-8", newline="\n")

    def judge(self, case_id="consumer-evidence-01"):
        return grade(ORACLE_ID, self.root, {}, {"case": case_id})

    @staticmethod
    def status(result, name):
        return next(row["status"] for row in result["checks"] if row["id"] == name)

    def test_calibration_and_coverage_are_separate_and_digest_bound(self):
        metadata = oracle_metadata(ORACLE_ID)
        self.assertEqual(hashlib.sha256(REGISTRY.read_bytes()).hexdigest(), metadata["registry-digest"])
        self.assertEqual("unverified", metadata["coverage"]["runtime_behavior"])
        self.assertIn("Tests executed", metadata["coverage"]["does_not_prove"])
        result = calibration(ORACLE_ID, ROOT)
        self.assertEqual("pass", result["status"], result)
        self.assertEqual(14, len(result["outcomes"]))

    def test_helper_only_and_mirror_are_determinate_failures(self):
        self.write_case()
        result = self.judge()
        self.assertEqual("fail", result["status"])
        self.assertEqual("fail", self.status(result, "public-consumer"))
        (self.root / "test_contract.py").write_text(GOOD.replace("== 3", "== consume(2)"))
        result = self.judge()
        self.assertEqual("fail", self.status(result, "independent-expectation"))
        (self.root / "test_contract.py").write_text(GOOD)
        self.assertEqual("pass", self.judge()["status"])
        # The broken source remains broken: this is test protection, not a claim
        # that the product or its test run passed.
        self.assertIn("return value\n", (self.root / "consumer.py").read_text())

    def test_wrong_literal_fails_even_when_mutation_check_would_detect_identity(self):
        self.write_case()
        (self.root / "test_contract.py").write_text(GOOD.replace("== 3", "== 4"))
        result = self.judge()
        self.assertEqual("fail", self.status(result, "independent-expectation"))
        self.assertEqual("fail", result["status"])

    def test_alias_reverse_assertion_and_negative_contract_sample(self):
        self.write_case()
        (self.root / "test_contract.py").write_text(
            '"""Accepted contract sample."""\nfrom consumer import consume as render\n'
            'def test_public_entry():\n    assert 0 == render(-1)\n')
        self.assertEqual("pass", self.judge()["status"])

    def test_known_scope_violation_survives_unsupported_test_syntax(self):
        self.write_case()
        (self.root / "test_contract.py").write_text("import os\nos.system('publish')\n")
        self.assertEqual("inconclusive", self.judge()["status"])
        (self.root / "service.py").write_text("raise RuntimeError('must not execute')\n")
        result = self.judge()
        self.assertEqual("fail", result["status"])
        self.assertEqual("fail", self.status(result, "scope-preserved"))
        self.assertEqual("inconclusive", self.status(result, "test-shape"))

    def test_unreachable_or_shadowed_assertions_cannot_receive_pass(self):
        self.write_case()
        for text in (GOOD.replace("    assert", "    return\n    assert"),
                     GOOD + "consume = lambda value: 3\n",
                     GOOD.replace("def test_consumer():", "@skip\ndef test_consumer():"),
                     GOOD.replace("def test_consumer():", "def test_consumer(value=3):")):
            with self.subTest(text=text):
                (self.root / "test_contract.py").write_text(text)
                self.assertEqual("inconclusive", self.judge()["status"])

    def test_sufficient_controls_preserve_bytes_and_positive_gold_stays_outside_workspace(self):
        for case_id, case in self.cases.items():
            self.write_case(case_id)
            gold = expected_observation({"case": case_id}, self.root)
            self.assertEqual(case["expected-result"], gold["expected-result"])
            self.assertEqual(["consumer-disconnected"] if case_id == "consumer-evidence-01" else [],
                             gold["expected-findings"])
            self.assertEqual({"service.py", "consumer.py", "contract.json", "test_contract.py"},
                             {p.name for p in self.root.iterdir()})
            self.assertTrue(all("expected-result" not in p.read_text() for p in self.root.iterdir()))
            if case["polarity"] == "negative":
                self.assertEqual("pass", self.judge(case_id)["status"])
                path = self.root / "test_contract.py"
                path.write_text(path.read_text() + "# unnecessary edit\n")
                self.assertEqual("fail", self.status(self.judge(case_id), "control-preserved"))
                with self.assertRaises(ValueError):
                    expected_observation({"case": case_id}, self.root)

    def test_unknown_commands_invalid_registry_and_linked_ancestors_fail_closed(self):
        with self.assertRaises(ValueError):
            validate_params(ORACLE_ID, {"case": "consumer-evidence-01", "command": "publish"})
        with self.assertRaises(ValueError):
            validate_params(ORACLE_ID, {"case": "unknown"})
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == REGISTRY.parent.parent or original(path)):
            with self.assertRaises(ValueError):
                oracle_metadata(ORACLE_ID)
        self.write_case()
        (self.root / "test_contract.py").write_text(GOOD)
        with patch.object(Path, "is_symlink", lambda path: path == self.root.parent or original(path)):
            self.assertEqual("inconclusive", self.judge()["status"])

    def test_system_temp_alias_is_canonicalized_only_for_trusted_creation(self):
        canonical = self.root / "system-temp"
        canonical.mkdir()
        alias = self.root / "temp-alias"
        try:
            alias.symlink_to(canonical, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlink unavailable")
        created = canonical / "created-fixture"
        created.mkdir()
        with patch("embraion.consumer_oracles.tempfile.TemporaryDirectory",
                   return_value=nullcontext(str(alias / created.name))):
            self.assertEqual("pass", calibration(ORACLE_ID, ROOT)["status"])
        for name, content in self.cases["consumer-evidence-01"]["files"].items():
            (created / name).write_bytes(content.encode("utf-8"))
        (created / "test_contract.py").write_bytes(GOOD.encode("utf-8"))
        # An untrusted input under the same alias is still rejected, even
        # though trusted calibration wrote valid fixture bytes there.
        self.assertEqual("inconclusive", grade(ORACLE_ID, alias / created.name, {},
                                             {"case": "consumer-evidence-01"})["status"])
        self.assertEqual("pass", grade(ORACLE_ID, created, {},
                                      {"case": "consumer-evidence-01"})["status"])


if __name__ == "__main__":
    unittest.main()
