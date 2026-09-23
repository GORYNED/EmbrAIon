from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliIntegrationTests(unittest.TestCase):
    def test_cli_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "embraion.cli", "--version"],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("0.2.2", result.stdout)

    def test_doctor_outside_project_is_human_readable_and_skips_project_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "would-be-secret.txt").write_text(
                "api_key=" + ("a" * 24),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, "-m", "embraion.cli", "doctor"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("EmbrAIon Doctor", result.stdout)
            self.assertIn("✓ Framework 0.2.2", result.stdout)
            self.assertIn("✓ Framework validation passed", result.stdout)
            self.assertIn("No EmbrAIon project detected.", result.stdout)
            self.assertIn("Project diagnostics were skipped.", result.stdout)
            self.assertIn("Everything looks good.", result.stdout)
            self.assertNotIn('"project":', result.stdout)
            self.assertFalse((root / ".embraion" / "state" / "mcp.json").exists())

    def test_doctor_json_preserves_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            result = subprocess.run(
                [sys.executable, "-m", "embraion.cli", "doctor", "--json"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )
            report = json.loads(result.stdout)

            self.assertEqual("0.2.2", report["framework"])
            self.assertIsNone(report["project"])
            self.assertEqual("skipped-no-project", report["project-diagnostics"])
            self.assertEqual(0, report["validation-errors"])
            self.assertEqual(0, report["security-findings"])
            self.assertEqual(0, report["mcp-servers"])
            self.assertEqual(0, report["worktrees"])


if __name__ == "__main__":
    unittest.main()
