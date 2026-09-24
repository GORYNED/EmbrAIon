from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion.common import read_yaml, write_yaml
from embraion.enforcement import (
    GITHUB_ACTIONS_PATH,
    check_enforcement,
    enforcement_status,
    install_enforcement_surface,
)
from embraion.evidence import start_run
from embraion.project import init_project


class EnforcementTests(unittest.TestCase):
    def _git(self, project: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(project), *args],
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()

    def _repo(self, project: Path) -> None:
        self._git(project, "init")
        self._git(project, "config", "user.email", "test@example.invalid")
        self._git(project, "config", "user.name", "EmbrAIon Test")
        (project / "src").mkdir()
        (project / "protected").mkdir()
        (project / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (project / "protected" / "contract.txt").write_text("stable\n", encoding="utf-8")
        self._git(project, "add", ".")
        self._git(project, "commit", "-m", "baseline")

    def _enable(self, project: Path, *, require_review: bool = False) -> None:
        policy_path = project / ".embraion" / "policy.yaml"
        policy = read_yaml(policy_path)
        policy["sources"]["protected"] = ["protected/**"]
        policy["enforcement"] = {
            "enabled": True,
            "validation-profile": "affected",
            "require-review": require_review,
        }
        write_yaml(policy_path, policy)

        validation_path = project / ".embraion" / "validation.yaml"
        validation = read_yaml(validation_path)
        validation["profiles"]["affected"] = [
            f'"{sys.executable}" -c "print(123)"'
        ]
        write_yaml(validation_path, validation)

    def test_check_blocks_protected_mutation_and_runs_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            self._repo(project)
            self._enable(project)
            self._git(project, "add", ".")
            self._git(project, "commit", "-m", "enable enforcement")

            safe_base = self._git(project, "rev-parse", "HEAD")
            (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
            safe = check_enforcement(base_ref=safe_base, project=project)
            self.assertTrue(safe["passed"])
            validation = next(
                item for item in safe["checks"] if item["id"] == "validation"
            )
            self.assertEqual("passed", validation["status"])

            self._git(project, "add", ".")
            self._git(project, "commit", "-m", "safe")
            protected_base = self._git(project, "rev-parse", "HEAD")
            (project / "protected" / "contract.txt").write_text(
                "changed\n",
                encoding="utf-8",
            )
            blocked = check_enforcement(
                base_ref=protected_base,
                project=project,
            )
            self.assertFalse(blocked["passed"])
            protected = next(
                item for item in blocked["checks"]
                if item["id"] == "protected-sources"
            )
            self.assertEqual("failed", protected["status"])

    def test_missing_validation_and_review_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            self._repo(project)
            policy_path = project / ".embraion" / "policy.yaml"
            policy = read_yaml(policy_path)
            policy["enforcement"] = {
                "enabled": True,
                "validation-profile": "affected",
                "require-review": True,
            }
            write_yaml(policy_path, policy)
            self._git(project, "add", ".")
            self._git(project, "commit", "-m", "policy")
            base = self._git(project, "rev-parse", "HEAD")
            (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")

            result = check_enforcement(base_ref=base, project=project)
            self.assertFalse(result["passed"])
            statuses = {item["id"]: item["status"] for item in result["checks"]}
            self.assertEqual("failed", statuses["validation"])
            self.assertEqual("failed", statuses["review"])

    def test_run_review_evidence_satisfies_review_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            self._repo(project)
            self._enable(project, require_review=True)
            self._git(project, "add", ".")
            self._git(project, "commit", "-m", "enable")
            self._git(project, "checkout", "-b", "work")
            base = self._git(project, "rev-parse", "HEAD")
            (project / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")

            start_run(
                "run-1",
                "Review gated change",
                "worker",
                "codex",
                "substantial",
                "PRIVATE",
                "write",
                ["src/**"],
                substantial=True,
                project=project,
            )
            run_path = project / ".embraion" / "state" / "runs" / "run-1.json"
            record = json.loads(run_path.read_text(encoding="utf-8"))
            record["review"] = "passed"
            run_path.write_text(
                json.dumps(record),
                encoding="utf-8",
            )

            result = check_enforcement(
                base_ref=base,
                project=project,
                run_id="run-1",
            )
            self.assertTrue(result["passed"])

    def test_github_actions_surface_is_explicit_and_conflict_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            self.assertFalse((project / GITHUB_ACTIONS_PATH).exists())

            report = install_enforcement_surface(
                surface="github-actions",
                project=project,
                validation_profile="affected",
                require_review=True,
            )
            self.assertTrue(report["enabled"])
            workflow = project / GITHUB_ACTIONS_PATH
            self.assertTrue(workflow.is_file())
            workflow_text = workflow.read_text(encoding="utf-8")
            self.assertIn("EmbrAIon enforcement", workflow_text)
            self.assertIn(
                "Require approved pull-request review",
                workflow_text,
            )
            self.assertIn(
                "${{ github.event.pull_request.head.sha }}",
                workflow_text,
            )
            self.assertIn(
                "${{ github.event.pull_request.base.sha }}",
                workflow_text,
            )
            self.assertIn("persist-credentials: false", workflow_text)
            self.assertIn(".commit_id == $head", workflow_text)

            status = enforcement_status(project)
            self.assertTrue(
                status["surfaces"]["github-actions"]["present"]
            )
            self.assertTrue(status["policy"]["enabled"])

            workflow.write_text("user-owned workflow\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                install_enforcement_surface(
                    surface="github-actions",
                    project=project,
                )


if __name__ == "__main__":
    unittest.main()
