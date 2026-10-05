from __future__ import annotations
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from embraion.common import framework_root
from embraion.refactor_oracles import ORACLE_ID, calibration, grade, oracle_metadata, validate_params


class RefactorOracleTests(unittest.TestCase):
    def setUp(self):
        self.root = framework_root()
        self.cases = {row["id"]: row for row in json.loads((self.root / "evals/evolution/refactor-cases.json").read_bytes())["cases"]}
        temporary = tempfile.TemporaryDirectory(dir=self.root / "build")
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)

    def prepare(self, case_id="refactor-move-en", moved=True):
        row = self.cases[case_id]
        for name, content in row["files"].items():
            (self.project / name).write_text(content, encoding="utf-8", newline="\n")
        request = json.loads(row["files"]["request.json"])
        if moved and request["action"] == "move":
            target = self.project / request["target"]
            target.parent.mkdir()
            target.write_text(row["files"]["legacy.py"], encoding="utf-8", newline="\n")
            module = request["target"].removesuffix(".py").replace("/", ".")
            (self.project / "legacy.py").write_text(f"from {module} import normalize\n", encoding="utf-8", newline="\n")
        elif request["action"] == "typo":
            (self.project / "legacy.py").write_text(row["files"]["legacy.py"].replace("Tranform", "Transform"), encoding="utf-8", newline="\n")
        return {"case": case_id}

    def test_calibration_covers_valid_controls_and_behavior_identity_mutations(self):
        result = calibration()
        self.assertEqual("pass", result["status"])
        self.assertEqual(15, len(result["outcomes"]))
        self.assertIn("model reasoning order", oracle_metadata()["coverage"]["does_not_prove"])

    def test_original_behavior_is_fixed_before_structural_change(self):
        params = self.prepare()
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("pass", result["status"])
        self.assertEqual([0, 1, 2, 42], result["characterization"]["original-outputs"])
        self.assertEqual("unverified", result["characterization"]["candidate-pre-mutation-reasoning"])
        (self.project / "ops/normalizer.py").write_text("def normalize(value):\n    return value + 2\n", encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", result["status"])
        self.assertEqual([0, 1, 2, 42], result["characterization"]["original-outputs"])
        self.assertEqual(2, result["characterization"]["public-delta"])

    def test_correct_behavior_without_requested_move_is_not_completion(self):
        params = self.prepare(moved=False)
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", result["status"])
        statuses = {c["id"]: c["status"] for c in result["checks"]}
        self.assertEqual("pass", statuses["public-api"])
        self.assertEqual("fail", statuses["structural-goal"])

    def test_alias_consumer_and_alternate_destination_are_characterized(self):
        result = grade(ORACLE_ID, self.project, {}, self.prepare("refactor-heldout-ru"))
        self.assertEqual("pass", result["status"])
        self.assertEqual(1, result["characterization"]["consumer-delta"])

    def test_typo_control_rejects_unrequested_reorganization(self):
        params = self.prepare("refactor-typo-en")
        self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
        (self.project / "ops").mkdir()
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", result["status"])

    def test_fixture_source_is_never_executed(self):
        params = self.prepare()
        marker = self.project / "executed"
        (self.project / "ops/normalizer.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n", encoding="utf-8")
        self.assertEqual("inconclusive", grade(ORACLE_ID, self.project, {}, params)["status"])
        self.assertFalse(marker.exists())

    def test_unknown_case_and_arbitrary_parameters_are_rejected(self):
        for params in ({"case": "unknown"}, {"case": "refactor-move-en", "command": "anything"}):
            with self.assertRaises(ValueError):
                validate_params(ORACLE_ID, params)

    def test_empty_package_initializer_is_allowed_but_new_behavior_is_not(self):
        params = self.prepare()
        initializer = self.project / "ops/__init__.py"
        initializer.write_text("# Namespace only\n", encoding="utf-8")
        self.assertEqual("pass", grade(ORACLE_ID, self.project, {}, params)["status"])
        initializer.write_text("ENABLED = True\n", encoding="utf-8")
        result = grade(ORACLE_ID, self.project, {}, params)
        self.assertEqual("fail", result["status"])
        self.assertTrue(any(c["id"] == "package-initializer" and c["status"] == "fail" for c in result["checks"]))

    def test_initial_digest_cannot_redefine_characterization(self):
        params = self.prepare()
        with self.assertRaisesRegex(ValueError, "initial fixture differs"):
            grade(ORACLE_ID, self.project, {"legacy.py": "0" * 64}, params)

    def test_registry_missing_malformed_and_oversized_are_not_candidate_failures(self):
        params = self.prepare()
        registry = self.project / "registry.json"
        with patch("embraion.refactor_oracles._REGISTRY", str(registry)):
            for content in (None, b"{bad", b" " * 100001, b'{"cases": [false]}'):
                if content is not None:
                    registry.write_bytes(content)
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    oracle_metadata()
                proof = grade(ORACLE_ID, self.project, {}, params)
                self.assertEqual("inconclusive", proof["status"])
                self.assertEqual([], proof["checks"])

    def test_registry_link_is_rejected_before_read(self):
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                oracle_metadata()


if __name__ == "__main__":
    unittest.main()
