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
            self.assertTrue((project / ".agents" / "skills" / "review" / "SKILL.md").is_file())
            self.assertTrue(
                (project / ".github" / "agents" / "reviewer.agent.md").is_file()
            )
            self.assertTrue(
                (project / ".github" / "skills" / "review" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (project / ".claude" / "agents" / "reviewer.md").is_file()
            )
            self.assertTrue(
                (project / ".claude" / "skills" / "review" / "SKILL.md").is_file()
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

            projection = json.loads(
                self._run(
                    project,
                    environment,
                    "projection",
                    "diff",
                    "--host",
                    "codex",
                    "--destination",
                    ".",
                    "--json",
                ).stdout
            )
            self.assertEqual([], projection["conflict"])
            self.assertGreater(len(projection["unchanged"]), 0)

            reviewer = project / ".codex" / "agents" / "reviewer.toml"
            reviewer.write_text(
                reviewer.read_text(encoding="utf-8") + "\n# local change\n",
                encoding="utf-8",
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
            self.assertIn("Projection conflicts", refused.stderr)

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

            self.assertTrue((project / ".embraion" / "policy.yaml").is_file())
            policy = json.loads(
                self._run(project, environment, "policy", "show", "--json").stdout
            )
            self.assertEqual("PRIVATE", policy["privacy"]["default-class"])

            context = json.loads(
                self._run(
                    project,
                    environment,
                    "context",
                    "build",
                    "--task",
                    "Review project architecture",
                    "--role",
                    "architect",
                    "--data",
                    "PRIVATE",
                ).stdout
            )
            self.assertIn("selected", context)

            harness = json.loads(
                self._run(
                    project,
                    environment,
                    "harness",
                    "audit",
                    "--host",
                    "codex",
                ).stdout
            )
            self.assertTrue(harness["hosts"][0]["ready"])

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
            self.assertTrue((project / ".embraion" / ".gitignore").is_file())

            existing_config = project / ".codex" / "config.toml"
            existing_config.parent.mkdir(parents=True)
            existing_config.write_text(
                "[project]\ncustom = true\n",
                encoding="utf-8",
            )

            selective = json.loads(
                self._run(
                    project,
                    environment,
                    "projection",
                    "diff",
                    "--host",
                    "codex",
                    "--destination",
                    ".",
                    "--component",
                    "skills",
                    "--json",
                ).stdout
            )
            self.assertEqual(["skills"], selective["components"])
            self.assertEqual([], selective["conflict"])

            self._run(
                project,
                environment,
                "install",
                "--host",
                "codex",
                "--destination",
                ".",
                "--component",
                "skills",
            )
            self.assertEqual(
                "[project]\ncustom = true\n",
                existing_config.read_text(encoding="utf-8"),
            )
            self.assertTrue(
                (project / ".agents" / "skills" / "review" / "SKILL.md").is_file()
            )
            self.assertFalse((project / ".codex" / "agents" / "reviewer.toml").exists())

            existing_config.unlink()
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
            self.assertTrue((project / ".codex" / "agents" / "reviewer.toml").is_file())

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

    def test_unity_reference_scene_and_scripts_are_linked(self) -> None:
        root = framework_root() / "examples" / "unity"
        scripts = root / "Assets" / "Scripts"
        scenes = root / "Assets" / "Scenes"

        package_manifest = root / "Packages" / "manifest.json"
        self.assertTrue(package_manifest.is_file())
        package_data = json.loads(package_manifest.read_text(encoding="utf-8"))
        self.assertEqual(
            "1.0.0",
            package_data["dependencies"]["com.unity.modules.imgui"],
        )

        self.assertTrue((root / "ProjectSettings" / "ProjectVersion.txt").is_file())
        self.assertTrue(
            (root / "ProjectSettings" / "EditorBuildSettings.asset").is_file()
        )

        self.assertTrue((scripts / "EmbrAIon.Reference.Unity.asmdef").is_file())
        self.assertTrue((scripts / "CounterState.cs").is_file())
        self.assertTrue((scripts / "CounterController.cs").is_file())
        self.assertTrue((scripts / "CounterSampleView.cs").is_file())

        scene = scenes / "SampleScene.unity"
        scene_meta = scenes / "SampleScene.unity.meta"
        controller_meta = scripts / "CounterController.cs.meta"
        view_meta = scripts / "CounterSampleView.cs.meta"

        self.assertTrue(scene.is_file())
        self.assertTrue(scene_meta.is_file())
        self.assertTrue(controller_meta.is_file())
        self.assertTrue(view_meta.is_file())

        def guid(path: Path) -> str:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("guid: "):
                    return line.removeprefix("guid: ").strip()
            self.fail(f"Missing guid in {path}")

        scene_text = scene.read_text(encoding="utf-8")
        controller_guid = guid(controller_meta)
        view_guid = guid(view_meta)
        scene_guid = guid(scene_meta)

        self.assertIn(f"guid: {controller_guid}, type: 3", scene_text)
        self.assertIn(f"guid: {view_guid}, type: 3", scene_text)
        self.assertIn("counter: {fileID: 1002}", scene_text)
        self.assertIn("m_Name: Counter Sample", scene_text)

        build_settings = (
            root / "ProjectSettings" / "EditorBuildSettings.asset"
        ).read_text(encoding="utf-8")
        self.assertIn("path: Assets/Scenes/SampleScene.unity", build_settings)
        self.assertIn(f"guid: {scene_guid}", build_settings)


if __name__ == "__main__":
    unittest.main()
