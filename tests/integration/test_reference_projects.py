from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from embraion import __version__
from embraion.common import framework_root


REFERENCE_PROJECTS = ("minimal", "python", "unity")


class ReferenceProjectEndToEndTests(unittest.TestCase):
    def _environment(self, cache: Path) -> dict[str, str]:
        environment = os.environ.copy()
        environment["EMBRAION_CACHE_HOME"] = str(cache)
        environment.pop("EMBRAION_HOME", None)
        environment.pop("EMBRAION_VERSION_RESOLVED", None)
        environment.pop("EMBRAION_DISABLE_VERSION_RESOLUTION", None)
        return environment

    def _run(
        self,
        project: Path,
        environment: dict[str, str],
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "embraion.cli", *args],
            cwd=project,
            env=environment,
            text=True,
            capture_output=True,
            check=check,
        )

    def _copy_reference(self, name: str, destination: Path) -> Path:
        source = framework_root() / "examples" / name
        self.assertTrue(source.is_dir(), source)
        project = destination / name
        shutil.copytree(source, project)
        return project

    def _exercise_reference(self, name: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            cache = temporary_root / "cache"
            project = self._copy_reference(name, temporary_root)
            environment = self._environment(cache)

            manifest = yaml.safe_load(
                (project / ".embraion" / "project.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(__version__, str(manifest["framework"]["version"]))

            status_before = json.loads(
                self._run(project, environment, "status", "--json").stdout
            )
            self.assertEqual(__version__, status_before["project-pin"])
            self.assertEqual(__version__, status_before["resolved-version"])
            self.assertEqual("launcher", status_before["runtime-source"])
            self.assertEqual([], status_before["host-projections"])

            doctor = self._run(project, environment, "doctor")
            self.assertIn("[OK] Framework", doctor.stdout)

            self._run(
                project,
                environment,
                "install",
                "--host",
                "codex",
                "--destination",
                ".",
            )
            self._run(
                project,
                environment,
                "install",
                "--host",
                "copilot",
                "--destination",
                ".",
            )
            self._run(
                project,
                environment,
                "install",
                "--host",
                "claude-code",
                "--destination",
                ".",
            )
            self._run(
                project,
                environment,
                "install",
                "--host",
                "portable",
                "--destination",
                "vendor/embraion",
            )

            self.assertTrue((project / ".codex" / "config.toml").is_file())
            self.assertTrue(
                (project / ".github" / "agents" / "reviewer.agent.md").is_file()
            )
            self.assertTrue(
                (project / ".claude" / "agents" / "reviewer.md").is_file()
            )
            self.assertTrue(
                (
                    project
                    / "vendor"
                    / "embraion"
                    / "embraion"
                    / "plugin.json"
                ).is_file()
            )

            status_after = json.loads(
                self._run(project, environment, "status", "--json").stdout
            )
            self.assertEqual(
                {"Codex", "GitHub Copilot", "Claude Code", "Portable"},
                set(status_after["host-projections"]),
            )

            refused = self._run(
                project,
                environment,
                "install",
                "--host",
                "codex",
                "--destination",
                ".",
                check=False,
            )
            self.assertNotEqual(0, refused.returncode)
            self.assertIn("Refusing to overwrite", refused.stderr)

            self._run(
                project,
                environment,
                "install",
                "--host",
                "codex",
                "--destination",
                ".",
                "--force",
            )

    def test_reference_projects_complete_consuming_lifecycle(self) -> None:
        for name in REFERENCE_PROJECTS:
            with self.subTest(reference=name):
                self._exercise_reference(name)

    def test_clean_project_bootstrap_and_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "bootstrap"
            cache = root / "cache"
            project.mkdir()
            environment = self._environment(cache)

            init = self._run(
                project,
                environment,
                "init",
                "--name",
                "BootstrapReference",
            )
            self.assertIn(".embraion", init.stdout)

            manifest_path = project / ".embraion" / "project.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(__version__, str(manifest["framework"]["version"]))

            manifest["framework"]["version"] = "0.3.2"
            manifest_path.write_text(
                yaml.safe_dump(manifest, sort_keys=False),
                encoding="utf-8",
            )

            updated = self._run(project, environment, "update")
            self.assertIn(f"0.3.2 -> {__version__}", updated.stdout)

            current = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(__version__, str(current["framework"]["version"]))

            self._run(
                project,
                environment,
                "install",
                "--host",
                "codex",
                "--destination",
                ".",
            )
            self.assertTrue((project / ".codex" / "config.toml").is_file())

    def test_python_reference_application_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self._copy_reference("python", root)
            environment = self._environment(root / "cache")
            environment["PYTHONPATH"] = str(project / "src")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_*.py",
                ],
                cwd=project,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("OK", result.stderr)

    def test_unity_reference_structure_is_public_and_generic(self) -> None:
        root = framework_root() / "examples" / "unity"

        self.assertTrue((root / "Packages" / "manifest.json").is_file())
        self.assertTrue((root / "ProjectSettings" / "ProjectVersion.txt").is_file())
        self.assertTrue(
            (
                root
                / "Assets"
                / "Scripts"
                / "EmbrAIon.Reference.Unity.asmdef"
            ).is_file()
        )
        self.assertTrue((root / "Assets" / "Scripts" / "CounterState.cs").is_file())
        self.assertTrue(
            (root / "Assets" / "Scripts" / "CounterController.cs").is_file()
        )


if __name__ == "__main__":
    unittest.main()
