from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(
    os.getenv("EMBRAION_RUN_NETWORK_E2E") == "1",
    "network resolver E2E is enabled explicitly by cross-platform CI",
)
class ResolverEndToEndTests(unittest.TestCase):
    def test_launcher_installs_and_reuses_exact_pinned_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            project = root / "project"
            nested = project / "src" / "nested"
            nested.mkdir(parents=True)

            manifest = project / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "framework:\n"
                "  repository: GORYNED/EmbrAIon\n"
                "  version: 0.2.2\n"
                "project:\n"
                "  name: ResolverE2E\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["EMBRAION_CACHE_HOME"] = str(cache)
            environment.pop("EMBRAION_HOME", None)
            environment.pop("EMBRAION_VERSION_RESOLVED", None)
            environment.pop("EMBRAION_DISABLE_VERSION_RESOLUTION", None)

            first = subprocess.run(
                [sys.executable, "-m", "embraion.cli", "--version"],
                cwd=nested,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual("0.2.2", first.stdout.strip())
            self.assertIn("preparing pinned runtime 0.2.2", first.stderr)

            marker = (
                cache
                / "versions"
                / "0.2.2"
                / ".embraion-runtime.json"
            )
            self.assertTrue(marker.is_file())

            second = subprocess.run(
                [sys.executable, "-m", "embraion.cli", "--version"],
                cwd=nested,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual("0.2.2", second.stdout.strip())
            self.assertNotIn("preparing pinned runtime", second.stderr)


if __name__ == "__main__":
    unittest.main()
