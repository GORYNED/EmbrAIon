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
        self.assertIn("0.2.1", result.stdout)

    def test_doctor_outside_project_skips_recursive_project_diagnostics(self) -> None:
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
            report = json.loads(result.stdout)

            self.assertIsNone(report["project"])
            self.assertEqual("skipped-no-project", report["project-diagnostics"])
            self.assertEqual(0, report["security-findings"])
            self.assertEqual(0, report["mcp-servers"])
            self.assertEqual(0, report["worktrees"])
            self.assertFalse((root / ".embraion" / "state" / "mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
