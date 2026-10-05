from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.experiment_gates import experiment_digest, promotion_eligibility as _promotion_eligibility, validate_failure_corpus
from embraion.eval_oracles import oracle_metadata
from embraion.eval_metrics import measure, rubric_metadata
from embraion.experiment_evals import identity, _files


ROOT = Path(__file__).resolve().parents[2]
METRICS = ("quality-correctness", "authority-scope", "security-privacy", "false-positive-rate",
           "unnecessary-clarification", "unnecessary-capability-activation", "tokens", "latency")


def evidence() -> tuple[dict, dict]:
    limits = {metric: 0 for metric in METRICS}
    experiment = {"schema-version": 1, "id": "scope-trial", "baseline": "base", "candidate": "candidate", "suite-digest": "c" * 64,
                  "baseline-reports": [{"id": "prior", "path": "prior.json", "digest": "a" * 64,
                                        "suite-path": "prior-suite.json", "suite-digest": "b" * 64}],
                  "change-ids": ["scope-rule"], "required-cases": ["scope"], "target-cases": ["scope"],
                  "traceability": [{"change-id": "scope-rule", "source-kind": "observed-problem",
                                    "observed-problem": "Framework upgrade expanded scope", "proposed-rule": "Keep requested action bounded",
                                    "capability-paths": ["core/skills/debugging/SKILL.md"], "scenarios": ["scope"],
                                    "expected-result": "Upgrade pin only"}],
                  "cases": [{"case": "scope", "limits": limits, "risk": "ordinary", "attempts": 5,
                             "baseline-manifest-digest": "a" * 64, "baseline-report-id": "prior",
                             "justification-id": "scope-budget"}]}
    base_metrics = {metric: 0 for metric in METRICS}
    base_metrics["quality-correctness"] = 1
    candidate_metrics = {metric: 0 for metric in METRICS}
    report = {"schema-version": 2, "baseline-id": "base", "phase": "confirmatory", "suite-digest": "c" * 64, "experiment-digest": experiment_digest(experiment),
              "variants": [{"id": "base", "manifest-digest": "a" * 64},
                           {"id": "candidate", "manifest-digest": "b" * 64,
                            "changes": [{"path": "core/skills/debugging/SKILL.md", "before": "a" * 64, "after": "b" * 64}]}],
              "case-contracts": [{"case": "scope", "risk": "ordinary", "language": "en", "polarity": "positive", "corpus-id": None,
                                  "owned-paths-required": False,
                                  "oracles": [{"id": "wiring-v1", "mandatory": True, "required-checks": []}]}],
              "inputs": {"corpus": identity(_files(ROOT / "evals/corpus")),
                         "oracle-metadata": {"wiring-v1": identity(oracle_metadata("wiring-v1"))},
                         "fixtures": {"scope": "f" * 64}},
              "planned-runs": [{"case": "scope", "variant": variant, "attempt": 1}
                               for variant in ("base", "candidate")],
              "runs": [{"case": "scope", "variant": "base", "attempt": 1, "status": "fail",
                        "checks": [{"id": "scope", "status": "fail", "mandatory": True,
                                    "category": "quality-correctness"}], "metrics": base_metrics, "contamination": []},
                       {"case": "scope", "variant": "candidate", "attempt": 1, "status": "pass",
                        "checks": [{"id": "scope", "status": "pass", "mandatory": True,
                                    "category": "quality-correctness"}], "metrics": candidate_metrics,
                        "contamination": []}],
              "comparisons": [{"case": "scope", "attempt": 1, "baseline": "base",
                               "candidate": "candidate", "status": "improved"}],
              "calibration": [{"id": "wiring-v1", "status": "pass",
                               "coverage": oracle_metadata("wiring-v1")["coverage"],
                               "correctness": oracle_metadata("wiring-v1")["correctness"]}],
              "projection-checks": {"base": {"status": "pass"}, "candidate": {"status": "pass"}},
              "native-preflight": {"status": "pass"}, "contamination": []}
    for attempt in range(2, 6):
        for variant in ("base", "candidate"):
            report["planned-runs"].append({"case": "scope", "variant": variant, "attempt": attempt})
            run = copy.deepcopy(next(r for r in report["runs"] if r["variant"] == variant))
            run["attempt"] = attempt
            report["runs"].append(run)
        comparison = copy.deepcopy(report["comparisons"][0])
        comparison["attempt"] = attempt
        report["comparisons"].append(comparison)
    for run in report["runs"]:
        run["host"] = {"status": "completed"}
        run["checks"] = [{**check, "oracle": "wiring-v1", "status": "fail" if run["variant"] == "base" and check["id"] == "registration" else "pass"}
                         for check in oracle_metadata("wiring-v1")["check-contracts"] if check["mandatory"]]
    report["metric-rubric"] = rubric_metadata()
    report["inputs"]["metric-rubric"] = report["metric-rubric"]["digest"]
    for run in report["runs"]:
        run["measurement-status"] = "complete"
        run["metric-evidence"] = {"rubric-id": "foundation-metrics-v1"}
    report["measurement-status"] = "complete"
    report.update({"host": "codex", "environment": {}, "evidence-kind": "live-native-full-core", "limitations": []})
    suite = _synthetic_suite(report)
    report["suite-digest"] = identity(suite)
    report["inputs"]["suite"] = report["suite-digest"]
    experiment["suite-digest"] = report["suite-digest"]
    report["experiment-digest"] = experiment_digest(experiment)
    report["status"] = "fail"
    return report, experiment


