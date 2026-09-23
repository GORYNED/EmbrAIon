from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from embraion import __version__


class CliIntegrationTests(unittest.TestCase):
    def _run(
        self,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "embraion.cli", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_cli_version(self) -> None:
        result = self._run("--version")
        self.assertEqual(__version__, result.stdout.strip())

    def test_main_help_is_structured_and_descriptive(self) -> None:
        result = self._run("--help")

        self.assertIn(f"EmbrAIon {__version__}", result.stdout)
        self.assertIn("Project & setup", result.stdout)
        self.assertIn("Health & runtime", result.stdout)
        self.assertIn("AI execution", result.stdout)
        self.assertIn("Engineering controls", result.stdout)
        self.assertIn("status     Show launcher, project pin", result.stdout)
        self.assertIn("cache      Inspect or clean cached project-pinned", result.stdout)
        self.assertIn("help       Show this command catalog", result.stdout)

    def test_help_command_matches_top_level_catalog(self) -> None:
        direct = self._run("--help")
        alias = self._run("help")
        self.assertEqual(direct.stdout, alias.stdout)

    def test_help_command_supports_nested_topics(self) -> None:
        result = self._run("help", "cache", "prune")
        self.assertIn("usage: embraion cache prune", result.stdout)
        self.assertIn("--older-than", result.stdout)
        self.assertIn("--apply", result.stdout)

    def test_help_is_launcher_owned_inside_older_pinned_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            project = root / "project"
            manifest = project / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "framework:\n"
                "  repository: GORYNED/EmbrAIon\n"
                "  version: 0.3.0\n"
                "project:\n"
                "  name: HelpAlias\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["EMBRAION_CACHE_HOME"] = str(cache)
            environment.pop("EMBRAION_HOME", None)
            environment.pop("EMBRAION_VERSION_RESOLVED", None)
            environment.pop("EMBRAION_DISABLE_VERSION_RESOLUTION", None)

            alias = self._run("help", cwd=project, env=environment)
            standard = self._run("--help", cwd=project, env=environment)

            self.assertIn(f"EmbrAIon {__version__}", alias.stdout)
            self.assertEqual(alias.stdout, standard.stdout)
            self.assertFalse((cache / "versions" / "0.3.0").exists())

    def test_doctor_outside_project_is_human_readable_and_skips_project_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "would-be-secret.txt").write_text(
                "api_key=" + ("a" * 24),
                encoding="utf-8",
            )

            result = self._run("doctor", cwd=root)

            self.assertIn("EmbrAIon Doctor", result.stdout)
            self.assertIn(f"[OK] Framework {__version__}", result.stdout)
            self.assertIn("[OK] Framework validation passed", result.stdout)
            self.assertIn("No EmbrAIon project detected.", result.stdout)
            self.assertIn("Project diagnostics were skipped.", result.stdout)
            self.assertIn("Everything looks good.", result.stdout)
            self.assertNotIn('"project":', result.stdout)
            self.assertFalse((root / ".embraion" / "state" / "mcp.json").exists())

    def test_doctor_json_preserves_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self._run("doctor", "--json", cwd=root)
            report = json.loads(result.stdout)

            self.assertEqual(__version__, report["framework"])
            self.assertIsNone(report["project"])
            self.assertEqual("skipped-no-project", report["project-diagnostics"])
            self.assertEqual(0, report["validation-errors"])
            self.assertEqual(0, report["security-findings"])
            self.assertEqual(0, report["mcp-servers"])
            self.assertEqual(0, report["worktrees"])

    def test_status_reports_project_pin_without_downloading_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            project = root / "project"
            manifest = project / ".embraion" / "project.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "framework:\n"
                "  repository: GORYNED/EmbrAIon\n"
                "  version: 0.2.2\n"
                "project:\n"
                "  name: Demo\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["EMBRAION_CACHE_HOME"] = str(cache)
            environment.pop("EMBRAION_HOME", None)
            environment.pop("EMBRAION_VERSION_RESOLVED", None)
            environment.pop("EMBRAION_DISABLE_VERSION_RESOLUTION", None)

            result = self._run(
                "status",
                "--json",
                cwd=project,
                env=environment,
            )
            status = json.loads(result.stdout)

            self.assertEqual(__version__, status["launcher-version"])
            self.assertEqual("0.2.2", status["project-pin"])
            self.assertEqual("0.2.2", status["resolved-version"])
            self.assertEqual("download-on-demand", status["runtime-source"])
            self.assertFalse(status["runtime-cached"])
            self.assertFalse((cache / "versions" / "0.2.2").exists())

    def test_cache_list_and_prune_are_safe_on_empty_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = os.environ.copy()
            environment["EMBRAION_CACHE_HOME"] = str(root / "cache")

            listed = self._run("cache", "list", "--json", cwd=root, env=environment)
            list_report = json.loads(listed.stdout)
            self.assertEqual([], list_report["runtimes"])

            pruned = self._run("cache", "prune", "--json", cwd=root, env=environment)
            prune_report = json.loads(pruned.stdout)
            self.assertEqual([], prune_report["candidates"])
            self.assertFalse(prune_report["apply"])


if __name__ == "__main__":
    unittest.main()
