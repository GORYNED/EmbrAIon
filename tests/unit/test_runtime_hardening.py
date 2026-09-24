from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from embraion.common import read_yaml, write_yaml
from embraion.context import build_context
from embraion.evidence import complete_run, start_run
from embraion.harness import audit_harness
from embraion.project import init_project, install
from embraion.security import (
    allowlisted_environment,
    redact_child_output,
    redact_text,
)


class RuntimeHardeningTests(unittest.TestCase):
    def test_context_selection_honors_role_trigger_and_data_class(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            knowledge = project / "knowledge"
            knowledge.mkdir()
            (knowledge / "architecture.md").write_text("architecture", encoding="utf-8")
            (knowledge / "public.md").write_text("public", encoding="utf-8")

            knowledge_path = manifest.with_name("knowledge.yaml")
            data = read_yaml(knowledge_path)
            data.update(
                {
                    "architecture": {
                        "path": "knowledge/architecture.md",
                        "data-class": "PRIVATE",
                        "trust": "project",
                        "roles": ["architect"],
                        "triggers": ["architecture"],
                    },
                    "public": {
                        "path": "knowledge/public.md",
                        "data-class": "PUBLIC",
                        "trust": "project",
                    },
                }
            )
            write_yaml(knowledge_path, data)

            record = build_context(
                "Review architecture boundaries",
                "architect",
                "PRIVATE",
                project=project,
                persist=False,
            )
            self.assertEqual(
                {"architecture", "public"},
                {item["id"] for item in record["selected"]},
            )

            public_only = build_context(
                "Review architecture boundaries",
                "architect",
                "PUBLIC",
                project=project,
                persist=False,
            )
            self.assertEqual(
                {"public"},
                {item["id"] for item in public_only["selected"]},
            )

    def test_execution_evidence_enforces_owned_and_protected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            policy_path = manifest.with_name("policy.yaml")
            policy_data = read_yaml(policy_path)
            policy_data["sources"]["protected"] = ["protected/**"]
            write_yaml(policy_path, policy_data)

            start_run(
                "run-1",
                "Implement bounded change",
                "worker",
                "codex",
                "substantial",
                "PRIVATE",
                "write",
                ["src/**"],
                substantial=True,
                project=project,
            )
            completed = complete_run(
                "run-1",
                changed_paths=["src/a.py"],
                validation=[{"profile": "fast", "status": "passed"}],
                review="passed",
                outcome="completed",
                residual_risks=[],
                project=project,
            )
            self.assertEqual("completed", completed["state"])

            start_run(
                "run-2",
                "Attempt protected change",
                "worker",
                "codex",
                "substantial",
                "PRIVATE",
                "write",
                ["protected/**"],
                project=project,
            )
            with self.assertRaises(RuntimeError):
                complete_run(
                    "run-2",
                    changed_paths=["protected/policy.md"],
                    validation=[],
                    review="not-required",
                    outcome="completed",
                    residual_risks=[],
                    project=project,
                )

    def test_runtime_redaction_removes_likely_credentials(self) -> None:
        secret = "abcdefgh" + "ijklmnop"
        value = "token=" + secret + " and Authorization: Bearer " + secret
        redacted = redact_text(value)
        self.assertNotIn(secret, redacted)
        self.assertIn("<REDACTED>", redacted)

    def test_environment_allowlist_excludes_unapproved_values(self) -> None:
        sensitive_name = "PROVIDER_" + "TOKEN"
        filtered = allowlisted_environment(
            {
                "PATH": "/tools",
                "HOME": "/home/worker",
                sensitive_name: "hidden",
                "TASK_ID": "42",
            },
            extra=["TASK_ID"],
        )
        self.assertEqual(
            {
                "HOME": "/home/worker",
                "PATH": "/tools",
                "TASK_ID": "42",
            },
            filtered,
        )
        self.assertNotIn(sensitive_name, filtered)

    def test_child_output_redaction_sanitizes_captured_streams(self) -> None:
        secret = "abcdefgh" + "ijklmnop"
        output = redact_child_output(
            "token=" + secret,
            "Authorization: Bearer " + secret,
        )
        combined = output["stdout"] + output["stderr"]
        self.assertNotIn(secret, combined)
        self.assertIn("<REDACTED>", combined)

    def test_harness_audit_reports_agents_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)
            report = audit_harness("codex", project)
            self.assertTrue(report["hosts"][0]["ready"])
            self.assertTrue(report["hosts"][0]["skills"]["present"])

            routing_skill = (
                project
                / ".agents"
                / "skills"
                / "routing-configuration"
                / "SKILL.md"
            )
            self.assertTrue(routing_skill.is_file())
            routing_text = routing_skill.read_text(encoding="utf-8")
            self.assertIn(".embraion/routing.yaml", routing_text)
            self.assertIn("overrides.<host>.routes", routing_text)


if __name__ == "__main__":
    unittest.main()