def _synthetic_suite(report):
    return {"schema-version": 2, "baseline": "base", "variants": [
        {"id": "base", "manifest-digest": "a" * 64}], "cases": [
        {"id": contract["case"], "fixture": "fixture", "prompt": "scope prompt", "risk": contract["risk"],
         "oracles": contract["oracles"], "language": contract["language"], "polarity": contract["polarity"]}
        for contract in report.get("case-contracts", []) if isinstance(contract, dict)]}


def _binding_args(report):
    """Synthetic prior evidence is separate from the candidate under test."""
    suite = _synthetic_suite(report)
    prior = copy.deepcopy(report)
    prior["phase"] = "baseline"
    prior["variants"] = [v for v in prior.get("variants", []) if v.get("id") == "base"]
    prior["planned-runs"] = [p for p in prior.get("planned-runs", []) if p.get("variant") == "base"]
    prior["runs"] = [r for r in prior.get("runs", []) if r.get("variant") == "base"]
    prior["comparisons"] = []
    prior["projection-checks"] = {"base": prior.get("projection-checks", {}).get("base", {})}
    prior["inputs"]["suite"] = identity(suite)
    prior["suite-digest"] = identity(suite)
    prior["status"] = "pass" if prior["runs"] and all(r.get("status") == "pass" for r in prior["runs"]) else "fail"
    return {"baseline_reports": {"prior": {
        "report": prior, "suite": copy.deepcopy(suite), "fixture-digests": {"scope": "f" * 64}}},
        "candidate_suite": {"suite": suite, "fixture-digests": {"scope": "f" * 64}}}


def promotion_eligibility(report, experiment):
    return _promotion_eligibility(report, experiment, **_binding_args(report))


