from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from embraion.common import read_yaml, write_yaml
from embraion.context import build_context
from embraion.evidence import complete_run, start_run
from embraion.harness import audit_harness
from embraion.project import init_project, install
from embraion.security import redact_text


class RuntimeHardeningTests(unittest.TestCase):
    def test_context_selection_honors_role_trigger_and_data_class(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            manifest = init_project(project, name="Consumer")
            knowledge = project / "knowledge"
            knowledge.mkdir()
            (knowledge / "architecture.md").write_text("architecture", encoding="utf-8")
            (knowledge / "public.md").write_text("public", encoding="utf-8")

            data = read_yaml(manifest)
            data["knowledge"] = {
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
            write_yaml(manifest, data)

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
            data = read_yaml(manifest)
            data["sources"]["protected"] = ["protected/**"]
            write_yaml(manifest, data)

            start_run(
                "run-1",
                "Implement bounded change",
                "worker",
                "codex",
                "strong",
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
                "strong",
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
        value = "token=abcdefghijklmnop and Authorization: Bearer abcdefghijklmnop"
        redacted = redact_text(value)
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertIn("<REDACTED>", redacted)

    def test_harness_audit_reports_agents_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init_project(project, name="Consumer")
            install("codex", project)
            report = audit_harness("codex", project)
            self.assertTrue(report["hosts"][0]["ready"])
            self.assertTrue(report["hosts"][0]["skills"]["present"])


if __name__ == "__main__":
    unittest.main()
