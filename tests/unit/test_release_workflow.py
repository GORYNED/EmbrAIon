from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.common import framework_root, read_yaml


def _workflow(name: str) -> dict:
    return read_yaml(framework_root() / ".github/workflows" / name)


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare `on` key as boolean true.
    return workflow.get("on", workflow.get(True)) or {}


def _step(workflow: dict, job: str, name: str) -> dict:
    return next(step for step in workflow["jobs"][job]["steps"] if step["name"] == name)


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
        checkout = _step(_workflow("release.yml"), "self-host-upgrade", "Checkout main")
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
        workflow = _workflow("docs.yml")
        push_only = "github.event_name == 'push'"
        self.assertEqual(push_only, workflow["jobs"]["deploy"]["if"])
        for name in ("Configure Pages", "Upload Pages artifact"):
            with self.subTest(step=name):
                self.assertEqual(push_only, _step(workflow, "build", name)["if"])

    def test_branch_left_without_a_pull_request_is_resumed_only_when_identical(self) -> None:
        run = _step(
            _workflow("release.yml"),
            "self-host-upgrade",
            "Open self-host upgrade pull request",
        )["run"]
        self.assertIn('git write-tree', run)
        self.assertIn('FETCH_HEAD^{tree}', run)
        self.assertIn("review it manually", run)


@unittest.skipIf(os.name == "nt" or shutil.which("bash") is None, "requires bash")
class SelfHostVersionGateTests(unittest.TestCase):
    """Run the real upgrade step against a fake launcher."""

    def run_step(self, pinned: str, target: str) -> tuple[int, str, list[str]]:
        script = _step(
            _workflow("release.yml"), "self-host-upgrade", "Upgrade self-host pin and Codex projection"
        )["run"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            calls = root / "calls.txt"
            fake = bin_dir / "embraion"
            fake.write_text(
                f'#!/bin/sh\necho "$@" >> "{calls}"\n'
                'if [ "$1" = update ]; then echo changed >> .embraion/project.yaml; fi\n',
                encoding="utf-8",
            )
            fake.chmod(0o755)
            project = root / "project"
            (project / ".embraion").mkdir(parents=True)
            (project / ".embraion/project.yaml").write_text(
                f"framework:\n  version: {pinned}\n", encoding="utf-8"
            )
            output = root / "output.txt"
            output.write_text("", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            subprocess.run(["git", "add", "-A"], cwd=project, check=True)
            subprocess.run(
                ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                 "commit", "-q", "-m", "base"],
                cwd=project,
                check=True,
            )
            environment = dict(os.environ)
            environment.update(
                PATH=f"{bin_dir}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{environment['PATH']}",
                GITHUB_REF_NAME=f"v{target}",
                GITHUB_OUTPUT=str(output),
            )
            result = subprocess.run(
                ["bash", "-e", "-c", script],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
            )
            recorded = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
            return result.returncode, output.read_text(encoding="utf-8"), recorded

    def test_older_pin_runs_update_and_install_in_order(self) -> None:
        code, output, calls = self.run_step("0.1.9", "0.1.10")
        self.assertEqual(0, code)
        self.assertIn("changed=true", output)
        self.assertEqual(
            ["update --framework-version 0.1.10",
             "install --host codex --destination . --config-mode merge"],
            calls,
        )

    def test_equal_or_newer_pin_proposes_nothing(self) -> None:
        for pinned, target in (("0.23.0", "0.23.0"), ("0.24.0", "0.23.0")):
            with self.subTest(pinned=pinned, target=target):
                code, output, calls = self.run_step(pinned, target)
                self.assertEqual(0, code)
                self.assertIn("changed=false", output)
                self.assertEqual([], calls)

    def test_uncomparable_pin_fails_instead_of_skipping(self) -> None:
        code, output, calls = self.run_step("0.9.0rc1", "0.9.0")
        self.assertNotEqual(0, code)
        self.assertNotIn("changed=false", output)
        self.assertEqual([], calls)

    def test_non_stable_tag_fails(self) -> None:
        code, _, calls = self.run_step("0.1.0", "0.2.0rc1")
        self.assertNotEqual(0, code)
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