class ExperimentGateTests(unittest.TestCase):
    def setUp(self):
        # Synthetic records isolate pairing, budgets and promotion contracts.
        # Actual metric evidence is tested without this stub below and in
        # test_eval_metrics; these records are not live evidence.
        validator = patch("embraion.eval_metrics.validate_evidence", return_value=[])
        validator.start()
        self.addCleanup(validator.stop)

    def test_matched_improvement_is_evidence_ready_without_promotion_authority(self) -> None:
        report, experiment = evidence()
        result = promotion_eligibility(report, experiment)
        self.assertEqual("eligible", result["status"], result)
        self.assertFalse(result["authorizes_core_promotion"])
        self.assertTrue(result["review_required"])

    def test_legacy_or_unbound_budget_cannot_be_promoted(self) -> None:
        report, experiment = evidence()
        del experiment["baseline-reports"]
        self.assertIn("missing-baseline-report-references", _promotion_eligibility(report, experiment)["reasons"])
        report, experiment = evidence()
        del experiment["cases"][0]["baseline-report-id"]
        report["experiment-digest"] = experiment_digest(experiment)
        result = _promotion_eligibility(report, experiment, **_binding_args(report))
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("unbound-baseline-budget:scope", result["reasons"])

    def test_historical_baseline_without_measurement_fixture_digest_is_inconclusive(self) -> None:
        report, experiment = evidence()
        args = _binding_args(report)
        del args["baseline_reports"]["prior"]["report"]["inputs"]["fixtures"]
        result = _promotion_eligibility(report, experiment, **args)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("baseline-fixture-provenance-unavailable:scope", result["reasons"])
        report, experiment = evidence()
        args = _binding_args(report)
        args["baseline_reports"]["prior"]["report"]["inputs"]["fixtures"]["scope"] = "0" * 64
        self.assertIn("baseline-fixture-mismatch:scope",
                      _promotion_eligibility(report, experiment, **args)["reasons"])

    def test_baseline_oracle_metadata_cannot_be_missing_or_rebound(self) -> None:
        for replacement in (None, {"wiring-v1": "0" * 64}):
            report, experiment = evidence()
            args = _binding_args(report)
            args["baseline_reports"]["prior"]["report"]["inputs"]["oracle-metadata"] = replacement
            result = _promotion_eligibility(report, experiment, **args)
            self.assertEqual("inconclusive", result["status"])
            self.assertIn("baseline-oracle-metadata-incomplete:scope", result["reasons"])

    def test_missing_oracle_metadata_cannot_erase_independent_candidate_safety_failure(self) -> None:
        report, experiment = evidence()
        args = _binding_args(report)
        candidate = next(r for r in report["runs"] if r["variant"] == "candidate")
        candidate["checks"].append({"id": "synthetic-disclosure", "status": "fail",
                                    "category": "security-privacy", "mandatory": True,
                                    "observed-violation": True})
        with patch("embraion.eval_oracles.oracle_metadata", side_effect=ValueError("missing metadata")):
            result = _promotion_eligibility(report, experiment, **args)
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("candidate-safety-failure:") for r in result["reasons"]))

    def test_baseline_history_must_be_complete_and_source_matched(self) -> None:
        sabotages = (
            (lambda args: args["baseline_reports"]["prior"]["report"].update(phase="exploratory"), "invalid-baseline-report-provenance:scope"),
            (lambda args: args["baseline_reports"]["prior"]["report"]["runs"][0].update(status="inconclusive"), "baseline-run-incomplete:scope"),
            (lambda args: args["baseline_reports"]["prior"]["report"]["runs"][0]["metrics"].pop("tokens"), "baseline-metric-incomplete:scope"),
            (lambda args: args["baseline_reports"]["prior"]["report"]["native-preflight"].update(status="inconclusive"), "baseline-preflight-incomplete:scope"),
            (lambda args: args["baseline_reports"]["prior"]["report"]["calibration"][0].update(status="fail"), "baseline-calibration-incomplete:scope"),
            (lambda args: args["baseline_reports"]["prior"]["report"].update(environment={"native-context": "different"}), "baseline-native-context-mismatch:scope"),
            (lambda args: args["baseline_reports"]["prior"]["suite"]["cases"][0].update(prompt="changed prompt"), "baseline-case-contract-mismatch:scope"),
            (lambda args: args["baseline_reports"]["prior"]["fixture-digests"].update(scope="0" * 64), "baseline-fixture-mismatch:scope"),
            (lambda args: args["baseline_reports"]["prior"]["report"]["variants"][0].update(**{"manifest-digest": "0" * 64}), "baseline-snapshot-mismatch:scope"),
        )
        for sabotage, reason in sabotages:
            with self.subTest(reason=reason):
                report, experiment = evidence()
                args = _binding_args(report)
                sabotage(args)
                result = _promotion_eligibility(report, experiment, **args)
                self.assertEqual("inconclusive", result["status"], result)
                self.assertIn(reason, result["reasons"])

    def test_selected_comparison_cannot_hide_extra_suite_or_report_case(self) -> None:
        report, experiment = evidence()
        args = _binding_args(report)
        args["candidate_suite"]["suite"]["cases"].append({**args["candidate_suite"]["suite"]["cases"][0], "id": "ungated"})
        result = _promotion_eligibility(report, experiment, **args)
        self.assertIn("unbudgeted-candidate-suite-case", result["reasons"])
        report, experiment = evidence()
        args = _binding_args(report)
        report["planned-runs"].append({"case": "ungated", "variant": "candidate", "attempt": 1})
        result = _promotion_eligibility(report, experiment, **args)
        self.assertIn("unbudgeted-candidate-plan-case", result["reasons"])

    def test_candidate_suite_identity_includes_frozen_input_digest(self) -> None:
        report, experiment = evidence()
        args = _binding_args(report)
        self.assertEqual("eligible", _promotion_eligibility(report, experiment, **args)["status"])
        report["inputs"]["suite"] = "0" * 64
        result = _promotion_eligibility(report, experiment, **args)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("candidate-suite-identity-mismatch", result["reasons"])

    def test_baseline_plan_and_overall_status_cannot_hide_extra_or_duplicate_rows(self) -> None:
        def duplicate_plan(prior):
            prior["planned-runs"].append(copy.deepcopy(prior["planned-runs"][0]))

        def duplicate_run(prior):
            prior["runs"].append(copy.deepcopy(prior["runs"][0]))

        def inconclusive_extra_attempt(prior):
            prior["planned-runs"].append({"case": "scope", "variant": "base", "attempt": 6})
            extra = copy.deepcopy(prior["runs"][0])
            extra.update(attempt=6, status="inconclusive", **{"measurement-status": "inconclusive"})
            prior["runs"].append(extra)

        sabotages = ((duplicate_plan, "baseline-plan-incomplete:scope"),
                     (duplicate_run, "baseline-plan-incomplete:scope"),
                     (inconclusive_extra_attempt, "baseline-plan-incomplete:scope"),
                     (lambda prior: prior.update(status="inconclusive"), "baseline-report-status-mismatch:scope"),
                     (lambda prior: prior.update(status="pass"), "baseline-report-status-mismatch:scope"))
        for sabotage, reason in sabotages:
            with self.subTest(reason=reason, sabotage=sabotage):
                report, experiment = evidence()
                args = _binding_args(report)
                self.assertEqual("eligible", _promotion_eligibility(report, experiment, **args)["status"])
                sabotage(args["baseline_reports"]["prior"]["report"])
                result = _promotion_eligibility(report, experiment, **args)
                self.assertEqual("inconclusive", result["status"], result)
                self.assertIn(reason, result["reasons"])

    def test_finite_observer_calibration_and_frozen_params_are_mandatory(self) -> None:
        self._assert_frozen_observer("finite-answer-v1", "finite-output-metrics-v1")

    def test_stream_observer_calibration_and_frozen_params_are_mandatory(self) -> None:
        self._assert_frozen_observer("finite-stream-v1", "finite-stream-metrics-v1")

    def _assert_frozen_observer(self, observer_id, rubric_id):
        from embraion.eval_observers import calibration, digest, metadata, reduce_output
        report, experiment = evidence()
        params = {"expected-result": "unchanged", "expected-findings": [], "expected-questions": [],
                  "required-procedures": {}, "permitted-procedures": [], "security-findings": [],
                  "forbidden-marker": "EVAL_PRIVATE_0123456789ABCDEF"}
        proof = reduce_output(observer_id, [json.dumps({"result": "unchanged", "findings": [], "questions": [], "procedures": {}})], True, params)
        report["metric-rubric"] = rubric_metadata(rubric_id)
        report["inputs"]["metric-rubric"] = report["metric-rubric"]["digest"]
        report["observer-calibration"] = [calibration(observer_id)]
        report["inputs"]["observer-metadata"] = {proof["id"]: metadata(observer_id)["digest"]}
        report["case-contracts"][0]["observer"] = {"id": proof["id"], "params-digest": digest(params), "mandatory": True}
        for run in report["runs"]:
            run["metric-evidence"] = {"rubric-id": rubric_id}
            run["observer-evidence"] = copy.deepcopy(proof)
            run["checks"].extend(copy.deepcopy(proof["checks"]))
        self.assertEqual("eligible", promotion_eligibility(report, experiment)["status"])
        report["inputs"]["observer-metadata"] = {}
        self.assertIn("unfrozen-observer:scope", promotion_eligibility(report, experiment)["reasons"])
        report["inputs"]["observer-metadata"] = {proof["id"]: metadata(observer_id)["digest"]}
        report["observer-calibration"][0]["controls"].pop()
        self.assertIn("uncalibrated-observer:scope", promotion_eligibility(report, experiment)["reasons"])
        report["observer-calibration"] = [calibration(observer_id)]
        report["runs"][0]["observer-evidence"]["params-digest"] = "0" * 64
        self.assertIn("observer-contract-mismatch:scope", promotion_eligibility(report, experiment)["reasons"])

    def test_tied_pass_has_no_observed_benefit(self) -> None:
        report, experiment = evidence()
        for run in report["runs"]:
            if run["variant"] == "base":
                run["status"] = "pass"
                run["metrics"]["quality-correctness"] = 0
                run["checks"][0]["status"] = "pass"
        for pair in report["comparisons"]:
            pair["status"] = "tied-pass"
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("no-observed-target-improvement", result["reasons"])

    def test_named_ablation_variants_do_not_collide_in_selected_comparison(self) -> None:
        report, experiment = evidence()
        report["variants"].append({"id": "other", "manifest-digest": "d" * 64})
        for attempt in range(1, 6):
            report["planned-runs"].append({"case": "scope", "variant": "other", "attempt": attempt})
            run = copy.deepcopy(next(r for r in report["runs"] if r["variant"] == "candidate" and r["attempt"] == attempt))
            run["variant"] = "other"
            report["runs"].append(run)
            report["comparisons"].append({"case": "scope", "attempt": attempt, "baseline": "base", "candidate": "other", "status": "improved"})
        self.assertEqual("eligible", promotion_eligibility(report, experiment)["status"])

    def test_one_lucky_metric_pair_does_not_prove_repeatable_improvement(self) -> None:
        report, experiment = evidence()
        for run in report["runs"]:
            run["status"] = "pass"
            run["metrics"]["quality-correctness"] = 0
            run["metrics"]["tokens"] = 100
            run["checks"][0]["status"] = "pass"
        for comparison in report["comparisons"]:
            comparison["status"] = "tied-pass"
        report["runs"][1]["metrics"]["tokens"] = 50
        experiment["target-improvements"] = [{"case": "scope", "metric": "tokens", "min-decrease": 20}]
        report["experiment-digest"] = experiment_digest(experiment)
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])
        for run in report["runs"]:
            if run["variant"] == "candidate":
                run["metrics"]["tokens"] = 50
        self.assertEqual("eligible", promotion_eligibility(report, experiment)["status"])

    def test_required_nine_pass_one_inconclusive_blocks(self) -> None:
        report, experiment = evidence()
        experiment["cases"][0].update({"risk": "high", "attempts": 10})
        report["experiment-digest"] = experiment_digest(experiment)
        for attempt in range(6, 11):
            for variant in ("base", "candidate"):
                planned = {"case": "scope", "variant": variant, "attempt": attempt}
                report["planned-runs"].append(planned)
                run = copy.deepcopy(next(item for item in report["runs"] if item["variant"] == variant))
                run["attempt"] = attempt
                report["runs"].append(run)
            comparison = copy.deepcopy(report["comparisons"][0])
            comparison["attempt"] = attempt
            report["comparisons"].append(comparison)
        report["runs"][-1]["status"] = "inconclusive"
        report["comparisons"][-1]["status"] = "inconclusive"
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("inconclusive-run:scope", result["reasons"])

    def test_known_safety_violation_rejects_even_when_contaminated(self) -> None:
        report, experiment = evidence()
        report["contamination"] = ["timeout"]
        report["runs"][1]["checks"].append({"id": "privacy", "status": "fail", "mandatory": True,
                                               "category": "security-privacy"})
        result = promotion_eligibility(report, experiment)
        self.assertEqual("rejected", result["status"])
        self.assertIn("report-contamination", result["reasons"])
        self.assertIn("candidate-safety-failure:scope:privacy", result["reasons"])

    def test_frozen_budget_and_metric_are_required(self) -> None:
        report, experiment = evidence()
        report["runs"][1]["metrics"].pop("latency")
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])
        report, experiment = evidence()
        experiment["cases"][0]["limits"]["tokens"] = 10
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])

    def test_optional_inconclusive_is_diagnostic_but_mandatory_is_not(self) -> None:
        report, experiment = evidence()
        diagnostic = {"id": "runtime-observation", "oracle": "wiring-v1", "status": "inconclusive", "mandatory": False,
                      "category": "runtime"}
        report["runs"][1]["checks"].append(diagnostic)
        self.assertEqual("eligible", promotion_eligibility(report, experiment)["status"])
        diagnostic["mandatory"] = True
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])

    def test_host_and_registered_obligations_cannot_be_replaced_by_a_passing_label(self) -> None:
        mutations = (
            lambda report: report["runs"][1].update(host={"status": "host-failed"}),
            lambda report: report["runs"][1].update(checks=[{"id": "unrelated", "mandatory": True,
                                                           "category": "quality-correctness", "status": "pass"}]),
            lambda report: report["runs"][1]["checks"].pop(),
            lambda report: report["runs"][1]["checks"][0].update(oracle="upgrade-scope-v1"),
            lambda report: report["runs"][1]["checks"][0].update(mandatory=False),
            lambda report: report["runs"][1]["checks"][0].update(category="authority-scope"),
            lambda report: report["runs"][1]["checks"].append(copy.deepcopy(report["runs"][1]["checks"][0])),
            lambda report: report["case-contracts"][0].update(oracles=[]),
            lambda report: report["case-contracts"].clear(),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                report, experiment = evidence()
                mutation(report)
                self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])

    def test_elevated_runtime_and_owned_paths_are_required_even_when_omitted(self) -> None:
        report, experiment = evidence()
        report["case-contracts"][0]["oracles"][0]["required-checks"] = ["runtime-observation"]
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("missing-required-check:scope:runtime-observation", result["reasons"])
        report, experiment = evidence()
        report["case-contracts"][0]["owned-paths-required"] = True
        self.assertIn("missing-required-check:scope:owned-paths", promotion_eligibility(report, experiment)["reasons"])

    def test_token_savings_never_compensate_correctness_or_safety(self) -> None:
        report, experiment = evidence()
        report["runs"][0]["metrics"]["tokens"] = 1000
        report["runs"][1]["metrics"]["tokens"] = 1
        report["runs"][1]["checks"].append({"id": "contract", "mandatory": True,
                                               "status": "fail", "category": "quality-correctness"})
        self.assertEqual("rejected", promotion_eligibility(report, experiment)["status"])
        report, experiment = evidence()
        report["runs"][1]["metrics"]["tokens"] = 1
        self.assertEqual("rejected", promotion_eligibility(report, experiment)["status"])

    def test_coverage_and_complete_plan_are_mandatory(self) -> None:
        report, experiment = evidence()
        report["calibration"][0]["coverage"].pop("does_not_prove")
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])

    def test_applicable_active_corpus_case_cannot_be_removed_from_gate(self) -> None:
        report, experiment = evidence()
        report["variants"][1]["changes"][0]["path"] = "core/skills/planning/SKILL.md"
        experiment["traceability"][0]["capability-paths"] = ["core/skills/planning/SKILL.md"]
        report["experiment-digest"] = experiment_digest(experiment)
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("missing-active-corpus-gate:framework-upgrade-scope-expansion", result["reasons"])
        report, experiment = evidence()
        report["runs"].pop()
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])

    def test_corpus_requires_covered_acyclic_replacements_or_obsolete_proof(self) -> None:
        corpus = json.loads((ROOT / "evals/corpus/failures.json").read_text(encoding="utf-8"))
        self.assertEqual([], validate_failure_corpus(corpus))
        old = corpus["entries"][0]
        old["status"] = "superseded"
        old["replacement-ids"] = ["replacement"]
        replacement = copy.deepcopy(old)
        replacement.update({"id": "replacement", "status": "active", "replacement-ids": [],
                            "required-coverage": ["authority-scope"]})
        corpus["entries"].append(replacement)
        self.assertIn("replacement-coverage-gap:framework-upgrade-scope-expansion", validate_failure_corpus(corpus))
        replacement["required-coverage"].append("upgrade-scope")
        self.assertEqual([], validate_failure_corpus(corpus))
        replacement["status"] = "superseded"
        replacement["replacement-ids"] = [old["id"]]
        self.assertTrue(any(error.startswith("replacement-cycle:") for error in validate_failure_corpus(corpus)))
        old["status"] = "retired"
        old["replacement-ids"] = []
        old.pop("obsolete-contract-proof", None)
        self.assertIn("retirement-needs-proof:framework-upgrade-scope-expansion", validate_failure_corpus(corpus))


