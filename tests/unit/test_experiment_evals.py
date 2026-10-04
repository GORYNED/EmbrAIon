from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from embraion.common import framework_root
from embraion.experiment_evals import capture_snapshot, identity, run_experiment


ROOT = framework_root()


class FullCoreExperiments(unittest.TestCase):
    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "build")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        shutil.copytree(ROOT / "core", self.source / "core")
        shutil.copyfile(ROOT / "framework.yaml", self.source / "framework.yaml")
        for name, text in {"core/skills/test/SKILL.md": "baseline\n", ".agents/skills/test/SKILL.md": "baseline\n",
                           "adapters/host.txt": "neutral\n"}.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        baseline = capture_snapshot(self.source, self.root / "baseline", self.root / "baseline.json")
        candidate = capture_snapshot(self.source, self.root / "candidate", self.root / "candidate.json")
        shutil.copytree(ROOT / "evals/foundation/fixtures/wiring-v1", self.root / "fixture")
        self.data = {"schema-version": 2, "id": "test", "baseline": "baseline", "seed": 42,
                     "variants": [{"id": name, "snapshot": name, "manifest": name + ".json",
                                   "manifest-digest": manifest["digest"], "changes": []}
                                  for name, manifest in (("baseline", baseline), ("candidate", candidate))],
                     "cases": [{"id": "wiring", "fixture": "fixture", "prompt": "PRIVATE_CANARY_7432",
                                "polarity": "positive", "language": "en", "risk": "ordinary",
                                "oracles": [{"id": "wiring-v1", "params": {}, "mandatory": True}]}]}
        self.suite = self.root / "suite.json"
        self.write_suite()
        self.route = {"host": "codex", "model": "test", "effort": "medium", "options": {}, "provider": None,
                      "data": "PUBLIC", "role": "worker", "access": "workspace-write", "resolution": "project-deployment"}

    def write_suite(self):
        self.suite.write_text(json.dumps(self.data), encoding="utf-8")

    def run_trial(self, invoke=None, environment=None, preflight=None, **kwargs):
        with patch("embraion.experiment_evals.verify_projection", return_value={"status": "pass"}), patch("embraion.adapters.eval_hosts.preflight_host", return_value=preflight or {"status": "pass"}):
            with patch("embraion.experiment_evals._environment", side_effect=environment,
                       return_value={"host": {"version": "1.0.0"}}):
                with patch("embraion.adapters.eval_hosts.invoke_host", side_effect=invoke,
                           return_value={"status": "completed", "duration-seconds": 1.0,
                                         "tokens": {"input_tokens": 2, "output_tokens": 3}}) as native:
                    report = run_experiment(self.suite, host="codex", model="test", effort="medium",
                                            route=self.route, attempts=2, output=self.root / "report.json", **kwargs)
                    return report, native

    def test_v2_full_core_variants_counterbalance_without_raw_prompt(self):
        report, native = self.run_trial()
        self.assertEqual("pass", report["status"], report["contamination"])
        self.assertEqual(4, native.call_count)
        self.assertEqual(4, len(report["planned-runs"]))
        self.assertNotEqual(report["runs"][0]["variant"], report["runs"][2]["variant"])
        self.assertEqual({"tied-pass"}, {pair["status"] for pair in report["comparisons"]})
        self.assertTrue(report["calibration"][0]["coverage"]["does_not_prove"])
        self.assertNotIn("PRIVATE_CANARY_7432", (self.root / "report.json").read_text())
        journal = [json.loads(line) for line in (self.root / "report.json.runs.jsonl").read_text().splitlines()]
        self.assertEqual(report["planned-runs"], journal[0]["planned-runs"])
        self.assertEqual(4, sum(row["kind"] == "run-result" for row in journal))
        self.assertNotIn("PRIVATE_CANARY_7432", str(journal))
        self.assertIsNone(report["runs"][0]["metrics"]["authority-scope"])

    def test_baseline_runs_only_reference_and_cannot_claim_candidate_benefit(self):
        report, native = self.run_trial(phase="baseline")
        self.assertEqual(2, native.call_count)
        self.assertEqual([], report["comparisons"])
        self.assertEqual({"baseline"}, {run["variant"] for run in report["runs"]})

    def test_native_pilot_cannot_expand_read_only_routing(self):
        self.route["access"] = "read-only"
        with self.assertRaisesRegex(ValueError, "sandbox"):
            self.run_trial()

    def test_unavailable_native_tools_block_behavioral_grading(self):
        report, native = self.run_trial(preflight={"status": "inconclusive"})
        self.assertEqual("inconclusive", report["status"])
        native.assert_not_called()
        self.assertIn("native-tools-preflight-unavailable", {l["reason"] for l in report["limitations"]})

    def test_preflight_requires_a_real_nonce_copy(self):
        from embraion.adapters.eval_hosts import preflight_host
        profile = self.source / ".codex/agents/worker.toml"
        profile.parent.mkdir(parents=True)
        profile.write_text('name="worker"\nsandbox_mode="workspace-write"\ndeveloper_instructions="worker instruction"\n')
        home = self.root / "eval-home"
        home.mkdir()
        (home / "config.toml").write_text("# private profile\n")
        (home / "embraion-eval-profile.json").write_text(json.dumps({"schema-version": 1, "purpose": "embraion-native-eval"}))
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}), patch("embraion.adapters.eval_hosts.invoke_host", return_value={"status": "completed"}):
            self.assertEqual("inconclusive", preflight_host("codex", "test", self.source, "test", "medium", 1)["status"])
        def copy(host, binary, project, *args):
            shutil.copyfile(project / "marker.txt", project / "result.txt")
            return {"status": "completed"}
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}), patch("embraion.adapters.eval_hosts.invoke_host", side_effect=copy):
            self.assertEqual("pass", preflight_host("codex", "test", self.source, "test", "medium", 1)["status"])

    def test_native_preparation_cannot_mutate_global_config_or_other_settings(self):
        from embraion.adapters.eval_hosts import preflight_host
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root / "unowned-profile")}), patch("embraion.adapters.eval_hosts.invoke_host") as native:
            result = preflight_host("codex", "test", self.source, "test", "medium", 1)
            self.assertEqual("private-eval-profile-required", result["reason"])
            native.assert_not_called()
        home = self.root / "eval-home"
        home.mkdir()
        (home / "config.toml").write_text("# private profile\n")
        (home / "embraion-eval-profile.json").write_text(json.dumps({"schema-version": 1, "purpose": "embraion-native-eval"}))
        profile = self.source / ".codex/agents/worker.toml"
        profile.parent.mkdir(parents=True)
        profile.write_text('name="worker"\nsandbox_mode="workspace-write"\ndeveloper_instructions="worker"\n')
        def mutate(host, binary, project, *args):
            shutil.copyfile(project / "marker.txt", project / "result.txt")
            (home / "config.toml").write_text('model="undeclared-model"\n')
            return {"status": "completed"}
        with patch.dict(os.environ, {"CODEX_HOME": str(home)}), patch("embraion.adapters.eval_hosts.invoke_host", side_effect=mutate):
            result = preflight_host("codex", "test", self.source, "test", "medium", 1)
            self.assertEqual("inconclusive", result["status"])
            self.assertEqual("unexpected-eval-profile-configuration-change", result["reason"])

    def test_preflight_and_trials_reuse_one_path_with_fresh_contents(self):
        seen = []
        def preflight(*args, workspace):
            seen.append(workspace)
            workspace.mkdir()
            (workspace / "marker.txt").write_text("preflight marker")
            return {"status": "pass"}
        def invoke(host, binary, project, *args):
            self.assertEqual(seen[0], project)
            self.assertFalse((project / "marker.txt").exists())
            self.assertFalse((project / "previous-run.txt").exists())
            (project / "previous-run.txt").write_text("candidate output")
            return {"status": "completed"}
        with patch("embraion.adapters.eval_hosts.preflight_host", side_effect=preflight), patch("embraion.experiment_evals.verify_projection", return_value={"status": "pass"}), patch("embraion.experiment_evals._environment", return_value={}):
            with patch("embraion.adapters.eval_hosts.invoke_host", side_effect=invoke) as native:
                report = run_experiment(self.suite, host="codex", model="test", effort="medium", route=self.route,
                                        attempts=2, output=self.root / "report.json")
        self.assertEqual(4, native.call_count)
        self.assertEqual("pass", report["status"])

    def test_candidate_scratch_cannot_be_inside_the_trusted_checkout(self):
        from embraion.experiment_evals import _scratch_root
        with patch("embraion.experiment_evals.tempfile.gettempdir", return_value=str(ROOT / "build")):
            with self.assertRaisesRegex(ValueError, "trusted controller"):
                _scratch_root()

    def test_native_adapter_applies_worker_instead_of_lead(self):
        from embraion.adapters.eval_hosts import invoke_host
        profile = self.source / ".codex/agents/worker.toml"
        profile.parent.mkdir(parents=True)
        profile.write_text('name="worker"\nsandbox_mode="workspace-write"\ndeveloper_instructions="worker instruction"\n')
        (self.source / ".codex/config.toml").write_text('developer_instructions="lead instruction"\n')
        with patch("embraion.adapters.eval_hosts._invoke_codex", return_value={"status": "completed"}) as native:
            result = invoke_host("codex", "test", self.source, "test", "test", "medium", 1, [], self.root)
        self.assertEqual("worker instruction", native.call_args.kwargs["developer_instructions"])
        self.assertTrue(native.call_args.kwargs["trusted_workspace"])
        self.assertEqual("worker-profile-explicit-argument", result["role-evidence"])
        profile.write_text('name="worker"\nsandbox_mode="read-only"\ndeveloper_instructions="worker instruction"\n')
        with patch("embraion.adapters.eval_hosts._invoke_codex") as native:
            result = invoke_host("codex", "test", self.source, "test", "test", "medium", 1, [], self.root)
        self.assertEqual("native-config-unverified", result["status"])
        native.assert_not_called()

    def test_raw_native_observations_do_not_survive_between_attempts(self):
        from embraion.adapters.eval_hosts import invoke_host
        profile = self.source / ".codex/agents/worker.toml"
        profile.parent.mkdir(parents=True)
        profile.write_text('name="worker"\nsandbox_mode="workspace-write"\ndeveloper_instructions="worker"\n')
        observations = []
        def bridge(*args, **kwargs):
            observation = args[-1]
            self.assertNotEqual(self.root, observation)
            self.assertTrue(all(not earlier.exists() for earlier in observations))
            for name in ("last-message.txt", "prompt.txt", "events.jsonl", "stderr.txt"):
                (observation / name).write_text("transient private canary")
            observations.append(observation)
            return {"status": "completed"}
        with patch("embraion.adapters.eval_hosts._invoke_codex", side_effect=bridge):
            for _ in range(2):
                invoke_host("codex", "test", self.source, "test", "test", "medium", 1, [], self.root)
                self.assertFalse(observations[-1].exists())
        self.assertNotEqual(observations[0], observations[1])

    def test_undeclared_core_or_adapter_difference_is_inconclusive_before_launch(self):
        path = self.root / "candidate" / "adapters/host.txt"
        path.write_text("hidden additional rule\n", encoding="utf-8")
        manifest = json.loads((self.root / "candidate.json").read_text())
        import hashlib
        manifest["files"]["adapters/host.txt"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["generator-digest"] = identity({k: v for k, v in manifest["files"].items() if k.startswith(("tools/cli/", "schemas/", "adapters/"))})
        manifest["digest"] = identity({k: v for k, v in manifest.items() if k != "digest"})
        (self.root / "candidate.json").write_text(json.dumps(manifest))
        self.data["variants"][1]["manifest-digest"] = manifest["digest"]
        self.write_suite()
        report, native = self.run_trial()
        self.assertEqual("inconclusive", report["status"])
        self.assertEqual(0, native.call_count)
        self.assertIn("undeclared-dependency-adapter-or-configuration-delta", {c["reason"] for c in report["contamination"]})

    def test_fixture_drift_keeps_uncertainty_instead_of_success(self):
        def mutate(*args):
            (self.root / "fixture" / "actions.json").write_text("{}")
            return {"status": "completed", "duration-seconds": 1.0}
        report, native = self.run_trial(invoke=mutate)
        self.assertEqual("inconclusive", report["status"])
        self.assertTrue(any(c["reason"] == "fixture-drift" for c in report["contamination"]))

    def test_host_version_change_is_contamination(self):
        calls = 0
        def changed(*args):
            nonlocal calls
            calls += 1
            return {"host": {"version": "1.0.0" if calls < 3 else "2.0.0"}}
        report, native = self.run_trial(environment=changed)
        self.assertEqual("inconclusive", report["status"])
        self.assertTrue(any(c["reason"] == "host-configuration-or-dependency-drift" for c in report["contamination"]))

    def test_timeout_remains_inconclusive_and_checks_are_retained(self):
        report, native = self.run_trial(invoke=lambda *args: {"status": "timeout", "duration-seconds": 1.0})
        self.assertEqual("inconclusive", report["status"])
        self.assertTrue(report["runs"][0]["checks"])

    def test_requested_runtime_evidence_cannot_inherit_static_pass(self):
        self.data["cases"][0]["oracles"][0]["required-checks"] = ["runtime-observation"]
        self.write_suite()
        report, native = self.run_trial()
        self.assertEqual("inconclusive", report["status"])
        runtime = next(c for c in report["runs"][0]["checks"] if c["id"] == "runtime-observation")
        self.assertTrue(runtime["mandatory"])
        self.assertEqual("unverified", runtime["status"])

    def test_manifest_changes_after_launch_are_contamination(self):
        def mutate(*args):
            (self.root / "baseline.json").write_text("{}")
            return {"status": "completed", "duration-seconds": 1.0}
        report, native = self.run_trial(invoke=mutate)
        self.assertEqual("inconclusive", report["status"])
        self.assertTrue(any(c["reason"] == "manifest-drift" for c in report["contamination"]))

    def test_snapshot_digest_fields_cannot_be_forged(self):
        manifest = json.loads((self.root / "baseline.json").read_text())
        manifest["core-digest"] = "a" * 64
        manifest["digest"] = identity({k: v for k, v in manifest.items() if k != "digest"})
        (self.root / "baseline.json").write_text(json.dumps(manifest))
        self.data["variants"][0]["manifest-digest"] = manifest["digest"]
        self.write_suite()
        with self.assertRaises(ValueError):
            self.run_trial()

    def test_capture_cannot_write_into_trusted_controller(self):
        with self.assertRaises(ValueError):
            capture_snapshot(self.source, ROOT / "tools/cli/embraion/new-snapshot", self.root / "new.json")

    def test_candidate_cannot_hide_scope_changes_in_cache_directory(self):
        self.data["cases"][0]["allowed-paths"] = []
        self.write_suite()
        def mutate(host, binary, project, *args):
            (project / ".cache").mkdir()
            (project / ".cache/unauthorized.json").write_text("{}")
            return {"status": "completed", "duration-seconds": 1.0}
        report, native = self.run_trial(invoke=mutate)
        self.assertEqual("fail", report["status"])
        self.assertEqual(1, report["runs"][0]["metrics"]["authority-scope"])

    def test_unknown_oracle_or_suite_command_cannot_execute(self):
        self.data["cases"][0]["oracles"][0]["id"] = "unknown"
        self.write_suite()
        with self.assertRaises(ValueError):
            self.run_trial()
        self.data["cases"][0]["oracles"][0]["id"] = "wiring-v1"
        self.data["cases"][0]["oracles"][0]["command"] = "arbitrary shell"
        self.write_suite()
        with self.assertRaises(ValueError):
            self.run_trial()

    def test_assessment_rejects_a_report_that_omits_schema_obligations(self):
        import argparse
        from embraion.cli import _eval_experiment
        report = self.root / "minimal-report.json"
        experiment = self.root / "minimal-experiment.json"
        report.write_text('{"schema-version":2}')
        experiment.write_text('{"schema-version":1}')
        args = argparse.Namespace(experiment_command="assess", report=str(report), experiment=str(experiment))
        with self.assertRaisesRegex(ValueError, "invalid experiment assessment"):
            _eval_experiment(args)

    def test_source_manifest_and_output_are_not_overwritable(self):
        with self.assertRaises(ValueError):
            capture_snapshot(self.source, self.root / "baseline", self.root / "baseline.json")
        with self.assertRaises(ValueError):
            run_experiment(self.suite, host="codex", model="test", effort="medium", route=self.route,
                           output=self.root / "baseline.json", attempts=1)


if __name__ == "__main__":
    unittest.main()
