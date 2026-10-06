from __future__ import annotations

import unittest

from embraion.common import framework_root, read_yaml


def _workflow(name: str) -> dict:
    return read_yaml(framework_root() / ".github/workflows" / name)


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare `on` key as boolean true.
    return workflow.get("on", workflow.get(True)) or {}


class SelfHostUpgradeWorkflowTests(unittest.TestCase):
    def test_upgrade_runs_only_after_the_release_artifact_is_published(self) -> None:
        jobs = _workflow("release.yml")["jobs"]
        job = jobs["self-host-upgrade"]
        self.assertEqual("consumer-artifact-lock-smoke", job["needs"])
        self.assertEqual("github-release", jobs["consumer-artifact-lock-smoke"]["needs"])
        self.assertNotIn("self-host-upgrade", str(jobs["pypi-publish"].get("needs")))
        self.assertEqual(
            {"contents": "write", "pull-requests": "write", "actions": "write"},
            job["permissions"],
        )
        checkout = job["steps"][0]
        self.assertTrue(checkout["uses"].startswith("actions/checkout@"))
        self.assertEqual("main", checkout["with"]["ref"])

    def test_upgrade_reproduces_the_manual_self_host_commands(self) -> None:
        steps = _workflow("release.yml")["jobs"]["self-host-upgrade"]["steps"]
        upgrade = next(step for step in steps if step.get("id") == "upgrade")["run"]
        self.assertIn('embraion update --framework-version "$VERSION"', upgrade)
        self.assertIn(
            "embraion install --host codex --destination . --config-mode merge",
            upgrade,
        )
        self.assertNotIn("--force", upgrade)
        self.assertIn("pinned < target", upgrade)

    def test_proposal_is_a_pull_request_with_dispatched_checks(self) -> None:
        steps = _workflow("release.yml")["jobs"]["self-host-upgrade"]["steps"]
        proposal = next(
            step for step in steps if step["name"] == "Open self-host upgrade pull request"
        )
        run = proposal["run"]
        self.assertEqual("steps.upgrade.outputs.changed == 'true'", proposal["if"])
        self.assertIn('git push origin "$BRANCH"', run)
        self.assertNotIn("--force", run)
        self.assertNotIn("git push origin main", run)
        self.assertIn("gh pr create", run)
        self.assertNotIn("gh pr merge", run)
        for workflow in ("validate.yml", "docs.yml"):
            with self.subTest(workflow=workflow):
                self.assertIn(f"gh workflow run {workflow}", run)
                self.assertIn("workflow_dispatch", _triggers(_workflow(workflow)))

    def test_dispatched_docs_build_never_deploys(self) -> None:
        jobs = _workflow("docs.yml")["jobs"]
        self.assertEqual("github.event_name == 'push'", jobs["deploy"]["if"])


if __name__ == "__main__":
    unittest.main()