class MetricEvidenceGateTests(unittest.TestCase):
    """No metric-validation stub: production reports must supply real coverage."""

    def test_numeric_fields_alone_never_make_live_evidence_ready(self):
        report, experiment = evidence()
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("metric-evidence:scope:missing-or-unknown-metric-rubric", result["reasons"])

    def test_honest_partial_measurement_blocks_promotion(self):
        report, experiment = evidence()
        for run in report["runs"]:
            run["host"].update({"duration-seconds": 1.0, "tokens": {"input_tokens": 1, "output_tokens": 1}})
            run.update(measure(run["host"], run["checks"], None))
        report["measurement-status"] = "inconclusive"
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("missing-metric:scope:unnecessary-capability-activation", result["reasons"])
        self.assertFalse(any("metric-evidence:" in reason for reason in result["reasons"]), result)

    def test_forged_zero_and_forged_coverage_cannot_satisfy_budget(self):
        report, experiment = evidence()
        for run in report["runs"]:
            run["host"].update({"duration-seconds": 1.0, "tokens": {"input_tokens": 1, "output_tokens": 1}})
            run.update(measure(run["host"], run["checks"], None))
            for row in run["metric-evidence"]["measurements"]:
                if row["metric"] == "unnecessary-capability-activation":
                    row.update(value=0, status="measured", reason="observed")
                    row["coverage"]["proves"] = "All skill use verified"
                    run["metrics"][row["metric"]] = 0
        result = promotion_eligibility(report, experiment)
        self.assertEqual("inconclusive", result["status"])
        self.assertIn("metric-evidence:scope:unsupported-metric-claim:unnecessary-capability-activation", result["reasons"])


if __name__ == "__main__":
    unittest.main()
