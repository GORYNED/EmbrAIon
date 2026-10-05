from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from embraion.eval_oracles import calibration, grade, oracle_metadata, validate_params


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals/foundation/fixtures/wiring-v1"
UPGRADE_FIXTURE = ROOT / "evals/foundation/fixtures/upgrade-scope-v1"


class OracleTests(unittest.TestCase):
    def test_registry_check_ids_match_the_actual_coverage(self) -> None:
        for oracle_id, fixture in (("wiring-v1", FIXTURE), ("upgrade-scope-v1", UPGRADE_FIXTURE)):
            with self.subTest(oracle=oracle_id):
                self.assertEqual(set(oracle_metadata(oracle_id)["check-ids"]),
                                 {check["id"] for check in grade(oracle_id, fixture, {}, {})["checks"]})

    def test_upgrade_scope_calibration_detects_local_scope_and_claim_mutations(self) -> None:
        result = calibration("upgrade-scope-v1", ROOT)
        self.assertEqual("pass", result["status"], result)
        self.assertEqual(8, len(result["outcomes"]))
        controls = {item["control"] for item in result["outcomes"]}
        self.assertIn("new-release-request", controls)
        self.assertIn("new-false-claim-field", controls)
        metadata = oracle_metadata("upgrade-scope-v1")
        self.assertTrue(metadata["coverage"]["mandatory"])
        self.assertIn("remote publication", metadata["coverage"]["does_not_prove"])

    def test_upgrade_scope_fixture_is_initially_unsatisfied_and_params_are_fixed(self) -> None:
        result = grade("upgrade-scope-v1", UPGRADE_FIXTURE, {}, {})
        self.assertEqual("fail", result["status"])
        self.assertEqual("fail", next(check for check in result["checks"]
                                      if check["id"] == "framework-target")["status"])
        self.assertEqual("unverified", result["checks"][-1]["status"])
        with self.assertRaises(ValueError):
            validate_params("upgrade-scope-v1", {"target": "0.23.0"})
        with self.assertRaises(ValueError):
            grade("upgrade-scope-v1", UPGRADE_FIXTURE, {"../README.md": "0" * 64}, {})

    def test_controls_prove_correctness_and_mutation_coverage(self) -> None:
        result = calibration("wiring-v1", ROOT)
        self.assertEqual("pass", result["status"], result)
        self.assertEqual(9, len(result["outcomes"]))
        self.assertEqual(
            {"disabled-wiring", "wrong-target", "disconnected-dispatcher", "missed-consumer", "removed-obligation",
             "false-completion-claim", "stale-checkpoint"},
            {item["control"] for item in result["outcomes"] if item["expected"] == "fail"},
        )
        metadata = oracle_metadata("wiring-v1")
        self.assertTrue(metadata["correctness"]["mandatory"])
        self.assertTrue(metadata["coverage"]["mandatory"])
        for section in ("correctness", "coverage"):
            self.assertTrue(metadata[section]["proves"])
            self.assertTrue(metadata[section]["does_not_prove"])
            self.assertTrue(metadata[section]["prerequisites"])

    def test_positive_is_static_and_runtime_remains_unverified(self) -> None:
        report = grade("wiring-v1", FIXTURE, {}, {})
        self.assertEqual("pass", report["status"])
        self.assertEqual(7, report["metrics"]["mandatory_passed"])
        self.assertEqual("unverified", report["checks"][-1]["status"])
        self.assertFalse(report["checks"][-1]["mandatory"])
        self.assertEqual("unverified", report["coverage"]["external_action"])

    def test_unknown_oracle_and_parameters_reject(self) -> None:
        with self.assertRaises(ValueError):
            oracle_metadata("unknown")
        with self.assertRaises(ValueError):
            validate_params("wiring-v1", {"target": "chosen-by-candidate"})
        with self.assertRaises(ValueError):
            grade("wiring-v1", FIXTURE, {"../outside": "0" * 64}, {})

    def test_valid_utf8_bom_is_not_an_oracle_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for file in FIXTURE.iterdir():
                if file.is_file():
                    shutil.copyfile(file, project / file.name)
            for name in ("consumer.py", "contract.json"):
                path = project / name
                path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
            self.assertEqual("pass", grade("wiring-v1", project, {}, {})["status"])

    def test_missing_candidate_file_fails_but_unsafe_path_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory(dir=FIXTURE) as temporary:
            project = Path(temporary)
            for file in FIXTURE.iterdir():
                if file.is_file():
                    shutil.copyfile(file, project / file.name)
            (project / "consumer.py").unlink()
            report = grade("wiring-v1", project, {}, {})
            self.assertEqual("fail", report["status"])
            self.assertEqual("fail", next(item for item in report["checks"] if item["id"] == "consumer")["status"])
            try:
                (project / "consumer.py").symlink_to(FIXTURE / "consumer.py")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            self.assertEqual("inconclusive", grade("wiring-v1", project, {}, {})["status"])

    def test_syntax_errors_are_candidate_failures_not_checker_success(self) -> None:
        with tempfile.TemporaryDirectory(dir=FIXTURE) as temporary:
            project = Path(temporary)
            for file in FIXTURE.iterdir():
                if file.is_file():
                    shutil.copyfile(file, project / file.name)
            (project / "router.py").write_text("ROUTES = {", encoding="utf-8")
            report = grade("wiring-v1", project, {}, {})
            self.assertEqual("fail", report["status"])
            self.assertEqual("fail", next(item for item in report["checks"] if item["id"] == "registration")["status"])

    def test_oversize_input_is_checker_inconclusive_without_leaking_text(self) -> None:
        with tempfile.TemporaryDirectory(dir=FIXTURE) as temporary:
            project = Path(temporary)
            for file in FIXTURE.iterdir():
                if file.is_file():
                    shutil.copyfile(file, project / file.name)
            marker = "candidate-secret-marker"
            (project / "consumer.py").write_text(marker * 4000, encoding="utf-8")
            report = grade("wiring-v1", project, {}, {})
            self.assertEqual("inconclusive", report["status"])
            self.assertNotIn(marker, str(report))


if __name__ == "__main__":
    unittest.main()
