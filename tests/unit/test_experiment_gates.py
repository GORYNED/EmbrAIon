from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from embraion.experiment_gates import experiment_digest, promotion_eligibility, validate_failure_corpus
from embraion.eval_oracles import oracle_metadata
from embraion.experiment_evals import identity, _files


ROOT = Path(__file__).resolve().parents[2]
METRICS = ("quality-correctness", "authority-scope", "security-privacy", "false-positive-rate",
           "unnecessary-clarification", "unnecessary-capability-activation", "tokens", "latency")


def evidence() -> tuple[dict, dict]:
    limits = {metric: 0 for metric in METRICS}
    experiment = {"schema-version": 1, "id": "scope-trial", "baseline": "base", "candidate": "candidate", "suite-digest": "c" * 64,
                  "change-ids": ["scope-rule"], "required-cases": ["scope"], "target-cases": ["scope"],
                  "traceability": [{"change-id": "scope-rule", "source-kind": "observed-problem",
                                    "observed-problem": "Framework upgrade expanded scope", "proposed-rule": "Keep requested action bounded",
                                    "capability-paths": ["core/skills/debugging/SKILL.md"], "scenarios": ["scope"],
                                    "expected-result": "Upgrade pin only"}],
                  "cases": [{"case": "scope", "limits": limits, "risk": "ordinary", "attempts": 5,
                             "baseline-manifest-digest": "a" * 64, "justification-id": "scope-budget"}]}
    base_metrics = {metric: 0 for metric in METRICS}
    base_metrics["quality-correctness"] = 1
    candidate_metrics = {metric: 0 for metric in METRICS}
    report = {"schema-version": 2, "baseline-id": "base", "phase": "confirmatory", "suite-digest": "c" * 64, "experiment-digest": experiment_digest(experiment),
              "variants": [{"id": "base", "manifest-digest": "a" * 64},
                           {"id": "candidate", "manifest-digest": "b" * 64,
                            "changes": [{"path": "core/skills/debugging/SKILL.md", "before": "a" * 64, "after": "b" * 64}]}],
              "case-contracts": [{"case": "scope", "risk": "ordinary", "language": "en", "polarity": "positive", "corpus-id": None,
                                  "oracles": [{"id": "wiring-v1", "mandatory": True}]}],
              "inputs": {"corpus": identity(_files(ROOT / "evals/corpus"))},
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
    return report, experiment


class ExperimentGateTests(unittest.TestCase):
    def test_matched_improvement_is_evidence_ready_without_promotion_authority(self) -> None:
        report, experiment = evidence()
        result = promotion_eligibility(report, experiment)
        self.assertEqual("eligible", result["status"], result)
        self.assertFalse(result["authorizes_core_promotion"])
        self.assertTrue(result["review_required"])

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
        diagnostic = {"id": "runtime", "status": "inconclusive", "mandatory": False,
                      "category": "quality-correctness"}
        report["runs"][1]["checks"].append(diagnostic)
        self.assertEqual("eligible", promotion_eligibility(report, experiment)["status"])
        diagnostic["mandatory"] = True
        self.assertEqual("inconclusive", promotion_eligibility(report, experiment)["status"])

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


if __name__ == "__main__":
    unittest.main()
