from __future__ import annotations

import subprocess
import sys
import unittest


class CliIntegrationTests(unittest.TestCase):
    def test_cli_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "embraion.cli", "--version"],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("0.1.0-dev", result.stdout)


if __name__ == "__main__":
    unittest.main()
