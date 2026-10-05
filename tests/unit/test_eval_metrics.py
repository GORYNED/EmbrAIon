from __future__ import annotations

import copy
import json
import unittest

from embraion.eval_metrics import measure, rubric_metadata, validate_evidence


class MetricCoverageTests(unittest.TestCase):
    def setUp(self):
        self.host = {"status": "completed", "duration-seconds": 1.2, "usage-complete": True,
                     "tokens": {"input_tokens": 12, "output_tokens": 3, "cached_input_tokens": 8}}
        self.checks = [{"id": "wiring", "mandatory": True, "category": "quality-correctness", "status": "fail"},
                       {"id": "owned-paths", "mandatory": True, "category": "authority-scope", "status": "pass", "unauthorized-count": 0}]

    def record(self):
        return {**measure(self.host, self.checks, 0), "host": self.host, "checks": self.checks}

    def test_observed_cost_and_artifacts_have_separate_coverage(self):
        record = self.record()
        self.assertEqual(1, record["metrics"]["quality-correctness"])
        self.assertEqual(0, record["metrics"]["authority-scope"])
        self.assertEqual(15, record["metrics"]["tokens"])
        self.assertEqual(1.2, record["metrics"]["latency"])
        self.assertEqual("inconclusive", record["measurement-status"])
        self.assertEqual([], validate_evidence(record))
        for name in ("security-privacy", "false-positive-rate", "unnecessary-clarification", "unnecessary-capability-activation"):
            self.assertIsNone(record["metrics"][name])

    def test_host_failure_does_not_convert_unchanged_files_into_successful_metrics(self):
        self.host["status"] = "host-failed"
        record = measure(self.host, self.checks, 0)
        for name in ("tokens", "quality-correctness", "authority-scope"):
            self.assertIsNone(record["metrics"][name])
        self.assertEqual(1.2, record["metrics"]["latency"])

    def test_missing_output_usage_is_not_zero(self):
        del self.host["tokens"]["output_tokens"]
        self.assertIsNone(measure(self.host, self.checks, 0)["metrics"]["tokens"])

    def test_partial_per_turn_usage_cannot_pass_even_when_both_aggregate_keys_exist(self):
        self.host["usage-complete"] = False
        self.assertIsNone(measure(self.host, self.checks, 0)["metrics"]["tokens"])

    def test_inconclusive_required_check_blocks_quality_count(self):
        self.checks[0]["status"] = "inconclusive"
        self.assertIsNone(measure(self.host, self.checks, 0)["metrics"]["quality-correctness"])

    def test_broadening_coverage_or_forging_activation_zero_is_rejected(self):
        record = self.record()
        activation = next(row for row in record["metric-evidence"]["measurements"] if row["metric"] == "unnecessary-capability-activation")
        record["metrics"]["unnecessary-capability-activation"] = 0
        activation.update(value=0, status="measured", reason="observed", source="skill-read-events")
        errors = validate_evidence(record)
        self.assertIn("unsupported-metric-claim:unnecessary-capability-activation", errors)
        self.assertIn("metric-coverage-mismatch:unnecessary-capability-activation", errors)

    def test_rubric_identity_and_all_measurements_are_required(self):
        record = self.record()
        record["metric-evidence"]["rubric-digest"] = "0" * 64
        self.assertEqual(["missing-or-unknown-metric-rubric"], validate_evidence(record))
        record = self.record()
        record["metric-evidence"]["measurements"][-1] = copy.deepcopy(record["metric-evidence"]["measurements"][0])
        self.assertIn("invalid-metric-identity", validate_evidence(record))

    def test_consistent_numeric_label_cannot_replace_usage_observation(self):
        record = self.record()
        record["metrics"]["tokens"] = 0
        row = next(item for item in record["metric-evidence"]["measurements"] if item["metric"] == "tokens")
        row["value"] = 0
        self.assertIn("metric-source-mismatch:tokens", validate_evidence(record))

    def test_boolean_usage_and_invalid_clock_are_not_measurements(self):
        self.host["tokens"]["input_tokens"] = True
        self.host["duration-seconds"] = float("nan")
        record = measure(self.host, self.checks, 0)
        self.assertIsNone(record["metrics"]["tokens"])
        self.assertIsNone(record["metrics"]["latency"])
        json.dumps(record, allow_nan=False)

    def test_metadata_is_copy_safe_and_explicit_about_skill_exposure(self):
        first = rubric_metadata()
        first["metrics"]["tokens"]["unit"] = "changed"
        second = rubric_metadata()
        self.assertNotEqual(first, second)
        self.assertIn("exposure only", second["metrics"]["unnecessary-capability-activation"]["coverage"]["does-not-prove"])

    def test_finite_values_require_the_actual_observer_checks_and_matching_coverage(self):
        from embraion.eval_observers import reduce_messages
        params = {"expected-result": "unchanged", "expected-findings": [], "expected-questions": [],
                  "required-procedures": {}, "permitted-procedures": [], "security-findings": [],
                  "forbidden-marker": "EVAL_PRIVATE_0123456789ABCDEF"}
        proof = reduce_messages([json.dumps({"result": "unchanged", "findings": [], "questions": [], "procedures": {}})], True, params)
        checks = self.checks + proof["checks"]
        record = {**measure(self.host, checks, 0, observer=proof, rubric_id="finite-output-metrics-v1"),
                  "host": self.host, "checks": checks, "observer-evidence": proof}
        self.assertEqual([], validate_evidence(record))
        self.assertEqual("complete", record["measurement-status"])
        record["observer-evidence"] = copy.deepcopy(proof)
        record["observer-evidence"]["checks"].pop()
        self.assertIn("invalid-finite-observer-checks", validate_evidence(record))

    def test_stream_metrics_require_matching_version_and_assessed_progress(self):
        from embraion.eval_observers import STREAM_OBSERVER_ID, reduce_output
        params = {"expected-result": "unchanged", "expected-findings": [], "expected-questions": [],
                  "required-procedures": {}, "permitted-procedures": [], "security-findings": [],
                  "forbidden-marker": "EVAL_PRIVATE_0123456789ABCDEF"}
        answer = json.dumps({"result": "unchanged", "findings": [], "questions": [], "procedures": {}})
        proof = reduce_output(STREAM_OBSERVER_ID, ['{"progress":"reading"}', answer], True, params)
        checks = self.checks + proof["checks"]
        record = {**measure(self.host, checks, 0, observer=proof, rubric_id="finite-stream-metrics-v1"),
                  "host": self.host, "checks": checks, "observer-evidence": proof}
        self.assertEqual([], validate_evidence(record))
        self.assertEqual("complete", record["measurement-status"])
        mismatched = {**measure(self.host, checks, 0, observer=proof, rubric_id="finite-output-metrics-v1"),
                      "host": self.host, "checks": checks, "observer-evidence": proof}
        self.assertIn("missing-finite-observer-evidence", validate_evidence(mismatched))
        proof = reduce_output(STREAM_OBSERVER_ID, ["unassessed progress", answer], True, params)
        unavailable = measure(self.host, self.checks, 0, observer=proof, rubric_id="finite-stream-metrics-v1")
        self.assertEqual("inconclusive", unavailable["measurement-status"])
        self.assertIsNone(unavailable["metrics"]["false-positive-rate"])


if __name__ == "__main__":
    unittest.main()
